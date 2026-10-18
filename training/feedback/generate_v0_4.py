"""Build feedback-v0.4 data with semantic issue/decision consistency anchors."""
from __future__ import annotations
from collections import Counter
import hashlib, json
from pathlib import Path
from analyzer.feedback_contract import SYSTEM_PROMPT, canonical_json, parse_output, validate_input
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint, judgment

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data"
BASE = DATA / "feedback_v0.3.jsonl"
HOLDOUT = ROOT / "evaluation/feedback/holdout_v0.5.jsonl"
PLACES = ["標本室", "映写室", "工作室", "閲覧室", "管理室", "倉庫前", "中庭", "資料館", "実験棟", "休養室", "多目的室", "配膳室", "写真室", "編集室", "相談窓口", "観測室", "訓練室", "展示棟", "保管室", "整備室", "講習室", "受付奥", "地下倉庫", "屋外広場", "連絡室"]
THINGS = ["標本箱", "映写機", "作業台", "検索端末", "監視盤", "運搬車", "案内灯", "模型", "実験装置", "寝台", "移動壁", "配膳台", "暗室灯", "編集卓", "番号表示器", "観測記録", "訓練器具", "説明模型", "予備部品", "工具箱", "教材棚", "受付端末", "保存容器", "案内標識", "無線機"]
ACTIONS = ["標本を整理します", "映像を確認します", "部品を組み立てます", "資料を閲覧します", "設備を監視します", "荷物を受け取ります", "植物を観察します", "模型を展示します", "実験を行います", "体を休めます", "会場を準備します", "食事を配ります", "写真を現像します", "映像を編集します", "相談を受けます", "星を観測します", "避難訓練をします", "作品を案内します", "在庫を数えます", "機械を点検します", "講習を行います", "来客を案内します", "食品を保管します", "催しを開きます", "連絡を取ります"]
DESTS = ["自然史館", "映像センター", "工芸館", "中央閲覧所", "設備管理棟", "貨物受付", "植物研究園", "郷土資料館", "先端実験棟", "保養所", "市民ホール", "給食センター", "写真美術館", "編集センター", "市民相談所", "気象観測所", "防災訓練所", "企画展示館", "部品保管所", "車両整備場", "技能講習所", "総合受付", "低温倉庫", "催事広場", "通信管理所"]
REASONS = ["조사와 서술어의 관계가 자연스럽습니다.", "해당 조사는 문장의 의미에 맞게 사용됐습니다.", "원문을 유지해도 문법상 문제가 없습니다.", "오류가 확인되지 않아 최소 교정이 필요하지 않습니다."]

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]
def feedback(verdict, issues, recommended, reason): return {"verdict": verdict, "issue_codes": issues, "recommended_judgment": recommended, "review_reason_ko": reason}

def targeted_rows():
    rows = []
    for group, (place, thing, action, dest) in enumerate(zip(PLACES, THINGS, ACTIONS, DESTS)):
        cases = []
        ok = f"平日は{place}に{thing}があります。"
        for reason in REASONS:
            cases.append((ok, judgment("acceptable", ok, [], reason), feedback("agree", [], None, "허용 판단과 원문 유지가 타당합니다."), "agree_reason_diversity", "existence_ni_reason_variants"))
        for text, corrected, family, error_type in [
            (f"朝は{place}で{thing}があります。", f"朝は{place}に{thing}があります。", "existence_de_false_negative", "particle_misuse"),
            (f"明後日は{dest}を行きます。", f"明後日は{dest}に行きます。", "destination_wo_false_negative", "particle_misuse"),
            (f"昨日は{place}で働くました。", f"昨日は{place}で働きました。", "verb_form_false_negative", "verb_conjugation"),
        ]:
            gold = judgment("needs_correction", corrected, [error_type], "문법 오류를 최소 범위로 교정해야 합니다.")
            candidate = judgment("acceptable", text, [], REASONS[group % 4])
            cases.append((text, candidate, feedback("disagree", ["false_negative"], gold, "명확한 문법 오류를 놓쳤습니다."), "false_negative_consistent", family))
        for text, source, replacement, family, reason in [
            (f"夕方は{place}で{action}。", "で", "に", "action_de_false_positive", "동작 장소 조사 で가 자연스럽습니다."),
            (f"夜は{place}に{thing}があります。", "に", "で", "existence_ni_false_positive", "존재 장소 조사 に가 자연스럽습니다."),
            (f"来週は{dest}に行きます。", "に", "を", "destination_ni_false_positive", "목적지 조사 に가 자연스럽습니다."),
        ]:
            gold = judgment("acceptable", text, [], reason)
            candidate = judgment("needs_correction", text.replace(source, replacement, 1), ["particle_misuse"], "조사 오류를 교정했습니다.")
            cases.append((text, candidate, feedback("disagree", ["false_positive", "wrong_correction"], gold, "허용되는 조사를 바꾸면 안 됩니다."), "false_positive_consistent", family))
        for text, family in [(f"昼は{place}で{action}。", "action_de_unnecessary_abstention"), (f"来年は{dest}に行きます。", "destination_ni_unnecessary_abstention")]:
            gold = judgment("acceptable", text, [], "완결된 일본어 문장입니다.")
            candidate = judgment("insufficient_evidence", text, [], "일본어인지 판단할 수 없습니다.")
            cases.append((text, candidate, feedback("disagree", ["wrong_decision", "unnecessary_abstention"], gold, "완결된 일본어이므로 보류할 이유가 없습니다."), "unnecessary_abstention_consistent", family))
        split = "eval" if group % 10 == 0 else "train"
        for text, candidate, expected, case_type, family in cases:
            row = {"id": f"FVT-04-{len(rows)+1:04d}", "source_judgment_id": f"target-v04-{group+1:03d}", "source_index": group, "split_group": split, "text": text, "context": None, "learner_level": "N4" if group % 4 == 0 else "N5", "candidate_judgment": candidate, "expected": expected, "case_type": case_type, "target_family": family, "review": {"status": "generated_validated", "reviewed_at": None}}
            validate_input({"text": text, "context": None, "learner_level": row["learner_level"], "judgment": candidate})
            parsed, error = parse_output(canonical_json(expected), text)
            if parsed is None: raise ValueError(f"invalid output for {row['id']}: {error}")
            rows.append(row)
    if len(rows) != 300: raise ValueError(f"expected 300 rows, got {len(rows)}")
    return rows

def build_rows(): return load(BASE) + targeted_rows()

def main():
    rows = build_rows()
    inputs, texts = {input_fingerprint(x) for x in rows}, {x["text"] for x in rows}
    protected = {"holdout_v0.5": HOLDOUT, "diagnostic_v0.1": ROOT / "evaluation/feedback/existence_particle_diagnostic_v0.1.jsonl", "diagnostic_v0.2": ROOT / "evaluation/feedback/existence_particle_diagnostic_v0.2.jsonl"}
    overlap = {}
    for name, path in protected.items():
        values = load(path)
        overlap[name] = {"exact_input": len(inputs & {input_fingerprint(x) for x in values}), "text": len(texts & {x["text"] for x in values})}
    if any(v["exact_input"] or v["text"] for v in overlap.values()): raise ValueError(f"protected overlap: {overlap}")
    source = DATA / "feedback_v0.4.jsonl"
    source.write_text("".join(canonical_json(x)+"\n" for x in rows), encoding="utf-8")
    splits = {"train": [], "eval": []}
    for row in rows:
        inp = {"text": row["text"], "context": row["context"], "learner_level": row["learner_level"], "judgment": row["candidate_judgment"]}
        splits[row["split_group"]].append({"messages": [{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":canonical_json(inp)},{"role":"assistant","content":canonical_json(row["expected"])}]})
    train, ev = DATA / "train_v0.4.chatml.jsonl", DATA / "eval_v0.4.chatml.jsonl"
    train.write_text("".join(canonical_json(x)+"\n" for x in splits["train"]), encoding="utf-8")
    ev.write_text("".join(canonical_json(x)+"\n" for x in splits["eval"]), encoding="utf-8")
    manifest = {"schema_version":"feedback-training-manifest-v0.4","records":len(rows),"train_records":len(splits["train"]),"eval_records":len(splits["eval"]),"base_dataset":str(BASE.relative_to(ROOT)),"base_dataset_sha256":sha(BASE),"targeted_records":len(targeted_rows()),"review_status":"generated_validated","holdout_used":False,"protected_overlap":overlap,"verdict_counts":dict(sorted(Counter(x["expected"]["verdict"] for x in rows).items())),"case_type_counts":dict(sorted(Counter(x["case_type"] for x in rows).items())),"source_sha256":sha(source),"train_sha256":sha(train),"eval_sha256":sha(ev),"limitations":["자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.","소비된 조사 진단 문장은 포함하지 않고 실패 유형만 새 템플릿으로 일반화했습니다.","봉인된 holdout v0.5는 학습에 사용하지 않았습니다."]}
    (DATA/"feedback_v0.4.manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")

if __name__ == "__main__": main()

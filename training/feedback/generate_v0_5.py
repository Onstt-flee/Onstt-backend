"""Build feedback-v0.5 data for v0.4's normal-destination and existence failures."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import SYSTEM_PROMPT, canonical_json, parse_output, validate_input
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint, judgment


ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data"
BASE = DATA / "feedback_v0.4.jsonl"
PLACES = ["監視室", "通信室", "収蔵庫", "分析室", "発送室", "調理室", "洗浄室", "点検室", "管制室", "研磨室", "培養室", "録音室", "補修室", "組立室", "冷却室", "加工室", "校正室", "検品室", "充電室", "保守室"]
THINGS = ["監視装置", "通信端末", "収蔵棚", "分析計", "送り状", "調理台", "洗浄機", "点検表", "管制盤", "研磨機", "培養器", "録音卓", "補修材", "組立台", "冷却器", "加工機", "基準器", "検品台", "充電器", "保守工具"]
PEOPLE = ["監視員", "通信係", "学芸員", "分析員", "発送係", "調理員", "洗浄係", "点検員", "管制官", "研磨工", "培養員", "録音技師", "補修員", "組立工", "冷却担当", "加工員", "校正員", "検品係", "充電担当", "保守員"]
ACTIONS = ["画面を監視します", "通信を確認します", "資料を収蔵します", "試料を分析します", "荷物を発送します", "料理を作ります", "器具を洗浄します", "設備を点検します", "運行を管理します", "部品を研磨します", "細胞を培養します", "音声を録音します", "壁を補修します", "部品を組み立てます", "装置を冷却します", "材料を加工します", "計器を校正します", "製品を検品します", "電池を充電します", "機械を保守します"]
DESTINATIONS = ["監視センター", "通信局", "保存資料館", "分析研究所", "発送拠点", "料理学校", "洗浄施設", "点検事務所", "交通管制所", "研磨工場", "培養研究所", "録音スタジオ", "補修工場", "組立工場", "冷却施設", "加工センター", "校正機関", "検品所", "充電施設", "保守センター"]
REASONS = ["목적지 조사 に가 자연스럽습니다.", "이동 동사와 목적지 조사의 결합이 올바릅니다.", "원문을 유지해도 문법상 문제가 없습니다."]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def feedback(verdict, issues, recommended, reason):
    return {"verdict": verdict, "issue_codes": issues, "recommended_judgment": recommended, "review_reason_ko": reason}


def targeted_rows() -> list[dict]:
    rows = []
    for group, (place, thing, person, action, destination) in enumerate(zip(PLACES, THINGS, PEOPLE, ACTIONS, DESTINATIONS)):
        cases = []
        for prefix, reason in zip(("次回は", "来年度は", "休暇中は"), REASONS):
            text = f"{prefix}{destination}に行きます。"
            candidate = judgment("acceptable", text, [], reason)
            cases.append((text, None, candidate, feedback("agree", [], None, "허용 판단과 원문 유지가 타당합니다."), "destination_agree_stability", "destination_ni_agree"))

        missed = [
            (f"朝方は{place}で{thing}があります。", f"朝方は{place}に{thing}があります。", "inanimate_existence_de_false_negative"),
            (f"夕食後は{place}で{thing}があります。", f"夕食後は{place}に{thing}があります。", "inanimate_existence_de_false_negative_variant"),
            (f"昼休みは{place}で{person}がいます。", f"昼休みは{place}に{person}がいます。", "animate_existence_de_false_negative"),
            (f"次の休日は{destination}を行きます。", f"次の休日は{destination}に行きます。", "destination_wo_false_negative"),
        ]
        for text, corrected, family in missed:
            gold = judgment("needs_correction", corrected, ["particle_misuse"], "조사 오류를 최소 범위로 교정해야 합니다.")
            candidate = judgment("acceptable", text, [], "문법 오류가 확인되지 않습니다.")
            cases.append((text, None, candidate, feedback("disagree", ["false_negative"], gold, "명확한 조사 오류를 놓쳤습니다."), "false_negative_contract_anchor", family))

        text = f"始業前は{place}で{thing}があります。"
        corrected = text.replace(f"{place}で", f"{place}に", 1)
        candidate = judgment("needs_correction", corrected, ["particle_misuse"], "조사 오류를 최소 범위로 교정했습니다.")
        cases.append((text, None, candidate, feedback("agree", [], None, "오류 탐지와 최소 교정이 모두 타당합니다."), "agree_existence_correction", "existence_de_correct_audit"))

        normal_existence = f"深夜は{place}に{thing}があります。"
        wrong_existence = judgment("needs_correction", normal_existence.replace("に", "で", 1), ["particle_misuse"], "장소 조사를 교정했습니다.")
        gold_existence = judgment("acceptable", normal_existence, [], "존재 장소 조사 に가 자연스럽습니다.")
        cases.append((normal_existence, None, wrong_existence, feedback("disagree", ["false_positive", "wrong_correction"], gold_existence, "올바른 존재 장소 조사를 바꾸면 안 됩니다."), "false_positive_contract_anchor", "existence_ni_false_positive"))

        normal_destination = f"次の春は{destination}に行きます。"
        wrong_destination = judgment("needs_correction", normal_destination.replace("に", "を", 1), ["particle_misuse"], "목적지 조사를 교정했습니다.")
        gold_destination = judgment("acceptable", normal_destination, [], "목적지 조사 に가 자연스럽습니다.")
        cases.append((normal_destination, None, wrong_destination, feedback("disagree", ["false_positive", "wrong_correction"], gold_destination, "올바른 목적지 조사를 바꾸면 안 됩니다."), "false_positive_contract_anchor", "destination_ni_false_positive"))

        action_text = f"翌日は{place}で{action}。"
        abstained = judgment("insufficient_evidence", action_text, [], "일본어인지 판단할 수 없습니다.")
        action_gold = judgment("acceptable", action_text, [], "완결된 일본어 문장입니다.")
        cases.append((action_text, None, abstained, feedback("disagree", ["wrong_decision", "unnecessary_abstention"], action_gold, "완결된 일본어이므로 보류할 이유가 없습니다."), "unnecessary_abstention_anchor", "valid_action_unnecessary_abstention"))

        orthography = f"わたしわ{place}に行きます。" if group % 2 == 0 else f"資料お{place}に運びます。"
        changed = orthography.replace("わ", "は", 1) if "わ" in orthography else orthography.replace("お", "を", 1)
        orthography_candidate = judgment("needs_correction", changed, ["particle_misuse"], "조사 표기를 바로잡았습니다.")
        cases.append((orthography, "STT 전사이며 원음은 제공되지 않았습니다.", orthography_candidate, feedback("unreviewable", [], None, "원음이 없어 발화 오류와 전사 오류를 구분할 수 없습니다."), "audio_boundary_anchor", "stt_orthography_unreviewable"))

        split = "eval" if group % 10 == 0 else "train"
        for text, context, candidate, expected, case_type, family in cases:
            row = {
                "id": f"FVT-05-{len(rows)+1:04d}", "source_judgment_id": f"target-v05-{group+1:03d}",
                "source_index": group, "split_group": split, "text": text, "context": context,
                "learner_level": "N4" if group % 4 == 0 else "N5", "candidate_judgment": candidate,
                "expected": expected, "case_type": case_type, "target_family": family,
                "review": {"status": "generated_validated", "reviewed_at": None},
            }
            validate_input({"text": text, "context": context, "learner_level": row["learner_level"], "judgment": candidate})
            parsed, error = parse_output(canonical_json(expected), text)
            if parsed is None:
                raise ValueError(f"invalid output for {row['id']}: {error}")
            rows.append(row)
    if len(rows) != 240:
        raise ValueError(f"expected 240 rows, got {len(rows)}")
    return rows


def build_rows() -> list[dict]:
    return load(BASE) + targeted_rows()


def main() -> None:
    rows = build_rows()
    inputs, texts = {input_fingerprint(row) for row in rows}, {row["text"] for row in rows}
    protected = {
        "holdout_v0.5": ROOT / "evaluation/feedback/holdout_v0.5.jsonl",
        "holdout_v0.6": ROOT / "evaluation/feedback/holdout_v0.6.jsonl",
        "diagnostic_v0.1": ROOT / "evaluation/feedback/existence_particle_diagnostic_v0.1.jsonl",
        "diagnostic_v0.2": ROOT / "evaluation/feedback/existence_particle_diagnostic_v0.2.jsonl",
    }
    overlap = {}
    for name, path in protected.items():
        values = load(path)
        overlap[name] = {
            "exact_input": len(inputs & {input_fingerprint(row) for row in values}),
            "text": len(texts & {row["text"] for row in values}),
        }
    if any(value["exact_input"] or value["text"] for value in overlap.values()):
        raise ValueError(f"protected overlap: {overlap}")

    source = DATA / "feedback_v0.5.jsonl"
    source.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    splits = {"train": [], "eval": []}
    for row in rows:
        model_input = {"text": row["text"], "context": row["context"], "learner_level": row["learner_level"], "judgment": row["candidate_judgment"]}
        splits[row["split_group"]].append({"messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": canonical_json(model_input)}, {"role": "assistant", "content": canonical_json(row["expected"])}]})
    train = DATA / "train_v0.5.chatml.jsonl"
    evaluation = DATA / "eval_v0.5.chatml.jsonl"
    train.write_text("".join(canonical_json(row) + "\n" for row in splits["train"]), encoding="utf-8")
    evaluation.write_text("".join(canonical_json(row) + "\n" for row in splits["eval"]), encoding="utf-8")
    manifest = {
        "schema_version": "feedback-training-manifest-v0.5", "records": len(rows),
        "train_records": len(splits["train"]), "eval_records": len(splits["eval"]),
        "base_dataset": str(BASE.relative_to(ROOT)), "base_dataset_sha256": sha(BASE),
        "targeted_records": len(targeted_rows()), "review_status": "generated_validated",
        "holdout_used": False, "protected_overlap": overlap,
        "verdict_counts": dict(sorted(Counter(row["expected"]["verdict"] for row in rows).items())),
        "case_type_counts": dict(sorted(Counter(row["case_type"] for row in rows).items())),
        "source_sha256": sha(source), "train_sha256": sha(train), "eval_sha256": sha(evaluation),
        "limitations": [
            "자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.",
            "소비된 v0.5 실패 문장은 포함하지 않고 실패 구조만 새 템플릿으로 일반화했습니다.",
            "봉인된 holdout v0.6은 학습에 사용하지 않았습니다.",
        ],
    }
    (DATA / "feedback_v0.5.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

"""Build and seal the feedback-v0.5 holdout before v0.4 training.

Deterministic generated validation data; not human or expert review.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import canonical_json, parse_output, validate_input
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint, judgment

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "holdout_v0.5.jsonl"
MANIFEST = HERE / "holdout_v0.5.manifest.json"
PROTOCOL = HERE / "holdout_v0.5.protocol.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feedback(verdict, issues, recommended, reason):
    return {"verdict": verdict, "issue_codes": issues, "recommended_judgment": recommended, "review_reason_ko": reason}


PLACES = ["温室", "配送室", "印刷室", "記録庫", "器材室", "展望室", "放送室", "準備室", "守衛室", "検査室"]
THINGS = ["温度計", "台車", "裁断機", "保管箱", "三脚", "双眼鏡", "音響卓", "予備机", "鍵箱", "測定器"]
ACTIONS = ["苗を植えます", "荷物を仕分けます", "資料を綴じます", "記録を確認します", "器具を洗います", "景色を眺めます", "番組を収録します", "教材を並べます", "来客を確認します", "試料を調べます"]
DESTINATIONS = ["植物園", "物流センター", "製本所", "公文書館", "科学館", "天文台", "放送局", "研修所", "警備室", "検査所"]
REASONS = ["조사와 서술어의 결합이 자연스럽습니다.", "문장 구조와 조사 사용이 허용 범위입니다.", "원문의 조사 선택을 유지해도 됩니다.", "문법 오류가 확인되지 않습니다.", "제공된 문맥에서 자연스러운 일본어입니다."]


def build_rows():
    specs = []
    for i, (place, thing, action, destination) in enumerate(zip(PLACES, THINGS, ACTIONS, DESTINATIONS)):
        normal = [
            (f"{place}に{thing}があります。", "existence_ni_agree"),
            (f"午前中は{place}で{action}。", "action_de_agree"),
            (f"来月は{destination}に行きます。", "destination_ni_agree"),
        ]
        for text, family in normal:
            candidate = judgment("acceptable", text, [], REASONS[i % len(REASONS)])
            specs.append((text, None, family, candidate, feedback("agree", [], None, "판단·원문 유지·근거가 서로 일치합니다."), "agree_reason_variant"))

        errors = [
            (f"夕方は{place}で{thing}があります。", f"夕方は{place}に{thing}があります。", "existence_de_false_negative"),
            (f"週末は{destination}を行きます。", f"週末は{destination}に行きます。", "destination_wo_false_negative"),
        ]
        for text, corrected, family in errors:
            gold = judgment("needs_correction", corrected, ["particle_misuse"], "조사 오류를 최소 범위로 교정해야 합니다.")
            missed = judgment("acceptable", text, [], REASONS[(i + 2) % len(REASONS)])
            specs.append((text, None, family, missed, feedback("disagree", ["false_negative"], gold, "명확한 조사 오류를 놓쳤습니다."), "false_negative_semantic_lock"))

        corrected_cases = [
            (f"正午は{place}で{thing}があります。", f"正午は{place}に{thing}があります。", "existence_de_correct_audit"),
            (f"再来週は{destination}を行きます。", f"再来週は{destination}に行きます。", "destination_wo_correct_audit"),
        ]
        for text, corrected, family in corrected_cases:
            candidate = judgment("needs_correction", corrected, ["particle_misuse"], "조사 오류를 최소 범위로 교정했습니다.")
            specs.append((text, None, family, candidate, feedback("agree", [], None, "오류 탐지와 최소 교정이 모두 타당합니다."), "agree_correction"))

        fp_cases = [
            (f"午後は{place}で{action}。", "で", "に", "action_de_false_positive", "동작 장소 조사 で가 자연스럽습니다."),
            (f"夜は{place}に{thing}があります。", "に", "で", "existence_ni_false_positive", "존재 장소 조사 に가 자연스럽습니다."),
        ]
        for text, source, replacement, family, gold_reason in fp_cases:
            candidate = judgment("needs_correction", text.replace(source, replacement, 1), ["particle_misuse"], "장소 조사를 교정했습니다.")
            gold = judgment("acceptable", text, [], gold_reason)
            expected = feedback("disagree", ["false_positive", "wrong_correction"], gold, "올바른 조사 선택을 바꾸면 안 됩니다.")
            specs.append((text, None, family, candidate, expected, "false_positive_semantic_lock"))

        mismatch_text = f"翌日は{destination}に行きます。"
        mismatch = judgment("acceptable", mismatch_text, [], "목적지 조사 오류를 교정했습니다.")
        mismatch_gold = judgment("acceptable", mismatch_text, [], "목적지 조사 に를 올바르게 사용했습니다.")
        specs.append((mismatch_text, None, "acceptable_reason_mismatch", mismatch, feedback("disagree", ["reason_mismatch"], mismatch_gold, "허용 판단과 오류를 교정했다는 근거가 일치하지 않습니다."), "reason_mismatch"))

        abstain_text = f"翌月は{place}で{action}。"
        abstain = judgment("insufficient_evidence", abstain_text, [], "일본어인지 판단할 수 없습니다.")
        abstain_gold = judgment("acceptable", abstain_text, [], "완결된 일본어 문장입니다.")
        specs.append((abstain_text, None, "valid_japanese_unnecessary_abstention", abstain, feedback("disagree", ["wrong_decision", "unnecessary_abstention"], abstain_gold, "완결된 일본어이므로 보류할 이유가 없습니다."), "unnecessary_abstention"))

    orthography = ["わたしわ温室に行きます。", "ぼくわ配送室で働きます。", "資料お印刷室に運びます。", "記録お棚に置きます。", "妹わ器材室にいます。", "地図お展望室で見ます。", "友達わ放送室に来ます。", "教材お準備室で使います。", "父わ守衛室で待ちます。", "試料お検査室に置きます。"]
    for text in orthography:
        changed = text.replace("わ", "は", 1) if "わ" in text else text.replace("お", "を", 1)
        candidate = judgment("needs_correction", changed, ["particle_misuse"], "조사 표기를 바로잡았습니다.")
        expected = feedback("unreviewable", [], None, "원음이 없어 발화 오류와 전사 오류를 구분할 수 없습니다.")
        specs.append((text, "STT 전사이며 원음은 제공되지 않았습니다.", "stt_orthography_unreviewable", candidate, expected, "audio_required_unreviewable"))

    rows = []
    for index, (text, context, family, candidate, expected, case_type) in enumerate(specs, 1):
        row = {"id": f"FVH-05-{index:03d}", "text": text, "context": context, "learner_level": "N4" if index % 4 == 0 else "N5", "candidate_judgment": candidate, "expected": expected, "family": family, "case_type": case_type, "source_kind": "deterministic_feedback_v0.5_template", "review_status": "generated_validated"}
        validate_input({"text": text, "context": context, "learner_level": row["learner_level"], "judgment": candidate})
        parsed, error = parse_output(canonical_json(expected), text)
        if parsed is None:
            raise ValueError(f"invalid expected output for {row['id']}: {error}")
        rows.append(row)
    if len(rows) != 120:
        raise ValueError(f"expected 120 rows, got {len(rows)}")
    return rows


def load(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main():
    if PROTOCOL.exists() and json.loads(PROTOCOL.read_text(encoding="utf-8")).get("consumed"):
        raise SystemExit("refusing to regenerate consumed feedback holdout v0.5")
    rows = build_rows()
    OUTPUT.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    current_inputs, current_texts = {input_fingerprint(row) for row in rows}, {row["text"] for row in rows}
    comparisons = {**{f"training_v0.{v}": ROOT / f"training/feedback/data/feedback_v0.{v}.jsonl" for v in (1, 2, 3)}, **{f"holdout_v0.{v}": HERE / f"holdout_v0.{v}.jsonl" for v in (1, 2, 3, 4)}, **{f"diagnostic_v0.{v}": HERE / f"existence_particle_diagnostic_v0.{v}.jsonl" for v in (1, 2)}}
    overlap = {}
    for name, path in comparisons.items():
        values = load(path)
        overlap[name] = {"exact_input": len(current_inputs & {input_fingerprint(row) for row in values}), "text": len(current_texts & {row["text"] for row in values})}
    if any(item["exact_input"] or item["text"] for item in overlap.values()):
        raise ValueError(f"holdout v0.5 overlap detected: {overlap}")
    manifest = {"schema_version": "feedback-holdout-manifest-v0.5", "dataset": OUTPUT.name, "sha256": sha(OUTPUT), "records": len(rows), "review_status": "generated_validated", "human_reviewed": False, "expert_reviewed": False, "model_inference_count": 0, "qualification_scope": "gpu_internal_model_selection_only", "verdict_counts": dict(sorted(Counter(row["expected"]["verdict"] for row in rows).items())), "case_type_counts": dict(sorted(Counter(row["case_type"] for row in rows).items())), "family_counts": dict(sorted(Counter(row["family"] for row in rows).items())), "overlap": overlap, "limitations": ["자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.", "feedback-v0.4 학습 전에 봉인하며 소비 후 재튜닝에 사용하지 않습니다.", "기존 진단 v0.1/v0.2 문장을 포함하지 않습니다."]}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol = {"schema_version": "feedback-holdout-protocol-v0.5", "dataset_sha256": manifest["sha256"], "contract_version": "feedback-v0.1", "candidate_family": "feedback-v0.4", "adapter_sha256": None, "training_data_sha256": None, "training_config_sha256": None, "training_run": None, "ready_for_inference": False, "single_use": True, "consumed": False, "temperature": 0.0, "top_p": 1.0, "max_tokens": 512, "serving": {"engine": "vllm", "reasoning_parser": "qwen3", "flashinfer_sampler": False}, "thresholds": {"contract_success_rate_min": 0.99, "false_disagreement_rate_max": 0.02, "disagreement_precision_min": 0.95, "disagreement_recall_min": 0.80, "recommended_decision_accuracy_min": 0.90, "accepted_correction_rate_min": 0.80, "p95_latency_seconds_max": 5.0}, "operational_qualification": "blocked_internal_generated_validation_only"}
    PROTOCOL.write_text(json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

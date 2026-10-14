"""Build a structurally varied feedback-v0.2 holdout deterministically.

The source texts come from the already frozen judgment holdout v0.5, but the
candidate judgments and feedback labels are newly derived for verifier
evaluation. The source stratum is simulated and never exposed to the model.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import ISSUE_CODES, parse_output, validate_input
from evaluation.judgment.dataset import ERROR_TYPES


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "evaluation/judgment/holdout_v0.5.jsonl"
OUTPUT = Path(__file__).with_name("holdout_v0.2.jsonl")
MANIFEST = Path(__file__).with_name("holdout_v0.2.manifest.json")
PROTOCOL = Path(__file__).with_name("holdout_v0.2.protocol.json")
TRAINING = ROOT / "training/feedback/data/feedback_v0.1.jsonl"
OLD_HOLDOUT = Path(__file__).with_name("holdout_v0.1.jsonl")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def judgment(decision, corrected, errors, reason):
    return {"decision": decision, "corrected_text": corrected, "error_types": errors, "reason_ko": reason}


def gold_judgment(row):
    expected = row["expected"]
    errors = []
    for edit in expected.get("edits", []):
        error_type = edit.get("error_type")
        if error_type and error_type not in errors:
            errors.append(error_type)
    return judgment(expected["decision"], expected["corrected_text"], errors, expected["reason_ko"])


def append_before_terminal(text, suffix="ね"):
    if text[-1:] in {"。", "！", "？", ".", "!", "?"}:
        return text[:-1] + suffix + text[-1]
    return text + suffix


def alternative_error_type(errors):
    return next(item for item in sorted(ERROR_TYPES) if item not in errors)


def feedback(verdict, issues, recommended, reason):
    return {
        "verdict": verdict,
        "issue_codes": issues,
        "recommended_judgment": recommended,
        "review_reason_ko": reason,
    }


def derive_case(row, ordinal):
    text = row["input"]["text"]
    gold = gold_judgment(row)
    decision = gold["decision"]
    family_index = ordinal // 3
    if decision == "needs_correction":
        mode = family_index % 4
        if mode == 0:
            return gold, feedback("agree", [], None, "판단과 최소 교정이 타당합니다."), "agree"
        if mode == 1:
            candidate = judgment("acceptable", text, [], "문법적으로 허용되는 문장입니다.")
            return candidate, feedback("disagree", ["false_negative"], gold, "명확한 문법 오류를 놓쳤습니다."), "false_negative"
        if mode == 2:
            candidate = judgment("needs_correction", gold["corrected_text"], [alternative_error_type(gold["error_types"])], "교정문은 맞지만 오류 유형을 다르게 분류했습니다.")
            return candidate, feedback("disagree", ["wrong_error_type"], gold, "교정문과 오류 유형이 일치하지 않습니다."), "wrong_error_type"
        wrong = append_before_terminal(gold["corrected_text"])
        candidate = judgment("needs_correction", wrong, gold["error_types"], "더 자연스럽게 다듬었습니다.")
        expected = feedback("disagree", ["wrong_correction", "nonminimal_correction"], gold, "필요한 교정 외의 표현을 불필요하게 추가했습니다.")
        return candidate, expected, "wrong_correction"
    if decision == "acceptable":
        mode = family_index % 4
        if mode == 0:
            return gold, feedback("agree", [], None, "문법적으로 허용되는 판단입니다."), "agree"
        if mode == 1:
            changed = append_before_terminal(text)
            candidate = judgment("needs_correction", changed, ["modifier_connection"], "더 자연스럽게 고쳤습니다.")
            expected = feedback("disagree", ["false_positive", "nonminimal_correction"], gold, "허용되는 원문을 불필요하게 바꾸었습니다.")
            return candidate, expected, "false_positive"
        if mode == 2:
            candidate = judgment("insufficient_evidence", text, [], "문맥이 없어 판단할 수 없습니다.")
            expected = feedback("disagree", ["wrong_decision", "unnecessary_abstention"], gold, "제공된 정보만으로 문법 판단이 가능한 문장입니다.")
            return candidate, expected, "unnecessary_abstention"
        candidate = judgment("acceptable", text, [], "과거 시제 오류를 올바르게 교정했습니다.")
        return candidate, feedback("disagree", ["reason_mismatch"], gold, "판단과 설명의 근거가 일치하지 않습니다."), "reason_mismatch"
    mode = family_index % 3
    if mode == 0:
        return gold, feedback("agree", [], None, "근거가 부족해 추측하지 않은 판단이 타당합니다."), "agree"
    if mode == 1:
        candidate = judgment("acceptable", text, [], "문법적으로 허용되는 완결문입니다.")
        expected = feedback("disagree", ["wrong_decision", "should_abstain"], gold, "누락된 정보를 추측하지 말고 판단을 보류해야 합니다.")
        return candidate, expected, "should_abstain"
    invented = append_before_terminal(text, "です")
    candidate = judgment("needs_correction", invented, ["copula_conjugation"], "누락된 종결을 보완했습니다.")
    expected = feedback("disagree", ["should_abstain", "wrong_correction"], gold, "근거 없이 누락 내용을 생성한 교정입니다.")
    return candidate, expected, "invented_correction"


def build_rows():
    source_rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line]
    rows = []
    for ordinal, source_row in enumerate(source_rows):
        candidate, expected, case_type = derive_case(source_row, ordinal)
        row = {
            "id": f"FVH-02-{ordinal + 1:03d}", "text": source_row["input"]["text"],
            "context": source_row["input"]["context"], "learner_level": source_row["input"]["learner_level"],
            "candidate_judgment": candidate, "expected": expected,
            "source_stratum": "gpu_bf16" if ordinal % 2 == 0 else "pi_gguf",
            "source_stratum_kind": "simulated_balance_only", "case_type": case_type,
            "source_judgment_id": source_row["id"], "source_group_id": source_row["group_id"],
            "review_status": "generated_validated",
        }
        validate_input({"text": row["text"], "context": row["context"], "learner_level": row["learner_level"], "judgment": candidate})
        parsed, error = parse_output(canonical(expected), row["text"])
        if parsed is None:
            raise ValueError(f"invalid expected output for {row['id']}: {error}")
        if not set(expected["issue_codes"]) <= ISSUE_CODES:
            raise ValueError(f"invalid issue code for {row['id']}")
        rows.append(row)
    return rows


def input_fingerprint(row):
    return canonical({"text": row["text"], "context": row["context"], "learner_level": row["learner_level"], "candidate_judgment": row["candidate_judgment"]})


def main():
    rows = build_rows()
    OUTPUT.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")
    training = [json.loads(line) for line in TRAINING.read_text(encoding="utf-8").splitlines() if line]
    old = [json.loads(line) for line in OLD_HOLDOUT.read_text(encoding="utf-8").splitlines() if line]
    current_inputs = {input_fingerprint(row) for row in rows}
    manifest = {
        "schema_version": "feedback-holdout-manifest-v0.2", "dataset": OUTPUT.name,
        "sha256": sha(OUTPUT), "records": len(rows), "review_status": "generated_validated",
        "model_inference_count": 0, "source_judgment_dataset": str(SOURCE.relative_to(ROOT)),
        "source_judgment_sha256": sha(SOURCE),
        "source_counts": dict(sorted(Counter(row["source_stratum"] for row in rows).items())),
        "source_stratum_kind": "simulated_balance_only",
        "decision_counts": dict(sorted(Counter(row["candidate_judgment"]["decision"] for row in rows).items())),
        "verdict_counts": dict(sorted(Counter(row["expected"]["verdict"] for row in rows).items())),
        "case_type_counts": dict(sorted(Counter(row["case_type"] for row in rows).items())),
        "exact_input_overlap": {
            "feedback_training_v0.1": len(current_inputs & {input_fingerprint(row) for row in training}),
            "feedback_holdout_v0.1": len(current_inputs & {input_fingerprint(row) for row in old}),
        },
        "limitations": [
            "자동 생성·검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.",
            "원문은 판단모델 평가에 사용된 judgment holdout v0.5에서 파생되어 외부 독립 코퍼스가 아닙니다.",
            "source_stratum은 실제 GPU/Pi 출력이 아니라 균형 검사용 모의 표식입니다.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol = {
        "schema_version": "feedback-holdout-protocol-v0.2", "dataset_sha256": manifest["sha256"],
        "contract_version": "feedback-v0.1", "model": "feedback-qwen3-8b-v01",
        "adapter_sha256": "efbbc9d2cf2bed81e6ce24da6070c25d7bc0755c213875224cfa204d58a22630",
        "serving": {"engine": "vllm", "version": "0.28.0", "reasoning_parser": "qwen3"},
        "temperature": 0.0, "max_tokens": 512, "single_use": True, "consumed": False,
        "thresholds": {
            "contract_success_rate_min": 0.99, "false_disagreement_rate_max": 0.02,
            "disagreement_precision_min": 0.95, "disagreement_recall_min": 0.80,
            "recommended_decision_accuracy_min": 0.90, "accepted_correction_rate_min": 0.80,
            "source_metric_gap_pp_max": 5.0, "p95_latency_seconds_max": 5.0,
        },
    }
    PROTOCOL.write_text(json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

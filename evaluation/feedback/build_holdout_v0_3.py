"""Build the pre-training feedback-v0.3 internal quality holdout."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import parse_output, validate_input
from evaluation.feedback.build_holdout_v0_2 import (
    canonical,
    derive_case,
    input_fingerprint,
    judgment,
)


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "evaluation/judgment/holdout_v0.4.jsonl"
OUTPUT = HERE / "holdout_v0.3.jsonl"
MANIFEST = HERE / "holdout_v0.3.manifest.json"
PROTOCOL = HERE / "holdout_v0.3.protocol.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def orthography_unreviewable(source_row):
    text = source_row["input"]["text"]
    if "わ" in text:
        changed = text.replace("わ", "は", 1)
    elif "お" in text:
        changed = text.replace("お", "を", 1)
    else:
        raise ValueError(f"orthography boundary lacks expected surface form: {text}")
    candidate = judgment("needs_correction", changed, ["particle_misuse"], "조사 표기를 바로잡았습니다.")
    expected = {
        "verdict": "unreviewable",
        "issue_codes": [],
        "recommended_judgment": None,
        "review_reason_ko": "원음이 없어 발화 오류와 STT 표기 오류를 구분할 수 없습니다.",
    }
    return candidate, expected, "audio_required_unreviewable"


def build_rows():
    source_rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line]
    rows = []
    for ordinal, source_row in enumerate(source_rows):
        if source_row["group_id"] == "stt_orthography_boundary_v4":
            candidate, expected, case_type = orthography_unreviewable(source_row)
        else:
            candidate, expected, case_type = derive_case(source_row, ordinal + 7)
        if source_row["input"]["text"] == "……" and case_type == "invented_correction":
            candidate = judgment("needs_correction", "……でした", ["copula_conjugation"], "누락된 종결을 보완했습니다.")
        row = {
            "id": f"FVH-03-{ordinal + 1:03d}",
            "text": source_row["input"]["text"],
            "context": source_row["input"]["context"],
            "learner_level": source_row["input"]["learner_level"],
            "candidate_judgment": candidate,
            "expected": expected,
            "source_kind": "synthetic_candidate_from_internal_judgment_holdout",
            "case_type": case_type,
            "source_judgment_id": source_row["id"],
            "source_group_id": source_row["group_id"],
            "review_status": "generated_validated",
        }
        validate_input({
            "text": row["text"], "context": row["context"],
            "learner_level": row["learner_level"], "judgment": candidate,
        })
        parsed, error = parse_output(canonical(expected), row["text"])
        if parsed is None:
            raise ValueError(f"invalid expected output for {row['id']}: {error}")
        rows.append(row)
    return rows


def load(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main():
    if PROTOCOL.exists():
        protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        if protocol.get("single_use") and protocol.get("consumed"):
            raise SystemExit("refusing to regenerate consumed feedback holdout v0.3")
    rows = build_rows()
    OUTPUT.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")
    current = {input_fingerprint(row) for row in rows}
    comparisons = {
        "feedback_training_v0.1": ROOT / "training/feedback/data/feedback_v0.1.jsonl",
        "feedback_holdout_v0.1": HERE / "holdout_v0.1.jsonl",
        "feedback_holdout_v0.2": HERE / "holdout_v0.2.jsonl",
    }
    overlap = {
        name: len(current & {input_fingerprint(row) for row in load(path)})
        for name, path in comparisons.items()
    }
    manifest = {
        "schema_version": "feedback-holdout-manifest-v0.3",
        "dataset": OUTPUT.name, "sha256": sha(OUTPUT), "records": len(rows),
        "review_status": "generated_validated", "model_inference_count": 0,
        "qualification_scope": "internal_model_selection_only",
        "source_judgment_dataset": str(SOURCE.relative_to(ROOT)),
        "source_judgment_sha256": sha(SOURCE),
        "candidate_decision_counts": dict(sorted(Counter(row["candidate_judgment"]["decision"] for row in rows).items())),
        "verdict_counts": dict(sorted(Counter(row["expected"]["verdict"] for row in rows).items())),
        "case_type_counts": dict(sorted(Counter(row["case_type"] for row in rows).items())),
        "exact_input_overlap": overlap,
        "missing_qualification_inputs": ["actual_pi_gguf_judgments", "external_independent_human_labels"],
        "limitations": [
            "자동 생성·검증 내부 모델 선택용 데이터이며 운영 자격 시험이 아닙니다.",
            "실제 Pi 출력과 외부 독립 사람 라벨이 없어 GPU/Pi 격차나 실제 품질을 주장할 수 없습니다.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol = {
        "schema_version": "feedback-holdout-protocol-v0.3",
        "dataset_sha256": manifest["sha256"], "contract_version": "feedback-v0.1",
        "candidate_family": "feedback-v0.2", "adapter_sha256": None,
        "training_data_sha256": None, "training_config_sha256": None,
        "ready_for_inference": False, "single_use": True, "consumed": False,
        "temperature": 0.0, "max_tokens": 512,
        "serving": {"engine": "vllm", "version": "0.28.0", "reasoning_parser": "qwen3", "flashinfer_sampler": False},
        "thresholds": {
            "contract_success_rate_min": 0.99, "false_disagreement_rate_max": 0.02,
            "disagreement_precision_min": 0.95, "disagreement_recall_min": 0.80,
            "recommended_decision_accuracy_min": 0.90, "accepted_correction_rate_min": 0.80,
            "p95_latency_seconds_max": 5.0,
        },
        "operational_qualification": "blocked_missing_actual_pi_and_external_labels",
    }
    PROTOCOL.write_text(json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

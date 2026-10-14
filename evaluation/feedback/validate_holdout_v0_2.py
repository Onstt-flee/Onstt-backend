"""Validate the sealed feedback-v0.2 holdout and its isolation claims."""

import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import parse_output, validate_input
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def load(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main():
    dataset = HERE / "holdout_v0.2.jsonl"
    manifest = json.loads((HERE / "holdout_v0.2.manifest.json").read_text(encoding="utf-8"))
    protocol = json.loads((HERE / "holdout_v0.2.protocol.json").read_text(encoding="utf-8"))
    rows = load(dataset)
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert digest == manifest["sha256"] == protocol["dataset_sha256"]
    assert len(rows) == manifest["records"] == 120
    assert len({row["id"] for row in rows}) == 120
    assert len({row["source_judgment_id"] for row in rows}) == 120
    assert manifest["source_counts"] == {"gpu_bf16": 60, "pi_gguf": 60}
    assert manifest["source_stratum_kind"] == "simulated_balance_only"
    assert manifest["model_inference_count"] == 120
    assert protocol["consumed"] is True
    assert protocol["official_run"] == {
        "executed_at": "2026-10-15",
        "result_manifest_sha256": "494fd429502f8d695026ff9225b21ccfb4bb487dc0f3395ea25f1cf16777602f",
        "result_sha256": "f99683b072177f70472ec17a8d188e8c73a21fbf6180c3acde6b4721bf9332c5",
        "score_sha256": "d55273426cd5d82b3a56143954c98810156db60d3c0e5d7e1edc310386052358",
    }
    for row in rows:
        assert row["review_status"] == "generated_validated"
        assert row["source_stratum_kind"] == "simulated_balance_only"
        validate_input({"text": row["text"], "context": row["context"], "learner_level": row["learner_level"], "judgment": row["candidate_judgment"]})
        parsed, error = parse_output(json.dumps(row["expected"], ensure_ascii=False), row["text"])
        assert parsed is not None, (row["id"], error)
    current = {input_fingerprint(row) for row in rows}
    training = {input_fingerprint(row) for row in load(ROOT / "training/feedback/data/feedback_v0.1.jsonl")}
    old = {input_fingerprint(row) for row in load(HERE / "holdout_v0.1.jsonl")}
    assert not current & training
    assert not current & old
    assert manifest["exact_input_overlap"] == {"feedback_training_v0.1": 0, "feedback_holdout_v0.1": 0}
    print(f"validated {len(rows)} sealed feedback v0.2 records: {digest}")


if __name__ == "__main__":
    main()

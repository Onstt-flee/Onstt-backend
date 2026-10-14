"""Validate the pre-training v0.3 feedback holdout seal."""

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
    dataset = HERE / "holdout_v0.3.jsonl"
    manifest = json.loads((HERE / "holdout_v0.3.manifest.json").read_text(encoding="utf-8"))
    protocol = json.loads((HERE / "holdout_v0.3.protocol.json").read_text(encoding="utf-8"))
    rows = load(dataset)
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert digest == manifest["sha256"] == protocol["dataset_sha256"]
    assert len(rows) == len({row["id"] for row in rows}) == 120
    assert len({row["source_judgment_id"] for row in rows}) == 120
    assert manifest["model_inference_count"] == 0
    assert protocol["ready_for_inference"] is True
    assert protocol["consumed"] is False
    assert protocol["adapter_sha256"] == "9b4fc64f1ce8ea5ac0f4a41be61ca407df6be866b67623727d2f003807c2f427"
    assert protocol["training_data_sha256"] == "e16ba93aa9ba2b4abc098d478a9a66ea9cf94fc7f3e0b6b5815a5afc83da9ff8"
    assert protocol["training_config_sha256"] == "e1aae512ed5f0e3e2b5ecc88494bd8f311f27640fd6fc2c522083cc39fc4350b"
    assert manifest["exact_input_overlap"] == {
        "feedback_holdout_v0.1": 0,
        "feedback_holdout_v0.2": 0,
        "feedback_training_v0.1": 0,
    }
    assert manifest["verdict_counts"].get("unreviewable") == 8
    for row in rows:
        validate_input({"text": row["text"], "context": row["context"], "learner_level": row["learner_level"], "judgment": row["candidate_judgment"]})
        parsed, error = parse_output(json.dumps(row["expected"], ensure_ascii=False), row["text"])
        assert parsed is not None, (row["id"], error)
    fingerprints = [input_fingerprint(row) for row in rows]
    assert len(fingerprints) == len(set(fingerprints))
    print(f"validated {len(rows)} pre-training feedback v0.3 records: {digest}")


if __name__ == "__main__":
    main()

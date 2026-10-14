import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import ISSUE_CODES, validate_input


HERE = Path(__file__).resolve().parent


def main():
    dataset = HERE / "holdout_v0.1.jsonl"
    manifest = json.loads((HERE / "holdout_v0.1.manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    assert hashlib.sha256(dataset.read_bytes()).hexdigest() == manifest["sha256"]
    assert len(rows) == manifest["records"] == 120
    assert len({row["id"] for row in rows}) == 120
    assert len({row["text"] for row in rows}) == 120
    assert {row["source_stratum"] for row in rows} == {"gpu_bf16", "pi_gguf"}
    for row in rows:
        validate_input({"text": row["text"], "context": row["context"],
                        "learner_level": row["learner_level"], "judgment": row["candidate_judgment"]})
        assert set(row["expected"]["required_issue_codes"]) <= ISSUE_CODES
        assert row["review_status"] == "generated_validated"
    print(f"validated {len(rows)} sealed feedback holdout records: {manifest['sha256']}")


if __name__ == "__main__": main()

import hashlib
import json
from pathlib import Path
import unittest

from analyzer.feedback_contract import parse_output, validate_input
from evaluation.feedback.build_holdout_v0_2 import build_rows
from evaluation.feedback.runner import validate_sealed_run


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "evaluation/feedback"


class FeedbackHoldoutV02Tests(unittest.TestCase):
    def test_sealed_dataset_is_deterministic_and_contract_valid(self):
        dataset = HERE / "holdout_v0.2.jsonl"
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((HERE / "holdout_v0.2.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, build_rows())
        self.assertEqual(len(rows), 120)
        self.assertEqual(hashlib.sha256(dataset.read_bytes()).hexdigest(), manifest["sha256"])
        self.assertEqual(manifest["exact_input_overlap"], {
            "feedback_training_v0.1": 0,
            "feedback_holdout_v0.1": 0,
        })
        for row in rows:
            validate_input({
                "text": row["text"], "context": row["context"],
                "learner_level": row["learner_level"], "judgment": row["candidate_judgment"],
            })
            parsed, error = parse_output(json.dumps(row["expected"], ensure_ascii=False), row["text"])
            self.assertIsNotNone(parsed, (row["id"], error))

    def test_runner_rejects_consumed_or_hash_mismatched_protocol(self):
        protocol = {"single_use": True, "consumed": False, "dataset_sha256": "a" * 64}
        validate_sealed_run(protocol, "a" * 64)
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            validate_sealed_run(protocol, "b" * 64)
        protocol["consumed"] = True
        with self.assertRaisesRegex(ValueError, "already been consumed"):
            validate_sealed_run(protocol, "a" * 64)
        with self.assertRaisesRegex(ValueError, "not ready for inference"):
            validate_sealed_run({
                "ready_for_inference": False,
                "single_use": True,
                "consumed": False,
                "dataset_sha256": "a" * 64,
            }, "a" * 64)


if __name__ == "__main__":
    unittest.main()

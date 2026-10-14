import hashlib
import json
from pathlib import Path
import unittest

from analyzer.feedback_contract import parse_output, validate_input
from evaluation.feedback.build_holdout_v0_3 import build_rows
from evaluation.feedback.runner import validate_sealed_run


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "evaluation/feedback"


class FeedbackHoldoutV03Tests(unittest.TestCase):
    def test_pretraining_seal_is_deterministic_and_isolated(self):
        dataset = HERE / "holdout_v0.3.jsonl"
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((HERE / "holdout_v0.3.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, build_rows())
        self.assertEqual(len(rows), 120)
        self.assertEqual(hashlib.sha256(dataset.read_bytes()).hexdigest(), manifest["sha256"])
        self.assertEqual(manifest["verdict_counts"]["unreviewable"], 8)
        self.assertTrue(all(value == 0 for value in manifest["exact_input_overlap"].values()))
        for row in rows:
            validate_input({
                "text": row["text"], "context": row["context"],
                "learner_level": row["learner_level"], "judgment": row["candidate_judgment"],
            })
            parsed, error = parse_output(json.dumps(row["expected"], ensure_ascii=False), row["text"])
            self.assertIsNotNone(parsed, (row["id"], error))

    def test_protocol_is_ready_only_after_candidate_hashes_are_fixed(self):
        protocol = json.loads((HERE / "holdout_v0.3.protocol.json").read_text(encoding="utf-8"))
        self.assertTrue(protocol["ready_for_inference"])
        self.assertEqual(protocol["adapter_sha256"], "9b4fc64f1ce8ea5ac0f4a41be61ca407df6be866b67623727d2f003807c2f427")
        validate_sealed_run(protocol, protocol["dataset_sha256"])


if __name__ == "__main__":
    unittest.main()

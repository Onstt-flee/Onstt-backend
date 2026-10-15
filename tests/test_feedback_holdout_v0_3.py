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

    def test_consumed_protocol_rejects_another_inference(self):
        protocol = json.loads((HERE / "holdout_v0.3.protocol.json").read_text(encoding="utf-8"))
        self.assertTrue(protocol["ready_for_inference"])
        self.assertTrue(protocol["consumed"])
        self.assertEqual(protocol["adapter_sha256"], "9b4fc64f1ce8ea5ac0f4a41be61ca407df6be866b67623727d2f003807c2f427")
        with self.assertRaisesRegex(ValueError, "already been consumed"):
            validate_sealed_run(protocol, protocol["dataset_sha256"])

    def test_official_result_matches_protocol(self):
        protocol = json.loads((HERE / "holdout_v0.3.protocol.json").read_text(encoding="utf-8"))
        result = json.loads((HERE / "holdout_v0.3.result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["decision"], "rejected")
        self.assertFalse(result["shadow_authorized"])
        self.assertEqual(result["holdout_sha256"], protocol["dataset_sha256"])
        self.assertEqual(result["adapter_sha256"], protocol["adapter_sha256"])
        self.assertEqual(result["result_sha256"], protocol["official_run"]["result_sha256"])
        self.assertEqual(result["score_sha256"], protocol["official_run"]["score_sha256"])
        self.assertEqual(len(result["false_disagreement_ids"]), 6)


if __name__ == "__main__":
    unittest.main()

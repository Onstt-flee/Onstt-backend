import hashlib
import json
from pathlib import Path
import unittest

from analyzer.feedback_contract import parse_output, validate_input
from evaluation.feedback.build_holdout_v0_4 import build_rows


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "evaluation/feedback"


class FeedbackHoldoutV04Tests(unittest.TestCase):
    def test_seal_is_deterministic_balanced_and_consumed_once(self):
        dataset = HERE / "holdout_v0.4.jsonl"
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((HERE / "holdout_v0.4.manifest.json").read_text(encoding="utf-8"))
        protocol = json.loads((HERE / "holdout_v0.4.protocol.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, build_rows())
        self.assertEqual(len(rows), 120)
        self.assertEqual(manifest["verdict_counts"], {"agree": 40, "disagree": 70, "unreviewable": 10})
        self.assertTrue(all(value == 0 for value in manifest["exact_input_overlap"].values()))
        self.assertTrue(all(value == 0 for value in manifest["text_overlap"].values()))
        self.assertFalse(manifest["human_reviewed"])
        self.assertFalse(manifest["expert_reviewed"])
        self.assertEqual(hashlib.sha256(dataset.read_bytes()).hexdigest(), manifest["sha256"])
        self.assertTrue(protocol["ready_for_inference"])
        self.assertTrue(protocol["consumed"])
        self.assertEqual(protocol["adapter_sha256"], "3bcbc80d1559dacf60a84c708a8ab4c51ee4bd33532acf2ab134394aa2dcd1ad")
        self.assertEqual(protocol["training_data_sha256"], hashlib.sha256((ROOT / "training/feedback/data/feedback_v0.3.jsonl").read_bytes()).hexdigest())
        self.assertEqual(protocol["training_config_sha256"], hashlib.sha256((ROOT / "training/feedback/config_v0.3.json").read_bytes()).hexdigest())
        self.assertEqual(protocol["official_run"]["result_sha256"], "6d3fe9032251403e05d2c8ab970ee7bd7f1ddb11c6f9c5d2afa9e1aeab4abf32")

    def test_official_result_matches_consumed_protocol(self):
        protocol = json.loads((HERE / "holdout_v0.4.protocol.json").read_text(encoding="utf-8"))
        result = json.loads((HERE / "holdout_v0.4.result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["decision"], "passed_internal_gpu_evaluation")
        self.assertTrue(result["gpu_only_shadow_ready"])
        self.assertFalse(result["operational_approved"])
        self.assertEqual(result["holdout_sha256"], protocol["dataset_sha256"])
        self.assertEqual(result["adapter_sha256"], protocol["adapter_sha256"])
        self.assertEqual(result["raw_result_sha256"], protocol["official_run"]["result_sha256"])
        self.assertGreaterEqual(result["metrics"]["contract_success_rate"], protocol["thresholds"]["contract_success_rate_min"])
        self.assertLessEqual(result["metrics"]["false_disagreement_rate"], protocol["thresholds"]["false_disagreement_rate_max"])

    def test_every_input_and_expected_output_obeys_contract(self):
        for row in build_rows():
            validate_input({
                "text": row["text"], "context": row["context"],
                "learner_level": row["learner_level"], "judgment": row["candidate_judgment"],
            })
            parsed, error = parse_output(json.dumps(row["expected"], ensure_ascii=False), row["text"])
            self.assertIsNotNone(parsed, (row["id"], error))


if __name__ == "__main__":
    unittest.main()

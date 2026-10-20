import hashlib
import json
from pathlib import Path
import unittest

from evaluation.feedback.build_holdout_v0_7 import build_rows


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "evaluation/feedback"


class FeedbackHoldoutV07Tests(unittest.TestCase):
    def test_preimplementation_seal_is_deterministic_balanced_and_isolated(self):
        dataset = HERE / "holdout_v0.7.jsonl"
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((HERE / "holdout_v0.7.manifest.json").read_text(encoding="utf-8"))
        protocol = json.loads((HERE / "holdout_v0.7.protocol.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, build_rows())
        self.assertEqual(len(rows), 120)
        self.assertEqual(len({row["id"] for row in rows}), 120)
        self.assertEqual(manifest["verdict_counts"], {"agree": 50, "disagree": 60, "unreviewable": 10})
        self.assertEqual(manifest["stage2_expected_rows"], 60)
        self.assertTrue(all(not item["exact_input"] and not item["text"] for item in manifest["overlap"].values()))
        self.assertEqual(hashlib.sha256(dataset.read_bytes()).hexdigest(), manifest["sha256"])
        self.assertTrue(manifest["sealed_before_two_stage_implementation"])
        self.assertFalse(manifest["human_reviewed"])
        self.assertFalse(manifest["expert_reviewed"])
        self.assertFalse(protocol["implementation_started"])
        self.assertFalse(protocol["ready_for_inference"])
        self.assertFalse(protocol["consumed"])
        self.assertEqual(protocol["model_inference_count"], 0)

    def test_stage2_gold_exists_if_and_only_if_stage1_disagrees(self):
        for row in build_rows():
            disagree = row["expected_stage1"]["verdict"] == "disagree"
            self.assertEqual(row["expected_stage2"] is not None, disagree, row["id"])

    def test_thresholds_are_frozen_before_implementation(self):
        protocol = json.loads((HERE / "holdout_v0.7.protocol.json").read_text(encoding="utf-8"))
        thresholds = protocol["thresholds"]
        self.assertEqual(thresholds["stage1_contract_success_rate_min"], 0.99)
        self.assertEqual(thresholds["stage2_call_discipline_rate_min"], 1.0)
        self.assertEqual(thresholds["recommended_decision_accuracy_min"], 0.90)
        self.assertEqual(thresholds["accepted_correction_rate_min"], 0.80)


if __name__ == "__main__":
    unittest.main()

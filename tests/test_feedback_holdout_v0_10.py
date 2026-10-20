import hashlib
import json
from pathlib import Path
import unittest

from evaluation.feedback.build_holdout_v0_10 import build_rows

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "evaluation/feedback"


class FeedbackHoldoutV10Tests(unittest.TestCase):
    def test_pretraining_seal_is_deterministic_isolated_and_unused(self):
        rows = [json.loads(line) for line in (HERE / "holdout_v0.10.jsonl").read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((HERE / "holdout_v0.10.manifest.json").read_text(encoding="utf-8"))
        protocol = json.loads((HERE / "holdout_v0.10.protocol.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, build_rows())
        self.assertEqual(len(rows), 120)
        self.assertEqual(len({row["id"] for row in rows}), 120)
        self.assertEqual(manifest["verdict_counts"], {"agree": 50, "disagree": 60, "unreviewable": 10})
        self.assertEqual(manifest["stage2_expected_rows"], 60)
        self.assertEqual(manifest["targeted_stage1_rows"], 40)
        self.assertTrue(all(not item["exact_input"] and not item["text"] for item in manifest["overlap"].values()))
        self.assertEqual(hashlib.sha256((HERE / "holdout_v0.10.jsonl").read_bytes()).hexdigest(), manifest["sha256"])
        self.assertTrue(manifest["sealed_before_v0.8_training"])
        self.assertFalse(protocol["training_started"])
        self.assertFalse(protocol["ready_for_inference"])
        self.assertFalse(protocol["consumed"])
        self.assertEqual(protocol["model_inference_count"], 0)

    def test_stage2_gold_exists_only_for_disagree(self):
        for row in build_rows():
            self.assertEqual(row["expected_stage1"]["verdict"] == "disagree", row["expected_stage2"] is not None)


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
from collections import Counter
from pathlib import Path
import unittest

from training.feedback.generate_v0_7_stage1_correction_comparison import build_targeted
from training.judgment.train_lora import load_config, validate_inputs

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "training/feedback/data"


class FeedbackTrainingV07Tests(unittest.TestCase):
    def test_targeted_pairs_are_balanced_and_deterministic(self):
        rows = build_targeted()
        self.assertEqual(len(rows), 160)
        self.assertEqual(len({row["id"] for row in rows}), 160)
        self.assertEqual(Counter(row["expected"]["verdict"] for row in rows), {"agree": 80, "disagree": 80})
        groups = Counter(row["pair_group"] for row in rows)
        self.assertEqual(len(groups), 20)
        self.assertTrue(all(count == 8 for count in groups.values()))
        self.assertTrue(all(row["task"] == "feedback_stage1" for row in rows))

    def test_combined_dataset_is_holdout_free_and_hash_bound(self):
        rows = [json.loads(line) for line in (DATA / "feedback_v0.7.stage1-comparison.jsonl").read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((DATA / "feedback_v0.7.stage1-comparison.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 3731)
        self.assertEqual(manifest["base_records"], 3571)
        self.assertEqual(manifest["targeted_records"], 160)
        self.assertEqual(manifest["train_records"], 3351)
        self.assertEqual(manifest["eval_records"], 380)
        self.assertEqual(manifest["task_counts"], {"feedback_stage1": 2482, "feedback_stage2": 1249})
        self.assertTrue(all(not value["exact_input"] and not value["text"] for value in manifest["protected_overlap"].values()))
        self.assertFalse(manifest["holdout_used"])
        self.assertEqual(manifest["source_sha256"], hashlib.sha256((DATA / "feedback_v0.7.stage1-comparison.jsonl").read_bytes()).hexdigest())

    def test_shared_trainer_validates_v07_without_changing_hyperparameters(self):
        old = load_config(ROOT / "training/feedback/config_v0.6.json")
        new = load_config(ROOT / "training/feedback/config_v0.7.json")
        changed = {"eval_file", "experiment_id", "output_dir", "source_dataset", "train_file"}
        for key in set(old) - changed:
            self.assertEqual(new[key], old[key], key)
        validation = validate_inputs(new)
        self.assertEqual(validation["train_count"], 3351)
        self.assertEqual(validation["eval_count"], 380)
        self.assertEqual(validation["source_review_statuses"], ["generated_validated"])


if __name__ == "__main__":
    unittest.main()

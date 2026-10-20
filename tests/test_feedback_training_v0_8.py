import hashlib
import json
from collections import Counter
from pathlib import Path
import unittest

from training.feedback.generate_v0_8_stage2_recovery_style import build_targeted
from training.judgment.train_lora import load_config, validate_inputs

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "training/feedback/data"


class FeedbackTrainingV08Tests(unittest.TestCase):
    def test_targeted_pairs_are_balanced_and_deterministic(self):
        rows = build_targeted()
        self.assertEqual(len(rows), 140)
        self.assertEqual(len({row["id"] for row in rows}), 140)
        self.assertEqual(Counter(row["task"] for row in rows), {"feedback_stage1": 40, "feedback_stage2": 100})
        groups = Counter(row["pair_group"] for row in rows)
        self.assertEqual(len(groups), 20)
        self.assertTrue(all(count == 7 for count in groups.values()))
        self.assertEqual(Counter(row["expected"]["verdict"] for row in rows if row["task"] == "feedback_stage1"), {"agree": 20, "disagree": 20})
        self.assertEqual(Counter(row["expected"]["decision"] for row in rows if row["task"] == "feedback_stage2"), {"acceptable": 40, "needs_correction": 60})

    def test_combined_dataset_is_holdout_free_and_hash_bound(self):
        rows = [json.loads(line) for line in (DATA / "feedback_v0.8.stage2-recovery-style.jsonl").read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((DATA / "feedback_v0.8.stage2-recovery-style.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 3871)
        self.assertEqual(manifest["base_records"], 3731)
        self.assertEqual(manifest["targeted_records"], 140)
        self.assertEqual(manifest["train_records"], 3477)
        self.assertEqual(manifest["eval_records"], 394)
        self.assertEqual(manifest["task_counts"], {"feedback_stage1": 2522, "feedback_stage2": 1349})
        self.assertTrue(all(not value["exact_input"] and not value["text"] for value in manifest["protected_overlap"].values()))
        self.assertFalse(manifest["holdout_used"])
        self.assertEqual(manifest["source_sha256"], hashlib.sha256((DATA / "feedback_v0.8.stage2-recovery-style.jsonl").read_bytes()).hexdigest())

    def test_shared_trainer_validates_v08_without_changing_hyperparameters(self):
        old = load_config(ROOT / "training/feedback/config_v0.7.json")
        new = load_config(ROOT / "training/feedback/config_v0.8.json")
        changed = {"eval_file", "experiment_id", "output_dir", "source_dataset", "train_file"}
        for key in set(old) - changed:
            self.assertEqual(new[key], old[key], key)
        validation = validate_inputs(new)
        self.assertEqual(validation["train_count"], 3477)
        self.assertEqual(validation["eval_count"], 394)
        self.assertEqual(validation["source_review_statuses"], ["generated_validated"])


if __name__ == "__main__":
    unittest.main()

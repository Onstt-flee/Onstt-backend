"""Integrity tests for the v0.2-I controlled training schedule."""

import hashlib
import unittest
from pathlib import Path

from training.judgment.build_failure_focus_v0_2_i import (
    EXPECTED_HOLDOUT_SHA256, SEALED_HOLDOUT, build,
)
from training.judgment.train_lora import load_config, validate_inputs


ROOT = Path(__file__).resolve().parents[1]


class JudgmentFailureFocusV02ITests(unittest.TestCase):
    def test_build_is_fixed_and_does_not_consume_holdout(self):
        result = build()
        self.assertEqual(result["combined"]["count"], 868)
        self.assertEqual(result["train"]["count"], 720)
        self.assertEqual(result["train"]["unique_inputs"], 684)
        self.assertEqual(result["train"]["base_d_once"], 594)
        self.assertEqual(result["train"]["f_augmentation_once"], 90)
        self.assertEqual(result["dev"]["count"], 184)
        self.assertEqual(result["review"]["new_gold_examples_created"], 0)
        self.assertFalse(result["sealed_holdout"]["content_read_by_builder"])
        self.assertEqual(result["sealed_holdout"]["model_inference_count"], 0)
        self.assertEqual(hashlib.sha256(SEALED_HOLDOUT.read_bytes()).hexdigest(), EXPECTED_HOLDOUT_SHA256)

    def test_training_config_validates(self):
        path = ROOT / "training/judgment/configs/qwen3_4b_failure_focus_v0.2_i.json"
        validation = validate_inputs(load_config(path))
        self.assertEqual(validation["train_count"], 720)
        self.assertEqual(validation["eval_count"], 184)
        self.assertEqual(validation["source_review_statuses"], ["generated_validated", "user_reviewed"])


if __name__ == "__main__":
    unittest.main()

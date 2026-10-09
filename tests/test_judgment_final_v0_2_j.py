"""Integrity tests for the final v0.2-J dataset and training schedule."""

import hashlib
import unittest
from pathlib import Path

from training.judgment.build_final_v0_2_j import (
    CONSUMED, EXPECTED_CONSUMED_SHA256, EXPECTED_HOLDOUT_SHA256,
    SEALED_HOLDOUT, build,
)
from training.judgment.train_lora import load_config, validate_inputs

ROOT = Path(__file__).resolve().parents[1]


class JudgmentFinalV02JTests(unittest.TestCase):
    def test_build_is_fixed_and_v04_is_permanently_consumed(self):
        result = build()
        self.assertEqual(result["combined"]["count"], 867)
        self.assertEqual(result["train"]["count"], 714)
        self.assertEqual(result["train"]["unique_inputs"], 713)
        self.assertEqual(result["train"]["base_d_once"], 594)
        self.assertEqual(result["train"]["consumed_v04_once"], 120)
        self.assertEqual(len(result["train"]["consumed_duplicate_exposures"]), 1)
        self.assertEqual(result["combined"]["consumed_unique_additions"], 119)
        self.assertEqual(result["dev"]["count"], 154)
        self.assertTrue(result["consumed_benchmark"]["permanently_retired_from_evaluation"])
        self.assertEqual(result["review"]["new_gold_examples_created"], 0)
        self.assertFalse(result["review"]["human_or_expert_review_claimed"])
        self.assertFalse(result["sealed_holdout"]["content_read_by_builder"])
        self.assertEqual(result["sealed_holdout"]["model_inference_count"], 0)
        self.assertEqual(hashlib.sha256(CONSUMED.read_bytes()).hexdigest(), EXPECTED_CONSUMED_SHA256)
        self.assertEqual(hashlib.sha256(SEALED_HOLDOUT.read_bytes()).hexdigest(), EXPECTED_HOLDOUT_SHA256)

    def test_training_config_validates(self):
        path = ROOT / "training/judgment/configs/qwen3_4b_final_v0.2_j.json"
        validation = validate_inputs(load_config(path))
        self.assertEqual(validation["train_count"], 714)
        self.assertEqual(validation["eval_count"], 154)
        self.assertEqual(validation["source_review_statuses"], ["generated_validated", "user_reviewed"])


if __name__ == "__main__":
    unittest.main()

"""Verify v0.2-H changes exposure only and never reads holdout labels."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from training.judgment import build_sampling_focus_v0_2_h as builder


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class JudgmentSamplingFocusV02HTests(unittest.TestCase):
    def test_schedule_manifest_and_reproducibility(self):
        manifest = json.loads(builder.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["train"]["count"], 720)
        self.assertEqual(manifest["train"]["unique_inputs"], 675)
        self.assertEqual(manifest["dev"]["count"], 181)
        self.assertEqual(len(manifest["sampling_policy"]["repeat_ids"]), 45)
        self.assertEqual(manifest["sampling_policy"]["g_extra_insufficient_evidence"], 24)
        self.assertEqual(manifest["sampling_policy"]["g_extra_acceptable"], 21)
        self.assertEqual(sha256(builder.TRAIN), manifest["train"]["sha256"])
        self.assertEqual(sha256(builder.DEV), manifest["dev"]["sha256"])
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with patch.multiple(builder, OUTPUT=base, TRAIN=base / "train.jsonl",
                                DEV=base / "dev.jsonl", MANIFEST=base / "manifest.json"):
                generated = builder.build()
            self.assertEqual(generated["train"]["sha256"], manifest["train"]["sha256"])
            self.assertEqual(generated["dev"]["sha256"], manifest["dev"]["sha256"])

    def test_config_matches_g_except_experiment_paths(self):
        root = builder.ROOT
        g = json.loads((root / "training/judgment/configs/qwen3_4b_contract_preservation_v0.2_g.json").read_text())
        h = json.loads((root / "training/judgment/configs/qwen3_4b_sampling_focus_v0.2_h.json").read_text())
        differing = {key for key in g if g[key] != h[key]}
        self.assertEqual(differing, {"experiment_id", "train_file", "eval_file", "output_dir"})
        self.assertEqual(h["max_steps"] * h["gradient_accumulation_steps"], 720)

    def test_no_holdout_dependency_or_model_output(self):
        source = Path(builder.__file__).read_text(encoding="utf-8")
        self.assertNotIn("holdout_v0.4.jsonl", source)
        self.assertNotIn("evaluation/judgment/runs", source)
        manifest = json.loads(builder.MANIFEST.read_text(encoding="utf-8"))
        self.assertFalse(manifest["holdout_policy"]["holdout_v0.4_read_by_builder"])


if __name__ == "__main__":
    unittest.main()

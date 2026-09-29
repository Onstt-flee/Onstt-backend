"""Keep v0.2-E augmentation reproducible, minimal, and holdout-isolated."""

import hashlib
import json
from pathlib import Path
import unittest

from training.judgment.build_failure_focus_v0_2_e import (
    ADDITION, BASE, CHATML, COMBINED, MANIFEST, build,
)
from training.judgment.data import load_records, validate_records
from training.judgment.train_lora import load_chatml, load_config, validate_inputs


ROOT = Path(__file__).resolve().parents[1]
HOLDOUTS = (
    ROOT / "evaluation/judgment/holdout_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.2.jsonl",
)


class JudgmentFailureFocusV02ETests(unittest.TestCase):
    def test_config_matches_d_except_experiment_paths(self):
        config_dir = ROOT / "training/judgment/configs"
        d = load_config(config_dir / "qwen3_4b_failure_focus_v0.2_d.json")
        e = load_config(config_dir / "qwen3_4b_failure_focus_v0.2_e.json")
        excluded = {"experiment_id", "train_file", "eval_file", "source_dataset", "output_dir"}
        self.assertEqual({key: value for key, value in d.items() if key not in excluded},
                         {key: value for key, value in e.items() if key not in excluded})
        self.assertNotEqual(d["output_dir"], e["output_dir"])
        self.assertEqual(validate_inputs(e)["source_dataset_sha256"],
                         json.loads(MANIFEST.read_text(encoding="utf-8"))["combined_sha256"])

    def test_distribution_source_prefix_and_minimal_edits(self):
        addition = load_records(ADDITION)
        base = load_records(BASE)
        combined = load_records(COMBINED)
        validate_records(addition, require_reviewed=True)
        validate_records(combined, require_reviewed=True)
        self.assertEqual(len(addition), 80)
        self.assertEqual(len(combined), 828)
        self.assertEqual(combined[:748], base)
        self.assertEqual(combined[748:], addition)
        self.assertEqual({row["review"]["status"] for row in addition}, {"generated_validated"})
        self.assertEqual({row["review"]["reviewed_at"] for row in addition}, {"2026-09-29"})
        self.assertEqual({row["id"] for row in addition}, {f"JT-{n:04d}" for n in range(749, 829)})
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["augmentation_summary"]["decisions"], {
            "acceptable": 32, "insufficient_evidence": 8, "needs_correction": 40,
        })
        self.assertEqual(manifest["augmentation_summary"]["splits"], {
            "pilot_dev": 20, "pilot_train": 60,
        })
        self.assertEqual(manifest["generated_validation"]["compound_error_cases"], 12)
        self.assertEqual(manifest["generated_validation"]["paired_cases"], 16)
        self.assertFalse(manifest["generated_validation"]["human_reviewed"])
        self.assertFalse(manifest["generated_validation"]["expert_reviewed"])
        corrections = [row for row in addition if row["expected"]["decision"] == "needs_correction"]
        self.assertTrue(any("読めるます" in row["input"]["text"] for row in corrections))
        self.assertTrue(any("小さいな" in row["input"]["text"] for row in corrections))
        self.assertTrue(any(len(row["expected"]["edits"]) > 1 for row in corrections))
        for row in corrections:
            self.assertNotEqual(row["input"]["text"], row["expected"]["corrected_text"])
        for row in addition:
            if row["expected"]["decision"] != "needs_correction":
                self.assertEqual(row["input"]["text"], row["expected"]["corrected_text"])

    def test_contamination_audit_and_hashes(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        audit = manifest["generated_validation"]["contamination_audit"]
        self.assertEqual(audit["exact_normalized_matches"], 0)
        self.assertEqual(audit["near_dataset_matches_at_or_above_0_85"], 0)
        for path, key in ((BASE, "source_dataset_sha256"),
                          (ADDITION, "augmentation_sha256"), (COMBINED, "combined_sha256")):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), manifest[key])
        for path in HOLDOUTS:
            relative = str(path.relative_to(ROOT))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             audit["source_sha256"][relative])

    def test_chatml_is_position_free_and_matches_gold(self):
        combined = load_records(COMBINED)
        for split in ("pilot_train", "pilot_dev"):
            exported = load_chatml(CHATML / f"{split}.chatml.jsonl")
            source = [row for row in combined if row["split"] == split]
            self.assertEqual(len(exported), len(source))
            for item, row in zip(exported, source):
                target = json.loads(item["messages"][2]["content"])
                self.assertEqual(set(target), {"decision", "corrected_text", "error_types", "reason_ko"})
                self.assertEqual(target["decision"], row["expected"]["decision"])
                self.assertEqual(target["corrected_text"], row["expected"]["corrected_text"])
                self.assertEqual(target["error_types"], list(dict.fromkeys(
                    edit["error_type"] for edit in row["expected"]["edits"])))

    def test_reproducible_and_holdouts_unmodified(self):
        paths = (BASE, ADDITION, COMBINED, MANIFEST,
                 CHATML / "pilot_train.chatml.jsonl", CHATML / "pilot_dev.chatml.jsonl",
                 *HOLDOUTS)
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        build()
        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

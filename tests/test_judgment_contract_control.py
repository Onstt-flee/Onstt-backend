"""Guard the matched-contract v0.2-B control input against label drift."""

import hashlib
import json
from pathlib import Path
import unittest

from training.judgment.build_contract_control import MANIFEST, OUTPUT, SOURCE, build
from training.judgment.data import load_records, validate_records
from training.judgment.train_lora import load_chatml, load_config, validate_inputs


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "training/judgment/configs/qwen3_4b_contract_control_v0.2_b.json"
C_CONFIG = ROOT / "training/judgment/configs/qwen3_4b_failure_focus_v0.2_c.json"


class JudgmentContractControlTests(unittest.TestCase):
    def test_reexport_preserves_gold_and_is_reproducible(self):
        before = [SOURCE.read_bytes()] + [
            (OUTPUT / f"{split}.chatml.jsonl").read_bytes()
            for split in ("pilot_train", "pilot_dev")
        ]
        manifest_before = MANIFEST.read_bytes()
        self.assertEqual(build(), json.loads(manifest_before))
        self.assertEqual(before, [SOURCE.read_bytes()] + [
            (OUTPUT / f"{split}.chatml.jsonl").read_bytes()
            for split in ("pilot_train", "pilot_dev")
        ])
        self.assertEqual(manifest_before, MANIFEST.read_bytes())
        records = load_records(SOURCE)
        validate_records(records, require_reviewed=True)
        self.assertEqual(len(records), 540)
        manifest = json.loads(manifest_before)
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(), manifest["source_dataset_sha256"])
        self.assertFalse(manifest["gold_labels_changed"])
        for split in ("pilot_train", "pilot_dev"):
            exported = load_chatml(OUTPUT / f"{split}.chatml.jsonl")
            source = [row for row in records if row["split"] == split]
            self.assertEqual(len(exported), len(source))
            for item, row in zip(exported, source):
                target = json.loads(item["messages"][2]["content"])
                self.assertEqual(set(target), {"decision", "corrected_text", "error_types", "reason_ko"})
                self.assertEqual(target["decision"], row["expected"]["decision"])
                self.assertEqual(target["corrected_text"], row["expected"]["corrected_text"])
                self.assertEqual(target["reason_ko"], row["expected"]["reason_ko"])
                self.assertEqual(target["error_types"], list(dict.fromkeys(
                    edit["error_type"] for edit in row["expected"]["edits"])))

    def test_training_conditions_match_c(self):
        control = load_config(CONFIG)
        comparison = load_config(C_CONFIG)
        excluded = {"experiment_id", "train_file", "eval_file", "source_dataset", "output_dir"}
        self.assertEqual({k: v for k, v in control.items() if k not in excluded},
                         {k: v for k, v in comparison.items() if k not in excluded})
        self.assertEqual(validate_inputs(control)["source_dataset_sha256"],
                         json.loads(MANIFEST.read_text())["source_dataset_sha256"])


if __name__ == "__main__":
    unittest.main()

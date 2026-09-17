import json
from pathlib import Path
import tempfile
import unittest

from training.judgment.build_reason_control import (
    DEFAULT_MANIFEST,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SOURCE,
    build,
    controlled_expected,
    validate_control,
)
from training.judgment.data import load_records
from training.judgment.train_lora import load_chatml, load_config, validate_inputs


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "training/judgment/configs/qwen3_4b_reason_control_v0.2_a.json"


class JudgmentReasonControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = load_records(DEFAULT_SOURCE)

    def test_only_training_reason_changes(self):
        report = validate_control(self.source)
        self.assertEqual(report["total"], 300)
        self.assertEqual(report["changed_reason_count"], 300)
        self.assertEqual(report["review_statuses"], ["user_reviewed"])
        for row in self.source:
            controlled = controlled_expected(row)
            self.assertEqual(controlled["decision"], row["expected"]["decision"])
            self.assertEqual(controlled["corrected_text"], row["expected"]["corrected_text"])
            self.assertEqual(controlled["edits"], row["expected"]["edits"])

    def test_checked_in_outputs_are_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = build(DEFAULT_SOURCE, root / "chatml", root / "manifest.json")
            checked = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
            self.assertEqual(generated["validation"], checked["validation"])
            self.assertEqual(generated["reason_by_family"], checked["reason_by_family"])
            for split in ("pilot_train", "pilot_dev"):
                self.assertEqual(
                    (root / "chatml" / f"{split}.chatml.jsonl").read_bytes(),
                    (DEFAULT_OUTPUT_DIR / f"{split}.chatml.jsonl").read_bytes(),
                )

    def test_chatml_matches_controlled_source(self):
        source_by_input = {
            json.dumps(row["input"], ensure_ascii=False, sort_keys=True, separators=(",", ":")): row
            for row in self.source
        }
        rows = []
        for split in ("pilot_train", "pilot_dev"):
            rows.extend(load_chatml(DEFAULT_OUTPUT_DIR / f"{split}.chatml.jsonl"))
        self.assertEqual(len(rows), 300)
        for sample in rows:
            model_input = sample["messages"][1]["content"]
            expected = json.loads(sample["messages"][2]["content"])
            self.assertEqual(expected, controlled_expected(source_by_input[model_input]))

    def test_training_config_preserves_v01_conditions(self):
        report = validate_inputs(load_config(CONFIG))
        self.assertEqual(report["train_count"], 240)
        self.assertEqual(report["eval_count"], 60)
        self.assertEqual(report["source_review_statuses"], ["user_reviewed"])
        self.assertEqual(
            report["source_dataset_sha256"],
            "ff330bb62d479c8779b80ec9fdd9b25ae074172bdc0df5759a83af8c65bff16b",
        )


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import tempfile
import unittest

from training.judgment.train_lora import load_chatml, load_config, validate_inputs


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "training" / "judgment" / "configs" / "qwen3_4b_pilot_v0.1.json"


class JudgmentLoraTrainingTests(unittest.TestCase):
    def test_experimental_inputs_are_pinned_and_split(self):
        report = validate_inputs(load_config(CONFIG))
        self.assertEqual(report["train_count"], 240)
        self.assertEqual(report["eval_count"], 60)
        self.assertEqual(report["source_review_statuses"], ["provisional"])
        self.assertEqual(
            report["train_sha256"],
            "56f75d73c07fd257e1daa746a71648548ee899ae9eaabfe7b2b3a61ca4b27a5f",
        )
        self.assertEqual(
            report["eval_sha256"],
            "31e03cecb444701ab8da6bc246de45cb6b7dddaff6a3955f053aa3601c2ddadd",
        )

    def test_reviewed_inputs_are_separate_from_provisional(self):
        reviewed_config = ROOT / "training" / "judgment" / "configs" / "qwen3_4b_reviewed_v0.1.json"
        report = validate_inputs(load_config(reviewed_config))
        self.assertEqual(report["train_count"], 240)
        self.assertEqual(report["eval_count"], 60)
        self.assertEqual(report["source_review_statuses"], ["user_reviewed"])
        self.assertEqual(
            report["source_dataset_sha256"],
            "ff330bb62d479c8779b80ec9fdd9b25ae074172bdc0df5759a83af8c65bff16b",
        )

    def test_chatml_rejects_metadata_and_wrong_role_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.jsonl"
            path.write_text(json.dumps({
                "messages": [
                    {"role": "system", "content": "{}"},
                    {"role": "assistant", "content": "{}"},
                    {"role": "user", "content": "{}"},
                ],
                "id": "must-not-leak",
            }) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "only messages is allowed"):
                load_chatml(path)


if __name__ == "__main__":
    unittest.main()

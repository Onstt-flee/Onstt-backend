import hashlib
import json
from pathlib import Path
import unittest

from analyzer.feedback_contract import parse_output, validate_input
from training.feedback.generate_v0_2 import build_rows


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "training/feedback/data"


class FeedbackTrainingV02Tests(unittest.TestCase):
    def test_dataset_is_paired_deterministic_and_holdout_isolated(self):
        rows = [json.loads(line) for line in (DATA / "feedback_v0.2.jsonl").read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((DATA / "feedback_v0.2.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, build_rows())
        self.assertEqual(len(rows), 1582)
        self.assertEqual(manifest["train_records"], 1424)
        self.assertEqual(manifest["eval_records"], 158)
        self.assertEqual(manifest["holdout_v0.3_exact_input_overlap"], 0)
        train_sources = {row["source_judgment_id"] for row in rows if row["split_group"] == "train"}
        eval_sources = {row["source_judgment_id"] for row in rows if row["split_group"] == "eval"}
        self.assertFalse(train_sources & eval_sources)
        self.assertEqual(hashlib.sha256((DATA / "feedback_v0.2.jsonl").read_bytes()).hexdigest(), manifest["source_sha256"])

    def test_chatml_outputs_obey_feedback_contract(self):
        for filename in ("train_v0.2.chatml.jsonl", "eval_v0.2.chatml.jsonl"):
            for line in (DATA / filename).read_text(encoding="utf-8").splitlines():
                chat = json.loads(line)
                model_input = json.loads(chat["messages"][1]["content"])
                validate_input(model_input)
                parsed, error = parse_output(chat["messages"][2]["content"], model_input["text"])
                self.assertIsNotNone(parsed, error)

    def test_training_config_uses_new_adapter_and_one_epoch(self):
        config = json.loads((ROOT / "training/feedback/config_v0.2.json").read_text(encoding="utf-8"))
        self.assertEqual(config["num_train_epochs"], 1)
        self.assertEqual(config["seed"], 42)
        self.assertTrue(config["output_dir"].endswith("/feedback-verifier-v0.2"))
        self.assertNotEqual(config["output_dir"], str(ROOT / "training/feedback/data"))


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
from pathlib import Path
import unittest

from analyzer.feedback_contract import parse_output, validate_input
from training.feedback.generate_v0_3 import build_rows, targeted_rows


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "training/feedback/data"


class FeedbackTrainingV03Tests(unittest.TestCase):
    def test_dataset_is_deterministic_targeted_and_holdout_isolated(self):
        rows = [json.loads(line) for line in (DATA / "feedback_v0.3.jsonl").read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((DATA / "feedback_v0.3.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, build_rows())
        self.assertEqual(len(targeted_rows()), 200)
        self.assertEqual(len(rows), 1782)
        self.assertEqual(manifest["train_records"], 1604)
        self.assertEqual(manifest["eval_records"], 178)
        self.assertEqual(manifest["holdout_v0.4_exact_input_overlap"], 0)
        self.assertEqual(manifest["holdout_v0.4_text_overlap"], 0)
        self.assertEqual(manifest["verdict_counts"], {"agree": 847, "disagree": 909, "unreviewable": 26})
        self.assertEqual(hashlib.sha256((DATA / "feedback_v0.3.jsonl").read_bytes()).hexdigest(), manifest["source_sha256"])

    def test_chatml_outputs_obey_feedback_contract(self):
        for filename in ("train_v0.3.chatml.jsonl", "eval_v0.3.chatml.jsonl"):
            for line in (DATA / filename).read_text(encoding="utf-8").splitlines():
                chat = json.loads(line)
                model_input = json.loads(chat["messages"][1]["content"])
                validate_input(model_input)
                parsed, error = parse_output(chat["messages"][2]["content"], model_input["text"])
                self.assertIsNotNone(parsed, error)

    def test_training_config_keeps_comparable_conditions(self):
        config = json.loads((ROOT / "training/feedback/config_v0.3.json").read_text(encoding="utf-8"))
        self.assertEqual(config["num_train_epochs"], 1)
        self.assertEqual(config["seed"], 42)
        self.assertEqual(config["lora_r"], 16)
        self.assertTrue(config["output_dir"].endswith("/feedback-verifier-v0.3"))


if __name__ == "__main__":
    unittest.main()

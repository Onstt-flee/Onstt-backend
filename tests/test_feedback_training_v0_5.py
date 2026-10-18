import hashlib
import json
from pathlib import Path
import unittest

from analyzer.feedback_contract import parse_output, validate_input
from training.feedback.generate_v0_5 import build_rows, targeted_rows


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "training/feedback/data"


class FeedbackTrainingV05Tests(unittest.TestCase):
    def test_dataset_is_deterministic_targeted_and_protected(self):
        rows = [json.loads(line) for line in (DATA / "feedback_v0.5.jsonl").read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((DATA / "feedback_v0.5.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, build_rows())
        self.assertEqual(len(targeted_rows()), 240)
        self.assertEqual(len(rows), 2322)
        self.assertEqual(manifest["train_records"], 2084)
        self.assertEqual(manifest["eval_records"], 238)
        self.assertEqual(manifest["case_type_counts"]["destination_agree_stability"], 60)
        self.assertEqual(manifest["case_type_counts"]["false_negative_contract_anchor"], 80)
        self.assertEqual(manifest["case_type_counts"]["false_positive_contract_anchor"], 40)
        self.assertEqual(manifest["case_type_counts"]["audio_boundary_anchor"], 20)
        self.assertTrue(all(not item["exact_input"] and not item["text"] for item in manifest["protected_overlap"].values()))
        self.assertEqual(hashlib.sha256((DATA / "feedback_v0.5.jsonl").read_bytes()).hexdigest(), manifest["source_sha256"])

    def test_chatml_outputs_obey_hardened_contract(self):
        for filename in ("train_v0.5.chatml.jsonl", "eval_v0.5.chatml.jsonl"):
            for line in (DATA / filename).read_text(encoding="utf-8").splitlines():
                chat = json.loads(line)
                model_input = json.loads(chat["messages"][1]["content"])
                validate_input(model_input)
                parsed, error = parse_output(chat["messages"][2]["content"], model_input["text"])
                self.assertIsNotNone(parsed, error)

    def test_training_config_matches_v04_except_artifact_paths(self):
        old = json.loads((ROOT / "training/feedback/config_v0.4.json").read_text(encoding="utf-8"))
        new = json.loads((ROOT / "training/feedback/config_v0.5.json").read_text(encoding="utf-8"))
        for key in set(old) - {"eval_file", "experiment_id", "output_dir", "source_dataset", "train_file"}:
            self.assertEqual(new[key], old[key], key)
        self.assertTrue(new["output_dir"].endswith("/feedback-verifier-v0.5"))
        self.assertEqual(new["seed"], 42)
        self.assertEqual(new["num_train_epochs"], 1)


if __name__ == "__main__":
    unittest.main()

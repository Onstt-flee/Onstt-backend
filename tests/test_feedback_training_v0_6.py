import hashlib
import json
from pathlib import Path
import unittest

from analyzer.feedback_contract import canonical_json, validate_input
from analyzer.feedback_two_stage_contract import (
    STAGE1_SYSTEM_PROMPT, STAGE2_SYSTEM_PROMPT, parse_stage1_output, parse_stage2_output,
)
from training.feedback.generate_v0_6_two_stage import build_examples, to_chat
from training.judgment.train_lora import load_chatml, load_config, validate_inputs


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "training/feedback/data"


class FeedbackTrainingV06Tests(unittest.TestCase):
    def test_stage_specific_dataset_is_deterministic_and_holdout_free(self):
        rows = [json.loads(line) for line in (DATA / "feedback_v0.6.two-stage.jsonl").read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((DATA / "feedback_v0.6.two-stage.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, build_examples())
        self.assertEqual(len(rows), 3571)
        self.assertEqual(manifest["task_counts"], {"feedback_stage1": 2322, "feedback_stage2": 1249})
        self.assertEqual(manifest["train_records"], 3207)
        self.assertEqual(manifest["eval_records"], 364)
        self.assertEqual(manifest["train_task_counts"], {"feedback_stage1": 2084, "feedback_stage2": 1123})
        self.assertEqual(manifest["eval_task_counts"], {"feedback_stage1": 238, "feedback_stage2": 126})
        self.assertTrue(all(not value["exact_input"] and not value["text"] for value in manifest["protected_overlap"].values()))
        self.assertFalse(manifest["holdout_used"])
        self.assertEqual(manifest["source_sha256"], hashlib.sha256((DATA / "feedback_v0.6.two-stage.jsonl").read_bytes()).hexdigest())

    def test_each_chat_example_uses_exact_stage_contract(self):
        for example in build_examples():
            validate_input(example["model_input"])
            chat = to_chat(example)
            self.assertEqual([message["role"] for message in chat["messages"]], ["system", "user", "assistant"])
            if example["task"] == "feedback_stage1":
                parsed, error = parse_stage1_output(chat["messages"][2]["content"])
            else:
                parsed, error = parse_stage2_output(
                    chat["messages"][2]["content"], example["model_input"]["text"],
                    example["stage1_audit"]["issue_codes"],
                )
            self.assertIsNotNone(parsed, f"{example['id']}: {error}")
            self.assertEqual(chat["messages"][2]["content"], canonical_json(example["expected"]))

    def test_training_config_keeps_v05_hyperparameters_and_new_paths(self):
        old = json.loads((ROOT / "training/feedback/config_v0.5.json").read_text(encoding="utf-8"))
        new = json.loads((ROOT / "training/feedback/config_v0.6.json").read_text(encoding="utf-8"))
        changed = {"eval_file", "experiment_id", "output_dir", "source_dataset", "train_file"}
        for key in set(old) - changed:
            self.assertEqual(new[key], old[key], key)
        self.assertTrue(new["output_dir"].endswith("/feedback-verifier-v0.6-two-stage"))
        self.assertEqual(new["seed"], 42)


    def test_shared_trainer_accepts_both_stage_contracts(self):
        config = load_config(ROOT / "training/feedback/config_v0.6.json")
        validation = validate_inputs(config)
        self.assertEqual(validation["train_count"], 3207)
        self.assertEqual(validation["eval_count"], 364)
        rows = load_chatml(DATA / "train_v0.6.two-stage.chatml.jsonl")
        prompts = {row["messages"][0]["content"] for row in rows}
        self.assertEqual(prompts, {STAGE1_SYSTEM_PROMPT, STAGE2_SYSTEM_PROMPT})


if __name__ == "__main__":
    unittest.main()

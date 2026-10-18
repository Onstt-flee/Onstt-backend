import hashlib
import json
from pathlib import Path
import unittest

from analyzer.feedback_contract import canonical_json, parse_output, validate_input
from evaluation.feedback.build_holdout_v0_5 import build_rows


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "evaluation/feedback"


class FeedbackHoldoutV05Tests(unittest.TestCase):
    def test_sealed_dataset_is_deterministic_balanced_and_consumed_once_per_candidate(self):
        dataset = HERE / "holdout_v0.5.jsonl"
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((HERE / "holdout_v0.5.manifest.json").read_text(encoding="utf-8"))
        protocol = json.loads((HERE / "holdout_v0.5.protocol.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, build_rows())
        self.assertEqual(len(rows), 120)
        self.assertEqual(manifest["verdict_counts"], {"agree": 50, "disagree": 60, "unreviewable": 10})
        self.assertTrue(all(not item["exact_input"] and not item["text"] for item in manifest["overlap"].values()))
        self.assertEqual(hashlib.sha256(dataset.read_bytes()).hexdigest(), manifest["sha256"])
        self.assertTrue(protocol["ready_for_inference"])
        self.assertTrue(protocol["consumed"])
        self.assertTrue(protocol["single_use"])
        self.assertEqual(protocol["adapter_sha256"], "2af21a821c1f3ad816fc28035479d3525f7aa22eac70c028b1e8a752cdebc78a")
        self.assertEqual(protocol["training_run"]["steps"], 234)
        self.assertEqual(protocol["official_run"]["model_inference_count"], 2)
        self.assertEqual(protocol["official_run"]["decision"], "failed_required_thresholds")
        self.assertEqual(
            protocol["official_run"]["failed_thresholds"],
            ["contract_success_rate", "accepted_correction_rate"],
        )
        self.assertEqual(
            [(item["role"], item["model"], item["max_runs"]) for item in protocol["planned_runs"]],
            [
                ("baseline", "feedback-qwen3-8b-base", 1),
                ("lora", "feedback-qwen3-8b-v04", 1),
            ],
        )

    def test_expected_outputs_obey_hardened_contract(self):
        for row in build_rows():
            model_input = {"text": row["text"], "context": row["context"], "learner_level": row["learner_level"], "judgment": row["candidate_judgment"]}
            validate_input(model_input)
            parsed, error = parse_output(canonical_json(row["expected"]), row["text"])
            self.assertIsNotNone(parsed, error)


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
from pathlib import Path
import unittest

from evaluation.feedback.build_existence_particle_diagnostic_v0_2 import build_rows


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "evaluation/feedback"


class FeedbackExistenceParticleDiagnosticV02Tests(unittest.TestCase):
    def test_unseen_dataset_is_deterministic_balanced_and_isolated(self):
        dataset = HERE / "existence_particle_diagnostic_v0.2.jsonl"
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((HERE / "existence_particle_diagnostic_v0.2.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, build_rows())
        self.assertEqual(len(rows), 40)
        self.assertEqual(manifest["verdict_counts"], {"agree": 20, "disagree": 20})
        self.assertTrue(all(not value["exact_input"] and not value["text"] for value in manifest["overlap"].values()))
        self.assertEqual(hashlib.sha256(dataset.read_bytes()).hexdigest(), manifest["sha256"])

    def test_protocol_is_consumed_after_single_hardened_prompt_run(self):
        protocol = json.loads((HERE / "existence_particle_diagnostic_v0.2.protocol.json").read_text(encoding="utf-8"))
        self.assertTrue(protocol["single_use"])
        self.assertTrue(protocol["consumed"])
        self.assertFalse(protocol["ready_for_inference"])
        self.assertEqual(protocol["purpose"], "hardened_prompt_regression_diagnostic_only")
        self.assertEqual(protocol["result_sha256"], "6317612d05720d5d6de25ec8febf862571156fbfd2e75a09ef7bd4eed90c012a")

    def test_recorded_result_blocks_operational_activation(self):
        result = json.loads((HERE / "existence_particle_diagnostic_v0.2.result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["records"], 40)
        self.assertEqual(result["contract_success"], 33)
        self.assertEqual(result["semantic_contract_rejections"], 7)
        self.assertEqual(result["false_disagreement_rate"], 0.0)
        self.assertFalse(result["operational_activation_allowed"])
        self.assertEqual(result["next_action"], "train_feedback_v0.4_before_new_unseen_evaluation")



if __name__ == "__main__":
    unittest.main()

import hashlib
import json
from pathlib import Path
import unittest

from evaluation.feedback.build_existence_particle_diagnostic_v0_1 import build_rows


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "evaluation/feedback"


class FeedbackExistenceParticleDiagnosticTests(unittest.TestCase):
    def test_dataset_is_deterministic_balanced_and_nonoverlapping(self):
        dataset = HERE / "existence_particle_diagnostic_v0.1.jsonl"
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((HERE / "existence_particle_diagnostic_v0.1.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, build_rows())
        self.assertEqual(len(rows), 40)
        self.assertEqual(manifest["verdict_counts"], {"agree": 20, "disagree": 20})
        self.assertTrue(all(not value["exact_input"] and not value["text"] for value in manifest["overlap"].values()))
        self.assertEqual(hashlib.sha256(dataset.read_bytes()).hexdigest(), manifest["sha256"])
        self.assertFalse(manifest["human_reviewed"])
        self.assertFalse(manifest["expert_reviewed"])

    def test_protocol_is_single_use_diagnostic_not_model_selection(self):
        protocol = json.loads((HERE / "existence_particle_diagnostic_v0.1.protocol.json").read_text(encoding="utf-8"))
        self.assertTrue(protocol["single_use"])
        self.assertTrue(protocol["consumed"])
        self.assertEqual(protocol["purpose"], "post_selection_regression_diagnostic_only")

    def test_recorded_result_fails_activation_and_records_hardened_contract(self):
        result = json.loads((HERE / "existence_particle_diagnostic_v0.1.result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["decision"], "failed_boundary_diagnostic")
        self.assertFalse(result["operational_activation_allowed"])
        self.assertEqual(result["original_parse"]["contract_success"], 40)
        self.assertEqual(result["hardened_parse"]["contract_success"], 20)
        self.assertEqual(len(result["failure_ids"]["semantic_contract_conflicts"]), 20)


if __name__ == "__main__":
    unittest.main()

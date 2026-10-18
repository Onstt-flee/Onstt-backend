import hashlib
import json
from pathlib import Path
import unittest

from evaluation.feedback.build_particle_risk_adversarial_v0_1 import build_rows
from evaluation.feedback.evaluate_particle_risk_adversarial import evaluate


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "evaluation/feedback"


class FeedbackParticleRiskAdversarialTests(unittest.TestCase):
    def test_dataset_is_deterministic_balanced_and_nonoverlapping(self):
        dataset = HERE / "particle_risk_adversarial_v0.1.jsonl"
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
        manifest = json.loads((HERE / "particle_risk_adversarial_v0.1.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, build_rows())
        self.assertEqual(len(rows), 80)
        self.assertEqual(len({row["id"] for row in rows}), 80)
        self.assertEqual(manifest["expected_signal_rows"], 30)
        self.assertEqual(manifest["expected_no_signal_rows"], 50)
        self.assertTrue(all(value == 0 for value in manifest["exact_text_overlap"].values()))
        self.assertEqual(hashlib.sha256(dataset.read_bytes()).hexdigest(), manifest["sha256"])
        self.assertFalse(manifest["human_reviewed"])
        self.assertFalse(manifest["expert_reviewed"])

    def test_protocol_disclaims_holdout_and_model_selection(self):
        protocol = json.loads((HERE / "particle_risk_adversarial_v0.1.protocol.json").read_text(encoding="utf-8"))
        self.assertEqual(protocol["purpose"], "development_adversarial_not_holdout")
        self.assertTrue(protocol["built_after_gate"])
        self.assertFalse(protocol["independent_model_selection_evidence"])

    def test_recorded_result_matches_evaluator_and_contains_no_sentences(self):
        rows = [json.loads(line) for line in (HERE / "particle_risk_adversarial_v0.1.jsonl").read_text(encoding="utf-8").splitlines() if line]
        protocol = json.loads((HERE / "particle_risk_adversarial_v0.1.protocol.json").read_text(encoding="utf-8"))
        recorded = json.loads((HERE / "particle_risk_adversarial_v0.1.result.json").read_text(encoding="utf-8"))
        expected = evaluate(rows, protocol["thresholds"])
        for key in ("confusion", "metrics", "checks", "decision", "strata"):
            self.assertEqual(recorded[key], expected[key])
        self.assertTrue(recorded["content_free"])
        serialized = json.dumps(recorded, ensure_ascii=False)
        self.assertNotIn("市民会館", serialized)
        self.assertFalse(recorded["operational_activation_allowed"])


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FeedbackSyntheticShadowResultTests(unittest.TestCase):
    def test_recorded_result_preserves_operational_only_boundary(self):
        result = json.loads(
            (ROOT / "evaluation/feedback/shadow_v0.1.result.json").read_text(encoding="utf-8")
        )
        self.assertEqual(result["input_count"], 200)
        self.assertFalse(result["quality_claim_allowed"])
        self.assertEqual(result["judgment"]["contract_valid"], 200)
        self.assertEqual(result["feedback"]["queued"], 200)
        self.assertEqual(result["feedback"]["job_status_counts"], {"succeeded": 200})
        self.assertEqual(result["feedback"]["audit_count"], 200)
        self.assertTrue(result["integrity"]["judgments_unchanged"])
        self.assertEqual(result["integrity"]["duplicate_job_count"], 0)
        self.assertEqual(result["integrity"]["duplicate_audit_count"], 0)
        self.assertTrue(result["integrity"]["feedback_input_excludes_runtime_and_model_identity"])


if __name__ == "__main__":
    unittest.main()

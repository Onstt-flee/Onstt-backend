import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "evaluation" / "feedback" / "actual_shadow_v0.1.result.json"


class FeedbackActualShadowResultTests(unittest.TestCase):
    def test_recorded_result_is_operational_only_and_passes_gate(self):
        result = json.loads(RESULT.read_text(encoding="utf-8"))

        self.assertEqual(result["input_count"], 200)
        self.assertFalse(result["quality_claim_allowed"])

        judgment = result["judgment"]
        self.assertEqual(judgment["contract_valid"], 198)
        self.assertEqual(judgment["contract_invalid"], 2)
        self.assertEqual(judgment["retry_attempts"], 5)
        self.assertEqual(judgment["retry_recoveries"], 3)
        self.assertEqual(judgment["retry_failures"], 2)
        self.assertLessEqual(judgment["retry_rate"], 0.05)
        self.assertLessEqual(judgment["latency_ms"]["p95"], 2500)

        final = result["post_run_finalization"]
        self.assertEqual(final["job_status_counts"], {
            "failed": 1,
            "succeeded": 197,
        })
        self.assertEqual(final["audit_count"], 197)
        self.assertEqual(final["failed_job_attempts"], 3)
        self.assertTrue(final["failed_job_was_safely_isolated"])

        self.assertTrue(result["integrity"]["judgments_unchanged"])
        self.assertEqual(result["integrity"]["duplicate_job_count"], 0)
        self.assertEqual(result["integrity"]["duplicate_audit_count"], 0)
        self.assertTrue(result["operational_acceptance"]["passed"])
        self.assertFalse(
            result["operational_acceptance"]["learner_exposure_approved"]
        )


if __name__ == "__main__":
    unittest.main()

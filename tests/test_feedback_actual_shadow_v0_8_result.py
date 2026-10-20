import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "evaluation" / "feedback" / "actual_shadow_v0.1.v08.result.json"
DIAGNOSTIC = ROOT / "evaluation" / "feedback" / "actual_shadow_v0.1.v08.failure-diagnostic.json"


class FeedbackActualShadowV08ResultTests(unittest.TestCase):
    def test_recorded_result_fails_only_feedback_coverage_gate(self):
        result = json.loads(RESULT.read_text(encoding="utf-8"))
        self.assertEqual(result["input_count"], 200)
        self.assertFalse(result["quality_claim_allowed"])
        self.assertEqual(result["judgment"]["contract_valid"], 198)
        self.assertEqual(result["judgment"]["contract_invalid"], 2)
        self.assertEqual(result["feedback"]["queued"], 198)
        final = result["post_run_finalization"]
        self.assertEqual(final["job_status_counts"], {"failed": 3, "succeeded": 195})
        self.assertEqual(final["audit_count"], 195)
        self.assertEqual(final["audit_coverage"], 0.984848)
        self.assertEqual(final["failed_job_attempts"], [3, 3, 3])
        self.assertTrue(final["failed_jobs_were_safely_isolated"])
        checks = result["operational_acceptance"]["checks"]
        self.assertFalse(checks["feedback_audit_coverage_at_least_99_percent"])
        self.assertTrue(all(value for key, value in checks.items() if key != "feedback_audit_coverage_at_least_99_percent"))
        self.assertFalse(result["operational_acceptance"]["passed"])
        self.assertFalse(result["operational_acceptance"]["learner_exposure_approved"])

    def test_tracked_result_contains_no_source_text_or_user_identity(self):
        tracked = RESULT.read_text(encoding="utf-8")
        self.assertNotIn("stt_text", tracked)
        self.assertNotIn("user_id", tracked)
        self.assertNotIn("corrected_text", tracked)

    def test_failure_diagnostic_is_stage2_only_and_content_free(self):
        result = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
        self.assertEqual(result["failed_job_count"], 3)
        self.assertEqual(result["outcome_counts"], {"contract_stage2": 3})
        self.assertTrue(result["database_unchanged"])
        self.assertFalse(result["quality_claim_allowed"])
        tracked = DIAGNOSTIC.read_text(encoding="utf-8")
        self.assertNotIn("stt_text", tracked)
        self.assertNotIn("user_id", tracked)
        self.assertNotIn("corrected_text", tracked)


if __name__ == "__main__":
    unittest.main()

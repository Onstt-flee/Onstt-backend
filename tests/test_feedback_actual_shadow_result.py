import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "evaluation" / "feedback" / "actual_shadow_v0.1.result.json"
ADMIN_RESULT = ROOT / "evaluation" / "feedback" / "actual_shadow_v0.1.admin.result.json"


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

    def test_recorded_admin_projection_is_read_only_and_content_free(self):
        result = json.loads(ADMIN_RESULT.read_text(encoding="utf-8"))

        self.assertEqual(
            result["scope"], "actual_stored_stt_operational_shadow_only"
        )
        self.assertFalse(result["quality_claim_allowed"])
        self.assertTrue(result["database_unchanged"])
        self.assertEqual(result["health"]["job_counts"], {
            "pending": 0, "running": 0, "succeeded": 197, "failed": 1,
        })
        self.assertEqual(result["health"]["audit_count"], 197)
        projections = result["admin_projections"]
        self.assertFalse(projections["list_contains_content_keys"])
        self.assertEqual(projections["detail_resolvable_count"], 197)
        self.assertEqual(projections["succeeded_retryable_count"], 0)
        self.assertEqual(projections["issue_kind_counts"], {
            "audit_failure": 1, "model_disagreement": 14,
        })
        self.assertEqual(projections["failure_category_counts"], {"contract": 1})


if __name__ == "__main__":
    unittest.main()

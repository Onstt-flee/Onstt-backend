import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

ACTUAL_RESULT = (
    ROOT / "evaluation" / "feedback" / "actual_shadow_v0.1.admin-http.result.json"
)

class FeedbackAdminHttpResultTests(unittest.TestCase):
    def test_recorded_http_result_is_fail_closed_and_content_free(self):
        result = json.loads(
            (ROOT / "evaluation/feedback/shadow_v0.1.admin-http.result.json")
            .read_text(encoding="utf-8")
        )
        self.assertFalse(result["quality_claim_allowed"])
        self.assertTrue(result["database_unchanged"])
        self.assertEqual(result["http"]["unauthenticated_audit_list_status"], 401)
        self.assertEqual(result["http"]["succeeded_job_retry_status"], 409)
        self.assertEqual(result["http"]["model_stopped_readiness_status"], 503)
        self.assertEqual(result["http"]["model_stopped_readiness_reason"], "model_unavailable")
        self.assertFalse(result["projections"]["audit_list_contains_content_keys"])
        self.assertFalse(result["projections"]["health_contains_request_content"])
        self.assertFalse(result["projections"]["detail_contains_source_text"])

    def test_actual_http_result_covers_swagger_auth_and_fail_closed_states(self):
        result = json.loads(ACTUAL_RESULT.read_text(encoding="utf-8"))

        self.assertEqual(
            result["scope"], "actual_stored_stt_operational_shadow_only"
        )
        self.assertFalse(result["quality_claim_allowed"])
        self.assertTrue(result["database_unchanged"])
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["http"], {
            "docs_status": 200,
            "openapi_status": 200,
            "unauthenticated_audit_list_status": 401,
            "authenticated_health_status": 200,
            "authenticated_audit_list_status": 200,
            "authenticated_issue_list_status": 200,
            "authenticated_detail_status": 200,
            "succeeded_job_retry_status": 409,
            "model_stopped_readiness_status": 503,
            "model_stopped_readiness_reason": "model_unavailable",
            "disabled_health_status": 503,
        })
        projections = result["projections"]
        self.assertEqual(projections["audit_list_count"], 197)
        self.assertEqual(projections["issue_group_count"], 8)
        self.assertEqual(
            projections["issue_status_counts"], {"emerging": 6, "recurrent": 2}
        )
        self.assertFalse(projections["audit_list_contains_content_keys"])
        self.assertFalse(projections["detail_contains_source_text"])


if __name__ == "__main__":
    unittest.main()

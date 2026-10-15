import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


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


if __name__ == "__main__":
    unittest.main()

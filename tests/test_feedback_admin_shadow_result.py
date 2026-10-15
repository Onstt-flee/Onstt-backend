import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FeedbackAdminShadowResultTests(unittest.TestCase):
    def test_recorded_projection_is_content_free_and_read_only(self):
        result = json.loads(
            (ROOT / "evaluation/feedback/shadow_v0.1.admin.result.json")
            .read_text(encoding="utf-8")
        )
        self.assertFalse(result["quality_claim_allowed"])
        self.assertTrue(result["database_unchanged"])
        self.assertEqual(result["health"]["job_counts"], {
            "pending": 0, "running": 0, "succeeded": 200, "failed": 0,
        })
        self.assertEqual(result["health"]["audit_count"], 200)
        self.assertFalse(result["health"]["contains_request_content"])
        self.assertFalse(result["admin_projections"]["list_contains_content_keys"])
        self.assertEqual(result["admin_projections"]["detail_resolvable_count"], 200)
        self.assertEqual(result["admin_projections"]["succeeded_retryable_count"], 0)
        self.assertEqual(result["admin_projections"]["issue_counts"], {"false_negative": 1})
        self.assertEqual(result["admin_projections"]["issue_status_counts"], {"emerging": 1})


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FeedbackWorkerRecoveryResultTests(unittest.TestCase):
    def test_recorded_drill_recovers_and_isolates_without_mutation(self):
        result = json.loads(
            (ROOT / "evaluation/feedback/shadow_v0.1.worker-recovery.result.json")
            .read_text(encoding="utf-8")
        )
        self.assertFalse(result["quality_claim_allowed"])
        self.assertFalse(result["contains_request_content"])
        self.assertTrue(result["judgments_unchanged"])
        self.assertEqual(result["expired_lease"], {
            "status": "succeeded", "attempts": 1, "audit_count": 1,
        })
        self.assertEqual(result["retry_recovery"], {
            "status": "succeeded", "attempts": 2, "audit_count": 1,
        })
        self.assertEqual(result["terminal_failure"], {
            "status": "failed", "attempts": 3,
            "error_category": "transport", "audit_count": 0,
        })
        self.assertEqual(result["duplicate_drill_audit_count"], 0)
        self.assertEqual(result["final"]["job_count"] - result["baseline"]["job_count"], 3)
        self.assertEqual(result["final"]["audit_count"] - result["baseline"]["audit_count"], 2)


if __name__ == "__main__":
    unittest.main()

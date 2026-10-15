import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FeedbackWorkerProcessCrashResultTests(unittest.TestCase):
    def test_recorded_process_crash_is_recovered_exactly_once(self):
        result = json.loads(
            (ROOT / "evaluation/feedback/shadow_v0.1.worker-process-crash.result.json")
            .read_text(encoding="utf-8")
        )
        self.assertFalse(result["quality_claim_allowed"])
        self.assertFalse(result["contains_request_content"])
        self.assertTrue(result["source_database_unchanged"])
        self.assertTrue(result["judgments_unchanged"])
        self.assertTrue(result["first_worker"]["terminated_by_signal"])
        self.assertEqual(result["first_worker"]["job_status_after_crash"], "running")
        self.assertEqual(result["first_worker"]["attempts_after_crash"], 1)
        self.assertTrue(result["first_worker"]["lease_present_after_crash"])
        self.assertEqual(result["restarted_worker"]["final_job_status"], "succeeded")
        self.assertEqual(result["restarted_worker"]["final_attempts"], 2)
        self.assertEqual(result["stub_request_count"], 2)
        self.assertEqual(result["recovery_audit_count"], 1)
        self.assertEqual(result["duplicate_recovery_audit_count"], 0)
        self.assertEqual(result["audit_count_delta"], 1)


if __name__ == "__main__":
    unittest.main()

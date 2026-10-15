import unittest

from scripts.audit_feedback_v0_3_checkpoint import audit


class FeedbackCheckpointAuditTests(unittest.TestCase):
    def test_current_checkpoint_is_classified_unstaged_and_safe(self):
        result = audit(require_external=False)
        self.assertTrue(result["passed"], result["errors"])
        self.assertFalse(result["unknown_paths"])
        self.assertFalse(result["staged_paths"])
        self.assertFalse(result["prohibited_checkpoint_paths"])
        self.assertFalse(result["oversized_checkpoint_files"])
        self.assertFalse(result["secret_pattern_matches"])
        self.assertGreaterEqual(result["checkpoint_path_count"], 0)
        self.assertTrue(set(result["deferred_pi_paths"]).issubset({
            "deployment/feedback-staging/finalize-runtime-pairs.sh",
            "deployment/judgment-pi5/run-feedback-pairs-50.sh",
            "evaluation/feedback/RUNTIME_PAIR_INTAKE.md",
            "tests/test_pi5_deployment_templates.py",
        }))


if __name__ == "__main__":
    unittest.main()

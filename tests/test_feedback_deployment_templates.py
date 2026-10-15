import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deployment/feedback-staging"
ADAPTER_SHA = "3bcbc80d1559dacf60a84c708a8ab4c51ee4bd33532acf2ab134394aa2dcd1ad"


class FeedbackDeploymentTemplateTests(unittest.TestCase):
    def test_environment_is_disabled_and_pins_v03(self):
        content = (DEPLOY / "feedback-staging.env.example").read_text()
        self.assertIn("FEEDBACK_AUDIT_ENABLED=false", content)
        self.assertIn("FEEDBACK_MODEL=feedback-qwen3-8b-v03", content)
        self.assertIn("FEEDBACK_ADAPTER=feedback-verifier-v0.3", content)
        self.assertIn(f"FEEDBACK_MODEL_SHA256={ADAPTER_SHA}", content)
        self.assertIn("FEEDBACK_MAX_CONCURRENCY=1", content)

    def test_vllm_is_loopback_single_concurrency_and_pins_v03(self):
        content = (DEPLOY / "feedback-vllm.service").read_text()
        self.assertIn("VLLM_USE_FLASHINFER_SAMPLER=0", content)
        self.assertIn("--host 127.0.0.1", content)
        self.assertIn("--port 1235", content)
        self.assertIn("--max-num-seqs 1", content)
        self.assertIn("--reasoning-parser qwen3", content)
        self.assertIn("feedback-qwen3-8b-v03=", content)
        self.assertIn("/feedback-verifier-v0.3", content)
        self.assertNotIn("feedback-qwen3-8b-v01", content)

    def test_readme_limits_candidate_to_gpu_shadow(self):
        content = " ".join((DEPLOY / "README.md").read_text().split())
        self.assertIn("GPU-judgment shadow", content)
        self.assertIn("no learner exposure", content)
        self.assertIn("Pi intake is deferred", content)


if __name__ == "__main__":
    unittest.main()

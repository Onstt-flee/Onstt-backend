"""Static safety contract for Raspberry Pi deployment templates."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deployment" / "judgment-pi5"


class Pi5DeploymentTemplateTests(unittest.TestCase):
    def test_llama_server_is_loopback_single_parallel_q4_lora(self):
        script = (DEPLOY / "run-llama-server.sh").read_text()
        for literal in (
            "--host 127.0.0.1", "--port 1234", "--parallel 1",
            "--ctx-size 2048", "--threads 4", "--lora",
        ):
            self.assertIn(literal, script)
        self.assertNotIn("--host 0.0.0.0", script)

    def test_pi_api_is_loopback_single_worker_and_uses_separate_db(self):
        script = (DEPLOY / "run-pi-api.sh").read_text()
        self.assertIn("STT_DATABASE_URL", script)
        self.assertIn("--host 127.0.0.1", script)
        self.assertIn("--workers 1", script)
        unit = (DEPLOY / "user/stt-api-pi5.service").read_text()
        self.assertIn("StateDirectory=stt-api-pi5", unit)
        self.assertIn("Wants=judgment-pi5-llama.service", unit)

    def test_examples_are_placeholder_only_and_gpu_remains_default(self):
        pi = (DEPLOY / "pi5.env.example").read_text()
        q5 = (DEPLOY / "pi5-q5-candidate.env.example").read_text()
        gpu = (DEPLOY / "gpu-sync.env.example").read_text()
        self.assertIn("EDGE_MODE=true", pi)
        self.assertIn("EDGE_QUANTIZATION=Q4_K_M", pi)
        self.assertIn("EDGE_QUANTIZATION=Q5_K_M", q5)
        self.assertIn("Qwen3-4B-Instruct-2507-Q5_K_M.gguf", q5)
        self.assertIn("EDGE_SYNC_ENABLED=true", gpu)
        self.assertIn("EDGE_MODE=false", gpu)
        self.assertIn("CHANGE_ME", pi + q5 + gpu)
        self.assertNotIn("BEGIN PRIVATE KEY", pi + q5 + gpu)

    def test_model_and_api_units_are_manual_but_sync_timer_is_explicit(self):
        model = (DEPLOY / "user/judgment-pi5-llama.service").read_text()
        api = (DEPLOY / "user/stt-api-pi5.service").read_text()
        timer = (DEPLOY / "user/stt-api-pi5-sync.timer").read_text()
        self.assertNotIn("\n[Install]\n", model)
        self.assertNotIn("\n[Install]\n", api)
        self.assertIn("\n[Install]\n", timer)
        installer = (DEPLOY / "install-user-services.sh").read_text()
        self.assertNotIn("enable --now", installer)
        self.assertNotIn("systemctl --user start", installer)

    def test_regression_and_benchmark_outputs_follow_active_quantization(self):
        for name in ("run-dev72-regression.sh", "run-benchmark-50.sh"):
            script = (DEPLOY / name).read_text()
            self.assertIn('quantization="${EDGE_QUANTIZATION:-Q4_K_M}"', script)
            self.assertIn('Q5_K_M) quantization_slug="q5"', script)
            self.assertIn("${quantization_slug}", script)


if __name__ == "__main__":
    unittest.main()

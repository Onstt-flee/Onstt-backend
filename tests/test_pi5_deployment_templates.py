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
        gpu = (DEPLOY / "gpu-sync.env.example").read_text()
        self.assertIn("EDGE_MODE=true", pi)
        self.assertIn("EDGE_SYNC_ENABLED=true", gpu)
        self.assertIn("EDGE_MODE=false", gpu)
        self.assertIn("CHANGE_ME", pi + gpu)
        self.assertNotIn("BEGIN PRIVATE KEY", pi + gpu)

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


if __name__ == "__main__":
    unittest.main()

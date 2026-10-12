"""Static safety-contract tests for judgment staging deployment templates."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENT = ROOT / "deployment" / "judgment-staging"


class JudgmentDeploymentTemplateTests(unittest.TestCase):
    def test_runtime_policy_allows_only_d_and_weights_are_ignored(self):
        policy = (DEPLOYMENT / "MODEL_POLICY.md").read_text()
        self.assertIn("Only the following model is permitted", policy)
        self.assertIn("alias: `judgment-v02d`", policy)
        self.assertIn("v0.2-A/B/C/E/F/G/H/I/J", policy)

        ignore = (ROOT / ".gitignore").read_text()
        for pattern in ("*.safetensors", "*.gguf", "*.ckpt", "*.pt", "*.pth"):
            self.assertIn(pattern, ignore)

        runtime_files = (
            ROOT / "analyzer/judgment_service.py",
            DEPLOYMENT / "judgment-staging.env.example",
            DEPLOYMENT / "judgment-vllm.service",
            DEPLOYMENT / "user/judgment-vllm.service",
        )
        for path in runtime_files:
            content = path.read_text()
            with self.subTest(path=path):
                self.assertIn("judgment-v02d", content)
                forbidden_aliases = (
                    "judgment-v02e",
                    "judgment-v02f",
                    "judgment-v02i",
                    "judgment-v02j",
                )
                for forbidden in forbidden_aliases:
                    self.assertNotIn(forbidden, content)

    def test_checked_in_environment_is_disabled_and_content_free(self):
        content = (DEPLOYMENT / "judgment-staging.env.example").read_text()
        self.assertIn("JUDGMENT_ENABLED=false", content)
        self.assertIn("JUDGMENT_MODEL=judgment-v02d", content)
        self.assertIn("JUDGMENT_MAX_CONCURRENCY=2", content)
        self.assertIn("JUDGMENT_SHADOW_QUEUE_MAX_SIZE=64", content)
        self.assertIn("JUDGMENT_SHADOW_ITEM_TTL_SECONDS=30", content)
        self.assertIn("JUDGMENT_SHADOW_ADMISSION_RPS=1", content)
        self.assertIn("JUDGMENT_SHADOW_ADMISSION_BURST=1", content)
        for forbidden in ("PASSWORD=", "TOKEN=", "SECRET=", "API_KEY="):
            self.assertNotIn(forbidden, content)

    def test_api_unit_is_single_worker_fail_closed_and_isolated(self):
        content = (DEPLOYMENT / "stt-api-judgment-staging.service").read_text()
        self.assertIn("--workers 1", content)
        self.assertNotIn("--workers 2", content)
        self.assertIn("scripts.check_judgment_staging", content)
        self.assertIn("--skip-live", content)
        self.assertIn("WorkingDirectory=/var/lib/stt-api-judgment-staging", content)
        self.assertIn("ReadWritePaths=/var/lib/stt-api-judgment-staging", content)
        self.assertIn("--host 127.0.0.1", content)
        self.assertIn("Wants=network-online.target judgment-vllm.service", content)
        self.assertNotIn("Requires=judgment-vllm.service", content)
        self.assertIn("StateDirectory=stt-api-judgment-staging", content)

    def test_model_unit_locks_alias_sampling_and_loopback(self):
        content = (DEPLOYMENT / "judgment-vllm.service").read_text()
        self.assertIn("VLLM_USE_FLASHINFER_SAMPLER=0", content)
        self.assertIn("--generation-config vllm", content)
        self.assertIn("--host 127.0.0.1", content)
        self.assertIn("--port 1234", content)
        self.assertIn("--lora-modules judgment-v02d=", content)
        self.assertIn("CacheDirectory=stt-api-judgment-vllm", content)

    def test_user_units_need_no_sudo_and_cannot_be_enabled(self):
        model = (DEPLOYMENT / "user" / "judgment-vllm.service").read_text()
        api = (DEPLOYMENT / "user" / "stt-api-judgment-staging.service").read_text()
        for content in (model, api):
            self.assertNotIn("User=", content)
            self.assertNotIn("Group=", content)
            self.assertNotIn("[Install]", content.replace("# Deliberately no [Install]", ""))
            self.assertIn("--host 127.0.0.1", content)
        self.assertIn("--workers 1", api)
        self.assertIn("%S/stt-api-judgment-staging/stt_data.db", api)
        self.assertNotIn("Requires=judgment-vllm.service", api)

    def test_user_installer_is_non_destructive_and_does_not_start(self):
        content = (ROOT / "scripts" / "install_judgment_user_services.sh").read_text()
        self.assertIn("systemctl --user daemon-reload", content)
        self.assertNotIn("systemctl --user start", content)
        self.assertNotIn("systemctl --user enable", content)
        self.assertNotIn("sudo ", content)
        self.assertIn('if [[ ! -e "$ENV_FILE" ]]', content)
        self.assertIn('if [[ ! -e "$DATABASE_FILE" ]]', content)

    def test_user_preflight_wrapper_loads_private_environment(self):
        content = (ROOT / "scripts" / "check_judgment_user_staging.sh").read_text()
        self.assertIn('source "$ENV_FILE"', content)
        self.assertIn("scripts.check_judgment_staging", content)
        self.assertIn('"$@"', content)
        self.assertNotIn("sudo ", content)


if __name__ == "__main__":
    unittest.main()

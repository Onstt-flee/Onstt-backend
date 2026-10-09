"""Tests for the fail-closed no-sudo staging lifecycle manager."""

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.manage_judgment_user_staging import (
    API_SERVICE,
    MODEL_HEALTH,
    MODEL_LIST,
    MODEL_SERVICE,
    UserStagingPaths,
    environment_enabled,
    environment_flag,
    set_environment_enabled,
    start,
    stop,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class _Harness:
    def __init__(self):
        self.active = set()
        self.calls = []

    def run(self, command, check, capture_output, text):
        del capture_output, text
        self.calls.append(command)
        action = command[2]
        service = command[3] if len(command) > 3 else None
        if action == "is-active":
            state = "active" if service in self.active else "inactive"
            return subprocess.CompletedProcess(command, 0 if state == "active" else 3, state + "\n", "")
        if action == "start":
            self.active.add(service)
        elif action == "stop":
            self.active.discard(service)
        return subprocess.CompletedProcess(command, 0, "", "")

    def open(self, url, timeout):
        del timeout
        url = getattr(url, "full_url", url)
        if url == MODEL_HEALTH:
            return _Response(None)
        if url == MODEL_LIST:
            return _Response({"data": [{"id": "judgment-v02d"}]})
        if url.endswith("/health"):
            return _Response({"status": "ok"})
        if url.endswith("/ready/judgment"):
            return _Response({"ready": True})
        if url.endswith("/openapi.json"):
            return _Response({"paths": {
                "/health/judgment": {},
                "/ready/judgment": {},
                "/utterances/{utterance_id}/judgment": {},
                "/utterances/{utterance_id}/judgments": {},
            }})
        raise AssertionError(url)


class JudgmentUserStagingManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.environment = root / "judgment.env"
        self.environment.write_text("JUDGMENT_ENABLED=false\nJUDGMENT_SHADOW_ENABLED=false\nJUDGMENT_MODEL=judgment-v02d\n")
        self.environment.chmod(0o600)
        self.database = root / "staging.db"
        self.database.write_bytes(b"sqlite-placeholder")
        self.paths = UserStagingPaths(self.environment, self.database)

    def tearDown(self):
        self.temp.cleanup()

    def test_atomic_toggle_preserves_private_mode(self):
        self.assertFalse(environment_enabled(self.environment))
        set_environment_enabled(self.environment, True)
        self.assertTrue(environment_enabled(self.environment))
        self.assertEqual(stat.S_IMODE(self.environment.stat().st_mode), 0o600)
        set_environment_enabled(self.environment, False)
        self.assertFalse(environment_enabled(self.environment))

    def test_rejects_insecure_duplicate_and_symlink_environment(self):
        self.environment.chmod(0o644)
        with self.assertRaises(RuntimeError):
            environment_enabled(self.environment)
        self.environment.chmod(0o600)
        self.environment.write_text("JUDGMENT_ENABLED=false\nJUDGMENT_ENABLED=true\n")
        with self.assertRaises(RuntimeError):
            environment_enabled(self.environment)
        link = self.environment.with_name("link.env")
        link.symlink_to(self.environment)
        with self.assertRaises(RuntimeError):
            environment_enabled(link)

    def test_start_orders_services_and_enables_only_after_guards(self):
        harness = _Harness()
        result = start(self.paths, timeout=1, runner=harness.run, opener=harness.open)
        self.assertTrue(result["environment_enabled"])
        self.assertEqual(result["model_service"], "active")
        self.assertEqual(result["api_service"], "active")
        self.assertTrue(result["live_preflight_passed"])
        self.assertFalse(result["shadow_enabled"])
        starts = [call[-1] for call in harness.calls if call[2] == "start"]
        self.assertEqual(starts, [MODEL_SERVICE, API_SERVICE])

    def test_explicit_shadow_start_sets_shadow_flag(self):
        harness = _Harness()
        result = start(
            self.paths, timeout=1, enable_shadow=True,
            runner=harness.run, opener=harness.open,
        )
        self.assertTrue(result["shadow_enabled"])
        self.assertTrue(environment_flag(self.environment, "JUDGMENT_SHADOW_ENABLED"))
        stop(self.paths, runner=harness.run)
        self.assertFalse(environment_flag(self.environment, "JUDGMENT_SHADOW_ENABLED"))

    def test_start_failure_rolls_back_services_and_environment(self):
        harness = _Harness()

        def unavailable(url, timeout):
            del url, timeout
            raise OSError("unavailable")

        with self.assertRaises(TimeoutError):
            start(self.paths, timeout=0.01, runner=harness.run, opener=unavailable)
        self.assertFalse(environment_enabled(self.environment))
        self.assertEqual(harness.active, set())

    def test_keyboard_interrupt_rolls_back_services_and_environment(self):
        harness = _Harness()

        def interrupted(url, timeout):
            del url, timeout
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            start(
                self.paths,
                timeout=1,
                enable_shadow=True,
                runner=harness.run,
                opener=interrupted,
            )
        self.assertFalse(environment_enabled(self.environment))
        self.assertFalse(environment_flag(self.environment, "JUDGMENT_SHADOW_ENABLED"))
        self.assertEqual(harness.active, set())

    def test_stop_orders_api_before_model_and_disables(self):
        harness = _Harness()
        harness.active.update({MODEL_SERVICE, API_SERVICE})
        set_environment_enabled(self.environment, True)
        result = stop(self.paths, runner=harness.run)
        stops = [call[-1] for call in harness.calls if call[2] == "stop"]
        self.assertEqual(stops, [API_SERVICE, MODEL_SERVICE])
        self.assertFalse(result["environment_enabled"])
        self.assertEqual(result["model_service"], "inactive")
        self.assertEqual(result["api_service"], "inactive")


if __name__ == "__main__":
    unittest.main()

"""Tests for the read-only judgment staging preflight checker."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.check_judgment_staging import (
    DEFAULT_API_BASE,
    DEFAULT_JUDGMENT_ENDPOINT,
    check_configuration,
    check_live_services,
    run_preflight,
    sha256_file,
)


VALID_ENVIRONMENT = {
    "JUDGMENT_ENABLED": "true",
    "JUDGMENT_ENDPOINT": DEFAULT_JUDGMENT_ENDPOINT,
    "JUDGMENT_MODEL": "judgment-v02d",
    "JUDGMENT_ADAPTER": "judgment-qwen3-4b-failure-focus-v0.2-d",
    "JUDGMENT_TIMEOUT_SECONDS": "120",
    "JUDGMENT_SHADOW_ENABLED": "false",
    "JUDGMENT_SHADOW_QUEUE_MAX_SIZE": "64",
    "JUDGMENT_SHADOW_ITEM_TTL_SECONDS": "30",
    "JUDGMENT_SHADOW_ADMISSION_RPS": "1",
    "JUDGMENT_SHADOW_ADMISSION_BURST": "1",
}


class _Response:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode("utf-8") if payload is not None else b""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


def _opener(payloads):
    def open_request(request, timeout):
        del timeout
        return _Response(payloads[request.full_url])

    return open_request


class JudgmentStagingPreflightTests(unittest.TestCase):
    def test_configuration_requires_locked_local_staging_values(self):
        self.assertTrue(check_configuration(VALID_ENVIRONMENT)["passed"])
        invalid = dict(VALID_ENVIRONMENT)
        invalid.update({
            "JUDGMENT_ENABLED": "false",
            "JUDGMENT_ENDPOINT": "https://example.com/v1/chat/completions",
            "JUDGMENT_MODEL": "other",
            "JUDGMENT_ADAPTER": "other",
            "JUDGMENT_TIMEOUT_SECONDS": "0",
        })
        result = check_configuration(invalid)
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["errors"]), 5)

        wrong_port = dict(VALID_ENVIRONMENT)
        wrong_port["JUDGMENT_ENDPOINT"] = (
            "http://127.0.0.1:9999/v1/chat/completions"
        )
        self.assertFalse(check_configuration(wrong_port)["passed"])

        bad_shadow = dict(VALID_ENVIRONMENT)
        bad_shadow["JUDGMENT_SHADOW_ENABLED"] = "sometimes"
        self.assertFalse(check_configuration(bad_shadow)["passed"])
        shadow = dict(VALID_ENVIRONMENT)
        shadow["JUDGMENT_SHADOW_ENABLED"] = "true"
        self.assertTrue(check_configuration(shadow)["effective"]["shadow_enabled"])

        bad_queue = dict(VALID_ENVIRONMENT)
        bad_queue["JUDGMENT_SHADOW_QUEUE_MAX_SIZE"] = "0"
        self.assertFalse(check_configuration(bad_queue)["passed"])
        bad_ttl = dict(VALID_ENVIRONMENT)
        bad_ttl["JUDGMENT_SHADOW_ITEM_TTL_SECONDS"] = "nan"
        self.assertFalse(check_configuration(bad_ttl)["passed"])
        bad_admission_rate = dict(VALID_ENVIRONMENT)
        bad_admission_rate["JUDGMENT_SHADOW_ADMISSION_RPS"] = "inf"
        self.assertFalse(check_configuration(bad_admission_rate)["passed"])
        bad_admission_burst = dict(VALID_ENVIRONMENT)
        bad_admission_burst["JUDGMENT_SHADOW_ADMISSION_BURST"] = "0"
        self.assertFalse(check_configuration(bad_admission_burst)["passed"])

    def test_skip_live_preflight_reads_database_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "staging.db"
            connection = sqlite3.connect(database)
            connection.executescript(
                "CREATE TABLE utterances (id INTEGER PRIMARY KEY);"
                "CREATE TABLE judgment_results (id INTEGER PRIMARY KEY);"
                "INSERT INTO utterances DEFAULT VALUES;"
            )
            connection.commit()
            connection.close()
            before = sha256_file(database)
            result = run_preflight(
                database_path=database,
                api_base=DEFAULT_API_BASE,
                environment=VALID_ENVIRONMENT,
                skip_live=True,
            )
            self.assertTrue(result["passed"])
            self.assertEqual(result["database"]["utterances"], 1)
            self.assertEqual(result["database"]["judgment_results"], 0)
            self.assertTrue(result["database"]["read_only"])
            self.assertFalse(result["mutations_performed"])
            self.assertEqual(sha256_file(database), before)

    def test_live_checks_require_model_alias_and_judgment_paths(self):
        payloads = {
            "http://127.0.0.1:1234/health": None,
            "http://127.0.0.1:1234/v1/models": {
                "data": [{"id": "judgment-v02d"}]
            },
            "http://127.0.0.1:8001/health": {"status": "ok"},
            "http://127.0.0.1:8001/ready/judgment": {"ready": True},
            "http://127.0.0.1:8001/openapi.json": {"paths": {
                "/health/judgment": {},
                "/ready/judgment": {},
                "/utterances/{utterance_id}/judgment": {},
                "/utterances/{utterance_id}/judgments": {},
            }},
        }
        result = check_live_services(
            api_base=DEFAULT_API_BASE,
            judgment_endpoint=DEFAULT_JUDGMENT_ENDPOINT,
            model_name="judgment-v02d",
            opener=_opener(payloads),
        )
        self.assertTrue(result["passed"])
        self.assertTrue(all(result["checks"].values()))

    def test_live_checks_fail_closed_when_alias_and_path_are_missing(self):
        payloads = {
            "http://127.0.0.1:1234/health": None,
            "http://127.0.0.1:1234/v1/models": {"data": [{"id": "base"}]},
            "http://127.0.0.1:8001/health": {"status": "ok"},
            "http://127.0.0.1:8001/ready/judgment": {"ready": True},
            "http://127.0.0.1:8001/ready/judgment": {"ready": False},
            "http://127.0.0.1:8001/openapi.json": {"paths": {}},
        }
        result = check_live_services(
            api_base=DEFAULT_API_BASE,
            judgment_endpoint=DEFAULT_JUDGMENT_ENDPOINT,
            model_name="judgment-v02d",
            opener=_opener(payloads),
        )
        self.assertFalse(result["passed"])
        self.assertIn("model alias missing: judgment-v02d", result["errors"])
        self.assertIn("judgment API paths are missing from OpenAPI", result["errors"])


if __name__ == "__main__":
    unittest.main()

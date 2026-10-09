"""Tests for the content-free /analyze shadow OFF/ON load probe."""

import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from scripts.run_analyze_shadow_load import (
    _valid_analysis_contract,
    run_probe,
)


class _Response:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class _Harness:
    def __init__(self, database: Path, shadow: bool):
        self.database = database
        self.shadow = shadow
        self.lock = threading.Lock()
        self.scheduled = 0
        self.invocations = 0
        self.successes = 0

    def monitor(self):
        return {
            "shadow": {
                "enabled": self.shadow,
                "scheduled_total": self.scheduled,
                "enqueued_total": self.scheduled,
                "model_invocation_total": self.invocations,
                "success_total": self.successes,
                "failure_total": 0,
                "dropped_total": 0,
                "expired_total": 0,
                "shutdown_dropped_total": 0,
                "sampled_out_total": 0,
                "decision_counts": {"acceptable": self.successes} if self.successes else {},
                "failure_categories": {},
                "retry_used_total": 0,
                "retry_recovered_total": 0,
                "latency_ms": {
                    "sample_count": self.successes,
                    "p50": 1.0 if self.successes else None,
                    "p95": 1.0 if self.successes else None,
                    "max": 1.0 if self.successes else None,
                },
                "queue_wait_latency_ms": {
                    "sample_count": self.successes,
                    "p50": 0.1 if self.successes else None,
                    "p95": 0.1 if self.successes else None,
                    "max": 0.1 if self.successes else None,
                },
                "configuration_valid": True,
                "accepting": self.shadow,
                "worker_running": self.shadow,
                "worker_active": False,
                "queue_capacity": 64,
                "queue_depth": 0,
                "item_ttl_seconds": 30.0,
                "admission_rate_per_second": 1.0,
                "admission_burst": 1,
                "admission_tokens": 1.0,
                "admission_jitter_tolerance_seconds": 0.05,
                "persists_results": False,
                "affects_analyze_response": False,
                "contains_request_content": False,
            }
        }

    def open(self, request, timeout):
        del timeout
        if request.full_url.endswith("/health/judgment"):
            with self.lock:
                return _Response(self.monitor())
        with self.lock:
            with sqlite3.connect(self.database) as connection:
                connection.execute("INSERT INTO analyses DEFAULT VALUES")
            if self.shadow:
                self.scheduled += 1
                self.invocations += 1
                self.successes += 1
            sequence = self.scheduled if self.shadow else 1
            return _Response({
                "id": sequence,
                "utterance_id": 1,
                "primary_type": "greeting",
                "candidate_types": "[]",
                "classification_reason": "synthetic",
                "needs_deep_analysis": False,
                "is_correct": True,
                "corrected_text": "synthetic",
                "error_types": "[]",
                "feedback_ko": "synthetic",
                "feedback_ja": "synthetic",
                "created_at": "2026-10-08T00:00:00Z",
            })


class AnalyzeShadowLoadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "staging.db"
        with sqlite3.connect(self.database) as connection:
            connection.executescript(
                "CREATE TABLE analyses (id INTEGER PRIMARY KEY);"
                "CREATE TABLE judgment_results (id INTEGER PRIMARY KEY);"
            )

    def tearDown(self):
        self.temp.cleanup()

    def test_contract_rejects_judgment_field_leakage(self):
        payload = {
            "id": 1, "utterance_id": 1, "primary_type": "greeting",
            "candidate_types": "[]", "classification_reason": "synthetic",
            "needs_deep_analysis": False, "is_correct": True,
            "corrected_text": "synthetic", "error_types": "[]",
            "feedback_ko": "synthetic", "feedback_ja": "synthetic",
            "created_at": "2026-10-08T00:00:00Z",
        }
        self.assertTrue(_valid_analysis_contract(payload))
        payload["decision"] = "acceptable"
        self.assertFalse(_valid_analysis_contract(payload))

    def test_shadow_off_has_no_shadow_or_judgment_writes(self):
        harness = _Harness(self.database, shadow=False)
        result = run_probe(
            api_base="http://127.0.0.1:8001", utterance_ids=[100, 101],
            phases=[(1, 2), (2, 2)], timeout=1, expect_shadow=False,
            database_path=self.database, opener=harness.open,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["database_delta"], {"analyses": 4, "judgment_results": 0})
        self.assertEqual(result["shadow_delta"]["scheduled_total"], 0)
        self.assertNotIn("synthetic", json.dumps(result))

    def test_shadow_on_completes_every_scheduled_task_and_plan_is_stable(self):
        first_harness = _Harness(self.database, shadow=True)
        first = run_probe(
            api_base="http://127.0.0.1:8001", utterance_ids=[100, 101],
            phases=[(1, 2), (2, 2)], timeout=1, expect_shadow=True,
            database_path=self.database, opener=first_harness.open,
        )
        second_harness = _Harness(self.database, shadow=True)
        second = run_probe(
            api_base="http://127.0.0.1:8001", utterance_ids=[100, 101],
            phases=[(1, 2), (2, 2)], timeout=1, expect_shadow=True,
            database_path=self.database, opener=second_harness.open,
        )
        self.assertTrue(first["passed"])
        self.assertEqual(first["shadow_delta"]["scheduled_total"], 4)
        self.assertEqual(first["shadow_delta"]["success_total"], 4)
        self.assertEqual(first["shadow_delta"]["failure_total"], 0)
        self.assertEqual(first["input_plan_sha256"], second["input_plan_sha256"])


if __name__ == "__main__":
    unittest.main()

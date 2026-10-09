"""Tests for the content-free bounded shadow arrival-rate probe."""

import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from scripts.run_analyze_shadow_rate_probe import run_probe, run_rate_phase


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
    def __init__(
        self, database: Path, drop_after: int | None = None,
        sample_after: int | None = None,
    ):
        self.database = database
        self.drop_after = drop_after
        self.sample_after = sample_after
        self.lock = threading.Lock()
        self.requests = 0
        self.enqueued = 0
        self.successes = 0
        self.failures = 0
        self.sampled_out = 0

    def monitor(self):
        drops = self.failures
        return {
            "shadow": {
                "enabled": True, "configuration_valid": True,
                "accepting": True, "worker_running": True,
                "worker_active": False, "queue_capacity": 64,
                "queue_depth": 0, "item_ttl_seconds": 30.0,
                "admission_rate_per_second": 1.0,
                "admission_burst": 1, "admission_tokens": 0.0,
                "admission_jitter_tolerance_seconds": 0.05,
                "scheduled_total": self.requests,
                "enqueued_total": self.enqueued,
                "model_invocation_total": self.successes,
                "success_total": self.successes, "failure_total": self.failures,
                "dropped_total": drops, "expired_total": 0,
                "shutdown_dropped_total": 0,
                "sampled_out_total": self.sampled_out,
                "decision_counts": {"acceptable": self.successes} if self.successes else {},
                "failure_categories": {"queue_full": drops} if drops else {},
                "retry_used_total": 0, "retry_recovered_total": 0,
                "latency_ms": {"sample_count": self.successes, "p50": 1.0, "p95": 1.0, "max": 1.0},
                "queue_wait_latency_ms": {"sample_count": self.successes, "p50": 0.1, "p95": 0.1, "max": 0.1},
                "persists_results": False, "affects_analyze_response": False,
                "contains_request_content": False,
            }
        }

    def open(self, request, timeout):
        del timeout
        if request.full_url.endswith("/health/judgment"):
            with self.lock:
                return _Response(self.monitor())
        with self.lock:
            self.requests += 1
            if self.drop_after is not None and self.requests > self.drop_after:
                self.failures += 1
            elif self.sample_after is not None and self.requests > self.sample_after:
                self.sampled_out += 1
            else:
                self.enqueued += 1
                self.successes += 1
            with sqlite3.connect(self.database) as connection:
                connection.execute("INSERT INTO analyses DEFAULT VALUES")
            return _Response({
                "id": self.requests, "utterance_id": 1,
                "primary_type": "greeting", "candidate_types": "[]",
                "classification_reason": "synthetic",
                "needs_deep_analysis": False, "is_correct": True,
                "corrected_text": "synthetic", "error_types": "[]",
                "feedback_ko": "synthetic", "feedback_ja": "synthetic",
                "created_at": "2026-10-08T00:00:00Z",
            })


class AnalyzeShadowRateProbeTests(unittest.TestCase):
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

    def test_stable_phase_requires_complete_drop_free_collection(self):
        harness = _Harness(self.database)
        result = run_rate_phase(
            api_base="http://127.0.0.1:8001", utterance_ids=[1, 2],
            target_rps=1000, request_count=4, mode="stable", timeout=1,
            database_path=self.database, opener=harness.open,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["shadow_delta"]["success_total"], 4)
        self.assertEqual(result["shadow_delta"]["dropped_total"], 0)
        self.assertEqual(result["database_delta"], {"analyses": 4, "judgment_results": 0})

    def test_drop_phase_accepts_only_bounded_queue_drop_categories(self):
        harness = _Harness(self.database, drop_after=1)
        result = run_rate_phase(
            api_base="http://127.0.0.1:8001", utterance_ids=[1],
            target_rps=1000, request_count=4, mode="drop", timeout=1,
            database_path=self.database, opener=harness.open,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["response_success_count"], 4)
        self.assertEqual(result["shadow_delta"]["failure_categories"], {"queue_full": 3})
        self.assertEqual(result["shadow_delta"]["dropped_total"], 3)

    def test_sample_phase_counts_admission_exclusions_as_non_failures(self):
        harness = _Harness(self.database, sample_after=1)
        result = run_rate_phase(
            api_base="http://127.0.0.1:8001", utterance_ids=[1],
            target_rps=1000, request_count=4, mode="sample", timeout=1,
            database_path=self.database, opener=harness.open,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["shadow_delta"]["success_total"], 1)
        self.assertEqual(result["shadow_delta"]["sampled_out_total"], 3)
        self.assertEqual(result["shadow_delta"]["failure_total"], 0)
        self.assertEqual(result["shadow_delta"]["dropped_total"], 0)

    def test_probe_has_stable_plan_hash_and_no_content(self):
        first = run_probe(
            api_base="http://127.0.0.1:8001", utterance_ids=[1],
            phases=[(1000, 2, "stable")], timeout=1, database_path=self.database,
            opener=_Harness(self.database).open,
        )
        second = run_probe(
            api_base="http://127.0.0.1:8001", utterance_ids=[1],
            phases=[(1000, 2, "stable")], timeout=1, database_path=self.database,
            opener=_Harness(self.database).open,
        )
        self.assertTrue(first["passed"])
        self.assertEqual(first["input_plan_sha256"], second["input_plan_sha256"])
        serialized = json.dumps(first)
        self.assertNotIn("synthetic", serialized)
        self.assertNotIn("utterance_id", serialized)


if __name__ == "__main__":
    unittest.main()

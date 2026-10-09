"""Regression tests for response-independent judgment shadow execution."""

import json
import os
import threading
import time
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from fastapi import BackgroundTasks

from analyzer import judgment_shadow as shadow
from analyzer.judgment_runtime import JudgmentOverloadedError
from analyzer.judgment_service import JudgmentServiceError


class JudgmentShadowIntegrationTests(unittest.TestCase):
    def setUp(self):
        shadow.reset_for_tests()

    def tearDown(self):
        shadow.reset_for_tests()

    @staticmethod
    def result(decision="acceptable"):
        return {
            "decision": decision,
            "latency_ms": 12.5,
            "retry_used": False,
        }

    def test_disabled_by_default_and_requires_both_flags(self):
        tasks = BackgroundTasks()
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(shadow.shadow_enabled())
            self.assertFalse(shadow.schedule_shadow(tasks, "まだです。", "N5"))
        with patch.dict(os.environ, {"JUDGMENT_SHADOW_ENABLED": "true"}, clear=True):
            self.assertFalse(shadow.shadow_enabled())
        with patch.dict(os.environ, {
            "JUDGMENT_ENABLED": "true", "JUDGMENT_SHADOW_ENABLED": "true",
        }, clear=True):
            self.assertTrue(shadow.shadow_enabled())
        self.assertEqual(len(tasks.tasks), 0)
        self.assertEqual(shadow.snapshot()["scheduled_total"], 0)

    def test_schedule_normalizes_level_without_exposing_content(self):
        tasks = BackgroundTasks()
        with patch.dict(os.environ, {
            "JUDGMENT_ENABLED": "true", "JUDGMENT_SHADOW_ENABLED": "true",
        }, clear=True):
            self.assertTrue(shadow.schedule_shadow(tasks, "学校を行きます。", "invalid"))
            result = shadow.snapshot()
        self.assertEqual(len(tasks.tasks), 1)
        self.assertEqual(tasks.tasks[0].args, ("学校を行きます。", "N5"))
        self.assertEqual(result["scheduled_total"], 1)
        self.assertFalse(result["persists_results"])
        self.assertFalse(result["affects_analyze_response"])
        serialized = json.dumps(result)
        self.assertNotIn("学校", serialized)
        self.assertNotIn("utterance_id", serialized)

    def test_success_is_aggregated_without_persistence(self):
        with patch.object(shadow, "reserve_capacity", return_value=nullcontext()), patch.object(
            shadow, "run_judgment", return_value=self.result("needs_correction")
        ) as run:
            shadow.execute_shadow("学校を行きます。", "N4")
        run.assert_called_once_with("学校を行きます。", context=None, learner_level="N4")
        result = shadow.snapshot()
        self.assertEqual(result["model_invocation_total"], 1)
        self.assertEqual(result["success_total"], 1)
        self.assertEqual(result["failure_total"], 0)
        self.assertEqual(result["decision_counts"], {"needs_correction": 1})
        self.assertEqual(result["latency_ms"]["p95"], 12.5)

    def test_model_and_capacity_failures_are_swallowed_and_sanitized(self):
        private = JudgmentServiceError("private raw model output")
        with patch.object(shadow, "reserve_capacity", return_value=nullcontext()), patch.object(
            shadow, "run_judgment", side_effect=private
        ):
            shadow.execute_shadow("秘密の文", "N5")
        with patch.object(
            shadow, "reserve_capacity", side_effect=JudgmentOverloadedError("full")
        ):
            shadow.execute_shadow("別の秘密", "N5")
        result = shadow.snapshot()
        self.assertEqual(result["success_total"], 0)
        self.assertEqual(result["failure_total"], 2)
        self.assertEqual(result["failure_categories"], {
            "model_unavailable": 1, "overloaded": 1,
        })
        serialized = json.dumps(result)
        self.assertNotIn("秘密", serialized)
        self.assertNotIn("private raw", serialized)

    def test_bounded_queue_drops_excess_without_blocking_or_exposing_content(self):
        started = threading.Event()
        release = threading.Event()

        def slow_result(*_args, **_kwargs):
            started.set()
            release.wait(1)
            return self.result()

        environment = {
            "JUDGMENT_ENABLED": "true",
            "JUDGMENT_SHADOW_ENABLED": "true",
            "JUDGMENT_SHADOW_QUEUE_MAX_SIZE": "1",
            "JUDGMENT_SHADOW_ITEM_TTL_SECONDS": "2",
            "JUDGMENT_SHADOW_ADMISSION_RPS": "1000",
            "JUDGMENT_SHADOW_ADMISSION_BURST": "4",
            "JUDGMENT_MAX_CONCURRENCY": "1",
            "JUDGMENT_QUEUE_TIMEOUT_SECONDS": "0",
        }
        with patch.dict(os.environ, environment, clear=True), patch.object(
            shadow, "run_judgment", side_effect=slow_result
        ):
            self.assertTrue(shadow.start_worker())
            self.assertTrue(shadow.enqueue_shadow("最初の秘密", "N5"))
            self.assertTrue(started.wait(1))
            self.assertTrue(shadow.enqueue_shadow("二番目の秘密", "N5"))
            self.assertFalse(shadow.enqueue_shadow("三番目の秘密", "N5"))
            release.set()
            self.assertTrue(shadow.stop_worker(2))
            result = shadow.snapshot()

        self.assertEqual(result["enqueued_total"], 2)
        self.assertEqual(result["success_total"], 2)
        self.assertEqual(result["dropped_total"], 1)
        self.assertEqual(result["failure_categories"], {"queue_full": 1})
        self.assertEqual(result["queue_depth"], 0)
        self.assertFalse(result["worker_running"])
        serialized = json.dumps(result)
        self.assertNotIn("秘密", serialized)

    def test_token_bucket_allows_only_small_boundary_jitter(self):
        with shadow._QUEUE_CONDITION:
            shadow._ADMISSION_TOKENS = 0.96
            shadow._ADMISSION_LAST_REFILL = 100.0
            self.assertTrue(shadow._take_admission_token(100.0, 1.0, 1))
            self.assertEqual(shadow._ADMISSION_TOKENS, 0.0)
            self.assertFalse(shadow._take_admission_token(100.1, 1.0, 1))

    def test_token_bucket_samples_excess_without_failure_or_content(self):
        started = threading.Event()
        release = threading.Event()

        def slow_result(*_args, **_kwargs):
            started.set()
            release.wait(1)
            return self.result()

        environment = {
            "JUDGMENT_ENABLED": "true",
            "JUDGMENT_SHADOW_ENABLED": "true",
            "JUDGMENT_SHADOW_QUEUE_MAX_SIZE": "4",
            "JUDGMENT_SHADOW_ITEM_TTL_SECONDS": "2",
            "JUDGMENT_SHADOW_ADMISSION_RPS": "1",
            "JUDGMENT_SHADOW_ADMISSION_BURST": "1",
            "JUDGMENT_MAX_CONCURRENCY": "1",
            "JUDGMENT_QUEUE_TIMEOUT_SECONDS": "0",
        }
        with patch.dict(os.environ, environment, clear=True), patch.object(
            shadow, "run_judgment", side_effect=slow_result
        ):
            self.assertTrue(shadow.start_worker())
            self.assertTrue(shadow.enqueue_shadow("最初の秘密", "N5"))
            self.assertTrue(started.wait(1))
            self.assertFalse(shadow.enqueue_shadow("除外する秘密", "N5"))
            release.set()
            self.assertTrue(shadow.stop_worker(2))
            result = shadow.snapshot()

        self.assertEqual(result["schema_version"], "judgment-shadow-monitor-v0.3")
        self.assertEqual(result["sampled_out_total"], 1)
        self.assertEqual(result["success_total"], 1)
        self.assertEqual(result["failure_total"], 0)
        self.assertEqual(result["dropped_total"], 0)
        self.assertEqual(result["failure_categories"], {})
        self.assertNotIn("秘密", json.dumps(result))

    def test_item_expires_while_single_worker_is_busy(self):
        started = threading.Event()
        release = threading.Event()

        def slow_result(*_args, **_kwargs):
            started.set()
            release.wait(1)
            return self.result()

        environment = {
            "JUDGMENT_ENABLED": "true",
            "JUDGMENT_SHADOW_ENABLED": "true",
            "JUDGMENT_SHADOW_QUEUE_MAX_SIZE": "4",
            "JUDGMENT_SHADOW_ITEM_TTL_SECONDS": "0.03",
            "JUDGMENT_SHADOW_ADMISSION_RPS": "1000",
            "JUDGMENT_SHADOW_ADMISSION_BURST": "4",
            "JUDGMENT_MAX_CONCURRENCY": "1",
            "JUDGMENT_QUEUE_TIMEOUT_SECONDS": "0",
        }
        with patch.dict(os.environ, environment, clear=True), patch.object(
            shadow, "run_judgment", side_effect=slow_result
        ):
            self.assertTrue(shadow.start_worker())
            self.assertTrue(shadow.enqueue_shadow("先行", "N5"))
            self.assertTrue(started.wait(1))
            self.assertTrue(shadow.enqueue_shadow("期限切れ", "N5"))
            time.sleep(0.05)
            release.set()
            self.assertTrue(shadow.stop_worker(2))
            result = shadow.snapshot()

        self.assertEqual(result["success_total"], 1)
        self.assertEqual(result["expired_total"], 1)
        self.assertEqual(result["dropped_total"], 1)
        self.assertEqual(result["failure_categories"], {"expired": 1})

    def test_stop_drains_queued_work_within_grace(self):
        environment = {
            "JUDGMENT_ENABLED": "true",
            "JUDGMENT_SHADOW_ENABLED": "true",
            "JUDGMENT_SHADOW_QUEUE_MAX_SIZE": "4",
            "JUDGMENT_SHADOW_ITEM_TTL_SECONDS": "2",
            "JUDGMENT_SHADOW_ADMISSION_RPS": "1000",
            "JUDGMENT_SHADOW_ADMISSION_BURST": "4",
            "JUDGMENT_MAX_CONCURRENCY": "1",
            "JUDGMENT_QUEUE_TIMEOUT_SECONDS": "0",
        }
        with patch.dict(os.environ, environment, clear=True), patch.object(
            shadow, "run_judgment", return_value=self.result()
        ):
            self.assertTrue(shadow.start_worker())
            self.assertTrue(shadow.enqueue_shadow("一", "N5"))
            self.assertTrue(shadow.enqueue_shadow("二", "N4"))
            self.assertTrue(shadow.stop_worker(1))
            result = shadow.snapshot()

        self.assertEqual(result["success_total"], 2)
        self.assertEqual(result["shutdown_dropped_total"], 0)
        self.assertEqual(result["queue_depth"], 0)
        self.assertFalse(result["accepting"])

    def test_stop_timeout_drops_only_pending_work(self):
        started = threading.Event()
        release = threading.Event()

        def blocked_result(*_args, **_kwargs):
            started.set()
            release.wait(1)
            return self.result()

        environment = {
            "JUDGMENT_ENABLED": "true",
            "JUDGMENT_SHADOW_ENABLED": "true",
            "JUDGMENT_SHADOW_QUEUE_MAX_SIZE": "4",
            "JUDGMENT_SHADOW_ITEM_TTL_SECONDS": "2",
            "JUDGMENT_SHADOW_ADMISSION_RPS": "1000",
            "JUDGMENT_SHADOW_ADMISSION_BURST": "4",
            "JUDGMENT_MAX_CONCURRENCY": "1",
            "JUDGMENT_QUEUE_TIMEOUT_SECONDS": "0",
        }
        with patch.dict(os.environ, environment, clear=True), patch.object(
            shadow, "run_judgment", side_effect=blocked_result
        ):
            self.assertTrue(shadow.start_worker())
            self.assertTrue(shadow.enqueue_shadow("実行中", "N5"))
            self.assertTrue(started.wait(1))
            self.assertTrue(shadow.enqueue_shadow("待機中", "N5"))
            self.assertFalse(shadow.stop_worker(0))
            release.set()
            deadline = time.monotonic() + 1
            while shadow.snapshot()["worker_running"] and time.monotonic() < deadline:
                time.sleep(0.005)
            result = shadow.snapshot()

        self.assertEqual(result["success_total"], 1)
        self.assertEqual(result["shutdown_dropped_total"], 1)
        self.assertEqual(result["dropped_total"], 1)
        self.assertEqual(result["failure_categories"], {"shutdown_drop": 1})
        self.assertEqual(result["queue_depth"], 0)
        self.assertFalse(result["worker_running"])


if __name__ == "__main__":
    unittest.main()

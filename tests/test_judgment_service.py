"""Unit tests for the feature-flagged D-only judgment client."""

import json
import os
import unittest
from unittest.mock import patch

from analyzer.judgment_service import (
    DEFAULT_ADAPTER,
    DEFAULT_MODEL,
    JudgmentServiceError,
    PRESERVATION_CONTRACT_ERROR,
    judgment_enabled,
    run_judgment,
)


class JudgmentServiceTests(unittest.TestCase):
    def test_disabled_by_default_and_explicit_enable_values(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(judgment_enabled())
        for value in ("1", "true", "YES", "on"):
            with self.subTest(value=value), patch.dict(
                os.environ, {"JUDGMENT_ENABLED": value}, clear=True
            ):
                self.assertTrue(judgment_enabled())

    def test_valid_correction_uses_locked_generation_and_backend_diff(self):
        captured = {}

        def transport(**kwargs):
            captured.update(kwargs)
            return {
                "transport_success": True,
                "raw_text": json.dumps({
                    "decision": "needs_correction",
                    "corrected_text": "学校に行きます。",
                    "error_types": ["particle_misuse"],
                    "reason_ko": "목적지 조사를 고칩니다.",
                }, ensure_ascii=False),
                "latency_ms": 12.5,
                "error": None,
            }

        result = run_judgment(
            "学校を行きます。", context="등교 상황", learner_level="N4",
            transport=transport,
        )
        request = captured["request_body"]
        self.assertEqual(request["model"], DEFAULT_MODEL)
        self.assertEqual(request["temperature"], 0.0)
        self.assertEqual(request["top_p"], 1.0)
        self.assertEqual(request["max_tokens"], 512)
        visible = json.loads(request["messages"][1]["content"])
        self.assertEqual(visible, {
            "context": "등교 상황", "learner_level": "N4", "text": "学校を行きます。"
        })
        self.assertEqual(result["edits"], [{
            "start": 2, "end": 3, "source": "を", "replacement": "に",
            "error_type": "particle_misuse",
        }])
        self.assertEqual(result["strategy"], "d_only")
        self.assertEqual(result["adapter_name"], DEFAULT_ADAPTER)
        self.assertEqual(result["attempt_count"], 1)
        self.assertFalse(result["retry_used"])
        self.assertNotIn("confidence", result)

    def test_preservation_violation_retries_once_and_records_recovery(self):
        calls = []

        def transport(**kwargs):
            calls.append(kwargs["request_body"])
            corrected = "잘못 바뀐 문장" if len(calls) == 1 else "……"
            return {
                "transport_success": True,
                "raw_text": json.dumps({
                    "decision": "insufficient_evidence",
                    "corrected_text": corrected,
                    "error_types": [],
                    "reason_ko": "판단 근거가 부족합니다.",
                }, ensure_ascii=False),
                "latency_ms": 8.0 if len(calls) == 1 else 9.5,
            }

        result = run_judgment(
            "……", context=None, learner_level="N5", transport=transport
        )
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[0]["messages"][0], calls[1]["messages"][0])
        self.assertEqual(calls[0]["messages"][1], calls[1]["messages"][1])
        self.assertEqual(result["corrected_text"], "……")
        self.assertEqual(result["attempt_count"], 2)
        self.assertTrue(result["retry_used"])
        self.assertEqual(result["first_contract_error"], PRESERVATION_CONTRACT_ERROR)
        self.assertEqual(result["latency_ms"], 17.5)

    def test_retry_failure_remains_service_error(self):
        calls = 0

        def transport(**kwargs):
            nonlocal calls
            calls += 1
            return {
                "transport_success": True,
                "raw_text": json.dumps({
                    "decision": "acceptable",
                    "corrected_text": f"changed-{calls}",
                    "error_types": [],
                    "reason_ko": "허용합니다.",
                }),
                "latency_ms": 1.0,
            }

        with self.assertRaisesRegex(JudgmentServiceError, PRESERVATION_CONTRACT_ERROR) as raised:
            run_judgment("原文", context=None, learner_level="N5", transport=transport)
        self.assertEqual(calls, 2)
        self.assertEqual(raised.exception.attempt_count, 2)
        self.assertTrue(raised.exception.retry_used)
        self.assertEqual(
            raised.exception.first_contract_error, PRESERVATION_CONTRACT_ERROR
        )

    def test_other_contract_and_transport_failures_are_not_retried(self):
        call_count = 0

        def failed(**kwargs):
            nonlocal call_count
            call_count += 1
            return {"transport_success": False, "error": "connection refused"}

        with self.assertRaisesRegex(JudgmentServiceError, "connection refused"):
            run_judgment("まだです。", context=None, learner_level="N5", transport=failed)
        self.assertEqual(call_count, 1)

        call_count = 0

        def malformed(**kwargs):
            nonlocal call_count
            call_count += 1
            return {"transport_success": True, "raw_text": "not-json", "latency_ms": 1}

        with self.assertRaisesRegex(JudgmentServiceError, "contract violation") as raised:
            run_judgment("まだです。", context=None, learner_level="N5", transport=malformed)
        self.assertEqual(call_count, 1)
        self.assertEqual(raised.exception.raw_text, "not-json")

        def raises(**kwargs):
            raise TimeoutError("socket timed out")

        with self.assertRaisesRegex(JudgmentServiceError, "timed out"):
            run_judgment("まだです。", context=None, learner_level="N5", transport=raises)

        with patch.dict(os.environ, {"JUDGMENT_MODEL": ""}, clear=True):
            with self.assertRaisesRegex(JudgmentServiceError, "model must be a nonblank"):
                run_judgment("まだです。", context=None, learner_level="N5")

    def test_invalid_local_inputs_are_rejected_without_transport(self):
        with self.assertRaisesRegex(ValueError, "nonblank"):
            run_judgment("  ", context=None, learner_level="N5")
        with self.assertRaisesRegex(ValueError, "N5 or N4"):
            run_judgment("まだです。", context=None, learner_level="N3")


if __name__ == "__main__":
    unittest.main()

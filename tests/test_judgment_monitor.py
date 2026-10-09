"""Privacy and aggregation tests for process-local judgment monitoring."""

import json
import os
import unittest
from unittest.mock import patch

from analyzer.judgment_monitor import (
    record_failure,
    record_internal_failure,
    record_model_invocation,
    record_rejection,
    record_request,
    record_success,
    reset_for_tests,
    snapshot,
)
from analyzer.judgment_service import JudgmentServiceError


class JudgmentMonitorTests(unittest.TestCase):
    def setUp(self):
        reset_for_tests()

    def tearDown(self):
        reset_for_tests()

    @staticmethod
    def success(decision="acceptable", latency=10.0, retry=False):
        return {
            "decision": decision,
            "latency_ms": latency,
            "retry_used": retry,
        }

    def test_disabled_empty_snapshot_contains_no_request_content(self):
        with patch.dict(os.environ, {}, clear=True):
            result = snapshot()
        self.assertFalse(result["enabled"])
        self.assertEqual(result["operational_state"], "disabled")
        self.assertEqual(result["request_total"], 0)
        self.assertFalse(result["contains_request_content"])
        serialized = json.dumps(result, default=str)
        for forbidden in ("utterance_id", "text", "context", "raw_text", "reason_ko"):
            self.assertNotIn(forbidden, serialized)

    def test_success_counts_decisions_retries_and_bounded_latency_summary(self):
        for result in (
            self.success("acceptable", 10.0),
            self.success("needs_correction", 100.0, retry=True),
            self.success("insufficient_evidence", float("nan")),
        ):
            record_request()
            record_model_invocation()
            record_success(result)
        with patch.dict(os.environ, {"JUDGMENT_ENABLED": "true"}, clear=True):
            result = snapshot()
        self.assertEqual(result["operational_state"], "ready")
        self.assertEqual(result["request_total"], 3)
        self.assertEqual(result["model_invocation_total"], 3)
        self.assertEqual(result["success_total"], 3)
        self.assertEqual(result["decision_counts"], {
            "acceptable": 1,
            "needs_correction": 1,
            "insufficient_evidence": 1,
        })
        self.assertEqual(result["retry_used_total"], 1)
        self.assertEqual(result["retry_recovered_total"], 1)
        self.assertEqual(result["latency_ms"], {
            "sample_count": 2, "p50": 10.0, "p95": 100.0, "max": 100.0,
        })

    def test_failures_are_sanitized_categories_and_degrade_last_state(self):
        errors = [
            JudgmentServiceError("contract violation: invalid json"),
            JudgmentServiceError("socket timed out"),
            JudgmentServiceError("Invalid judgment timeout configuration"),
            JudgmentServiceError("connection refused"),
            JudgmentServiceError(
                "private raw response", retry_used=True,
                first_contract_error="private detail",
            ),
        ]
        for error in errors:
            record_request()
            record_model_invocation()
            record_failure(error)
        record_internal_failure("persistence_failure")
        with patch.dict(os.environ, {"JUDGMENT_ENABLED": "true"}, clear=True):
            result = snapshot()
        self.assertEqual(result["operational_state"], "degraded")
        self.assertEqual(result["failure_total"], 6)
        self.assertEqual(result["failure_categories"], {
            "contract_violation": 1,
            "timeout": 1,
            "configuration": 1,
            "model_unavailable": 1,
            "preservation_retry_failed": 1,
            "persistence_failure": 1,
        })
        serialized = json.dumps(result, default=str)
        self.assertNotIn("private raw response", serialized)
        self.assertNotIn("private detail", serialized)

    def test_pre_model_rejections_do_not_count_as_model_failures(self):
        for category in ("not_found", "empty_input", "disabled"):
            record_request()
            record_rejection(category)
        result = snapshot()
        self.assertEqual(result["request_total"], 3)
        self.assertEqual(result["model_invocation_total"], 0)
        self.assertEqual(result["failure_total"], 0)
        self.assertEqual(result["rejection_counts"], {
            "not_found": 1, "empty_input": 1, "disabled": 1,
        })


if __name__ == "__main__":
    unittest.main()

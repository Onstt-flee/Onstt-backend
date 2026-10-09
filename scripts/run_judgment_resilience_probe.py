"""Deterministic concurrent accounting probe for judgment staging monitoring."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Any

from analyzer.judgment_monitor import (
    record_failure,
    record_model_invocation,
    record_rejection,
    record_request,
    record_success,
    reset_for_tests,
    snapshot,
)
from analyzer.judgment_service import JudgmentServiceError


CONCURRENT_EVENTS = 999
WORKERS = 16
EXPECTED = {
    "request_total": 1000,
    "model_invocation_total": 900,
    "success_total": 700,
    "failure_total": 200,
    "rejection_counts": {"disabled": 100},
    "decision_counts": {"acceptable": 600, "needs_correction": 100},
    "failure_categories": {
        "timeout": 100,
        "preservation_retry_failed": 100,
    },
    "retry_used_total": 200,
    "retry_recovered_total": 100,
}


def _record_event(index: int) -> None:
    record_request()
    if index < 599:
        record_model_invocation()
        record_success({
            "decision": "acceptable",
            "latency_ms": 10.0 + (index % 91),
            "retry_used": False,
        })
    elif index < 699:
        record_model_invocation()
        record_success({
            "decision": "needs_correction",
            "latency_ms": 150.0 + (index % 51),
            "retry_used": True,
        })
    elif index < 799:
        record_model_invocation()
        record_failure(JudgmentServiceError("socket timed out"))
    elif index < 899:
        record_model_invocation()
        record_failure(JudgmentServiceError(
            "preservation contract failed after retry",
            retry_used=True,
            first_contract_error="non-correction preservation",
        ))
    else:
        record_rejection("disabled")


def run_probe() -> dict[str, Any]:
    reset_for_tests()
    started = perf_counter()
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        list(executor.map(_record_event, range(CONCURRENT_EVENTS)))

    # Deterministic final success fixes the last state after concurrent completion.
    record_request()
    record_model_invocation()
    record_success({
        "decision": "acceptable",
        "latency_ms": 10.0,
        "retry_used": False,
    })
    elapsed_ms = (perf_counter() - started) * 1000.0

    previous = os.environ.get("JUDGMENT_ENABLED")
    os.environ["JUDGMENT_ENABLED"] = "true"
    try:
        metrics = snapshot()
    finally:
        if previous is None:
            os.environ.pop("JUDGMENT_ENABLED", None)
        else:
            os.environ["JUDGMENT_ENABLED"] = previous

    mismatches = {
        key: {"expected": expected, "actual": metrics.get(key)}
        for key, expected in EXPECTED.items()
        if metrics.get(key) != expected
    }
    return {
        "schema_version": "judgment-resilience-probe-v0.1",
        "passed": not mismatches,
        "measurement_scope": "monitor_accounting_only_not_model_or_api_load",
        "workers": WORKERS,
        "concurrent_events": CONCURRENT_EVENTS,
        "total_events": EXPECTED["request_total"],
        "elapsed_ms": round(elapsed_ms, 3),
        "event_rate_per_second": round(
            EXPECTED["request_total"] / (elapsed_ms / 1000), 3
        ),
        "mismatches": mismatches,
        "metrics": metrics,
        "contains_request_content": False,
        "mutations_performed": False,
    }


def main() -> None:
    result = run_probe()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

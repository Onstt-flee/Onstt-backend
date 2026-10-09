"""Process-local, content-free operational metrics for judgment staging."""

from __future__ import annotations

import math
import threading
from collections import Counter, deque
from datetime import datetime, timezone
from time import monotonic
from typing import Any

from analyzer.judgment_service import JudgmentServiceError, judgment_enabled


SCHEMA_VERSION = "judgment-monitor-v0.2"
_MAX_LATENCY_SAMPLES = 1000
_STARTED_MONOTONIC = monotonic()
_STARTED_AT = datetime.now(timezone.utc)
_LOCK = threading.Lock()
_REQUEST_TOTAL = 0
_MODEL_INVOCATION_TOTAL = 0
_SUCCESS_TOTAL = 0
_FAILURE_TOTAL = 0
_REJECTIONS: Counter[str] = Counter()
_DECISIONS: Counter[str] = Counter()
_FAILURE_CATEGORIES: Counter[str] = Counter()
_RETRY_USED_TOTAL = 0
_RETRY_RECOVERED_TOTAL = 0
_LATENCIES: deque[float] = deque(maxlen=_MAX_LATENCY_SAMPLES)
_LAST_OUTCOME: str | None = None
_LAST_EVENT_AT: datetime | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record_request() -> None:
    global _REQUEST_TOTAL, _LAST_EVENT_AT
    with _LOCK:
        _REQUEST_TOTAL += 1
        _LAST_EVENT_AT = _now()


def record_rejection(category: str) -> None:
    global _LAST_OUTCOME, _LAST_EVENT_AT
    if category not in {
        "not_found", "empty_input", "disabled", "overloaded", "shutting_down",
        "runtime_configuration",
    }:
        raise ValueError("unknown rejection category")
    with _LOCK:
        _REJECTIONS[category] += 1
        _LAST_OUTCOME = category
        _LAST_EVENT_AT = _now()


def record_model_invocation() -> None:
    global _MODEL_INVOCATION_TOTAL, _LAST_EVENT_AT
    with _LOCK:
        _MODEL_INVOCATION_TOTAL += 1
        _LAST_EVENT_AT = _now()


def classify_failure(error: JudgmentServiceError) -> str:
    message = str(error).lower()
    if error.retry_used:
        return "preservation_retry_failed"
    if "contract violation" in message:
        return "contract_violation"
    if "configuration" in message:
        return "configuration"
    if "timeout" in message or "timed out" in message:
        return "timeout"
    return "model_unavailable"


def record_failure(error: JudgmentServiceError) -> None:
    global _FAILURE_TOTAL, _RETRY_USED_TOTAL, _LAST_OUTCOME, _LAST_EVENT_AT
    category = classify_failure(error)
    with _LOCK:
        _FAILURE_TOTAL += 1
        _FAILURE_CATEGORIES[category] += 1
        if error.retry_used:
            _RETRY_USED_TOTAL += 1
        _LAST_OUTCOME = "failure"
        _LAST_EVENT_AT = _now()


def record_internal_failure(category: str) -> None:
    global _FAILURE_TOTAL, _LAST_OUTCOME, _LAST_EVENT_AT
    if category != "persistence_failure":
        raise ValueError("unknown internal failure category")
    with _LOCK:
        _FAILURE_TOTAL += 1
        _FAILURE_CATEGORIES[category] += 1
        _LAST_OUTCOME = "failure"
        _LAST_EVENT_AT = _now()


def record_success(result: dict[str, Any]) -> None:
    global _SUCCESS_TOTAL, _RETRY_USED_TOTAL, _RETRY_RECOVERED_TOTAL
    global _LAST_OUTCOME, _LAST_EVENT_AT
    decision = result.get("decision")
    if decision not in {"acceptable", "needs_correction", "insufficient_evidence"}:
        raise ValueError("unknown judgment decision")
    latency = result.get("latency_ms")
    with _LOCK:
        _SUCCESS_TOTAL += 1
        _DECISIONS[decision] += 1
        if result.get("retry_used"):
            _RETRY_USED_TOTAL += 1
            _RETRY_RECOVERED_TOTAL += 1
        if isinstance(latency, (int, float)) and not isinstance(latency, bool):
            latency = float(latency)
            if math.isfinite(latency) and latency >= 0:
                _LATENCIES.append(latency)
        _LAST_OUTCOME = "success"
        _LAST_EVENT_AT = _now()


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * quantile) - 1)
    return round(ordered[index], 3)


def snapshot() -> dict[str, Any]:
    enabled = judgment_enabled()
    now = _now()
    with _LOCK:
        latencies = list(_LATENCIES)
        last_outcome = _LAST_OUTCOME
        state = "disabled" if not enabled else (
            "degraded" if last_outcome == "failure" else "ready"
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "enabled": enabled,
            "operational_state": state,
            "process_started_at": _STARTED_AT,
            "snapshot_at": now,
            "uptime_seconds": round(monotonic() - _STARTED_MONOTONIC, 3),
            "request_total": _REQUEST_TOTAL,
            "model_invocation_total": _MODEL_INVOCATION_TOTAL,
            "success_total": _SUCCESS_TOTAL,
            "failure_total": _FAILURE_TOTAL,
            "rejection_counts": dict(_REJECTIONS),
            "decision_counts": dict(_DECISIONS),
            "failure_categories": dict(_FAILURE_CATEGORIES),
            "retry_used_total": _RETRY_USED_TOTAL,
            "retry_recovered_total": _RETRY_RECOVERED_TOTAL,
            "latency_ms": {
                "sample_count": len(latencies),
                "p50": _percentile(latencies, 0.50),
                "p95": _percentile(latencies, 0.95),
                "max": round(max(latencies), 3) if latencies else None,
            },
            "last_outcome": last_outcome,
            "last_event_at": _LAST_EVENT_AT,
            "contains_request_content": False,
        }


def reset_for_tests() -> None:
    """Reset process-local counters; never expose this through the API."""
    global _REQUEST_TOTAL, _MODEL_INVOCATION_TOTAL, _SUCCESS_TOTAL, _FAILURE_TOTAL
    global _RETRY_USED_TOTAL, _RETRY_RECOVERED_TOTAL, _LAST_OUTCOME, _LAST_EVENT_AT
    with _LOCK:
        _REQUEST_TOTAL = 0
        _MODEL_INVOCATION_TOTAL = 0
        _SUCCESS_TOTAL = 0
        _FAILURE_TOTAL = 0
        _REJECTIONS.clear()
        _DECISIONS.clear()
        _FAILURE_CATEGORIES.clear()
        _RETRY_USED_TOTAL = 0
        _RETRY_RECOVERED_TOTAL = 0
        _LATENCIES.clear()
        _LAST_OUTCOME = None
        _LAST_EVENT_AT = None

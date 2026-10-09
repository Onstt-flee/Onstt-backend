"""Bounded, response-independent shadow execution for the judgment model."""

from __future__ import annotations

import math
import os
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any

from fastapi import BackgroundTasks

from analyzer.judgment_runtime import (
    JudgmentOverloadedError,
    JudgmentRuntimeConfigurationError,
    JudgmentShuttingDownError,
    reserve_capacity,
)
from analyzer.judgment_service import (
    JudgmentServiceError,
    judgment_enabled,
    run_judgment,
)
from analyzer.judgment_monitor import classify_failure


SCHEMA_VERSION = "judgment-shadow-monitor-v0.3"
_MAX_LATENCY_SAMPLES = 1000
_CAPACITY_RETRY_SECONDS = 0.01
_ADMISSION_JITTER_TOLERANCE_SECONDS = 0.05
_LOCK = threading.Lock()
_QUEUE_CONDITION = threading.Condition()
_QUEUE: deque[ShadowItem] = deque()
_WORKER: threading.Thread | None = None
_QUEUE_ACCEPTING = False
_WORKER_ACTIVE = False
_STOP_DEADLINE: float | None = None
_SCHEDULED_TOTAL = 0
_ENQUEUED_TOTAL = 0
_MODEL_INVOCATION_TOTAL = 0
_SUCCESS_TOTAL = 0
_FAILURE_TOTAL = 0
_DROPPED_TOTAL = 0
_EXPIRED_TOTAL = 0
_SHUTDOWN_DROPPED_TOTAL = 0
_SAMPLED_OUT_TOTAL = 0
_ADMISSION_TOKENS = 0.0
_ADMISSION_LAST_REFILL: float | None = None
_DECISIONS: Counter[str] = Counter()
_FAILURE_CATEGORIES: Counter[str] = Counter()
_RETRY_USED_TOTAL = 0
_RETRY_RECOVERED_TOTAL = 0
_LATENCIES: deque[float] = deque(maxlen=_MAX_LATENCY_SAMPLES)
_QUEUE_WAIT_LATENCIES: deque[float] = deque(maxlen=_MAX_LATENCY_SAMPLES)


@dataclass(frozen=True)
class ShadowItem:
    text: str
    learner_level: str
    enqueued_at: float


def shadow_enabled() -> bool:
    shadow = os.getenv("JUDGMENT_SHADOW_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }
    return shadow and judgment_enabled()


def _positive_int(name: str, default: str) -> int:
    try:
        value = int(os.getenv(name, default))
    except ValueError as exc:
        raise JudgmentRuntimeConfigurationError(f"Invalid {name}") from exc
    if value <= 0:
        raise JudgmentRuntimeConfigurationError(f"Invalid {name}")
    return value


def _positive_float(name: str, default: str) -> float:
    try:
        value = float(os.getenv(name, default))
    except ValueError as exc:
        raise JudgmentRuntimeConfigurationError(f"Invalid {name}") from exc
    if not math.isfinite(value) or value <= 0:
        raise JudgmentRuntimeConfigurationError(f"Invalid {name}")
    return value


def _queue_configuration() -> tuple[int, float]:
    return (
        _positive_int("JUDGMENT_SHADOW_QUEUE_MAX_SIZE", "64"),
        _positive_float("JUDGMENT_SHADOW_ITEM_TTL_SECONDS", "30"),
    )


def _admission_configuration() -> tuple[float, int]:
    return (
        _positive_float("JUDGMENT_SHADOW_ADMISSION_RPS", "1"),
        _positive_int("JUDGMENT_SHADOW_ADMISSION_BURST", "1"),
    )


def _record_scheduled() -> None:
    global _SCHEDULED_TOTAL
    with _LOCK:
        _SCHEDULED_TOTAL += 1


def _record_enqueued() -> None:
    global _ENQUEUED_TOTAL
    with _LOCK:
        _ENQUEUED_TOTAL += 1


def _record_sampled_out() -> None:
    global _SAMPLED_OUT_TOTAL
    with _LOCK:
        _SAMPLED_OUT_TOTAL += 1


def _take_admission_token(now: float, rate: float, burst: int) -> bool:
    global _ADMISSION_TOKENS, _ADMISSION_LAST_REFILL
    if _ADMISSION_LAST_REFILL is None:
        _ADMISSION_TOKENS = float(burst)
        _ADMISSION_LAST_REFILL = now
    else:
        elapsed = max(0.0, now - _ADMISSION_LAST_REFILL)
        _ADMISSION_TOKENS = min(float(burst), _ADMISSION_TOKENS + elapsed * rate)
        _ADMISSION_LAST_REFILL = now
    tolerance_tokens = min(0.25, rate * _ADMISSION_JITTER_TOLERANCE_SECONDS)
    if _ADMISSION_TOKENS < 1.0 - tolerance_tokens:
        return False
    _ADMISSION_TOKENS = max(0.0, _ADMISSION_TOKENS - 1.0)
    return True


def _record_invocation(queue_wait_ms: float | None = None) -> None:
    global _MODEL_INVOCATION_TOTAL
    with _LOCK:
        _MODEL_INVOCATION_TOTAL += 1
        if queue_wait_ms is not None and math.isfinite(queue_wait_ms) and queue_wait_ms >= 0:
            _QUEUE_WAIT_LATENCIES.append(queue_wait_ms)


def _record_failure(category: str, *, dropped: bool = False) -> None:
    global _FAILURE_TOTAL, _DROPPED_TOTAL, _EXPIRED_TOTAL, _SHUTDOWN_DROPPED_TOTAL
    allowed = {
        "overloaded", "shutting_down", "runtime_configuration",
        "contract_violation", "timeout", "configuration",
        "model_unavailable", "preservation_retry_failed", "internal_failure",
        "queue_full", "expired", "worker_unavailable", "shutdown_drop",
    }
    if category not in allowed:
        raise ValueError("unknown shadow failure category")
    with _LOCK:
        _FAILURE_TOTAL += 1
        _FAILURE_CATEGORIES[category] += 1
        if dropped:
            _DROPPED_TOTAL += 1
        if category == "expired":
            _EXPIRED_TOTAL += 1
        elif category == "shutdown_drop":
            _SHUTDOWN_DROPPED_TOTAL += 1


def _record_success(result: dict[str, Any]) -> None:
    global _SUCCESS_TOTAL, _RETRY_USED_TOTAL, _RETRY_RECOVERED_TOTAL
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


def _run_reserved(text: str, learner_level: str, *, queue_wait_ms: float | None = None) -> None:
    _record_invocation(queue_wait_ms)
    try:
        result = run_judgment(text, context=None, learner_level=learner_level)
    except JudgmentServiceError as exc:
        _record_failure(classify_failure(exc))
        return
    try:
        _record_success(result)
    except Exception:
        _record_failure("internal_failure")


def execute_shadow(text: str, learner_level: str) -> None:
    """Run one judgment directly for diagnostics; never propagate into /analyze."""
    try:
        with reserve_capacity():
            _run_reserved(text, learner_level)
    except JudgmentOverloadedError:
        _record_failure("overloaded")
    except JudgmentShuttingDownError:
        _record_failure("shutting_down")
    except JudgmentRuntimeConfigurationError:
        _record_failure("runtime_configuration")
    except Exception:
        _record_failure("internal_failure")


def _process_queued(item: ShadowItem) -> None:
    try:
        _, ttl = _queue_configuration()
    except JudgmentRuntimeConfigurationError:
        _record_failure("runtime_configuration", dropped=True)
        return
    expires_at = item.enqueued_at + ttl
    while True:
        now = time.monotonic()
        with _QUEUE_CONDITION:
            stop_deadline = _STOP_DEADLINE
        if now >= expires_at:
            _record_failure("expired", dropped=True)
            return
        if stop_deadline is not None and now >= stop_deadline:
            _record_failure("shutdown_drop", dropped=True)
            return
        try:
            with reserve_capacity():
                wait_ms = (time.monotonic() - item.enqueued_at) * 1000
                _run_reserved(item.text, item.learner_level, queue_wait_ms=wait_ms)
                return
        except JudgmentOverloadedError:
            time.sleep(min(_CAPACITY_RETRY_SECONDS, max(0.0, expires_at - time.monotonic())))
        except JudgmentShuttingDownError:
            _record_failure("shutting_down", dropped=True)
            return
        except JudgmentRuntimeConfigurationError:
            _record_failure("runtime_configuration", dropped=True)
            return
        except Exception:
            _record_failure("internal_failure")
            return


def _drop_pending(category: str) -> None:
    with _QUEUE_CONDITION:
        count = len(_QUEUE)
        _QUEUE.clear()
        _QUEUE_CONDITION.notify_all()
    for _ in range(count):
        _record_failure(category, dropped=True)


def _worker_loop() -> None:
    global _WORKER, _WORKER_ACTIVE
    try:
        while True:
            expired_without_run = False
            with _QUEUE_CONDITION:
                while not _QUEUE:
                    if not _QUEUE_ACCEPTING:
                        return
                    _QUEUE_CONDITION.wait()
                if _STOP_DEADLINE is not None and time.monotonic() >= _STOP_DEADLINE:
                    break
                item = _QUEUE.popleft()
                _WORKER_ACTIVE = True
                _QUEUE_CONDITION.notify_all()
            try:
                try:
                    _, ttl = _queue_configuration()
                    expired_without_run = time.monotonic() >= item.enqueued_at + ttl
                except JudgmentRuntimeConfigurationError:
                    _record_failure("runtime_configuration", dropped=True)
                    continue
                if expired_without_run:
                    _record_failure("expired", dropped=True)
                else:
                    _process_queued(item)
            finally:
                with _QUEUE_CONDITION:
                    _WORKER_ACTIVE = False
                    _QUEUE_CONDITION.notify_all()
            with _QUEUE_CONDITION:
                if not _QUEUE_ACCEPTING and not _QUEUE:
                    return
        _drop_pending("shutdown_drop")
    finally:
        with _QUEUE_CONDITION:
            _WORKER_ACTIVE = False
            _WORKER = None
            _QUEUE_CONDITION.notify_all()


def start_worker() -> bool:
    """Start the single shadow consumer only when both feature flags are enabled."""
    global _WORKER, _QUEUE_ACCEPTING, _STOP_DEADLINE
    global _ADMISSION_TOKENS, _ADMISSION_LAST_REFILL
    if not shadow_enabled():
        return False
    try:
        _queue_configuration()
        _, burst = _admission_configuration()
    except JudgmentRuntimeConfigurationError:
        return False
    with _QUEUE_CONDITION:
        if _WORKER is not None and _WORKER.is_alive():
            _QUEUE_ACCEPTING = True
            _STOP_DEADLINE = None
            return True
        _QUEUE_ACCEPTING = True
        _STOP_DEADLINE = None
        _ADMISSION_TOKENS = float(burst)
        _ADMISSION_LAST_REFILL = time.monotonic()
        _WORKER = threading.Thread(
            target=_worker_loop, name="judgment-shadow-worker", daemon=True
        )
        _WORKER.start()
        return True


def stop_worker(timeout: float) -> bool:
    """Stop accepting, drain within timeout, then drop remaining queued work."""
    global _QUEUE_ACCEPTING, _STOP_DEADLINE
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout < 0:
        raise ValueError("timeout must be nonnegative")
    deadline = time.monotonic() + float(timeout)
    with _QUEUE_CONDITION:
        _QUEUE_ACCEPTING = False
        _STOP_DEADLINE = deadline
        worker = _WORKER
        _QUEUE_CONDITION.notify_all()
    if worker is None:
        _drop_pending("shutdown_drop")
        return True
    worker.join(max(0.0, deadline - time.monotonic()))
    if worker.is_alive():
        _drop_pending("shutdown_drop")
        with _QUEUE_CONDITION:
            _STOP_DEADLINE = time.monotonic()
            _QUEUE_CONDITION.notify_all()
        return False
    return True


def enqueue_shadow(text: str, learner_level: str) -> bool:
    """Enqueue without blocking the response path; content remains process-local."""
    if learner_level not in {"N5", "N4"}:
        learner_level = "N5"
    try:
        capacity, _ = _queue_configuration()
        rate, burst = _admission_configuration()
    except JudgmentRuntimeConfigurationError:
        _record_failure("runtime_configuration", dropped=True)
        return False
    with _QUEUE_CONDITION:
        worker_running = _WORKER is not None and _WORKER.is_alive()
        if not _QUEUE_ACCEPTING or not worker_running:
            category = "shutting_down" if not _QUEUE_ACCEPTING else "worker_unavailable"
        elif not _take_admission_token(time.monotonic(), rate, burst):
            category = "sampled_out"
        elif len(_QUEUE) >= capacity:
            category = "queue_full"
        else:
            _QUEUE.append(ShadowItem(text, learner_level, time.monotonic()))
            _QUEUE_CONDITION.notify()
            category = None
    if category is not None:
        if category == "sampled_out":
            _record_sampled_out()
            return False
        _record_failure(category, dropped=True)
        return False
    _record_enqueued()
    return True


def schedule_shadow(
    background_tasks: BackgroundTasks,
    text: str,
    learner_level: str,
) -> bool:
    if not shadow_enabled():
        return False
    if not isinstance(text, str) or not text.strip():
        return False
    if learner_level not in {"N5", "N4"}:
        learner_level = "N5"
    _record_scheduled()
    background_tasks.add_task(enqueue_shadow, text, learner_level)
    return True


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * quantile) - 1)
    return round(ordered[index], 3)


def _latency_summary(values: list[float]) -> dict[str, int | float | None]:
    return {
        "sample_count": len(values),
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "max": round(max(values), 3) if values else None,
    }


def snapshot() -> dict[str, Any]:
    try:
        capacity, ttl = _queue_configuration()
        admission_rate, admission_burst = _admission_configuration()
        configuration_valid = True
    except JudgmentRuntimeConfigurationError:
        capacity = None
        ttl = None
        admission_rate = None
        admission_burst = None
        configuration_valid = False
    with _QUEUE_CONDITION:
        queue_depth = len(_QUEUE)
        worker_running = _WORKER is not None and _WORKER.is_alive()
        worker_active = _WORKER_ACTIVE
        accepting = _QUEUE_ACCEPTING
        admission_tokens = round(_ADMISSION_TOKENS, 6)
    with _LOCK:
        latencies = list(_LATENCIES)
        queue_waits = list(_QUEUE_WAIT_LATENCIES)
        return {
            "schema_version": SCHEMA_VERSION,
            "enabled": shadow_enabled(),
            "configuration_valid": configuration_valid,
            "accepting": accepting,
            "worker_running": worker_running,
            "worker_active": worker_active,
            "queue_capacity": capacity,
            "queue_depth": queue_depth,
            "item_ttl_seconds": ttl,
            "admission_rate_per_second": admission_rate,
            "admission_burst": admission_burst,
            "admission_tokens": admission_tokens,
            "admission_jitter_tolerance_seconds": _ADMISSION_JITTER_TOLERANCE_SECONDS,
            "scheduled_total": _SCHEDULED_TOTAL,
            "enqueued_total": _ENQUEUED_TOTAL,
            "model_invocation_total": _MODEL_INVOCATION_TOTAL,
            "success_total": _SUCCESS_TOTAL,
            "failure_total": _FAILURE_TOTAL,
            "dropped_total": _DROPPED_TOTAL,
            "expired_total": _EXPIRED_TOTAL,
            "shutdown_dropped_total": _SHUTDOWN_DROPPED_TOTAL,
            "sampled_out_total": _SAMPLED_OUT_TOTAL,
            "decision_counts": dict(_DECISIONS),
            "failure_categories": dict(_FAILURE_CATEGORIES),
            "retry_used_total": _RETRY_USED_TOTAL,
            "retry_recovered_total": _RETRY_RECOVERED_TOTAL,
            "latency_ms": _latency_summary(latencies),
            "queue_wait_latency_ms": _latency_summary(queue_waits),
            "persists_results": False,
            "affects_analyze_response": False,
            "contains_request_content": False,
        }


def reset_for_tests() -> None:
    global _SCHEDULED_TOTAL, _ENQUEUED_TOTAL, _MODEL_INVOCATION_TOTAL
    global _SUCCESS_TOTAL, _FAILURE_TOTAL, _DROPPED_TOTAL, _EXPIRED_TOTAL
    global _SHUTDOWN_DROPPED_TOTAL, _SAMPLED_OUT_TOTAL
    global _RETRY_USED_TOTAL, _RETRY_RECOVERED_TOTAL
    global _ADMISSION_TOKENS, _ADMISSION_LAST_REFILL
    global _QUEUE_ACCEPTING, _STOP_DEADLINE, _WORKER_ACTIVE, _WORKER
    stop_worker(0)
    with _QUEUE_CONDITION:
        _QUEUE.clear()
        _QUEUE_ACCEPTING = False
        _STOP_DEADLINE = None
        _WORKER_ACTIVE = False
        _ADMISSION_TOKENS = 0.0
        _ADMISSION_LAST_REFILL = None
        if _WORKER is not None and not _WORKER.is_alive():
            _WORKER = None
    with _LOCK:
        _SCHEDULED_TOTAL = 0
        _ENQUEUED_TOTAL = 0
        _MODEL_INVOCATION_TOTAL = 0
        _SUCCESS_TOTAL = 0
        _FAILURE_TOTAL = 0
        _DROPPED_TOTAL = 0
        _EXPIRED_TOTAL = 0
        _SHUTDOWN_DROPPED_TOTAL = 0
        _SAMPLED_OUT_TOTAL = 0
        _DECISIONS.clear()
        _FAILURE_CATEGORIES.clear()
        _LATENCIES.clear()
        _QUEUE_WAIT_LATENCIES.clear()
        _RETRY_USED_TOTAL = 0
        _RETRY_RECOVERED_TOTAL = 0

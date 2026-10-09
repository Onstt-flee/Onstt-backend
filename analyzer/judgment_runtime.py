"""Process-local capacity, readiness, and shutdown controls for judgment."""

from __future__ import annotations

import json
import math
import os
import threading
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from analyzer.judgment_service import DEFAULT_MODEL, judgment_enabled
from evaluation.judgment.runner import DEFAULT_ENDPOINT


READINESS_SCHEMA_VERSION = "judgment-readiness-v0.1"
Opener = Callable[..., Any]


class JudgmentCapacityError(RuntimeError):
    """Base class for safe capacity-control failures."""


class JudgmentOverloadedError(JudgmentCapacityError):
    """No model execution slot became available within the configured wait."""


class JudgmentShuttingDownError(JudgmentCapacityError):
    """The process is draining and does not accept new judgment work."""


class JudgmentRuntimeConfigurationError(JudgmentCapacityError):
    """Runtime capacity configuration is invalid."""


_CONDITION = threading.Condition()
_ACCEPTING = True
_ACTIVE = 0


def _positive_int(name: str, default: str) -> int:
    raw = os.getenv(name, default)
    try:
        value = int(raw)
    except ValueError as exc:
        raise JudgmentRuntimeConfigurationError(f"Invalid {name}") from exc
    if value <= 0:
        raise JudgmentRuntimeConfigurationError(f"Invalid {name}")
    return value


def _nonnegative_float(name: str, default: str) -> float:
    raw = os.getenv(name, default)
    try:
        value = float(raw)
    except ValueError as exc:
        raise JudgmentRuntimeConfigurationError(f"Invalid {name}") from exc
    if not math.isfinite(value) or value < 0:
        raise JudgmentRuntimeConfigurationError(f"Invalid {name}")
    return value


def runtime_snapshot() -> dict[str, Any]:
    with _CONDITION:
        accepting = _ACCEPTING
        active = _ACTIVE
    try:
        maximum = _positive_int("JUDGMENT_MAX_CONCURRENCY", "4")
        queue_timeout = _nonnegative_float("JUDGMENT_QUEUE_TIMEOUT_SECONDS", "0")
        configuration_valid = True
    except JudgmentRuntimeConfigurationError:
        maximum = None
        queue_timeout = None
        configuration_valid = False
    return {
        "accepting": accepting,
        "active_requests": active,
        "max_concurrency": maximum,
        "queue_timeout_seconds": queue_timeout,
        "configuration_valid": configuration_valid,
    }


@contextmanager
def reserve_capacity() -> Iterator[None]:
    global _ACTIVE
    maximum = _positive_int("JUDGMENT_MAX_CONCURRENCY", "4")
    wait_seconds = _nonnegative_float("JUDGMENT_QUEUE_TIMEOUT_SECONDS", "0")
    deadline = time.monotonic() + wait_seconds
    with _CONDITION:
        while True:
            if not _ACCEPTING:
                raise JudgmentShuttingDownError("Judgment service is shutting down")
            if _ACTIVE < maximum:
                _ACTIVE += 1
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JudgmentOverloadedError("Judgment service is at capacity")
            _CONDITION.wait(remaining)
    try:
        yield
    finally:
        with _CONDITION:
            _ACTIVE -= 1
            _CONDITION.notify_all()


def set_accepting(value: bool) -> None:
    global _ACCEPTING
    with _CONDITION:
        _ACCEPTING = bool(value)
        _CONDITION.notify_all()


def wait_for_idle(timeout: float) -> bool:
    if timeout < 0:
        raise ValueError("timeout must be nonnegative")
    deadline = time.monotonic() + timeout
    with _CONDITION:
        while _ACTIVE:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            _CONDITION.wait(remaining)
        return True


def _read_json(url: str, opener: Opener, timeout: float) -> Any:
    request = urllib.request.Request(url, method="GET")
    with opener(request, timeout=timeout) as response:
        body = response.read()
    return json.loads(body.decode("utf-8")) if body else None


def readiness_snapshot(*, opener: Opener = urllib.request.urlopen) -> dict[str, Any]:
    runtime = runtime_snapshot()
    enabled = judgment_enabled()
    result = {
        "schema_version": READINESS_SCHEMA_VERSION,
        "ready": False,
        "reason": "disabled",
        "enabled": enabled,
        "accepting": runtime["accepting"],
        "active_requests": runtime["active_requests"],
        "max_concurrency": runtime["max_concurrency"],
        "model_health": False,
        "model_alias_present": False,
        "contains_request_content": False,
    }
    if not enabled:
        return result
    if not runtime["configuration_valid"]:
        result["reason"] = "invalid_configuration"
        return result
    if not runtime["accepting"]:
        result["reason"] = "shutting_down"
        return result
    try:
        timeout = _nonnegative_float("JUDGMENT_READINESS_TIMEOUT_SECONDS", "2")
        if timeout == 0:
            raise JudgmentRuntimeConfigurationError(
                "Invalid JUDGMENT_READINESS_TIMEOUT_SECONDS"
            )
        endpoint = os.getenv("JUDGMENT_ENDPOINT", DEFAULT_ENDPOINT)
        parsed = urllib.parse.urlsplit(endpoint)
        model_base = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, "", "", "")
        ).rstrip("/")
        _read_json(f"{model_base}/health", opener, timeout)
        result["model_health"] = True
        models = _read_json(f"{model_base}/v1/models", opener, timeout)
        model_name = os.getenv("JUDGMENT_MODEL", DEFAULT_MODEL)
        ids = []
        if isinstance(models, dict) and isinstance(models.get("data"), list):
            ids = [
                item.get("id") for item in models["data"] if isinstance(item, dict)
            ]
        result["model_alias_present"] = model_name in ids
        if not result["model_alias_present"]:
            result["reason"] = "model_alias_missing"
            return result
    except JudgmentRuntimeConfigurationError:
        result["reason"] = "invalid_configuration"
        return result
    except Exception:
        result["reason"] = "model_unavailable"
        return result
    result["ready"] = True
    result["reason"] = "ready"
    return result


def reset_for_tests() -> None:
    global _ACCEPTING, _ACTIVE
    with _CONDITION:
        _ACCEPTING = True
        _ACTIVE = 0
        _CONDITION.notify_all()

"""Content-free OFF/ON load probe for /analyze judgment shadow integration."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "analyze-shadow-load-v0.1"
DEFAULT_API_BASE = "http://127.0.0.1:8001"
Opener = Callable[..., Any]


@dataclass(frozen=True)
class Attempt:
    ok: bool
    status: int
    latency_ms: float
    contract_valid: bool
    error_category: str | None


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * quantile) - 1)
    return round(ordered[index], 3)


def _valid_analysis_contract(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    required = {
        "id", "utterance_id", "primary_type", "candidate_types",
        "classification_reason", "needs_deep_analysis", "is_correct",
        "corrected_text", "error_types", "feedback_ko", "feedback_ja",
        "created_at",
    }
    forbidden = {
        "decision", "strategy", "contract_version", "edits", "reason_ko",
        "selection_reason", "learner_level",
    }
    return (
        required.issubset(payload)
        and not forbidden.intersection(payload)
        and isinstance(payload.get("corrected_text"), str)
        and isinstance(payload.get("candidate_types"), str)
        and isinstance(payload.get("error_types"), str)
    )


def _request_json(url: str, *, method: str, timeout: float, opener: Opener) -> tuple[int, Any]:
    request = urllib.request.Request(url, method=method)
    with opener(request, timeout=timeout) as response:
        status = int(getattr(response, "status", 200))
        body = response.read()
    return status, json.loads(body.decode("utf-8")) if body else None


def _one_request(url: str, *, timeout: float, opener: Opener) -> Attempt:
    started = time.perf_counter()
    try:
        status, payload = _request_json(
            url, method="POST", timeout=timeout, opener=opener
        )
        latency_ms = (time.perf_counter() - started) * 1000
        valid = _valid_analysis_contract(payload)
        return Attempt(
            ok=status == 200 and valid,
            status=status,
            latency_ms=latency_ms,
            contract_valid=valid,
            error_category=None if valid else "contract_invalid",
        )
    except urllib.error.HTTPError as exc:
        return Attempt(
            False, exc.code, (time.perf_counter() - started) * 1000,
            False, f"http_{exc.code}",
        )
    except TimeoutError:
        return Attempt(
            False, 0, (time.perf_counter() - started) * 1000,
            False, "timeout",
        )
    except Exception as exc:
        category = "timeout" if "timed out" in str(exc).lower() else "transport"
        return Attempt(
            False, 0, (time.perf_counter() - started) * 1000,
            False, category,
        )


def run_phase(
    *,
    api_base: str,
    utterance_ids: list[int],
    concurrency: int,
    request_count: int,
    timeout: float,
    opener: Opener = urllib.request.urlopen,
) -> dict[str, Any]:
    if concurrency < 1 or request_count < 1 or not utterance_ids:
        raise ValueError("concurrency, request_count, and utterance_ids must be positive")
    urls = [
        f"{api_base.rstrip('/')}/utterances/"
        f"{utterance_ids[index % len(utterance_ids)]}/analyze"
        for index in range(request_count)
    ]
    started = time.perf_counter()
    attempts: list[Attempt] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(_one_request, url, timeout=timeout, opener=opener)
            for url in urls
        ]
        for future in as_completed(futures):
            attempts.append(future.result())
    elapsed = time.perf_counter() - started
    latencies = [item.latency_ms for item in attempts]
    successes = sum(item.ok for item in attempts)
    statuses: dict[str, int] = {}
    categories: dict[str, int] = {}
    for item in attempts:
        statuses[str(item.status)] = statuses.get(str(item.status), 0) + 1
        if item.error_category:
            categories[item.error_category] = categories.get(item.error_category, 0) + 1
    return {
        "concurrency": concurrency,
        "request_count": request_count,
        "success_count": successes,
        "failure_count": request_count - successes,
        "contract_valid_count": sum(item.contract_valid for item in attempts),
        "status_counts": statuses,
        "error_categories": categories,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_rps": round(request_count / elapsed, 3),
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "max": round(max(latencies), 3),
        },
    }


def _monitor(api_base: str, timeout: float, opener: Opener) -> dict[str, Any]:
    status, payload = _request_json(
        f"{api_base.rstrip('/')}/health/judgment",
        method="GET", timeout=timeout, opener=opener,
    )
    if status != 200 or not isinstance(payload, dict) or not isinstance(payload.get("shadow"), dict):
        raise RuntimeError("judgment shadow monitor is unavailable")
    return payload["shadow"]


def _monitor_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    scalar_keys = (
        "scheduled_total", "enqueued_total", "model_invocation_total",
        "success_total", "failure_total", "dropped_total", "expired_total",
        "shutdown_dropped_total", "sampled_out_total", "retry_used_total",
        "retry_recovered_total",
    )
    result = {
        key: int(after.get(key, 0)) - int(before.get(key, 0))
        for key in scalar_keys
    }
    result["decision_counts"] = {
        key: int(after.get("decision_counts", {}).get(key, 0))
        - int(before.get("decision_counts", {}).get(key, 0))
        for key in sorted(set(before.get("decision_counts", {})) | set(after.get("decision_counts", {})))
    }
    result["decision_counts"] = {k: v for k, v in result["decision_counts"].items() if v}
    result["failure_categories"] = {
        key: int(after.get("failure_categories", {}).get(key, 0))
        - int(before.get("failure_categories", {}).get(key, 0))
        for key in sorted(set(before.get("failure_categories", {})) | set(after.get("failure_categories", {})))
    }
    result["failure_categories"] = {k: v for k, v in result["failure_categories"].items() if v}
    result["enabled"] = bool(after.get("enabled"))
    result["configuration_valid"] = bool(after.get("configuration_valid", True))
    result["accepting"] = bool(after.get("accepting", after.get("enabled")))
    result["worker_running"] = bool(after.get("worker_running", after.get("enabled")))
    result["worker_active"] = bool(after.get("worker_active", False))
    result["queue_capacity"] = after.get("queue_capacity")
    result["queue_depth"] = int(after.get("queue_depth", 0))
    result["item_ttl_seconds"] = after.get("item_ttl_seconds")
    result["admission_rate_per_second"] = after.get("admission_rate_per_second")
    result["admission_burst"] = after.get("admission_burst")
    result["admission_tokens"] = after.get("admission_tokens")
    result["admission_jitter_tolerance_seconds"] = after.get(
        "admission_jitter_tolerance_seconds"
    )
    result["persists_results"] = bool(after.get("persists_results"))
    result["affects_analyze_response"] = bool(after.get("affects_analyze_response"))
    result["contains_request_content"] = bool(after.get("contains_request_content"))
    result["latency_ms"] = after.get("latency_ms")
    result["queue_wait_latency_ms"] = after.get("queue_wait_latency_ms")
    return result


def _wait_for_shadow(
    *, api_base: str, expected: int, before: dict[str, Any], timeout: float,
    opener: Opener,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    latest = before
    while time.monotonic() < deadline:
        latest = _monitor(api_base, min(timeout, 5.0), opener)
        delta = _monitor_delta(before, latest)
        complete = (
            delta["success_total"] + delta["failure_total"]
            + delta["sampled_out_total"]
        )
        if delta["scheduled_total"] >= expected and complete >= delta["scheduled_total"]:
            return latest
        time.sleep(0.1)
    raise TimeoutError("shadow tasks did not complete before timeout")


def database_snapshot(path: Path) -> dict[str, int]:
    resolved = path.resolve()
    connection = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        analyses = connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        judgments = connection.execute("SELECT COUNT(*) FROM judgment_results").fetchone()[0]
    finally:
        connection.close()
    return {"analyses": analyses, "judgment_results": judgments}


def run_probe(
    *, api_base: str, utterance_ids: list[int], phases: list[tuple[int, int]],
    timeout: float, expect_shadow: bool, database_path: Path,
    opener: Opener = urllib.request.urlopen,
) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    monitor_before = _monitor(api_base, min(timeout, 5.0), opener)
    database_before = database_snapshot(database_path)
    phase_results = [
        run_phase(
            api_base=api_base, utterance_ids=utterance_ids,
            concurrency=concurrency, request_count=request_count,
            timeout=timeout, opener=opener,
        )
        for concurrency, request_count in phases
    ]
    total = sum(item["request_count"] for item in phase_results)
    successes = sum(item["success_count"] for item in phase_results)
    if expect_shadow:
        monitor_after = _wait_for_shadow(
            api_base=api_base, expected=successes, before=monitor_before,
            timeout=timeout, opener=opener,
        )
    else:
        monitor_after = _monitor(api_base, min(timeout, 5.0), opener)
    database_after = database_snapshot(database_path)
    shadow = _monitor_delta(monitor_before, monitor_after)
    database_delta = {
        key: database_after[key] - database_before[key] for key in database_before
    }
    identity = json.dumps(
        {"utterance_ids": utterance_ids, "phases": phases},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    passed = (
        successes == total
        and sum(item["contract_valid_count"] for item in phase_results) == total
        and database_delta["analyses"] == total
        and database_delta["judgment_results"] == 0
        and shadow["contains_request_content"] is False
        and shadow["persists_results"] is False
        and shadow["affects_analyze_response"] is False
        and (
            shadow["scheduled_total"] == total
            and shadow["enqueued_total"] == total
            and shadow["model_invocation_total"] == total
            and shadow["success_total"] == total
            and shadow["failure_total"] == 0
            and shadow["dropped_total"] == 0
            and shadow["queue_depth"] == 0
            and shadow["configuration_valid"] is True
            and shadow["worker_running"] is True
            if expect_shadow else (
                shadow["scheduled_total"] == 0
                and shadow["enqueued_total"] == 0
                and shadow["model_invocation_total"] == 0
            )
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "passed": passed,
        "mode": "shadow_on" if expect_shadow else "shadow_off",
        "contains_request_or_response_content": False,
        "input_plan_sha256": hashlib.sha256(identity).hexdigest(),
        "total_requests": total,
        "success_count": successes,
        "failure_count": total - successes,
        "database_delta": database_delta,
        "shadow_delta": shadow,
        "phases": phase_results,
    }


def _parse_phase(value: str) -> tuple[int, int]:
    try:
        concurrency, requests = (int(part) for part in value.split(":", 1))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("phase must be CONCURRENCY:REQUESTS") from exc
    if concurrency < 1 or requests < 1:
        raise argparse.ArgumentTypeError("phase values must be positive")
    return concurrency, requests


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--utterance-id", type=int, action="append", required=True)
    parser.add_argument("--phase", type=_parse_phase, action="append")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--expect-shadow", action="store_true")
    args = parser.parse_args()
    result = run_probe(
        api_base=args.api_base,
        utterance_ids=args.utterance_id,
        phases=args.phase or [(1, 6), (2, 8), (4, 12)],
        timeout=args.timeout,
        expect_shadow=args.expect_shadow,
        database_path=args.database,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

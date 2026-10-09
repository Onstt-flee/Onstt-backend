"""Content-free arrival-rate probe for the bounded /analyze shadow queue."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

from scripts.run_analyze_shadow_load import (
    DEFAULT_API_BASE,
    _monitor,
    _monitor_delta,
    _one_request,
    _percentile,
    database_snapshot,
)


SCHEMA_VERSION = "analyze-shadow-rate-probe-v0.2"
Opener = Callable[..., Any]


def _wait_terminal(
    *, api_base: str, expected: int, before: dict[str, Any], timeout: float,
    opener: Opener,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    latest = before
    while time.monotonic() < deadline:
        latest = _monitor(api_base, min(timeout, 5.0), opener)
        delta = _monitor_delta(before, latest)
        terminal = (
            delta["success_total"] + delta["failure_total"]
            + delta["sampled_out_total"]
        )
        if (
            delta["scheduled_total"] >= expected
            and terminal >= delta["scheduled_total"]
            and delta["queue_depth"] == 0
            and not delta["worker_active"]
        ):
            return latest
        time.sleep(0.05)
    raise TimeoutError("shadow rate phase did not reach a terminal state")


def run_rate_phase(
    *, api_base: str, utterance_ids: list[int], target_rps: float,
    request_count: int, mode: str, timeout: float, database_path: Path,
    opener: Opener = urllib.request.urlopen,
) -> dict[str, Any]:
    if not utterance_ids or target_rps <= 0 or request_count <= 0 or timeout <= 0:
        raise ValueError("utterance_ids, target_rps, request_count, and timeout must be positive")
    if mode not in {"stable", "drop", "sample"}:
        raise ValueError("mode must be stable, drop, or sample")
    monitor_before = _monitor(api_base, min(timeout, 5.0), opener)
    database_before = database_snapshot(database_path)
    attempts = []
    issued_at: list[float] = []
    started = time.monotonic()
    for index in range(request_count):
        target = started + index / target_rps
        remaining = target - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        utterance_id = utterance_ids[index % len(utterance_ids)]
        issued_at.append(time.monotonic())
        attempts.append(_one_request(
            f"{api_base.rstrip('/')}/utterances/{utterance_id}/analyze",
            timeout=timeout,
            opener=opener,
        ))
    delivered_at = time.monotonic()
    monitor_delivered = _monitor(api_base, min(timeout, 5.0), opener)
    monitor_after = _wait_terminal(
        api_base=api_base,
        expected=request_count,
        before=monitor_before,
        timeout=timeout,
        opener=opener,
    )
    completed_at = time.monotonic()
    database_after = database_snapshot(database_path)
    shadow = _monitor_delta(monitor_before, monitor_after)
    delivered = _monitor_delta(monitor_before, monitor_delivered)
    database_delta = {
        key: database_after[key] - database_before[key] for key in database_before
    }
    successes = sum(item.ok for item in attempts)
    latencies = [item.latency_ms for item in attempts]
    status_counts: dict[str, int] = {}
    error_categories: dict[str, int] = {}
    for item in attempts:
        status_counts[str(item.status)] = status_counts.get(str(item.status), 0) + 1
        if item.error_category:
            error_categories[item.error_category] = error_categories.get(item.error_category, 0) + 1
    common = (
        successes == request_count
        and sum(item.contract_valid for item in attempts) == request_count
        and database_delta == {"analyses": request_count, "judgment_results": 0}
        and shadow["scheduled_total"] == request_count
        and shadow["success_total"] + shadow["failure_total"]
        + shadow["sampled_out_total"] == request_count
        and shadow["queue_depth"] == 0
        and shadow["configuration_valid"] is True
        and shadow["persists_results"] is False
        and shadow["affects_analyze_response"] is False
        and shadow["contains_request_content"] is False
    )
    if mode == "drop":
        queue_failures = sum(
            count for category, count in shadow["failure_categories"].items()
            if category in {"queue_full", "expired"}
        )
        mode_ok = (
            shadow["sampled_out_total"] == 0
            and shadow["dropped_total"] > 0
            and queue_failures == shadow["failure_total"] == shadow["dropped_total"]
            and set(shadow["failure_categories"]).issubset({"queue_full", "expired"})
            and shadow["model_invocation_total"] == shadow["success_total"]
        )
    elif mode == "sample":
        mode_ok = (
            shadow["sampled_out_total"] > 0
            and shadow["enqueued_total"] == shadow["success_total"]
            and shadow["model_invocation_total"] == shadow["success_total"]
            and shadow["success_total"] + shadow["sampled_out_total"] == request_count
            and shadow["failure_total"] == 0
            and shadow["dropped_total"] == 0
            and shadow["expired_total"] == 0
            and not shadow["failure_categories"]
        )
    else:
        mode_ok = (
            shadow["sampled_out_total"] == 0
            and shadow["enqueued_total"] == request_count
            and shadow["model_invocation_total"] == request_count
            and shadow["success_total"] == request_count
            and shadow["failure_total"] == 0
            and shadow["dropped_total"] == 0
        )
    delivery_seconds = delivered_at - started
    arrival_span_seconds = (
        issued_at[-1] - issued_at[0] if len(issued_at) > 1 else 0.0
    )
    actual_delivery_rps = (
        (request_count - 1) / arrival_span_seconds
        if request_count > 1 and arrival_span_seconds > 0 else None
    )
    total_seconds = completed_at - started
    return {
        "passed": common and mode_ok,
        "target_rps": target_rps,
        "request_count": request_count,
        "mode": mode,
        "response_success_count": successes,
        "response_failure_count": request_count - successes,
        "contract_valid_count": sum(item.contract_valid for item in attempts),
        "status_counts": status_counts,
        "error_categories": error_categories,
        "delivery_seconds": round(delivery_seconds, 3),
        "arrival_span_seconds": round(arrival_span_seconds, 3),
        "actual_delivery_rps": (
            round(actual_delivery_rps, 3) if actual_delivery_rps is not None else None
        ),
        "terminal_seconds": round(total_seconds, 3),
        "response_latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "max": round(max(latencies), 3),
        },
        "queue_depth_after_delivery": delivered["queue_depth"],
        "latency_scope": "process_cumulative_since_api_start",
        "database_delta": database_delta,
        "shadow_delta": shadow,
    }


def run_probe(
    *, api_base: str, utterance_ids: list[int],
    phases: list[tuple[float, int, str]], timeout: float, database_path: Path,
    phase_cooldown: float = 0.0, opener: Opener = urllib.request.urlopen,
) -> dict[str, Any]:
    if phase_cooldown < 0:
        raise ValueError("phase_cooldown must be nonnegative")
    results = []
    for index, (rate, count, mode) in enumerate(phases):
        if index and phase_cooldown:
            time.sleep(phase_cooldown)
        results.append(run_rate_phase(
            api_base=api_base,
            utterance_ids=utterance_ids,
            target_rps=rate,
            request_count=count,
            mode=mode,
            timeout=timeout,
            database_path=database_path,
            opener=opener,
        ))
    identity = json.dumps(
        {"utterance_ids": utterance_ids, "phases": phases,
         "phase_cooldown_seconds": phase_cooldown},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    return {
        "schema_version": SCHEMA_VERSION,
        "passed": all(item["passed"] for item in results),
        "contains_request_or_response_content": False,
        "phase_cooldown_seconds": phase_cooldown,
        "input_plan_sha256": hashlib.sha256(identity).hexdigest(),
        "phases": results,
    }


def _parse_phase(value: str, mode: str) -> tuple[float, int, str]:
    try:
        rate, count = value.split(":", 1)
        parsed = (float(rate), int(count), mode)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("phase must be RATE:REQUESTS") from exc
    if parsed[0] <= 0 or parsed[1] <= 0:
        raise argparse.ArgumentTypeError("phase values must be positive")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--utterance-id", type=int, action="append", required=True)
    parser.add_argument("--stable-phase", action="append", default=[])
    parser.add_argument("--drop-phase", action="append", default=[])
    parser.add_argument("--sample-phase", action="append", default=[])
    parser.add_argument("--phase-cooldown", type=float, default=1.1)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    phases = [
        _parse_phase(value, "stable") for value in args.stable_phase
    ] + [
        _parse_phase(value, "drop") for value in args.drop_phase
    ] + [
        _parse_phase(value, "sample") for value in args.sample_phase
    ]
    if not phases:
        phases = [(0.5, 4, "stable"), (1.0, 6, "stable"), (2.0, 10, "sample")]
    result = run_probe(
        api_base=args.api_base,
        utterance_ids=args.utterance_id,
        phases=phases,
        timeout=args.timeout,
        database_path=args.database,
        phase_cooldown=args.phase_cooldown,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

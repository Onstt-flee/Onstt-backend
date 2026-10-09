"""Bounded HTTP load probe for the feature-flagged judgment staging API.

The probe never prints request or response content.  It expects synthetic
utterance IDs that already exist in an isolated staging database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable


SCHEMA_VERSION = "judgment-staging-http-load-v0.1"
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


def _valid_contract(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    required = {
        "decision",
        "corrected_text",
        "edits",
        "error_types",
        "reason_ko",
        "strategy",
        "model_name",
        "adapter_name",
        "selection_reason",
        "contract_version",
        "latency_ms",
        "created_at",
    }
    return (
        required.issubset(payload)
        and payload.get("decision")
        in {"acceptable", "needs_correction", "insufficient_evidence"}
        and isinstance(payload.get("corrected_text"), str)
        and isinstance(payload.get("edits"), list)
        and isinstance(payload.get("error_types"), list)
        and payload.get("strategy") == "d_only"
        and payload.get("contract_version") == "judgment-v0.2"
    )


def _one_request(
    url: str,
    *,
    timeout: float,
    opener: Opener,
) -> Attempt:
    body = json.dumps(
        {"context": None, "learner_level": "N5"}, ensure_ascii=False
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with opener(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            payload = json.loads(response.read().decode("utf-8"))
        latency_ms = (time.perf_counter() - started) * 1000
        valid = _valid_contract(payload)
        return Attempt(
            ok=status == 200 and valid,
            status=status,
            latency_ms=latency_ms,
            contract_valid=valid,
            error_category=None if valid else "contract_invalid",
        )
    except urllib.error.HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return Attempt(False, exc.code, latency_ms, False, f"http_{exc.code}")
    except TimeoutError:
        latency_ms = (time.perf_counter() - started) * 1000
        return Attempt(False, 0, latency_ms, False, "timeout")
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        category = "timeout" if "timed out" in str(exc).lower() else "transport"
        return Attempt(False, 0, latency_ms, False, category)


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
        f"{utterance_ids[index % len(utterance_ids)]}/judgment"
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
    elapsed_seconds = time.perf_counter() - started
    latencies = [item.latency_ms for item in attempts]
    successes = sum(item.ok for item in attempts)
    categories: dict[str, int] = {}
    statuses: dict[str, int] = {}
    for item in attempts:
        statuses[str(item.status)] = statuses.get(str(item.status), 0) + 1
        if item.error_category:
            categories[item.error_category] = categories.get(item.error_category, 0) + 1
    return {
        "concurrency": concurrency,
        "request_count": request_count,
        "success_count": successes,
        "failure_count": request_count - successes,
        "success_rate": round(successes / request_count, 6),
        "contract_valid_count": sum(item.contract_valid for item in attempts),
        "status_counts": statuses,
        "error_categories": categories,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "throughput_rps": round(request_count / elapsed_seconds, 3),
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "max": round(max(latencies), 3),
        },
    }


def run_probe(
    *,
    api_base: str,
    utterance_ids: list[int],
    phases: list[tuple[int, int]],
    timeout: float,
    opener: Opener = urllib.request.urlopen,
) -> dict[str, Any]:
    phase_results = [
        run_phase(
            api_base=api_base,
            utterance_ids=utterance_ids,
            concurrency=concurrency,
            request_count=request_count,
            timeout=timeout,
            opener=opener,
        )
        for concurrency, request_count in phases
    ]
    total = sum(item["request_count"] for item in phase_results)
    successes = sum(item["success_count"] for item in phase_results)
    identity = json.dumps(
        {"utterance_ids": utterance_ids, "phases": phases},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "measurement_scope": "live_fastapi_vllm_http_staging_load",
        "contains_request_or_response_content": False,
        "input_plan_sha256": hashlib.sha256(identity).hexdigest(),
        "api_base": api_base,
        "timeout_seconds": timeout,
        "total_requests": total,
        "success_count": successes,
        "failure_count": total - successes,
        "success_rate": round(successes / total, 6),
        "phases": phase_results,
    }


def _parse_phase(value: str) -> tuple[int, int]:
    try:
        concurrency, request_count = (int(part) for part in value.split(":", 1))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("phase must be CONCURRENCY:REQUESTS") from exc
    if concurrency < 1 or request_count < 1:
        raise argparse.ArgumentTypeError("phase values must be positive")
    return concurrency, request_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--utterance-id", type=int, action="append", required=True)
    parser.add_argument(
        "--phase",
        type=_parse_phase,
        action="append",
        default=None,
        help="CONCURRENCY:REQUESTS; repeat for multiple phases",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    phases = args.phase or [(1, 6), (2, 8), (4, 12)]
    result = run_probe(
        api_base=args.api_base,
        utterance_ids=args.utterance_id,
        phases=phases,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["failure_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

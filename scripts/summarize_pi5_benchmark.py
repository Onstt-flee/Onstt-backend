"""Create a content-free Pi latency/contract acceptance summary."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def validated_sha256(value: str) -> str:
    if not SHA256_RE.fullmatch(value):
        raise ValueError("artifact hashes must be lowercase SHA-256 values")
    return value


def build_report(
    records: list[dict], *, memory_peak_bytes: int, throttled_before: str,
    throttled_after: str, quantization: str, model_sha256: str,
    adapter_sha256: str, run_sha256: str,
) -> dict:
    latencies = [
        float(row["response"]["latency_ms"])
        for row in records
        if row.get("response", {}).get("contract_valid")
        and isinstance(row["response"].get("latency_ms"), (int, float))
    ]
    valid = sum(bool(row.get("response", {}).get("contract_valid")) for row in records)
    p95 = percentile(latencies, 0.95)
    passed = (
        len(records) == 50
        and valid == 50
        and p95 is not None and p95 <= 45000
        and 0 < memory_peak_bytes <= 10 * 1024 ** 3
        and throttled_before == "throttled=0x0"
        and throttled_after == "throttled=0x0"
    )
    return {
        "schema_version": "pi5-benchmark-summary-v0.2",
        "passed": passed,
        "sample_count": len(records),
        "contract_valid": valid,
        "latency_ms": {
            "p50": percentile(latencies, 0.50),
            "p95": p95,
            "max": max(latencies) if latencies else None,
        },
        "memory_peak_bytes": memory_peak_bytes,
        "throttled_before": throttled_before,
        "throttled_after": throttled_after,
        "artifacts": {
            "quantization": quantization,
            "model_sha256": validated_sha256(model_sha256),
            "adapter_sha256": validated_sha256(adapter_sha256),
            "raw_run_sha256": validated_sha256(run_sha256),
        },
        "contains_request_content": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--memory-peak-bytes", type=int, required=True)
    parser.add_argument("--throttled-before", required=True)
    parser.add_argument("--throttled-after", required=True)
    parser.add_argument("--quantization", choices=("Q4_K_M", "Q5_K_M"), required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--adapter-sha256", required=True)
    args = parser.parse_args()
    run_bytes = args.run.read_bytes()
    records = [
        json.loads(line) for line in run_bytes.decode("utf-8").splitlines() if line
    ]
    report = build_report(
        records,
        memory_peak_bytes=args.memory_peak_bytes,
        throttled_before=args.throttled_before,
        throttled_after=args.throttled_after,
        quantization=args.quantization,
        model_sha256=args.model_sha256,
        adapter_sha256=args.adapter_sha256,
        run_sha256=hashlib.sha256(run_bytes).hexdigest(),
    )
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

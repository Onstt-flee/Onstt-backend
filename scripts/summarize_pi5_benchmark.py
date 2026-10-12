"""Create a content-free Pi latency/contract acceptance summary."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--memory-peak-bytes", type=int, required=True)
    parser.add_argument("--throttled-before", required=True)
    parser.add_argument("--throttled-after", required=True)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.run.read_text(encoding="utf-8").splitlines() if line]
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
        and args.memory_peak_bytes <= 10 * 1024 ** 3
        and args.throttled_before == "throttled=0x0"
        and args.throttled_after == "throttled=0x0"
    )
    report = {
        "schema_version": "pi5-benchmark-summary-v0.1",
        "passed": passed,
        "sample_count": len(records),
        "contract_valid": valid,
        "latency_ms": {"p50": percentile(latencies, 0.50), "p95": p95,
                       "max": max(latencies) if latencies else None},
        "memory_peak_bytes": args.memory_peak_bytes,
        "throttled_before": args.throttled_before,
        "throttled_after": args.throttled_after,
        "contains_request_content": False,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

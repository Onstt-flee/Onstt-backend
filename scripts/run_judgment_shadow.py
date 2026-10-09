"""Run D-only judgment shadow inference without writing to the source DB."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from analyzer.judgment_service import (
    CONTRACT_VERSION,
    DEFAULT_ADAPTER,
    DEFAULT_MODEL,
    JudgmentServiceError,
    run_judgment,
)

JudgmentFn = Callable[..., dict[str, Any]]
INPUT_KEYS = (
    "utterance_id", "text", "text_source", "learner_level", "stt_model"
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    value = ordered[lower]
    if lower != upper:
        value += (ordered[upper] - ordered[lower]) * (position - lower)
    return round(value, 3)


def input_snapshot_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item[key] for key in INPUT_KEYS}


def input_fingerprint(item: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(input_snapshot_item(item)).encode())


def load_exclusion_snapshot(
    raw_path: Path,
    summary_path: Path,
) -> tuple[set[str], dict[str, Any]]:
    """Load and authenticate a prior private shadow input snapshot."""
    if not raw_path.is_file() or not summary_path.is_file():
        raise FileNotFoundError("Both exclusion raw and summary files must exist")
    records = [
        json.loads(line)
        for line in raw_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    snapshot = [input_snapshot_item(record) for record in records]
    snapshot_sha256 = sha256_bytes(canonical_json(snapshot).encode())
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    expected = summary.get("selection", {}).get("input_snapshot_sha256")
    if snapshot_sha256 != expected:
        raise ValueError(
            "Exclusion raw snapshot does not match its summary input snapshot SHA-256"
        )
    requested = summary.get("selection", {}).get("selected")
    if requested != len(snapshot):
        raise ValueError("Exclusion summary selected count does not match raw rows")
    fingerprints = {input_fingerprint(item) for item in snapshot}
    if len(fingerprints) != len(snapshot):
        raise ValueError("Exclusion snapshot contains duplicate input fingerprints")
    return fingerprints, {
        "policy": "authenticated_prior_input_snapshot",
        "excluded_count": len(snapshot),
        "input_snapshot_sha256": snapshot_sha256,
        "raw_sha256": sha256_file(raw_path),
        "summary_sha256": sha256_file(summary_path),
    }


def load_shadow_inputs(
    database_path: Path,
    limit: int,
    *,
    excluded_fingerprints: set[str] | None = None,
) -> list[dict[str, Any]]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    resolved = database_path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Database not found: {resolved}")
    connection = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT u.id AS utterance_id,
                CASE
                    WHEN TRIM(COALESCE(u.processed_text, '')) <> '' THEN u.processed_text
                    WHEN TRIM(COALESCE(u.normalized_text, '')) <> '' THEN u.normalized_text
                    ELSE u.stt_text
                END AS text,
                CASE
                    WHEN TRIM(COALESCE(u.processed_text, '')) <> '' THEN 'processed_text'
                    WHEN TRIM(COALESCE(u.normalized_text, '')) <> '' THEN 'normalized_text'
                    ELSE 'stt_text'
                END AS text_source,
                CASE WHEN usr.level IN ('N5', 'N4') THEN usr.level ELSE 'N5' END
                    AS learner_level,
                COALESCE(u.stt_model, 'unknown') AS stt_model
            FROM utterances AS u
            JOIN sessions AS s ON s.id = u.session_id
            LEFT JOIN users AS usr ON usr.id = s.user_id
            WHERE COALESCE(u.language, 'ja') = 'ja'
              AND (TRIM(COALESCE(u.processed_text, '')) <> ''
                   OR TRIM(COALESCE(u.normalized_text, '')) <> ''
                   OR TRIM(COALESCE(u.stt_text, '')) <> '')
            ORDER BY u.id DESC
            """
        ).fetchall()
    finally:
        connection.close()
    excluded_fingerprints = excluded_fingerprints or set()
    eligible = [
        dict(row) for row in rows
        if input_fingerprint(dict(row)) not in excluded_fingerprints
    ]
    return eligible[:limit]


def database_state(database_path: Path) -> dict[str, Any]:
    resolved = database_path.resolve()
    connection = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        judgment_count = connection.execute(
            "SELECT COUNT(*) FROM judgment_results"
        ).fetchone()[0]
    finally:
        connection.close()
    return {
        "sha256": sha256_file(resolved),
        "judgment_results_count": judgment_count,
    }


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def run_shadow(
    *,
    database_path: Path,
    limit: int,
    raw_output: Path,
    summary_output: Path,
    endpoint: str | None = None,
    model_name: str = DEFAULT_MODEL,
    judgment_fn: JudgmentFn = run_judgment,
    generated_at: str | None = None,
    excluded_fingerprints: set[str] | None = None,
    exclusion_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    database_before = database_state(database_path)
    inputs = load_shadow_inputs(
        database_path, limit, excluded_fingerprints=excluded_fingerprints
    )
    if len(inputs) < limit:
        raise ValueError(
            f"Need {limit} eligible Japanese rows, found {len(inputs)} after exclusions"
        )
    snapshot = [input_snapshot_item(item) for item in inputs]
    input_sha256 = sha256_bytes(canonical_json(snapshot).encode())
    raw_records: list[dict[str, Any]] = []
    decisions: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    levels: Counter[str] = Counter()
    stt_models: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    latencies: list[float] = []
    model_calls = 0
    retry_attempts = 0
    retry_recoveries = 0
    retry_failures = 0
    first_attempt_successes = 0

    for item in inputs:
        sources[item["text_source"]] += 1
        levels[item["learner_level"]] += 1
        stt_models[item["stt_model"]] += 1
        record = {**item, "context": None}
        try:
            result = judgment_fn(
                item["text"],
                context=None,
                learner_level=item["learner_level"],
                endpoint=endpoint,
                model_name=model_name,
            )
        except (JudgmentServiceError, ValueError) as exc:
            attempts = getattr(exc, "attempt_count", 1)
            retried = bool(getattr(exc, "retry_used", False))
            model_calls += attempts
            retry_attempts += int(retried)
            retry_failures += int(retried)
            failures[type(exc).__name__] += 1
            record.update(
                success=False,
                failure_type=type(exc).__name__,
                error=str(exc),
                attempt_count=attempts,
                retry_used=retried,
                first_contract_error=getattr(exc, "first_contract_error", None),
            )
            if isinstance(exc, JudgmentServiceError) and exc.raw_text is not None:
                record["raw_model_output"] = exc.raw_text
        else:
            attempts = int(result.get("attempt_count", 1))
            retried = bool(result.get("retry_used", False))
            model_calls += attempts
            retry_attempts += int(retried)
            retry_recoveries += int(retried)
            first_attempt_successes += int(not retried)
            decisions[result["decision"]] += 1
            if isinstance(result.get("latency_ms"), (int, float)):
                latencies.append(float(result["latency_ms"]))
            record.update(success=True, result=result)
        raw_records.append(record)

    raw_bytes = "".join(canonical_json(row) + "\n" for row in raw_records).encode()
    atomic_write(raw_output, raw_bytes)
    database_after = database_state(database_path)
    successes = sum(decisions.values())
    final_success_rate = successes / len(inputs)
    retry_rate = retry_attempts / len(inputs)
    latency_p95 = percentile(latencies, 0.95)
    database_unchanged = database_before == database_after
    gates = {
        "final_contract_success_at_least_99_of_100": (
            len(inputs) == 100 and successes >= 99
        ),
        "final_failures_at_most_1": len(inputs) - successes <= 1,
        "retry_rate_at_most_5_percent": retry_rate <= 0.05,
        "total_latency_p95_at_most_2500_ms": (
            latency_p95 is not None and latency_p95 <= 2500.0
        ),
        "database_unchanged": database_unchanged,
    }
    summary = {
        "schema_version": "judgment-shadow-v0.2",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "status": "operational_shadow_without_gold_labels",
        "database_write_policy": "read_only_no_judgment_persistence",
        "selection": {
            "policy": "latest_eligible_japanese_excluding_authenticated_prior_snapshot",
            "requested": limit,
            "selected": len(inputs),
            "exclusion": exclusion_metadata,
            "context_policy": "null_exact_dialogue_context_unavailable",
            "input_snapshot_sha256": input_sha256,
            "text_source_counts": dict(sorted(sources.items())),
            "learner_level_counts": dict(sorted(levels.items())),
            "stt_model_counts": dict(sorted(stt_models.items())),
        },
        "runtime": {
            "strategy": "d_only_with_single_preservation_retry",
            "model_name": model_name,
            "adapter_name": DEFAULT_ADAPTER,
            "contract_version": CONTRACT_VERSION,
            "model_calls": model_calls,
            "retry_policy": "preservation_contract_violation_only_once",
            "retry_attempts": retry_attempts,
            "retry_recoveries": retry_recoveries,
            "retry_failures": retry_failures,
            "e_calls": 0,
        },
        "results": {
            "first_attempt_successes": first_attempt_successes,
            "first_attempt_contract_success_rate": round(
                first_attempt_successes / len(inputs), 6
            ),
            "successes": successes,
            "failures": len(inputs) - successes,
            "json_contract_success_rate": round(final_success_rate, 6),
            "retry_rate": round(retry_rate, 6),
            "decision_counts": dict(sorted(decisions.items())),
            "failure_counts": dict(sorted(failures.items())),
            "latency_ms": {
                "count": len(latencies),
                "p50": percentile(latencies, 0.50),
                "p95": latency_p95,
                "max": round(max(latencies), 3) if latencies else None,
            },
        },
        "database_integrity": {
            "before": database_before,
            "after": database_after,
            "unchanged": database_unchanged,
            "writes": 0,
        },
        "acceptance": {
            "thresholds": {
                "sample_size": 100,
                "minimum_successes": 99,
                "maximum_final_failures": 1,
                "maximum_retry_rate": 0.05,
                "maximum_p95_latency_ms": 2500.0,
            },
            "checks": gates,
            "passed": all(gates.values()),
        },
        "artifacts": {
            "raw_output": str(raw_output),
            "raw_sha256": sha256_bytes(raw_bytes),
            "raw_contains_private_text": True,
            "raw_git_ignored": True,
        },
        "interpretation": {
            "quality_metrics_available": False,
            "reason": "No gold labels or audio evidence are used in shadow mode.",
            "pronunciation_or_stt_blame_assigned": False,
            "learner_exposure_approved": False,
        },
    }
    atomic_write(
        summary_output,
        (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode(),
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("stt_data.db"))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--raw-output", type=Path,
        default=Path("evaluation/judgment/runs/shadow_v0.2/raw.jsonl"),
    )
    parser.add_argument(
        "--summary-output", type=Path,
        default=Path("evaluation/judgment/shadow_v0.2.result.json"),
    )
    parser.add_argument(
        "--exclude-raw", type=Path,
        default=Path("evaluation/judgment/runs/shadow_v0.1/raw.jsonl"),
    )
    parser.add_argument(
        "--exclude-summary", type=Path,
        default=Path("evaluation/judgment/shadow_v0.1.result.json"),
    )
    parser.add_argument("--endpoint")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    excluded, exclusion_metadata = load_exclusion_snapshot(
        args.exclude_raw, args.exclude_summary
    )
    summary = run_shadow(
        database_path=args.database,
        limit=args.limit,
        raw_output=args.raw_output,
        summary_output=args.summary_output,
        endpoint=args.endpoint,
        model_name=args.model,
        excluded_fingerprints=excluded,
        exclusion_metadata=exclusion_metadata,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

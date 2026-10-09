"""Aggregate-only dry-run of the deterministic boundary gate on stored STT.

The source database is opened read-only. No model is called and the report
contains no utterance text, utterance IDs, or user identifiers.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from evaluation.judgment.boundary_gate import (
    POLICY_VERSION,
    assess_boundary,
)
from scripts.run_judgment_shadow import (
    atomic_write,
    canonical_json,
    load_shadow_inputs,
    sha256_bytes,
)


STT_ADVISORY_CONTEXT = (
    "저장된 STT 전사 텍스트이며 원음이나 대안 전사는 제공되지 않았습니다."
)


def _database_counts(database_path: Path) -> dict[str, int | None]:
    resolved = database_path.resolve()
    connection = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        utterances = connection.execute(
            "SELECT COUNT(*) FROM utterances"
        ).fetchone()[0]
        has_judgments = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name='judgment_results'"
        ).fetchone()[0]
        judgments = (
            connection.execute("SELECT COUNT(*) FROM judgment_results").fetchone()[0]
            if has_judgments
            else None
        )
    finally:
        connection.close()
    return {
        "utterances": int(utterances),
        "judgment_results": int(judgments) if judgments is not None else None,
    }


def _policy_sha256() -> str:
    path = Path(__file__).resolve().parents[1] / "evaluation/judgment/boundary_gate.py"
    return sha256_bytes(path.read_bytes())


def run_boundary_dry_run(
    *,
    database_path: Path,
    summary_output: Path,
    limit: int | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("limit must be a positive integer or null")
    database_path = database_path.resolve()
    summary_output = summary_output.resolve()
    if not database_path.is_file():
        raise FileNotFoundError(f"Database not found: {database_path}")
    if summary_output == database_path:
        raise ValueError("summary_output must not overwrite the source database")

    before_sha = sha256_bytes(database_path.read_bytes())
    before_counts = _database_counts(database_path)
    all_inputs = load_shadow_inputs(database_path, 2_147_483_647)
    inputs = all_inputs[:limit] if limit is not None else all_inputs
    if not inputs:
        raise ValueError("No eligible stored Japanese utterances found")

    snapshot = [
        {
            key: item[key]
            for key in (
                "utterance_id",
                "text",
                "text_source",
                "learner_level",
                "stt_model",
            )
        }
        for item in inputs
    ]
    input_sha256 = sha256_bytes(canonical_json(snapshot).encode("utf-8"))

    routes: Counter[str] = Counter()
    boundary_types: Counter[str] = Counter()
    text_sources: Counter[str] = Counter()
    levels: Counter[str] = Counter()
    stt_models: Counter[str] = Counter()
    advisory_kinds: Counter[str] = Counter()
    advisory_rows = 0
    advisory_count = 0

    for item in inputs:
        result = assess_boundary(item["text"], STT_ADVISORY_CONTEXT)
        routes[result["route"]] += 1
        if result["boundary_type"] is not None:
            boundary_types[result["boundary_type"]] += 1
        if result["advisories"]:
            advisory_rows += 1
            advisory_count += len(result["advisories"])
            advisory_kinds.update(
                advisory["kind"] for advisory in result["advisories"]
            )
        text_sources[item["text_source"]] += 1
        levels[item["learner_level"]] += 1
        stt_models[item["stt_model"]] += 1

    after_counts = _database_counts(database_path)
    after_sha = sha256_bytes(database_path.read_bytes())
    bypass_count = routes["deterministic"]
    report = {
        "schema_version": "judgment-boundary-dry-run-v0.1",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "status": "aggregate_only_read_only_no_model_calls",
        "policy": {
            "version": POLICY_VERSION,
            "sha256": _policy_sha256(),
            "stt_advisory_context_policy": (
                "stored utterance is treated as STT-derived; no audio evidence"
            ),
        },
        "database": {
            "path": str(database_path),
            "open_mode": "read_only",
            "sha256_before": before_sha,
            "sha256_after": after_sha,
            "unchanged": before_sha == after_sha,
            "counts_before": before_counts,
            "counts_after": after_counts,
        },
        "selection": {
            "policy": (
                "eligible_language_ja_rows_by_descending_id_with_api_text_priority"
            ),
            "available": len(all_inputs),
            "limit": limit,
            "selected": len(inputs),
            "input_snapshot_sha256": input_sha256,
            "text_source_counts": dict(sorted(text_sources.items())),
            "learner_level_counts": dict(sorted(levels.items())),
            "stt_model_counts": dict(sorted(stt_models.items())),
        },
        "routing": {
            "counts": dict(sorted(routes.items())),
            "boundary_type_counts": dict(sorted(boundary_types.items())),
            "model_call_avoided_count": bypass_count,
            "model_call_avoided_rate": round(bypass_count / len(inputs), 6),
            "model_call_required_count": routes["model"],
        },
        "advisories": {
            "rows": advisory_rows,
            "count": advisory_count,
            "kind_counts": dict(sorted(advisory_kinds.items())),
            "attribution_policy": "unknown_no_audio_evidence",
            "action_policy": "advisory_only_not_grammar_correction",
        },
        "privacy": {
            "contains_utterance_text": False,
            "contains_utterance_ids": False,
            "contains_user_identifiers": False,
            "per_row_output_created": False,
        },
        "runtime": {
            "model_calls": 0,
            "database_writes": 0,
            "judgment_results_written": (
                None
                if before_counts["judgment_results"] is None
                else after_counts["judgment_results"]
                - before_counts["judgment_results"]
            ),
        },
        "interpretation": {
            "quality_metrics_available": False,
            "reason": (
                "No gold labels or audio evidence are used; counts measure routing "
                "behavior only."
            ),
            "safe_for_operational_integration": False,
            "next_gate": (
                "review aggregate bypass rate and expand adversarial false-positive "
                "tests before any feature-flagged integration"
            ),
        },
    }
    atomic_write(
        summary_output,
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("stt_data.db"))
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("evaluation/judgment/boundary_dry_run_v0.1.result.json"),
    )
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    report = run_boundary_dry_run(
        database_path=args.database,
        summary_output=args.summary_output,
        limit=args.limit,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

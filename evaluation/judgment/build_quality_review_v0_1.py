"""Build a private, prediction-free real-STT quality review sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.run_judgment_shadow import (
    atomic_write,
    canonical_json,
    database_state,
    input_fingerprint,
    load_exclusion_snapshot,
    load_shadow_inputs,
    sha256_bytes,
)

SAMPLE_SEED = "judgment-quality-review-v0.1"
DEFAULT_QUOTAS = {
    "faster-whisper-small": 3,
    "faster-whisper-tiny": 2,
    "faster-whisper-tiny-tuned": 3,
    "whisper-tiny-lowskilled": 10,
    "whisper-tiny-tts": 12,
}


def _rank(row: dict[str, Any], seed: str) -> str:
    return hashlib.sha256(
        f"{seed}:{input_fingerprint(row)}".encode("utf-8")
    ).hexdigest()


def select_quality_sample(
    rows: list[dict[str, Any]],
    quotas: dict[str, int],
    *,
    seed: str = SAMPLE_SEED,
) -> list[dict[str, Any]]:
    """Deterministically stratify rows without looking at text or model output."""
    if not quotas or any(type(value) is not int or value <= 0 for value in quotas.values()):
        raise ValueError("quotas must contain positive integer counts")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["stt_model"], []).append(row)
    selected: list[dict[str, Any]] = []
    for model, quota in sorted(quotas.items()):
        candidates = sorted(grouped.get(model, []), key=lambda row: _rank(row, seed))
        if len(candidates) < quota:
            raise ValueError(
                f"Need {quota} rows for {model}, found {len(candidates)}"
            )
        selected.extend(candidates[:quota])
    return sorted(selected, key=lambda row: _rank(row, seed))


def _audio_availability(
    database_path: Path, utterance_ids: list[int]
) -> dict[int, bool]:
    placeholders = ",".join("?" for _ in utterance_ids)
    connection = sqlite3.connect(
        f"file:{database_path.resolve()}?mode=ro", uri=True
    )
    try:
        rows = connection.execute(
            f"SELECT id, raw_audio_path, audio_path FROM utterances "
            f"WHERE id IN ({placeholders})",
            utterance_ids,
        ).fetchall()
    finally:
        connection.close()
    availability = {}
    for utterance_id, raw_audio_path, audio_path in rows:
        paths = [path for path in (raw_audio_path, audio_path) if path and str(path).strip()]
        availability[utterance_id] = any(Path(path).is_file() for path in paths)
    return availability


def build_quality_review(
    *,
    database_path: Path,
    prior_runs: list[tuple[Path, Path]],
    review_output: Path,
    mapping_output: Path,
    manifest_output: Path,
    quotas: dict[str, int] = DEFAULT_QUOTAS,
    seed: str = SAMPLE_SEED,
    sealed_at: str | None = None,
) -> dict[str, Any]:
    database_before = database_state(database_path)
    excluded: set[str] = set()
    exclusion_records = []
    for raw_path, summary_path in prior_runs:
        fingerprints, metadata = load_exclusion_snapshot(raw_path, summary_path)
        if excluded.intersection(fingerprints):
            raise ValueError("Prior shadow snapshots overlap")
        excluded.update(fingerprints)
        exclusion_records.append(metadata)

    candidates = load_shadow_inputs(
        database_path,
        2_147_483_647,
        excluded_fingerprints=excluded,
    )
    selected = select_quality_sample(candidates, quotas, seed=seed)
    audio = _audio_availability(
        database_path, [row["utterance_id"] for row in selected]
    )
    if any(audio.values()):
        raise ValueError(
            "Audio unexpectedly became available; define a separate audio review protocol"
        )

    review_records = []
    mapping_records = []
    for index, row in enumerate(selected, start=1):
        review_id = f"QR-{index:03d}"
        review_records.append({
            "id": review_id,
            "text": row["text"],
            "context": None,
            "learner_level": row["learner_level"],
            "grammar_decision": None,
            "corrected_text": None,
            "error_types": None,
            "reason_ko": None,
            "review_status": "pending",
            "reviewed_at": None,
            "audio_review": {
                "status": "unavailable",
                "stt_transcription": "not_assessable_without_audio",
                "pronunciation": "not_assessable_without_audio",
            },
        })
        mapping_records.append({
            "id": review_id,
            "source_fingerprint": input_fingerprint(row),
            "utterance_id": row["utterance_id"],
            "text_source": row["text_source"],
            "stt_model": row["stt_model"],
            "audio_file_available": False,
        })

    review_bytes = "".join(
        canonical_json(record) + "\n" for record in review_records
    ).encode("utf-8")
    review_input_bytes = canonical_json([
        {key: record[key] for key in ("id", "text", "context", "learner_level")}
        for record in review_records
    ]).encode("utf-8")
    mapping_bytes = "".join(
        canonical_json(record) + "\n" for record in mapping_records
    ).encode("utf-8")
    atomic_write(review_output, review_bytes)
    atomic_write(mapping_output, mapping_bytes)
    database_after = database_state(database_path)
    if database_before != database_after:
        raise RuntimeError("Source database changed during quality review sampling")

    manifest = {
        "schema_version": "judgment-quality-review-v0.1",
        "sealed_at": sealed_at or datetime.now(timezone.utc).isoformat(),
        "status": "sealed_awaiting_independent_text_review",
        "sample_seed": seed,
        "sample_size": len(selected),
        "selection": {
            "source": "real_stored_stt_read_only",
            "prior_shadow_inputs_excluded": len(excluded),
            "remaining_candidates": len(candidates),
            "quotas": dict(sorted(quotas.items())),
            "selected_stt_model_counts": dict(sorted(Counter(
                row["stt_model"] for row in selected
            ).items())),
            "text_source_counts": dict(sorted(Counter(
                row["text_source"] for row in selected
            ).items())),
            "learner_level_counts": dict(sorted(Counter(
                row["learner_level"] for row in selected
            ).items())),
            "algorithm": "sha256_rank_with_fixed_seed_within_stt_model_strata",
            "text_or_model_output_used_for_selection": False,
        },
        "exclusions": exclusion_records,
        "review_contract": {
            "grammar_decisions": [
                "acceptable", "needs_correction", "insufficient_evidence"
            ],
            "anonymous_reviewer": True,
            "reviewer_identifier_stored": False,
            "model_predictions_in_review_file": False,
            "audio_review_status": "unavailable",
            "pronunciation_or_stt_attribution_allowed": False,
            "expert_review_claimed": False,
        },
        "artifacts": {
            "review_output": str(review_output),
            "review_sha256": sha256_bytes(review_bytes),
            "review_input_sha256": sha256_bytes(review_input_bytes),
            "mapping_output": str(mapping_output),
            "mapping_sha256": sha256_bytes(mapping_bytes),
            "private_git_ignored": True,
        },
        "database_integrity": {
            "before": database_before,
            "after": database_after,
            "unchanged": True,
            "writes": 0,
        },
        "model_inference_count": 0,
        "activation_policy": {
            "labels_must_be_sealed_before_model_run": True,
            "all_30_rows_must_be_reviewed": True,
            "unresolved_rows_allowed": 0,
            "maximum_system_failures": 1,
            "false_positive_corrections_allowed": 0,
            "meaning_changing_corrections_allowed": 0,
            "learner_exposure_approved_by_this_sample_alone": False,
        },
    }
    atomic_write(
        manifest_output,
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("stt_data.db"))
    parser.add_argument(
        "--review-output", type=Path,
        default=Path("evaluation/judgment/runs/quality_review_v0.1/review.jsonl"),
    )
    parser.add_argument(
        "--mapping-output", type=Path,
        default=Path("evaluation/judgment/runs/quality_review_v0.1/mapping.jsonl"),
    )
    parser.add_argument(
        "--manifest-output", type=Path,
        default=Path("evaluation/judgment/quality_review_v0.1.manifest.json"),
    )
    parser.add_argument("--sealed-at")
    args = parser.parse_args()
    manifest = build_quality_review(
        database_path=args.database,
        prior_runs=[
            (
                Path("evaluation/judgment/runs/shadow_v0.1/raw.jsonl"),
                Path("evaluation/judgment/shadow_v0.1.result.json"),
            ),
            (
                Path("evaluation/judgment/runs/shadow_v0.2/raw.jsonl"),
                Path("evaluation/judgment/shadow_v0.2.result.json"),
            ),
        ],
        review_output=args.review_output,
        mapping_output=args.mapping_output,
        manifest_output=args.manifest_output,
        sealed_at=args.sealed_at,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

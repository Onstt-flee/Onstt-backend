"""Validate completed anonymous labels for quality_review_v0.1."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.judgment.dataset import ERROR_TYPES
from scripts.run_judgment_shadow import canonical_json, sha256_bytes

REVIEW_FIELDS = {
    "id", "text", "context", "learner_level", "grammar_decision",
    "corrected_text", "error_types", "reason_ko", "review_status",
    "reviewed_at", "audio_review",
}
AUDIO_LOCK = {
    "status": "unavailable",
    "stt_transcription": "not_assessable_without_audio",
    "pronunciation": "not_assessable_without_audio",
}
DECISIONS = {"acceptable", "needs_correction", "insufficient_evidence"}
FORBIDDEN_IDENTITY_FIELDS = {
    "reviewer", "reviewer_id", "reviewer_name", "email", "student_id", "signature"
}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"line {line_number} must be an object")
        rows.append(value)
    return rows


def validate_completed_review(
    review_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    rows = _load_jsonl(review_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_count = manifest["sample_size"]
    if len(rows) != expected_count:
        raise ValueError(f"Expected {expected_count} review rows, found {len(rows)}")
    expected_ids = [f"QR-{index:03d}" for index in range(1, expected_count + 1)]
    if [row.get("id") for row in rows] != expected_ids:
        raise ValueError("Review IDs must be unique, ordered, and complete")

    input_snapshot = []
    decisions: Counter[str] = Counter()
    for row in rows:
        if set(row) != REVIEW_FIELDS:
            extra_identity = set(row).intersection(FORBIDDEN_IDENTITY_FIELDS)
            if extra_identity:
                raise ValueError("Reviewer identity fields are forbidden")
            raise ValueError(f"{row.get('id')} has missing or extra fields")
        input_snapshot.append({
            key: row[key] for key in ("id", "text", "context", "learner_level")
        })
        if not isinstance(row["text"], str) or not row["text"].strip():
            raise ValueError(f"{row['id']} text must remain nonblank")
        if row["context"] is not None or row["learner_level"] != "N5":
            raise ValueError(f"{row['id']} fixed input metadata changed")
        decision = row["grammar_decision"]
        if decision not in DECISIONS:
            raise ValueError(f"{row['id']} has an invalid grammar_decision")
        corrected = row["corrected_text"]
        error_types = row["error_types"]
        reason = row["reason_ko"]
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{row['id']} reason_ko must be nonblank")
        if (
            not isinstance(error_types, list)
            or len(error_types) != len(set(error_types))
            or any(value not in ERROR_TYPES for value in error_types)
        ):
            raise ValueError(f"{row['id']} error_types are invalid")
        if decision == "needs_correction":
            if not isinstance(corrected, str) or not corrected.strip() or corrected == row["text"]:
                raise ValueError(f"{row['id']} correction must change nonblank text")
            if not error_types:
                raise ValueError(f"{row['id']} correction requires error_types")
        else:
            if corrected != row["text"]:
                raise ValueError(f"{row['id']} non-correction must preserve text")
            if error_types:
                raise ValueError(f"{row['id']} non-correction must have no error_types")
        if row["review_status"] != "independently_reviewed":
            raise ValueError(f"{row['id']} is not independently reviewed")
        if not isinstance(row["reviewed_at"], str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", row["reviewed_at"]
        ):
            raise ValueError(f"{row['id']} reviewed_at must be YYYY-MM-DD")
        if row["audio_review"] != AUDIO_LOCK:
            raise ValueError(f"{row['id']} audio review must remain unavailable")
        decisions[decision] += 1

    input_hash = sha256_bytes(canonical_json(input_snapshot).encode("utf-8"))
    expected_hash = manifest["artifacts"]["review_input_sha256"]
    if input_hash != expected_hash:
        raise ValueError("Review input text or metadata changed after sealing")
    review_bytes = review_path.read_bytes()
    return {
        "schema_version": "judgment-quality-review-v0.1-validation",
        "status": "labels_complete_and_structurally_valid",
        "sample_size": len(rows),
        "decision_counts": dict(sorted(decisions.items())),
        "review_sha256": sha256_bytes(review_bytes),
        "review_input_sha256": input_hash,
        "reviewer_identifier_stored": False,
        "expert_review_claimed": False,
        "audio_review_status": "unavailable",
        "ready_for_single_model_evaluation": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--review", type=Path,
        default=Path("evaluation/judgment/runs/quality_review_v0.1/review.jsonl"),
    )
    parser.add_argument(
        "--manifest", type=Path,
        default=Path("evaluation/judgment/quality_review_v0.1.manifest.json"),
    )
    args = parser.parse_args()
    print(json.dumps(
        validate_completed_review(args.review, args.manifest),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()

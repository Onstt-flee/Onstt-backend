"""Normalize an anonymous external review and build a reviewed pilot dataset."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re

from training.judgment.data import (
    exact_overlap,
    load_records,
    near_seed_overlap,
    summary,
    validate_records,
)
from training.judgment.generate_pilot import RAG_DIR, ROOT, SEED_DATASET, write_jsonl


REVIEW_KEYS = {
    "id", "decision", "corrected_text", "accepted_corrections",
    "reason_ko", "review_confidence", "reviewed_at",
}
CONFIRMED_ACCEPTABLE = {"JT-0205"}
CONFIRMED_CANONICAL = {"JT-0247": "有名店に時計があります。"}
CONFIRMED_REASON = {
    "JT-0247": "사물의 존재를 나타내는 동사 あります(ある)와 함께 쓰일 때, 장소 조사는 동작 장소의 で가 아니라 존재 장소의 に를 사용합니다. (평가 기준 1: 조사 오류)",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strip_citation(reason: str) -> str:
    return re.sub(r"\s*\[cite:\s*\d+\]\s*$", "", reason).strip()


def _correction_candidates(value: str) -> list[str]:
    parts = [part.strip() for part in value.split(" / ")]
    candidates = []
    for part in parts:
        part = re.sub(r"^(?:대표|代表|허용|許容)\s*:\s*", "", part).strip()
        if part and part not in candidates:
            candidates.append(part)
    return candidates


def normalize_external_review(
    base_records: list[dict], external: list[dict], reviewed_at: str
) -> list[dict]:
    date.fromisoformat(reviewed_at)
    base_by_id = {row["id"]: row for row in base_records}
    if len(external) != len(base_records):
        raise ValueError("External review must contain every base record")
    if [row.get("id") for row in external] != [row["id"] for row in base_records]:
        raise ValueError("External review IDs must exactly match base order")

    normalized = []
    for item in external:
        if set(item) != {"id", "text", "context", "교정여부", "교정안", "근거"}:
            raise ValueError(f"Unexpected external fields for {item.get('id')}")
        base = base_by_id[item["id"]]
        if item["text"] != base["input"]["text"] or item["context"] != base["input"]["context"]:
            raise ValueError(f"Input mismatch for {item['id']}")
        if type(item["교정여부"]) is not bool:
            raise ValueError(f"교정여부 must be boolean for {item['id']}")
        reason = CONFIRMED_REASON.get(
            item["id"], _strip_citation(item["근거"])
        )
        if not reason:
            raise ValueError(f"Missing review reason for {item['id']}")

        if item["교정여부"]:
            if not isinstance(item["교정안"], str) or not item["교정안"].strip():
                raise ValueError(f"Correction is required for {item['id']}")
            decision = "needs_correction"
            candidates = _correction_candidates(item["교정안"])
            canonical = CONFIRMED_CANONICAL.get(item["id"])
            if canonical is None:
                base_canonical = base["expected"]["corrected_text"]
                canonical = base_canonical if base_canonical in candidates else candidates[0]
            accepted = []
            for candidate in [canonical, *candidates, *base["accepted_corrections"]]:
                if candidate != item["text"] and candidate not in accepted:
                    accepted.append(candidate)
        else:
            if item["교정안"] is not None:
                raise ValueError(f"Non-correction must have null 교정안 for {item['id']}")
            if item["id"] in CONFIRMED_ACCEPTABLE:
                decision = "acceptable"
            else:
                decision = base["expected"]["decision"]
                if decision == "needs_correction":
                    raise ValueError(f"Unresolved decision disagreement for {item['id']}")
            canonical = item["text"]
            accepted = []

        normalized.append({
            "id": item["id"],
            "decision": decision,
            "corrected_text": canonical,
            "accepted_corrections": accepted,
            "reason_ko": reason,
            "review_confidence": "not_recorded",
            "reviewed_at": reviewed_at,
        })
    return normalized


def load_review_source(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            value = json.loads(line)
            if not isinstance(value, dict) or set(value) != REVIEW_KEYS:
                raise ValueError(f"{path}:{number}: invalid review source fields")
            if value["decision"] not in {
                "acceptable", "needs_correction", "insufficient_evidence"
            }:
                raise ValueError(f"{path}:{number}: invalid decision")
            if value["review_confidence"] not in {"high", "medium", "low", "not_recorded"}:
                raise ValueError(f"{path}:{number}: invalid review confidence")
            date.fromisoformat(value["reviewed_at"])
            records.append(value)
    return records


def apply_review(base_records: list[dict], reviews: list[dict]) -> list[dict]:
    if [row["id"] for row in reviews] != [row["id"] for row in base_records]:
        raise ValueError("Review source IDs must exactly match base order")
    result = []
    for base, review in zip(base_records, reviews):
        row = json.loads(json.dumps(base, ensure_ascii=False))
        text = row["input"]["text"]
        decision = review["decision"]
        corrected = review["corrected_text"]
        if decision == "needs_correction":
            if corrected == base["expected"]["corrected_text"]:
                edits = base["expected"]["edits"]
            elif row["id"] == "JT-0247" and corrected == CONFIRMED_CANONICAL["JT-0247"]:
                start = text.index("で")
                edits = [{
                    "start": start,
                    "end": start + 1,
                    "source": "で",
                    "replacement": "に",
                    "error_type": "particle_misuse",
                }]
            else:
                raise ValueError(f"No reviewed edit mapping for {row['id']}")
        else:
            if corrected != text:
                raise ValueError(f"Non-correction changes text for {row['id']}")
            edits = []
        row["expected"] = {
            "decision": decision,
            "corrected_text": corrected,
            "edits": edits,
            "reason_ko": review["reason_ko"],
        }
        row["accepted_corrections"] = review["accepted_corrections"]
        row["review"] = {
            "status": "user_reviewed",
            "reviewed_at": review["reviewed_at"],
        }
        error_types = sorted({edit["error_type"] for edit in edits})
        row["tags"] = [decision, row["template_family_id"], *error_types]
        if row["id"] == "JT-0205":
            row["template_family_id"] = "acceptable_lexical_compound"
            row["tags"] = ["acceptable", "acceptable_lexical_compound"]
        elif row["id"] == "JT-0247":
            row["template_family_id"] = "particle_existence_lexical_compound"
            row["tags"] = [
                "needs_correction", "particle_existence_lexical_compound",
                "particle_misuse",
            ]
        result.append(row)
    validate_records(result, require_reviewed=True)
    return result


def write_manifest(
    path: Path, dataset_path: Path, base_path: Path, review_path: Path,
    records: list[dict]
) -> dict:
    overlap = exact_overlap(records, seed_path=SEED_DATASET, rag_dir=RAG_DIR)
    if overlap["matches"]:
        raise ValueError(f"Exact seed/RAG overlap: {overlap['matches']}")
    manifest = {
        "schema_version": "0.1",
        "dataset_id": "judgment-pilot-v0.1-reviewed",
        "status": "user_reviewed",
        "reviewed_at": records[0]["review"]["reviewed_at"],
        "dataset_path": str(dataset_path.resolve().relative_to(ROOT)),
        "dataset_sha256": _sha256(dataset_path),
        "base_dataset_path": str(base_path.resolve().relative_to(ROOT)),
        "base_dataset_sha256": _sha256(base_path),
        "review_source_path": str(review_path.resolve().relative_to(ROOT)),
        "review_source_sha256": _sha256(review_path),
        "seed_eval_sha256": _sha256(SEED_DATASET),
        "summary": summary(records),
        "exact_seed_rag_overlap": overlap,
        "near_seed_overlap_threshold": 0.85,
        "near_seed_overlap_for_manual_review": near_seed_overlap(
            records, seed_path=SEED_DATASET
        ),
        "review_policy": {
            "reviewer_identity_stored": False,
            "expert_review_claimed": False,
            "three_way_decision": True,
            "edit_offsets": "deterministic_from_reviewed_correction",
        },
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--review-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--external-json", type=Path)
    parser.add_argument("--reviewed-at", default="2026-09-14")
    args = parser.parse_args(argv)
    base = load_records(args.base)
    if args.external_json:
        external = json.loads(args.external_json.read_text(encoding="utf-8"))
        reviews = normalize_external_review(base, external, args.reviewed_at)
        write_jsonl(args.review_source, reviews)
    else:
        reviews = load_review_source(args.review_source)
    reviewed = apply_review(base, reviews)
    write_jsonl(args.output, reviewed)
    manifest = write_manifest(
        args.manifest, args.output, args.base, args.review_source, reviewed
    )
    print(json.dumps({
        "dataset": str(args.output),
        "dataset_sha256": manifest["dataset_sha256"],
        "review_source_sha256": manifest["review_source_sha256"],
        **manifest["summary"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

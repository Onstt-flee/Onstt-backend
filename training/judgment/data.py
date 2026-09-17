"""Validate and inspect judgment-training records without training dependencies."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from evaluation.judgment.dataset import ERROR_TYPES, validate_judgment


SCHEMA_VERSION = "0.1"
SPLITS = {"pilot_train", "pilot_dev", "train", "dev", "test"}
REVIEW_STATUSES = {
    "provisional", "generated_validated", "user_reviewed", "expert_reviewed",
}
PROVENANCE_KINDS = {"deterministic_template", "local_model_assisted"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _keys(value, expected, name: str) -> None:
    _require(isinstance(value, dict), f"{name} must be an object")
    _require(set(value) == set(expected), f"{name} must have exactly: {', '.join(sorted(expected))}")


def _nonblank(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Non-standard JSON constant: {value}")


def load_records(path: Path | str) -> list[dict]:
    records = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                records.append(json.loads(
                    line,
                    object_pairs_hook=_strict_object,
                    parse_constant=_reject_constant,
                ))
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
    return records


def validate_record(record: dict) -> None:
    _keys(record, {
        "schema_version", "id", "split", "template_family_id", "tags", "input",
        "expected", "accepted_corrections", "provenance", "review",
    }, "record")
    _require(record["schema_version"] == SCHEMA_VERSION, "Unsupported schema_version")
    _require(
        isinstance(record["id"], str) and re.fullmatch(r"JT-\d{4,}", record["id"]),
        "Invalid training id",
    )
    _require(record["split"] in SPLITS, f"Invalid split: {record['split']!r}")
    family = record["template_family_id"]
    _require(
        isinstance(family, str) and re.fullmatch(r"[a-z][a-z0-9_]*", family),
        "Invalid template_family_id",
    )
    tags = record["tags"]
    _require(
        isinstance(tags, list) and tags and all(_nonblank(tag) for tag in tags),
        "tags must be nonblank strings",
    )
    _require(len(tags) == len(set(tags)), "Duplicate tags")

    model_input = record["input"]
    _keys(model_input, {"text", "context", "learner_level"}, "input")
    _require(isinstance(model_input["text"], str), "input.text must be a string")
    _require(
        model_input["context"] is None or _nonblank(model_input["context"]),
        "context must be null or nonblank",
    )
    _require(model_input["learner_level"] in {"N5", "N4"}, "Invalid learner_level")
    validate_judgment(record["expected"], model_input["text"])

    alternatives = record["accepted_corrections"]
    _require(
        isinstance(alternatives, list) and all(_nonblank(item) for item in alternatives),
        "accepted_corrections must be strings",
    )
    _require(len(alternatives) == len(set(alternatives)), "Duplicate accepted correction")
    if record["expected"]["decision"] == "needs_correction":
        _require(
            record["expected"]["corrected_text"] in alternatives,
            "Canonical correction must be accepted",
        )
        _require(model_input["text"] not in alternatives, "Uncorrected input cannot be accepted")
    else:
        _require(not alternatives, "Only corrections can have accepted alternatives")

    provenance = record["provenance"]
    _keys(provenance, {
        "kind", "source_id", "external_text_used", "generator_model",
        "generator_revision", "generator_prompt_sha256",
    }, "provenance")
    _require(provenance["kind"] in PROVENANCE_KINDS, "Invalid provenance.kind")
    _require(_nonblank(provenance["source_id"]), "provenance.source_id is required")
    _require(provenance["external_text_used"] is False, "External text is not allowed in pilot v0.1")
    assisted = provenance["kind"] == "local_model_assisted"
    for key in ("generator_model", "generator_revision", "generator_prompt_sha256"):
        value = provenance[key]
        _require(_nonblank(value) if assisted else value is None, f"Invalid provenance.{key}")
    if assisted:
        _require(
            re.fullmatch(r"[0-9a-f]{64}", provenance["generator_prompt_sha256"]) is not None,
            "generator_prompt_sha256 must be SHA-256",
        )

    review = record["review"]
    _keys(review, {"status", "reviewed_at"}, "review")
    _require(review["status"] in REVIEW_STATUSES, "Invalid review.status")
    if review["status"] == "provisional":
        _require(review["reviewed_at"] is None, "Provisional record cannot have reviewed_at")
    else:
        _require(
            isinstance(review["reviewed_at"], str)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", review["reviewed_at"]),
            "reviewed_at must be YYYY-MM-DD",
        )
        date.fromisoformat(review["reviewed_at"])


def validate_records(records: list[dict], *, require_reviewed: bool = False) -> None:
    _require(isinstance(records, list) and records, "Dataset must be non-empty")
    ids = set()
    inputs = set()
    family_splits: dict[str, set[str]] = defaultdict(set)
    for number, record in enumerate(records, 1):
        try:
            validate_record(record)
            _require(record["id"] not in ids, f"Duplicate id: {record['id']}")
            input_key = json.dumps(record["input"], ensure_ascii=False, sort_keys=True)
            _require(input_key not in inputs, "Duplicate input including context and level")
            if require_reviewed:
                _require(record["review"]["status"] != "provisional", "Record is not reviewed")
            ids.add(record["id"])
            inputs.add(input_key)
            family_splits[record["template_family_id"]].add(record["split"])
        except ValueError as exc:
            raise ValueError(f"Record {number}: {exc}") from exc
    leaked = sorted(family for family, splits in family_splits.items() if len(splits) != 1)
    _require(not leaked, f"Template families cross splits: {', '.join(leaked)}")


def fingerprint(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(
        char for char in normalized
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def exact_overlap(records: list[dict], *, seed_path: Path, rag_dir: Path) -> dict:
    references: dict[str, set[str]] = defaultdict(set)
    with seed_path.open(encoding="utf-8") as stream:
        for line in stream:
            seed = json.loads(line)
            values = {
                seed["input"]["text"], seed["expected"]["corrected_text"],
                *seed["accepted_corrections"],
            }
            for value in values:
                key = fingerprint(value)
                if len(key) >= 4:
                    references[key].add("seed_eval")
    rag_files = sorted(rag_dir.rglob("*.json"))
    for path in rag_files:
        with path.open(encoding="utf-8") as stream:
            for value in _strings(json.load(stream)):
                key = fingerprint(value)
                if len(key) >= 4:
                    references[key].add(str(path.relative_to(rag_dir)))
    matches = []
    for record in records:
        candidates = {
            record["input"]["text"], record["expected"]["corrected_text"],
            *record["accepted_corrections"],
        }
        for candidate in candidates:
            key = fingerprint(candidate)
            if len(key) >= 4 and key in references:
                matches.append({
                    "id": record["id"], "text": candidate,
                    "references": sorted(references[key]),
                })
    return {"seed_path": str(seed_path), "rag_files": len(rag_files), "matches": matches}


def _trigrams(text: str) -> set[str]:
    value = fingerprint(text)
    return {value[index:index + 3] for index in range(max(0, len(value) - 2))}


def near_seed_overlap(records: list[dict], *, seed_path: Path, threshold: float = 0.85) -> list[dict]:
    seeds = []
    with seed_path.open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            seeds.append((record["id"], record["input"]["text"], _trigrams(record["input"]["text"])))
    matches = []
    for record in records:
        candidate_text = record["input"]["text"]
        candidate = _trigrams(candidate_text)
        if not candidate:
            continue
        for seed_id, seed_text, seed in seeds:
            union = candidate | seed
            score = len(candidate & seed) / len(union) if union else 0.0
            if score >= threshold:
                matches.append({
                    "id": record["id"], "seed_id": seed_id,
                    "score": round(score, 4), "text": candidate_text, "seed_text": seed_text,
                })
    return sorted(matches, key=lambda item: (-item["score"], item["id"], item["seed_id"]))


def summary(records: list[dict]) -> dict:
    return {
        "total": len(records),
        "splits": dict(sorted(Counter(row["split"] for row in records).items())),
        "decisions": dict(sorted(Counter(row["expected"]["decision"] for row in records).items())),
        "levels": dict(sorted(Counter(row["input"]["learner_level"] for row in records).items())),
        "review_status": dict(sorted(Counter(row["review"]["status"] for row in records).items())),
        "provenance": dict(sorted(Counter(row["provenance"]["kind"] for row in records).items())),
        "error_types": dict(sorted(Counter(
            edit["error_type"] for row in records for edit in row["expected"]["edits"]
        ).items())),
        "compound_corrections": sum(len(row["expected"]["edits"]) > 1 for row in records),
        "template_families": len({row["template_family_id"] for row in records}),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--seed", type=Path, default=Path("evaluation/judgment/seed_v0.1.jsonl"))
    parser.add_argument("--rag-dir", type=Path, default=Path("rag_data"))
    parser.add_argument("--require-reviewed", action="store_true")
    args = parser.parse_args()
    records = load_records(args.dataset)
    validate_records(records, require_reviewed=args.require_reviewed)
    overlap = exact_overlap(records, seed_path=args.seed, rag_dir=args.rag_dir)
    report = summary(records)
    report["sha256"] = sha256_file(args.dataset)
    report["exact_overlap"] = overlap
    report["near_seed_overlap_0_85"] = near_seed_overlap(records, seed_path=args.seed)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if overlap["matches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

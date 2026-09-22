"""Validate and inspect the judgment seed set using only stdlib."""

import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata


DEFAULT_DATASET = Path(__file__).with_name("seed_v0.1.jsonl")
DECISIONS = {"acceptable", "needs_correction", "insufficient_evidence"}
ERROR_TYPES = {
    "particle_misuse", "verb_conjugation", "adjective_conjugation",
    "copula_conjugation", "modifier_connection", "tense_mismatch",
}
REVIEW_STATUSES = {"provisional", "generated_validated", "user_reviewed", "expert_reviewed"}
REVIEW_CHECK_LABELS = {
    "check:filler_preserve": "필러 유지",
    "check:lexical_content_preserve": "의미 있는 표현 유지",
    "check:style_preserve": "문체 변경 불필요",
    "check:style_advisory": "문체 개선 별도 안내",
    "check:orthography_candidate": "표기 정규화 후보 있음",
    "check:attribution_unknown": "학습자 오류 여부 미확인",
    "check:context_mismatch": "질문과 내용 불일치",
    "check:context_match": "질문과 내용 일치",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _keys(value, keys, name):
    _require(isinstance(value, dict), f"{name} must be an object")
    _require(set(value) == set(keys), f"{name} must have exactly: {', '.join(sorted(keys))}")


def _nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def _choice(value, choices, name):
    _require(isinstance(value, str) and value in choices, f"Invalid {name}: {value!r}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Non-standard JSON constant: {value}")


def load_records(path=DEFAULT_DATASET):
    records = []
    with Path(path).open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                records.append(json.loads(
                    line, object_pairs_hook=_unique_object, parse_constant=_reject_constant,
                ))
            except ValueError as exc:
                raise ValueError(f"{path}:{number}: {exc}") from exc
    return records


def validate_judgment(judgment, text):
    """Validate the new strict contract, without inferring or repairing a decision.

    This checks structure and edit reconstruction, NOT linguistic correctness.
    Offsets are Python Unicode code-point indexes into the unchanged input.
    """
    _keys(judgment, {"decision", "corrected_text", "edits", "reason_ko"}, "judgment")
    _require(isinstance(text, str), "input text must be a string")
    _choice(judgment["decision"], DECISIONS, "decision")
    corrected = judgment["corrected_text"]
    _require(isinstance(corrected, str), "corrected_text must be a string")
    _require(_nonblank(judgment["reason_ko"]), "reason_ko must be nonblank")
    edits = judgment["edits"]
    _require(isinstance(edits, list), "edits must be a list")
    if judgment["decision"] != "needs_correction":
        _require(corrected == text, "Non-correction decisions must preserve input text")
        _require(not edits, "Non-correction decisions must not contain edits")
        return

    _require(_nonblank(text) and _nonblank(corrected), "A correction needs nonblank texts")
    _require(corrected != text and edits, "A correction must change text and provide edits")
    previous_start, previous_end = -1, 0
    for edit in edits:
        _keys(edit, {"start", "end", "source", "replacement", "error_type"}, "edit")
        start, end = edit["start"], edit["end"]
        _require(type(start) is int and type(end) is int, "Edit offsets must be integers, not bools")
        _require(0 <= start <= end <= len(text), "Edit offsets are out of bounds")
        _require(start > previous_start and start >= previous_end, "Edits must be sorted and non-overlapping")
        _require(isinstance(edit["source"], str), "Edit source must be a string")
        _require(isinstance(edit["replacement"], str), "Edit replacement must be a string")
        _require(text[start:end] == edit["source"], "Edit source does not match input span")
        _require(edit["source"] != edit["replacement"], "An edit must change its span")
        _choice(edit["error_type"], ERROR_TYPES, "error_type")
        previous_start, previous_end = start, end
    reconstructed = text
    for edit in reversed(edits):
        reconstructed = reconstructed[:edit["start"]] + edit["replacement"] + reconstructed[edit["end"]:]
    _require(reconstructed == corrected, "Edits do not reconstruct corrected_text")


def validate_record(record):
    _keys(record, {
        "schema_version", "id", "split", "group_id", "tags", "input", "expected",
        "accepted_corrections", "provenance", "review",
    }, "record")
    _require(record["schema_version"] == "0.1", "Unsupported schema_version")
    split = record["split"]
    _choice(split, {"seed_eval", "holdout_eval"}, "split")
    id_pattern = r"JG-\d{3,}" if split == "seed_eval" else r"JH-\d{4,}"
    _require(isinstance(record["id"], str) and re.fullmatch(id_pattern, record["id"]), "Invalid id for split")
    group = record["group_id"]
    _require(isinstance(group, str) and re.fullmatch(r"[a-z][a-z0-9_]*", group), "Invalid group_id")
    tags = record["tags"]
    _require(isinstance(tags, list) and tags and all(_nonblank(tag) for tag in tags), "tags must be nonblank strings")
    _require(len(set(tags)) == len(tags) and group in tags, "tags must be unique and include group_id")
    for tag in tags:
        if tag.startswith("check:"):
            _choice(tag, REVIEW_CHECK_LABELS, "review check tag")

    model_input = record["input"]
    _keys(model_input, {"text", "context", "learner_level"}, "input")
    _require(isinstance(model_input["text"], str), "input.text must be a string")
    _require(model_input["context"] is None or _nonblank(model_input["context"]), "context must be null or nonblank")
    _choice(model_input["learner_level"], {"N5", "N4"}, "learner_level")
    validate_judgment(record["expected"], model_input["text"])

    alternatives = record["accepted_corrections"]
    _require(isinstance(alternatives, list) and all(_nonblank(text) for text in alternatives), "accepted_corrections must be strings")
    _require(len(set(alternatives)) == len(alternatives), "Duplicate accepted correction")
    if record["expected"]["decision"] == "needs_correction":
        _require(record["expected"]["corrected_text"] in alternatives, "Canonical correction must be accepted")
        _require(model_input["text"] not in alternatives, "Uncorrected error cannot be an accepted correction")
    else:
        _require(not alternatives, "Only needs_correction can have accepted_corrections")

    provenance = record["provenance"]
    _keys(provenance, {"kind", "source_id", "external_text_used"}, "provenance")
    expected_kind = "assistant_authored" if split == "seed_eval" else "deterministic_template"
    _require(provenance["kind"] == expected_kind, f"Invalid provenance.kind for {split}")
    _require(_nonblank(provenance["source_id"]), "provenance.source_id is required")
    _require(provenance["external_text_used"] is False, "Seed must not claim imported external text")

    review = record["review"]
    _keys(review, {"status", "reviewed_at"}, "review")
    _choice(review["status"], REVIEW_STATUSES, "review.status")
    if review["status"] in {"provisional", "generated_validated"}:
        _require(review["reviewed_at"] is None, "Unreviewed records cannot claim completed review")
    else:
        reviewed_at = review["reviewed_at"]
        _require(isinstance(reviewed_at, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", reviewed_at), "reviewed_at must be YYYY-MM-DD")
        date.fromisoformat(reviewed_at)


def validate_records(records):
    _require(isinstance(records, list) and records, "Dataset must be a non-empty list")
    ids, inputs = set(), set()
    for number, record in enumerate(records, 1):
        try:
            validate_record(record)
            _require(record["id"] not in ids, f"Duplicate id: {record['id']}")
            fingerprint = json.dumps(record["input"], ensure_ascii=False, sort_keys=True)
            _require(fingerprint not in inputs, "Duplicate input including context and level")
            ids.add(record["id"])
            inputs.add(fingerprint)
        except ValueError as exc:
            raise ValueError(f"Record {number}: {exc}") from exc


def model_inputs(records):
    """Allowlist model-visible fields: never expose labels, groups or rationales."""
    validate_records(records)
    return [{"id": row["id"], "input": dict(row["input"])} for row in records]


def sentence_fingerprint(text):
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(char for char in normalized if not char.isspace() and not unicodedata.category(char).startswith("P"))


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def rag_overlap_report(records, rag_dir):
    """Read JSON only; do not load pickle, embeddings, user DB or model weights."""
    paths = sorted(Path(rag_dir).rglob("*.json"))
    _require(bool(paths), f"No RAG JSON files found in {rag_dir}")
    corpus = defaultdict(set)
    count = 0
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            for text in _strings(json.load(stream)):
                count += 1
                fingerprint = sentence_fingerprint(text)
                if len(fingerprint) >= 4:
                    corpus[fingerprint].add(str(path.relative_to(rag_dir)))
    matches = []
    for record in records:
        candidates = {record["input"]["text"], record["expected"]["corrected_text"], *record["accepted_corrections"]}
        for candidate in sorted(candidates):
            fingerprint = sentence_fingerprint(candidate)
            if len(fingerprint) >= 4 and fingerprint in corpus:
                matches.append({"id": record["id"], "text": candidate, "rag_files": sorted(corpus[fingerprint])})
    return {
        "files_scanned": len(paths), "strings_scanned": count,
        "minimum_fingerprint_length": 4, "normalization": "NFKC, remove whitespace and punctuation",
        "matches": matches,
        "limitation": "Exact normalized strings only; short strings, templates, paraphrases and pretraining overlap are not ruled out.",
    }


def summary(records):
    return {
        "total": len(records),
        "decisions": dict(sorted(Counter(row["expected"]["decision"] for row in records).items())),
        "review_status": dict(sorted(Counter(row["review"]["status"] for row in records).items())),
        "learner_levels": dict(sorted(Counter(row["input"]["learner_level"] for row in records).items())),
        "decisions_by_level": {
            level: dict(sorted(Counter(
                row["expected"]["decision"] for row in records if row["input"]["learner_level"] == level
            ).items()))
            for level in sorted({row["input"]["learner_level"] for row in records})
        },
        "groups": len({row["group_id"] for row in records}),
        "compound_error_cases": sum(len(row["expected"]["edits"]) > 1 for row in records),
        "boundary_cases": sum("boundary_case" in row["tags"] for row in records),
        "review_checks": dict(sorted(Counter(
            tag for row in records for tag in row["tags"] if tag in REVIEW_CHECK_LABELS
        ).items())),
        "linguistic_accuracy_verified": False,
    }


def _cell(value):
    return str(value).replace("|", "&#124;").replace("\n", "<br>")


def render_review(records):
    all_user_reviewed = all(row["review"]["status"] == "user_reviewed" for row in records)
    if all_user_reviewed:
        review_intro = (
            "아래 라벨은 익명 사용자 검수를 완료했습니다. 일본어 전문가 검수나 교육 품질 인증을 의미하지 않습니다."
        )
        review_instruction = (
            "문맥·최소 교정·한국어 근거를 다시 확인할 때에는 JSONL 원본을 수정하고 이 보기를 갱신합니다."
        )
    else:
        review_intro = "아래 라벨에는 아직 검수되지 않은 초안이 포함되어 있습니다."
        review_instruction = (
            "문맥을 함께 읽고 판단·최소 교정·한국어 근거를 검토하세요. 사람 확인 전에는 검수 상태를 올리지 않습니다."
        )
    lines = [
        "# 일본어 판단 평가셋 v0.1 — 검수용 보기", "",
        f"원본: `seed_v0.1.jsonl`. {review_intro}",
        f"{review_instruction} 빈칸은 `[빈 입력]`으로 표시합니다.", "",
        "`문법상 허용`은 표기·문체·문맥·발음까지 모두 통과했다는 뜻이 아닙니다.",
        "보조 검수 항목은 정답 쪽의 태그이며 현재 모델 출력 필드나 자동 판정 결과가 아닙니다.", "",
        "| ID | 수준 | 입력 | 문맥 | 문법 판단안 | 문법 교정 후보 | 보조 검수 항목 | 초안 근거 | 검수 상태 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    decisions = {"acceptable": "문법상 허용", "needs_correction": "교정 필요", "insufficient_evidence": "판단 보류"}
    for row in records:
        values = [
            row["id"], row["input"]["learner_level"], row["input"]["text"] or "[빈 입력]",
            row["input"]["context"] or "—", decisions[row["expected"]["decision"]],
            " / ".join(row["accepted_corrections"]) or "원문 유지",
            "; ".join(REVIEW_CHECK_LABELS[tag] for tag in row["tags"] if tag in REVIEW_CHECK_LABELS) or "—",
            row["expected"]["reason_ko"], row["review"]["status"],
        ]
        lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--rag-dir", type=Path, help="Optional read-only, normalized exact-match audit")
    parser.add_argument("--require-reviewed", action="store_true", help="Fail if any label is provisional")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--inputs-only", action="store_true", help="Print label-free JSONL; no model is called")
    modes.add_argument("--review-markdown", action="store_true", help="Print the review table")
    args = parser.parse_args(argv)
    try:
        records = load_records(args.dataset)
        validate_records(records)
        if args.require_reviewed:
            _require(all(row["review"]["status"] != "provisional" for row in records), "Human review required: provisional labels remain")
        report = summary(records)
        report["sha256"] = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
        if args.rag_dir is not None:
            report["rag_overlap"] = rag_overlap_report(records, args.rag_dir)
        if args.inputs_only:
            for row in model_inputs(records):
                print(json.dumps(row, ensure_ascii=False))
        elif args.review_markdown:
            print(render_review(records), end="")
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

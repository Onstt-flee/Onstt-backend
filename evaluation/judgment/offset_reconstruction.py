"""Offline prototype: deterministically rebuild edit offsets from corrected text.

This does not mutate stored runs or the production contract. It measures whether
offset generation should move from the model to deterministic backend code.
"""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import json
from pathlib import Path
from typing import Any

from evaluation.judgment.content_diagnostics import parse_content
from evaluation.judgment.dataset import ERROR_TYPES, validate_judgment
from evaluation.judgment.scorer import load_verified_run


def rebuild_judgment(text: str, raw_text: str) -> tuple[dict[str, Any] | None, str | None]:
    value = parse_content(raw_text)
    if value is None:
        return None, "raw output is not a four-field JSON object"
    if value["decision"] != "needs_correction":
        try:
            validate_judgment(value, text)
        except ValueError as exc:
            return None, str(exc)
        return value, None
    if value["corrected_text"] == text:
        return None, "correction does not change text"

    raw_edits = value["edits"]
    error_types = [
        edit.get("error_type")
        for edit in raw_edits
        if isinstance(edit, dict) and edit.get("error_type") in ERROR_TYPES
    ]
    opcodes = [
        opcode for opcode in SequenceMatcher(
            None, text, value["corrected_text"], autojunk=False
        ).get_opcodes()
        if opcode[0] != "equal"
    ]
    if not opcodes:
        return None, "correction has no diff"
    if len(error_types) == len(opcodes):
        assigned_types = error_types
    elif len(set(error_types)) == 1:
        assigned_types = error_types * len(opcodes)
    else:
        return None, "cannot map model error types to deterministic diff"

    edits = []
    for (_, source_start, source_end, target_start, target_end), error_type in zip(
        opcodes, assigned_types
    ):
        edits.append({
            "start": source_start,
            "end": source_end,
            "source": text[source_start:source_end],
            "replacement": value["corrected_text"][target_start:target_end],
            "error_type": error_type,
        })
    rebuilt = {**value, "edits": edits}
    try:
        validate_judgment(rebuilt, text)
    except ValueError as exc:
        return None, str(exc)
    return rebuilt, None


def evaluate_reconstruction(verified: dict[str, Any]) -> dict[str, Any]:
    success_ids = []
    failure_by_id = {}
    for row in verified["rows"]:
        if not row["response"]["transport_success"]:
            failure_by_id[row["id"]] = "transport failure"
            continue
        rebuilt, error = rebuild_judgment(
            row["input"]["text"], row["response"]["raw_text"]
        )
        if rebuilt is None:
            failure_by_id[row["id"]] = error
        else:
            success_ids.append(row["id"])
    return {
        "status": "offline_contract_v0.2_prototype_not_official_score",
        "model": verified["manifest"]["model"],
        "run_id": verified["manifest"]["run_id"],
        "run_output_sha256": verified["manifest"]["output_sha256"],
        "dataset_sha256": verified["dataset_sha256"],
        "original_strict_contract": {
            "numerator": verified["manifest"]["contract_valid_count"],
            "denominator": len(verified["rows"]),
        },
        "reconstructed_contract": {
            "numerator": len(success_ids),
            "denominator": len(verified["rows"]),
        },
        "recovered_ids": [
            row["id"] for row in verified["rows"]
            if row["id"] in success_ids and not row["response"]["contract_valid"]
        ],
        "remaining_failures": failure_by_id,
        "warning": "Reconstruction proves structural feasibility only; it does not make wrong linguistic content correct.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = evaluate_reconstruction(load_verified_run(args.run))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

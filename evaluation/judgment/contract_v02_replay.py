"""Replay a v0.1 run through the position-free v0.2 contract.

This does not call a model or change linguistic content. It removes model-provided
spans, retains the reported error types, and lets the backend rebuild edits.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.judgment.runner import PROMPT_VERSION_V2, parse_model_output
from evaluation.judgment.scorer import load_verified_run


def _to_v02_raw(raw_text: str) -> str:
    value = json.loads(raw_text)
    if not isinstance(value, dict) or set(value) != {
        "decision", "corrected_text", "edits", "reason_ko",
    }:
        raise ValueError("raw output is not a v0.1 four-field object")
    error_types: list[str] = []
    for edit in value["edits"]:
        if not isinstance(edit, dict):
            raise ValueError("v0.1 edit is not an object")
        error_type = edit.get("error_type")
        if isinstance(error_type, str) and error_type not in error_types:
            error_types.append(error_type)
    converted = {
        "decision": value["decision"],
        "corrected_text": value["corrected_text"],
        "error_types": error_types,
        "reason_ko": value["reason_ko"],
    }
    return json.dumps(converted, ensure_ascii=False, separators=(",", ":"))


def replay_verified_run(verified: dict[str, Any]) -> dict[str, Any]:
    valid_ids: list[str] = []
    review_ids: list[str] = []
    content_changed_ids: list[str] = []
    failures: dict[str, str] = {}
    for row in verified["rows"]:
        item_id = row["id"]
        if not row["response"]["transport_success"]:
            failures[item_id] = "transport failure"
            continue
        try:
            original = json.loads(row["response"]["raw_text"])
            converted = _to_v02_raw(row["response"]["raw_text"])
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            failures[item_id] = str(exc)
            continue
        parsed, error = parse_model_output(
            converted, row["input"]["text"], PROMPT_VERSION_V2
        )
        if parsed is None:
            failures[item_id] = error or "unknown contract failure"
            continue
        valid_ids.append(item_id)
        if parsed["classification_review_required"]:
            review_ids.append(item_id)
        if any(
            parsed[key] != original[key]
            for key in ("decision", "corrected_text", "reason_ko")
        ):
            content_changed_ids.append(item_id)
    total = len(verified["rows"])
    return {
        "status": "offline_contract_v0.2_replay_not_model_rerun",
        "source_model": verified["manifest"]["model"],
        "source_run_id": verified["manifest"]["run_id"],
        "source_run_sha256": verified["manifest"]["output_sha256"],
        "dataset_sha256": verified["dataset_sha256"],
        "prompt_version": PROMPT_VERSION_V2,
        "structure_success": {
            "numerator": len(valid_ids),
            "denominator": total,
            "value": len(valid_ids) / total if total else None,
        },
        "content_preserved": {
            "numerator": total - len(content_changed_ids),
            "denominator": total,
            "value": (total - len(content_changed_ids)) / total if total else None,
        },
        "classification_review_required_ids": review_ids,
        "content_changed_ids": content_changed_ids,
        "failures": failures,
        "warning": (
            "This replay validates contract separation only. It does not show how "
            "the model will respond to the v0.2 prompt."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = replay_verified_run(load_verified_run(args.run))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Compute diagnostic content metrics while deliberately ignoring edit offsets.

These metrics are secondary diagnostics, never replacements for scorer.py.  They
help distinguish a linguistic decision/correction failure from a strict edit
contract failure during model development.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from evaluation.judgment.dataset import DECISIONS
from evaluation.judgment.scorer import load_verified_run


OUTPUT_KEYS = {"decision", "corrected_text", "edits", "reason_ko"}


def parse_content(raw_text: str) -> dict[str, Any] | None:
    """Parse the four-field object without validating edit spans/reconstruction."""
    try:
        value = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or set(value) != OUTPUT_KEYS:
        return None
    if value["decision"] not in DECISIONS:
        return None
    if not isinstance(value["corrected_text"], str):
        return None
    if not isinstance(value["edits"], list):
        return None
    if not isinstance(value["reason_ko"], str) or not value["reason_ko"].strip():
        return None
    return value


def _fraction(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def diagnose_verified_run(verified: dict[str, Any]) -> dict[str, Any]:
    cases = []
    for row, record in zip(verified["rows"], verified["records"]):
        prediction = (
            parse_content(row["response"]["raw_text"])
            if row["response"]["transport_success"]
            else None
        )
        cases.append((row["id"], record, prediction, row["response"]))

    parseable = [(item_id, gold, pred, response) for item_id, gold, pred, response in cases if pred]
    decision_correct = [item_id for item_id, gold, pred, _ in parseable if pred["decision"] == gold["expected"]["decision"]]
    acceptable = [(item_id, gold, pred) for item_id, gold, pred, _ in parseable if gold["expected"]["decision"] == "acceptable"]
    corrections = [(item_id, gold, pred) for item_id, gold, pred, _ in parseable if gold["expected"]["decision"] == "needs_correction"]
    insufficient = [(item_id, gold, pred) for item_id, gold, pred, _ in parseable if gold["expected"]["decision"] == "insufficient_evidence"]
    predicted_corrections = [(item_id, gold, pred) for item_id, gold, pred, _ in parseable if pred["decision"] == "needs_correction"]
    true_positive = [item_id for item_id, gold, _ in predicted_corrections if gold["expected"]["decision"] == "needs_correction"]
    overcorrected = [item_id for item_id, _, pred in acceptable if pred["decision"] == "needs_correction"]
    correctly_withheld = [item_id for item_id, _, pred in insufficient if pred["decision"] == "insufficient_evidence"]
    accepted_text = [
        item_id for item_id, gold, pred in corrections
        if pred["decision"] == "needs_correction"
        and pred["corrected_text"] in gold["accepted_corrections"]
    ]
    wrong_decision = [
        item_id for item_id, gold, pred, _ in parseable
        if pred["decision"] != gold["expected"]["decision"]
    ]
    bad_correction_text = [
        item_id for item_id, gold, pred in corrections
        if pred["decision"] == "needs_correction"
        and pred["corrected_text"] not in gold["accepted_corrections"]
    ]
    contract_errors = Counter(
        response["contract_error"]
        for _, _, _, response in cases
        if response["contract_error"] is not None
    )
    return {
        "status": "diagnostic_only_not_official_score",
        "model": verified["manifest"]["model"],
        "run_id": verified["manifest"]["run_id"],
        "run_output_sha256": verified["manifest"]["output_sha256"],
        "dataset_sha256": verified["dataset_sha256"],
        "metrics": {
            "transport_success": _fraction(sum(row["response"]["transport_success"] for row in verified["rows"]), len(cases)),
            "strict_contract_success": _fraction(sum(row["response"]["contract_valid"] for row in verified["rows"]), len(cases)),
            "raw_four_field_json": _fraction(len(parseable), len(cases)),
            "raw_decision_accuracy": _fraction(len(decision_correct), len(cases)),
            "raw_correction_precision": _fraction(len(true_positive), len(predicted_corrections)),
            "raw_correction_recall": _fraction(len(true_positive), sum(gold["expected"]["decision"] == "needs_correction" for _, gold, _, _ in cases)),
            "raw_overcorrection": _fraction(len(overcorrected), sum(gold["expected"]["decision"] == "acceptable" for _, gold, _, _ in cases)),
            "raw_correct_withholding": _fraction(len(correctly_withheld), sum(gold["expected"]["decision"] == "insufficient_evidence" for _, gold, _, _ in cases)),
            "accepted_correction_text": _fraction(len(accepted_text), sum(gold["expected"]["decision"] == "needs_correction" for _, gold, _, _ in cases)),
        },
        "error_ids": {
            "wrong_decision": wrong_decision,
            "overcorrection": overcorrected,
            "bad_correction_text": bad_correction_text,
        },
        "strict_contract_errors": dict(sorted(contract_errors.items())),
        "warning": "Edit offsets and reconstruction are ignored here. Use scorer.py metrics for official comparisons.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    kwargs = {"dataset_path": args.dataset} if args.dataset else {}
    report = diagnose_verified_run(load_verified_run(args.run, **kwargs))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

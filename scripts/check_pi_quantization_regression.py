"""Compare Pi Q4 output with the preserved GPU BF16 v0.2-D dev run."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def parsed(record: dict) -> dict | None:
    response = record.get("response", {})
    if not response.get("contract_valid"):
        return None
    value = response.get("parsed_judgment")
    return value if isinstance(value, dict) else None


def accepted_texts(row: dict) -> set[str]:
    values = set(row.get("accepted_corrections") or [])
    expected = row.get("expected", {}).get("corrected_text")
    if isinstance(expected, str):
        values.add(expected)
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dataset = {row["id"]: row for row in load_jsonl(args.dataset)}
    reference = {row["id"]: row for row in load_jsonl(args.reference)}
    candidate = {row["id"]: row for row in load_jsonl(args.candidate)}
    if set(dataset) != set(reference) or set(dataset) != set(candidate):
        parser.error("dataset, reference, and candidate IDs must match exactly")

    total = len(dataset)
    valid = 0
    agreements = 0
    new_overcorrections = []
    hold_to_correction = []
    reference_accepted = 0
    candidate_accepted = 0
    for item_id, gold in dataset.items():
        ref = parsed(reference[item_id])
        cand = parsed(candidate[item_id])
        if ref and ref["decision"] == "needs_correction" and ref.get("corrected_text") in accepted_texts(gold):
            reference_accepted += 1
        if cand is None:
            continue
        valid += 1
        if ref and cand["decision"] == ref["decision"]:
            agreements += 1
        if gold["expected"]["decision"] == "acceptable" and cand["decision"] == "needs_correction" and (not ref or ref["decision"] != "needs_correction"):
            new_overcorrections.append(item_id)
        if ref and ref["decision"] == "insufficient_evidence" and cand["decision"] == "needs_correction":
            hold_to_correction.append(item_id)
        if cand["decision"] == "needs_correction" and cand.get("corrected_text") in accepted_texts(gold):
            candidate_accepted += 1

    thresholds = {
        "minimum_contract_valid": math.ceil(total * 0.99),
        "minimum_decision_agreement": math.ceil(total * 0.95),
        "maximum_new_overcorrections": 1,
        "maximum_accepted_correction_loss": 2,
        "maximum_hold_to_correction": 0,
    }
    metrics = {
        "total": total,
        "contract_valid": valid,
        "decision_agreement": agreements,
        "new_overcorrections": new_overcorrections,
        "reference_accepted_corrections": reference_accepted,
        "candidate_accepted_corrections": candidate_accepted,
        "accepted_correction_loss": reference_accepted - candidate_accepted,
        "hold_to_correction": hold_to_correction,
    }
    passed = (
        valid >= thresholds["minimum_contract_valid"]
        and agreements >= thresholds["minimum_decision_agreement"]
        and len(new_overcorrections) <= thresholds["maximum_new_overcorrections"]
        and metrics["accepted_correction_loss"] <= thresholds["maximum_accepted_correction_loss"]
        and not hold_to_correction
    )
    report = {
        "schema_version": "pi5-quantization-regression-v0.1",
        "passed": passed,
        "metrics": metrics,
        "thresholds": thresholds,
        "limitations": "Development-set quantization regression only; not a new quality claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

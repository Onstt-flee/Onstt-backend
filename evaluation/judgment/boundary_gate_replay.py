"""Replay a verified development run through the deterministic boundary policy.

This is an offline diagnostic. It does not call a model, mutate the source run,
or produce an official model score.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from evaluation.judgment.boundary_gate import POLICY_VERSION, apply_boundary_policy
from evaluation.judgment.dataset import DEFAULT_DATASET
from evaluation.judgment.scorer import load_verified_run, score_verified_run


METRICS = (
    "json_contract_success_rate",
    "decision_accuracy",
    "overcorrection_rate",
    "correction_detection_precision",
    "correction_detection_recall",
    "correct_withholding_rate",
    "clear_case_handling_rate",
    "accepted_correction_rate_end_to_end",
    "compound_complete_rate",
)


def _metric_summary(score: dict[str, Any]) -> dict[str, Any]:
    return {name: score["metrics"][name] for name in METRICS}


def replay_boundary_policy(verified: dict[str, Any]) -> dict[str, Any]:
    modified = deepcopy(verified)
    bypass_ids: list[str] = []
    advisory_ids: list[str] = []
    override_ids: list[str] = []
    changed_ids: list[str] = []

    for source_row, target_row in zip(verified["rows"], modified["rows"]):
        response = source_row["response"]
        model_judgment = (
            response["parsed_judgment"]
            if response["transport_success"] and response["contract_valid"]
            else None
        )
        applied = apply_boundary_policy(
            source_row["input"]["text"],
            source_row["input"]["context"],
            model_judgment,
        )
        if applied["advisories"]:
            advisory_ids.append(source_row["id"])

        if applied["route"] == "deterministic":
            bypass_ids.append(source_row["id"])
            prediction = applied["judgment"]
            target_response = target_row["response"]
            target_response.update({
                "transport_success": True,
                "http_status": None,
                "raw_text": "",
                "raw_response": "",
                "usage": None,
                "error": None,
                "latency_ms": 0.0,
                "contract_valid": True,
                "contract_error": None,
                "parsed_judgment": prediction,
            })
        elif model_judgment is not None:
            prediction = applied["judgment"]
            target_row["response"]["parsed_judgment"] = prediction
            target_row["response"]["contract_valid"] = True
            target_row["response"]["contract_error"] = None
            if applied["model_output_overridden"]:
                override_ids.append(source_row["id"])
        else:
            prediction = None

        if prediction != model_judgment:
            changed_ids.append(source_row["id"])

    original = score_verified_run(verified)
    after = score_verified_run(modified)
    return {
        "schema_version": "0.1",
        "status": "offline_boundary_policy_replay_not_model_rerun",
        "policy_version": POLICY_VERSION,
        "source_model": verified["manifest"]["model"],
        "source_run_id": verified["manifest"]["run_id"],
        "source_run_sha256": verified["manifest"]["output_sha256"],
        "dataset_sha256": verified["dataset_sha256"],
        "input_count": len(verified["rows"]),
        "model_call_avoided_count": len(bypass_ids),
        "model_call_avoided_ids": bypass_ids,
        "orthography_advisory_ids": advisory_ids,
        "orthography_override_ids": override_ids,
        "changed_ids": changed_ids,
        "before": _metric_summary(original),
        "after": _metric_summary(after),
        "before_system_failure_ids": original["case_lists"]["system_failure_ids"],
        "after_system_failure_ids": after["case_lists"]["system_failure_ids"],
        "before_decision_error_ids": original["case_lists"]["decision_error_ids"],
        "after_decision_error_ids": after["case_lists"]["decision_error_ids"],
        "warning": (
            "Development-set replay only. The policy does not use gold labels for "
            "routing, but these metrics use reviewed labels after prediction. "
            "Do not treat this as holdout or production evidence."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = replay_boundary_policy(
        load_verified_run(args.run, dataset_path=args.dataset)
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

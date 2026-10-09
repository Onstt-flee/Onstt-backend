"""Apply the frozen holdout v0.4 D/F selection policy without model calls."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTOCOL = ROOT / "evaluation/judgment/holdout_v0.4.protocol.json"
DEFAULT_REPORT = ROOT / "evaluation/judgment/results/qwen3-4b-v02d-vs-v02f-holdout-v04.json"
DEFAULT_OUTPUT = ROOT / "evaluation/judgment/holdout_v0.4.result.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metric(run: dict[str, Any], name: str) -> dict[str, Any]:
    return run["metrics"][name]


def summarize(run: dict[str, Any]) -> dict[str, Any]:
    latency = run["performance"]["latency_ms"]
    names = (
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
    return {
        "model": run["run"]["model"],
        "run_id": run["run"]["run_id"],
        "metrics": {
            name: {
                "numerator": metric(run, name)["numerator"],
                "denominator": metric(run, name)["denominator"],
                "value": metric(run, name)["value"],
            }
            for name in names
        },
        "p95_latency_ms": latency["p95"],
        "system_failure_ids": run["case_lists"]["system_failure_ids"],
        "decision_error_ids": run["case_lists"]["decision_error_ids"],
        "overcorrection_ids": run["case_lists"]["overcorrection_ids"],
        "missed_correction_ids": run["case_lists"]["missed_correction_ids"],
    }


def eligibility(summary: dict[str, Any], thresholds: dict[str, Any]) -> dict[str, bool]:
    m = summary["metrics"]
    return {
        "json_contract_success_rate": m["json_contract_success_rate"]["value"] >= thresholds["json_contract_success_rate_min"],
        "overcorrection_rate": (
            m["overcorrection_rate"]["value"] <= thresholds["overcorrection_rate_max"]
            and m["overcorrection_rate"]["numerator"] <= thresholds["overcorrection_max_count_among_50_acceptable"]
        ),
        "correction_detection_precision": m["correction_detection_precision"]["value"] >= thresholds["correction_detection_precision_min"],
        "correction_detection_recall": m["correction_detection_recall"]["value"] >= thresholds["correction_detection_recall_min"],
        "clear_case_handling_rate": m["clear_case_handling_rate"]["value"] >= thresholds["clear_case_handling_rate_min"],
        "correct_withholding_rate": m["correct_withholding_rate"]["value"] >= thresholds["correct_withholding_rate_min"],
        "accepted_correction_rate": m["accepted_correction_rate_end_to_end"]["value"] >= thresholds["accepted_correction_rate_min"],
    }


def f_adoption(d: dict[str, Any], f: dict[str, Any], rules: dict[str, Any]) -> dict[str, bool]:
    dm, fm = d["metrics"], f["metrics"]
    return {
        "decision_correct_gain": fm["decision_accuracy"]["numerator"] - dm["decision_accuracy"]["numerator"] >= rules["decision_correct_gain_min_count"],
        "accepted_correction_gain": fm["accepted_correction_rate_end_to_end"]["numerator"] - dm["accepted_correction_rate_end_to_end"]["numerator"] >= rules["accepted_correction_gain_min_count"],
        "overcorrection_no_regression": fm["overcorrection_rate"]["numerator"] <= dm["overcorrection_rate"]["numerator"],
        "precision_no_regression": fm["correction_detection_precision"]["value"] >= dm["correction_detection_precision"]["value"],
        "recall_no_regression": fm["correction_detection_recall"]["value"] >= dm["correction_detection_recall"]["value"],
        "correct_withholding_no_regression": fm["correct_withholding_rate"]["value"] >= dm["correct_withholding_rate"]["value"],
        "compound_complete_no_regression": fm["compound_complete_rate"]["numerator"] >= dm["compound_complete_rate"]["numerator"],
        "p95_absolute": f["p95_latency_ms"] <= rules["p95_ms_max"],
        "p95_ratio": f["p95_latency_ms"] <= d["p95_latency_ms"] * rules["p95_to_d_ratio_max"],
    }


def decide(protocol: dict[str, Any], comparison: dict[str, Any]) -> dict[str, Any]:
    by_model = {run["run"]["model"]: run for run in comparison["runs"]}
    d = summarize(by_model[protocol["candidates"]["d"]["served_model"]])
    f = summarize(by_model[protocol["candidates"]["f"]["served_model"]])
    de = eligibility(d, protocol["eligibility_thresholds"])
    fe = eligibility(f, protocol["eligibility_thresholds"])
    d_ok, f_ok = all(de.values()), all(fe.values())
    adoption = f_adoption(d, f, protocol["f_adoption_over_d"])

    if d_ok and not f_ok:
        selected, decision = "judgment-v02d", "d_only_eligible"
    elif f_ok and not d_ok:
        selected, decision = "judgment-v02f", "f_only_eligible"
    elif d_ok and f_ok:
        if all(adoption.values()):
            selected, decision = "judgment-v02f", "f_met_all_adoption_conditions"
        else:
            selected, decision = "judgment-v02d", "both_eligible_f_adoption_failed_keep_d"
    else:
        selected, decision = None, "neither_candidate_eligible"

    return {
        "candidates": {
            "d": {**d, "eligibility_checks": de, "eligible": d_ok},
            "f": {**f, "eligibility_checks": fe, "eligible": f_ok},
        },
        "f_adoption_checks": adoption,
        "selected_candidate": selected,
        "selection_decision": decision,
        "operational_promotion_allowed": selected is not None,
    }


def build_result(
    protocol_path: Path,
    report_path: Path,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    comparison = json.loads(report_path.read_text(encoding="utf-8"))
    result = decide(protocol, comparison)
    result.update({
        "schema_version": "judgment-holdout-v0.4-result-1",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "status": "consumed",
        "protocol_path": str(protocol_path.resolve()),
        "protocol_sha256": sha256(protocol_path),
        "protocol_checkpoint": "e84fb74f5ecbaaf18b7f5fa3777f01810c248e8a",
        "holdout_sha256": protocol["holdout"]["sha256"],
        "comparison_report_path": str(report_path.resolve()),
        "comparison_report_sha256": sha256(report_path),
        "execution_policy": {
            "d_inference_count": 1,
            "f_inference_count": 1,
            "rerun_for_model_selection_allowed": False,
        },
    })
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--created-at")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.output.exists() and not args.overwrite:
        raise SystemExit(f"Output already exists: {args.output}")
    result = build_result(args.protocol.resolve(), args.report.resolve(), created_at=args.created_at)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output.resolve()),
        "selected_candidate": result["selected_candidate"],
        "selection_decision": result["selection_decision"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

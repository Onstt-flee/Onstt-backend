"""Score two-stage feedback results without repairing malformed outputs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(quantile * len(ordered)) - 1]


def _unique_by_id(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        item_id = row.get("id")
        if not isinstance(item_id, str) or not item_id or item_id in result:
            raise ValueError(f"{label} contains missing or duplicate ids")
        result[item_id] = row
    return result


def score(gold_rows: list[dict[str, Any]], result_rows: list[dict[str, Any]]) -> dict[str, Any]:
    gold_by_id = _unique_by_id(gold_rows, "gold")
    results = _unique_by_id(result_rows, "result")
    if set(gold_by_id) != set(results):
        raise ValueError("gold and result ids differ")

    total = len(gold_rows)
    stage1_contract = false_disagree = tp = fp = fn = unreviewable_correct = 0
    expected_unreviewable = stage2_calls = stage2_contract = disciplined = 0
    recommendation_correct = correction_correct = correction_total = 0
    total_latencies: list[float] = []

    for gold in gold_rows:
        result = results[gold["id"]]
        expected1 = gold["expected_stage1"]
        expected2 = gold["expected_stage2"]
        parsed1 = result.get("stage1_parsed") if result.get("stage1_contract_success") else None
        parsed2 = result.get("stage2_parsed") if result.get("stage2_contract_success") else None
        if parsed1 is not None:
            stage1_contract += 1
        expected_disagree = expected1["verdict"] == "disagree"
        predicted_disagree = bool(parsed1 and parsed1.get("verdict") == "disagree")
        if not expected_disagree and predicted_disagree:
            false_disagree += 1
        tp += int(expected_disagree and predicted_disagree)
        fp += int(not expected_disagree and predicted_disagree)
        fn += int(expected_disagree and not predicted_disagree)
        if expected1["verdict"] == "unreviewable":
            expected_unreviewable += 1
            unreviewable_correct += int(bool(parsed1 and parsed1.get("verdict") == "unreviewable"))

        called = result.get("stage2_called") is True
        stage2_calls += int(called)
        disciplined += int(called == predicted_disagree)
        if called and parsed2 is not None:
            stage2_contract += 1
        if expected2 is not None:
            if parsed2 and parsed2.get("decision") == expected2["decision"]:
                recommendation_correct += 1
            if expected2["decision"] == "needs_correction":
                correction_total += 1
                if parsed2 and parsed2.get("corrected_text") == expected2["corrected_text"]:
                    correction_correct += 1
        latency = result.get("total_latency_ms")
        if isinstance(latency, (int, float)) and math.isfinite(latency) and latency >= 0:
            total_latencies.append(float(latency))

    non_disagree = total - sum(row["expected_stage1"]["verdict"] == "disagree" for row in gold_rows)
    expected_recommendations = sum(row["expected_stage2"] is not None for row in gold_rows)
    p95 = percentile(total_latencies, 0.95)
    return {
        "schema_version": "feedback-two-stage-score-v0.1",
        "records": total,
        "stage1_contract_success_rate": ratio(stage1_contract, total),
        "false_disagreement_rate": ratio(false_disagree, non_disagree),
        "disagreement_precision": ratio(tp, tp + fp),
        "disagreement_recall": ratio(tp, tp + fn),
        "unreviewable_accuracy": ratio(unreviewable_correct, expected_unreviewable),
        "stage2_called_count": stage2_calls,
        "stage2_call_discipline_rate": ratio(disciplined, total),
        "stage2_contract_success_rate": ratio(stage2_contract, stage2_calls),
        "recommended_decision_accuracy": ratio(recommendation_correct, expected_recommendations),
        "accepted_correction_rate": ratio(correction_correct, correction_total),
        "conditional_total_p95_seconds": (p95 or 0.0) / 1000.0,
    }


def evaluate_thresholds(metrics: dict[str, Any], thresholds: dict[str, float]) -> dict[str, Any]:
    mapping = {
        "stage1_contract_success_rate": (">=", "stage1_contract_success_rate_min"),
        "false_disagreement_rate": ("<=", "false_disagreement_rate_max"),
        "disagreement_precision": (">=", "disagreement_precision_min"),
        "disagreement_recall": (">=", "disagreement_recall_min"),
        "unreviewable_accuracy": (">=", "unreviewable_accuracy_min"),
        "stage2_call_discipline_rate": (">=", "stage2_call_discipline_rate_min"),
        "stage2_contract_success_rate": (">=", "stage2_contract_success_rate_min"),
        "recommended_decision_accuracy": (">=", "recommended_decision_accuracy_min"),
        "accepted_correction_rate": (">=", "accepted_correction_rate_min"),
        "conditional_total_p95_seconds": ("<=", "conditional_total_p95_seconds_max"),
    }
    checks = {}
    for metric_name, (operator, threshold_name) in mapping.items():
        value = metrics[metric_name]
        threshold = thresholds[threshold_name]
        checks[metric_name] = value >= threshold if operator == ">=" else value <= threshold
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "failed_thresholds": sorted(name for name, passed in checks.items() if not passed),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    metrics = score(load(args.gold), load(args.result))
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    summary = {"metrics": metrics, "threshold_evaluation": evaluate_thresholds(metrics, protocol["thresholds"])}
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

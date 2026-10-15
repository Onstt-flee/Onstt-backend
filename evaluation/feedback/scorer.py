"""Score feedback verifier results without accepting malformed outputs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def ratio(n, d): return n / d if d else 0.0
def percentile(values, q):
    if not values: return None
    values = sorted(values); return values[math.ceil(q * len(values)) - 1]


def score(gold_rows, result_rows):
    results = {row["id"]: row for row in result_rows}
    total = len(gold_rows); contract = false_disagree = tp = fp = fn = 0
    recommendation_correct = correction_correct = correction_total = 0
    source_names = sorted({row.get("source_stratum") for row in gold_rows
                           if row.get("source_stratum")})
    source = {name: {"total": 0, "correct": 0} for name in source_names}
    latencies = []
    for gold in gold_rows:
        result = results.get(gold["id"], {}); parsed = result.get("parsed")
        expected_disagree = gold["expected"]["verdict"] == "disagree"
        predicted_disagree = bool(parsed and parsed["verdict"] == "disagree")
        if result.get("contract_success"): contract += 1
        source_name = gold.get("source_stratum")
        if source_name:
            if parsed and parsed["verdict"] == gold["expected"]["verdict"]:
                source[source_name]["correct"] += 1
            source[source_name]["total"] += 1
        if not expected_disagree and predicted_disagree: false_disagree += 1
        tp += int(expected_disagree and predicted_disagree)
        fp += int(not expected_disagree and predicted_disagree)
        fn += int(expected_disagree and not predicted_disagree)
        expected_rec = gold["expected"]["recommended_judgment"]
        if expected_rec is not None:
            predicted_rec = parsed.get("recommended_judgment") if parsed else None
            if predicted_rec and predicted_rec["decision"] == expected_rec["decision"]:
                recommendation_correct += 1
            if expected_rec["decision"] == "needs_correction":
                correction_total += 1
                if predicted_rec and predicted_rec["corrected_text"] == expected_rec["corrected_text"]:
                    correction_correct += 1
        if isinstance(result.get("latency_ms"), (int, float)): latencies.append(result["latency_ms"])
    expected_non_disagree = sum(row["expected"]["verdict"] != "disagree" for row in gold_rows)
    expected_recommendations = sum(row["expected"]["recommended_judgment"] is not None
                                   for row in gold_rows)
    metrics = {"records": total, "contract_success_rate": ratio(contract, total),
               "false_disagreement_rate": ratio(false_disagree, expected_non_disagree),
               "disagreement_precision": ratio(tp, tp + fp), "disagreement_recall": ratio(tp, tp + fn),
               "recommended_decision_accuracy": ratio(recommendation_correct, expected_recommendations),
               "accepted_correction_rate": ratio(correction_correct, correction_total),
               "p95_latency_seconds": (percentile(latencies, .95) or 0) / 1000}
    accuracies = [ratio(value["correct"], value["total"]) for value in source.values()]
    metrics["source_metric_gap_pp"] = ((max(accuracies) - min(accuracies)) * 100
                                        if len(accuracies) >= 2 else None)
    return metrics


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda p: [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line]
    metrics = score(load(args.gold), load(args.result))
    args.output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__": main()

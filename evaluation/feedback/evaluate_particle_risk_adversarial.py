"""Evaluate the particle-risk gate on its development adversarial dataset."""

from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from analyzer.feedback_particle_risk_gate import GATE_VERSION, detect_particle_risks


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(rows: list[dict[str, Any]], thresholds: dict[str, float]) -> dict[str, Any]:
    tp = fp = fn = tn = 0
    strata: dict[str, Counter] = {}
    for row in rows:
        expected = set(row["expected_signal_codes"])
        actual = {signal.code for signal in detect_particle_risks(row["text"])}
        expected_positive = bool(expected)
        actual_positive = bool(actual)
        if expected_positive and actual_positive and expected == actual:
            outcome = "tp"
            tp += 1
        elif expected_positive:
            outcome = "fn"
            fn += 1
        elif actual_positive:
            outcome = "fp"
            fp += 1
        else:
            outcome = "tn"
            tn += 1
        strata.setdefault(row["stratum"], Counter())[outcome] += 1

    recall = tp / (tp + fn) if tp + fn else 1.0
    precision = tp / (tp + fp) if tp + fp else 1.0
    false_signal_rate = fp / (fp + tn) if fp + tn else 0.0
    checks = {
        "signal_recall": recall >= thresholds["signal_recall_min"],
        "signal_precision": precision >= thresholds["signal_precision_min"],
        "false_signal_rate": false_signal_rate <= thresholds["false_signal_rate_max"],
    }
    return {
        "schema_version": "feedback-particle-risk-adversarial-result-v0.1",
        "gate_version": GATE_VERSION,
        "evaluation_scope": "development_adversarial_not_holdout",
        "built_after_gate": True,
        "operational_activation_allowed": False,
        "total": len(rows),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "metrics": {
            "signal_recall": recall,
            "signal_precision": precision,
            "false_signal_rate": false_signal_rate,
        },
        "thresholds": thresholds,
        "checks": checks,
        "decision": "passed_development_diagnostic" if all(checks.values()) else "failed_development_diagnostic",
        "strata": {name: dict(sorted(counts.items())) for name, counts in sorted(strata.items())},
        "content_free": True,
        "limitations": [
            "관문 구현 뒤 설계한 개발 진단이며 독립 홀드아웃이 아닙니다.",
            "통과하더라도 운영 활성화나 문법 품질을 승인하지 않습니다.",
            "결과에는 원문, 교정문, 사용자 식별자를 저장하지 않습니다.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.dataset.read_text(encoding="utf-8").splitlines() if line]
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    result = evaluate(rows, protocol["thresholds"])
    result["dataset_sha256"] = sha256(args.dataset)
    result["protocol_sha256"] = sha256(args.protocol)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

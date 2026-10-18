"""Retrospective coverage diagnostic for the review-only particle risk gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from analyzer.feedback_particle_risk_gate import GATE_VERSION, detect_particle_risks


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verifier_target(row: dict[str, Any]) -> bool:
    expected = row["expected"]
    recommended = expected.get("recommended_judgment")
    return bool(
        expected.get("verdict") == "disagree"
        and recommended
        and recommended.get("decision") == "needs_correction"
        and "particle_misuse" in recommended.get("error_types", [])
    )


def _risk_target(row: dict[str, Any]) -> bool:
    if _verifier_target(row):
        return True
    candidate = row.get("candidate_judgment") or {}
    return bool(
        row["expected"].get("verdict") == "agree"
        and candidate.get("decision") == "needs_correction"
        and candidate.get("corrected_text") != row.get("text")
        and "particle_misuse" in candidate.get("error_types", [])
    )


def evaluate(gold_rows: list[dict[str, Any]], result_rows: list[dict[str, Any]]) -> dict[str, Any]:
    results = {row["id"]: row for row in result_rows}
    risk_ids = {row["id"] for row in gold_rows if _risk_target(row)}
    verifier_target_ids = {row["id"] for row in gold_rows if _verifier_target(row)}
    signaled_ids = {row["id"] for row in gold_rows if detect_particle_risks(row["text"])}
    model_failure_ids: set[str] = set()
    for row in gold_rows:
        if row["id"] not in verifier_target_ids:
            continue
        parsed = results.get(row["id"], {}).get("parsed")
        expected = row["expected"]["recommended_judgment"]
        predicted = parsed.get("recommended_judgment") if parsed else None
        if not predicted or predicted.get("decision") != expected["decision"] or predicted.get("corrected_text") != expected["corrected_text"]:
            model_failure_ids.add(row["id"])
    covered_risks = risk_ids & signaled_ids
    covered_failures = model_failure_ids & signaled_ids
    return {
        "schema_version": "feedback-particle-risk-diagnostic-v0.1",
        "gate_version": GATE_VERSION,
        "retrospective_only": True,
        "total": len(gold_rows),
        "risk_rows": len(risk_ids),
        "signaled_rows": len(signaled_ids),
        "risk_coverage": len(covered_risks),
        "non_risk_signals": len(signaled_ids - risk_ids),
        "verifier_particle_review_rows": len(verifier_target_ids),
        "model_target_failures": len(model_failure_ids),
        "covered_model_target_failures": len(covered_failures),
        "limitations": [
            "소비 완료된 시험지의 후향 진단이며 모델 선택이나 운영 승인 근거가 아닙니다.",
            "표면 패턴 위험 신호일 뿐 문법 정답이나 자동 교정이 아닙니다.",
            "원문, 교정문, 사용자 식별자는 결과 요약에 저장하지 않습니다.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    summary = evaluate(load(args.gold), load(args.result))
    summary["gold_sha256"] = sha256_file(args.gold)
    summary["result_sha256"] = sha256_file(args.result)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

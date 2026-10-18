"""Compare baseline and LoRA feedback-verifier runs on one fixed dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from evaluation.feedback.scorer import score


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _core_match(result: dict, gold: dict) -> bool:
    parsed = result.get("parsed")
    if not result.get("contract_success") or not parsed:
        return False
    expected = gold["expected"]
    if parsed["verdict"] != expected["verdict"]:
        return False
    expected_recommendation = expected["recommended_judgment"]
    if expected_recommendation is None:
        return True
    predicted = parsed.get("recommended_judgment")
    if not predicted or predicted["decision"] != expected_recommendation["decision"]:
        return False
    if expected_recommendation["decision"] == "needs_correction":
        return predicted["corrected_text"] == expected_recommendation["corrected_text"]
    return True


def compare(gold_rows: list[dict], base_rows: list[dict], lora_rows: list[dict]) -> dict:
    gold = {row["id"]: row for row in gold_rows}
    base = {row["id"]: row for row in base_rows}
    lora = {row["id"]: row for row in lora_rows}
    if set(base) != set(gold) or set(lora) != set(gold):
        raise ValueError("gold, baseline, and LoRA IDs must match exactly")
    base_metrics = score(gold_rows, base_rows)
    lora_metrics = score(gold_rows, lora_rows)
    improved = [key for key in gold if not _core_match(base[key], gold[key]) and _core_match(lora[key], gold[key])]
    regressed = [key for key in gold if _core_match(base[key], gold[key]) and not _core_match(lora[key], gold[key])]
    metric_deltas = {
        key: lora_metrics[key] - base_metrics[key]
        for key in base_metrics
        if isinstance(base_metrics[key], (int, float))
        and isinstance(lora_metrics.get(key), (int, float))
        and key != "records"
    }
    return {
        "base_metrics": base_metrics,
        "lora_metrics": lora_metrics,
        "metric_deltas_lora_minus_base": metric_deltas,
        "core_match": {
            "baseline": sum(_core_match(base[key], gold[key]) for key in gold),
            "lora": sum(_core_match(lora[key], gold[key]) for key in gold),
            "improved_count": len(improved),
            "regressed_count": len(regressed),
            "regressed_ids": regressed,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--lora", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--prospective",
        action="store_true",
        help="Record a baseline/LoRA comparison that was planned before either run.",
    )
    args = parser.parse_args()
    result = compare(load_jsonl(args.gold), load_jsonl(args.baseline), load_jsonl(args.lora))
    if args.prospective:
        scope = "prospective_internal_generated_validation"
        timing_limitation = "베이스라인과 LoRA를 사전 계획에 따라 각각 한 번 실행했습니다."
    else:
        scope = "retrospective_internal_generated_validation"
        timing_limitation = "LoRA 공식 실행 뒤 누락된 베이스라인을 추가한 후향적 내부 비교입니다."
    result.update({
        "schema_version": "feedback-baseline-lora-comparison-v0.1",
        "comparison_scope": scope,
        "dataset_sha256": sha256(args.gold),
        "baseline_result_sha256": sha256(args.baseline),
        "lora_result_sha256": sha256(args.lora),
        "limitations": [
            "자동 생성·검증 시험지이며 사람 또는 일본어 전문가 검수 결과가 아닙니다.",
            timing_limitation,
            "운영 승인이나 실제 학습자 품질의 근거로 단독 사용하지 않습니다.",
        ],
    })
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

"""Transform feedback-v0.5 into stage-specific two-stage training examples."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import canonical_json, validate_input
from analyzer.feedback_two_stage_contract import (
    STAGE1_SYSTEM_PROMPT,
    STAGE2_SYSTEM_PROMPT,
    parse_stage1_output,
    parse_stage2_output,
)
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint


ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data"
SOURCE = DATA / "feedback_v0.5.jsonl"
OUTPUT = DATA / "feedback_v0.6.two-stage.jsonl"
TRAIN = DATA / "train_v0.6.two-stage.chatml.jsonl"
EVAL = DATA / "eval_v0.6.two-stage.chatml.jsonl"
MANIFEST = DATA / "feedback_v0.6.two-stage.manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def model_input(row: dict) -> dict:
    value = {
        "text": row["text"], "context": row["context"],
        "learner_level": row["learner_level"], "judgment": row["candidate_judgment"],
    }
    validate_input(value)
    return value


def stage1_gold(row: dict) -> dict:
    expected = row["expected"]
    return {
        "verdict": expected["verdict"],
        "issue_codes": expected["issue_codes"],
        "review_reason_ko": expected["review_reason_ko"],
    }


def build_examples() -> list[dict]:
    examples = []
    for row in load(SOURCE):
        source_input = model_input(row)
        audit = stage1_gold(row)
        parsed1, error1 = parse_stage1_output(canonical_json(audit))
        if parsed1 is None:
            raise ValueError(f"invalid stage1 gold for {row['id']}: {error1}")
        examples.append({
            "id": f"FVT-06-S1-{row['id']}", "task": "feedback_stage1",
            "source_id": row["id"], "split_group": row["split_group"],
            "model_input": source_input, "stage1_audit": None, "expected": audit,
            "review": {"status": "generated_validated", "reviewed_at": None},
        })
        if audit["verdict"] == "disagree":
            recommendation = row["expected"]["recommended_judgment"]
            parsed2, error2 = parse_stage2_output(
                canonical_json(recommendation), row["text"], audit["issue_codes"]
            )
            if parsed2 is None:
                raise ValueError(f"invalid stage2 gold for {row['id']}: {error2}")
            examples.append({
                "id": f"FVT-06-S2-{row['id']}", "task": "feedback_stage2",
                "source_id": row["id"], "split_group": row["split_group"],
                "model_input": source_input, "stage1_audit": audit, "expected": recommendation,
                "review": {"status": "generated_validated", "reviewed_at": None},
            })
    if len(examples) != 3571 or len({row["id"] for row in examples}) != 3571:
        raise ValueError(f"expected 3571 unique stage examples, got {len(examples)}")
    return examples


def to_chat(example: dict) -> dict:
    if example["task"] == "feedback_stage1":
        system = STAGE1_SYSTEM_PROMPT
        visible = example["model_input"]
    else:
        system = STAGE2_SYSTEM_PROMPT
        visible = {"input": example["model_input"], "stage1_audit": example["stage1_audit"]}
    return {"messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": canonical_json(visible)},
        {"role": "assistant", "content": canonical_json(example["expected"])},
    ]}


def main() -> int:
    examples = build_examples()
    source_rows = load(SOURCE)
    source_inputs = {input_fingerprint(row) for row in source_rows}
    source_texts = {row["text"] for row in source_rows}
    protected = {
        "holdout_v0.7": ROOT / "evaluation/feedback/holdout_v0.7.jsonl",
        "holdout_v0.8": ROOT / "evaluation/feedback/holdout_v0.8.jsonl",
    }
    overlap = {}
    for name, path in protected.items():
        rows = load(path)
        overlap[name] = {
            "exact_input": len(source_inputs & {input_fingerprint(row) for row in rows}),
            "text": len(source_texts & {row["text"] for row in rows}),
        }
    if any(value["exact_input"] or value["text"] for value in overlap.values()):
        raise ValueError(f"protected holdout overlap: {overlap}")

    OUTPUT.write_text("".join(canonical_json(row) + "\n" for row in examples), encoding="utf-8")
    splits = {"train": [], "eval": []}
    for example in examples:
        splits[example["split_group"]].append(to_chat(example))
    TRAIN.write_text("".join(canonical_json(row) + "\n" for row in splits["train"]), encoding="utf-8")
    EVAL.write_text("".join(canonical_json(row) + "\n" for row in splits["eval"]), encoding="utf-8")
    manifest = {
        "schema_version": "feedback-training-manifest-v0.6-two-stage",
        "records": len(examples), "train_records": len(splits["train"]),
        "eval_records": len(splits["eval"]), "task_counts": dict(sorted(Counter(row["task"] for row in examples).items())),
        "train_task_counts": dict(sorted(Counter(row["task"] for row in examples if row["split_group"] == "train").items())),
        "eval_task_counts": dict(sorted(Counter(row["task"] for row in examples if row["split_group"] == "eval").items())),
        "source_dataset": str(SOURCE.relative_to(ROOT)), "source_dataset_sha256": sha256(SOURCE),
        "review": {"status": "generated_validated", "reviewed_at": None}, "holdout_used": False,
        "protected_overlap": overlap, "source_sha256": sha256(OUTPUT),
        "train_sha256": sha256(TRAIN), "eval_sha256": sha256(EVAL),
        "limitations": [
            "자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.",
            "기존 v0.5 입력을 단계별 출력 계약으로 재표현했으며 새 언어 정답을 만들지 않았습니다.",
            "봉인된 holdout v0.7과 v0.8은 학습에 사용하지 않았습니다.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

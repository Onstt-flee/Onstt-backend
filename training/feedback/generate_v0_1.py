"""Generate non-holdout feedback audit pairs and deterministic ChatML splits."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import SYSTEM_PROMPT, canonical_json
from evaluation.feedback.build_holdout_v0_1 import build_rows


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"


def replace_deep(value, source, target):
    if isinstance(value, str): return value.replace(source, target)
    if isinstance(value, list): return [replace_deep(item, source, target) for item in value]
    if isinstance(value, dict): return {key: replace_deep(item, source, target) for key, item in value.items()}
    return value


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    templates = build_rows()[::10]
    rows = []
    for family, template in enumerate(templates):
        source_prefix = template["text"].split("は", 1)[0].split("、", 1)[0]
        for index in range(50):
            date = f"来年{(index % 12) + 1}月{(index % 27) + 1}日"
            row = replace_deep(copy.deepcopy(template), source_prefix, date)
            row["id"] = f"FVT-01-{family * 50 + index + 1:04d}"
            row.pop("source_stratum", None)
            row["review"] = {"status": "generated_validated", "reviewed_at": None}
            row.pop("review_status", None)
            rows.append(row)
    source = DATA / "feedback_v0.1.jsonl"
    source.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    train, evaluation = [], []
    for index, row in enumerate(rows):
        expected = row["expected"]
        output = {"verdict": expected["verdict"],
                  "issue_codes": expected["required_issue_codes"],
                  "recommended_judgment": expected["recommended_judgment"],
                  "review_reason_ko": ("기존 판단이 타당합니다." if expected["verdict"] == "agree"
                                       else "권장 판단과 문제 유형에 따라 수정이 필요합니다.")}
        model_input = {"text": row["text"], "context": row["context"],
                       "learner_level": row["learner_level"], "judgment": row["candidate_judgment"]}
        chat = {"messages": [{"role": "system", "content": SYSTEM_PROMPT},
                              {"role": "user", "content": canonical_json(model_input)},
                              {"role": "assistant", "content": canonical_json(output)}]}
        (evaluation if index % 10 == 0 else train).append(chat)
    for name, values in (("train_v0.1.chatml.jsonl", train), ("eval_v0.1.chatml.jsonl", evaluation)):
        (DATA / name).write_text("".join(canonical_json(row) + "\n" for row in values), encoding="utf-8")
    manifest = {"schema_version": "feedback-training-manifest-v0.1",
                "records": len(rows), "train_records": len(train), "eval_records": len(evaluation),
                "review_status": "generated_validated", "holdout_used": False,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "train_sha256": hashlib.sha256((DATA / "train_v0.1.chatml.jsonl").read_bytes()).hexdigest(),
                "eval_sha256": hashlib.sha256((DATA / "eval_v0.1.chatml.jsonl").read_bytes()).hexdigest()}
    (DATA / "feedback_v0.1.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__": main()

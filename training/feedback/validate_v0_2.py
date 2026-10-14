"""Validate paired feedback-v0.2 training data and v0.3 isolation."""

import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import parse_output, validate_input
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint


ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main():
    manifest = json.loads((DATA / "feedback_v0.2.manifest.json").read_text(encoding="utf-8"))
    source_path = DATA / "feedback_v0.2.jsonl"
    train_path = DATA / "train_v0.2.chatml.jsonl"
    eval_path = DATA / "eval_v0.2.chatml.jsonl"
    assert sha(source_path) == manifest["source_sha256"]
    assert sha(train_path) == manifest["train_sha256"]
    assert sha(eval_path) == manifest["eval_sha256"]
    rows = load(source_path)
    assert len(rows) == manifest["records"]
    assert len({row["id"] for row in rows}) == len(rows)
    train_sources = {row["source_judgment_id"] for row in rows if row["split_group"] == "train"}
    eval_sources = {row["source_judgment_id"] for row in rows if row["split_group"] == "eval"}
    assert not train_sources & eval_sources
    holdout = load(ROOT / "evaluation/feedback/holdout_v0.3.jsonl")
    assert not ({input_fingerprint(row) for row in rows} & {input_fingerprint(row) for row in holdout})
    assert not ({row["text"] for row in rows} & {row["text"] for row in holdout})
    assert manifest["holdout_v0.3_exact_input_overlap"] == 0
    assert manifest["holdout_used"] is False
    for split_path in (train_path, eval_path):
        for chat in load(split_path):
            model_input = json.loads(chat["messages"][1]["content"])
            validate_input(model_input)
            parsed, error = parse_output(chat["messages"][2]["content"], model_input["text"])
            assert parsed is not None, error
    print(f"validated feedback v0.2 training={len(rows)}, holdout_v0.3_overlap=0")


if __name__ == "__main__":
    main()

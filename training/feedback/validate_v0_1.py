import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import parse_output, validate_input


ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data"


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((DATA / "feedback_v0.1.manifest.json").read_text(encoding="utf-8"))
    paths = {"source": DATA / "feedback_v0.1.jsonl", "train": DATA / "train_v0.1.chatml.jsonl",
             "eval": DATA / "eval_v0.1.chatml.jsonl"}
    assert sha(paths["source"]) == manifest["source_sha256"]
    assert sha(paths["train"]) == manifest["train_sha256"]
    assert sha(paths["eval"]) == manifest["eval_sha256"]
    source = [json.loads(line) for line in paths["source"].read_text(encoding="utf-8").splitlines() if line]
    holdout = [json.loads(line) for line in (ROOT / "evaluation/feedback/holdout_v0.1.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert len(source) == 600 and len({row["id"] for row in source}) == 600
    assert not ({row["text"] for row in source} & {row["text"] for row in holdout})
    for split in (paths["train"], paths["eval"]):
        for line in split.read_text(encoding="utf-8").splitlines():
            row = json.loads(line); model_input = json.loads(row["messages"][1]["content"])
            validate_input(model_input)
            parsed, error = parse_output(row["messages"][2]["content"], model_input["text"])
            assert parsed is not None, error
    assert manifest["holdout_used"] is False
    print(f"validated feedback training={len(source)}, holdout_overlap=0")


if __name__ == "__main__": main()

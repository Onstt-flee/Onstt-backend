"""Reparse a preserved feedback run with the current fail-closed contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import CONTRACT_VERSION, canonical_json, parse_output


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite reparsed run")
    gold = {row["id"]: row for row in load_jsonl(args.dataset)}
    rows = load_jsonl(args.run)
    if {row["id"] for row in rows} != set(gold):
        raise SystemExit("dataset and run IDs differ")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        for row in rows:
            parsed, error = parse_output(row.get("raw_text", ""), gold[row["id"]]["text"])
            updated = {
                **row,
                "parsed": parsed,
                "contract_success": parsed is not None,
                "contract_error": error,
                "reparsed_contract_version": CONTRACT_VERSION,
            }
            stream.write(canonical_json(updated) + "\n")
    manifest = {
        "schema_version": "feedback-reparsed-run-manifest-v0.1",
        "contract_version": CONTRACT_VERSION,
        "dataset_sha256": sha256(args.dataset),
        "source_run_sha256": sha256(args.run),
        "records": len(rows),
        "result_sha256": sha256(args.output),
    }
    args.output.with_suffix(args.output.suffix + ".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

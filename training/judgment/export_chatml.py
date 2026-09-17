"""Export reviewed canonical judgment data to split-specific ChatML JSONL."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from evaluation.judgment.runner import SYSTEM_PROMPT
from training.judgment.data import load_records, validate_records


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export(dataset: Path, output_dir: Path, *, allow_provisional: bool = False) -> dict:
    records = load_records(dataset)
    validate_records(records, require_reviewed=not allow_provisional)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for split in sorted({row["split"] for row in records}):
        path = output_dir / f"{split}.chatml.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            for row in records:
                if row["split"] != split:
                    continue
                sample = {
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": _canonical(row["input"])},
                        {"role": "assistant", "content": _canonical(row["expected"])},
                    ]
                }
                stream.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n")
        results[split] = {"path": str(path), "count": sum(row["split"] == split for row in records), "sha256": _sha256(path)}
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-provisional", action="store_true")
    args = parser.parse_args()
    results = export(args.dataset, args.output_dir, allow_provisional=args.allow_provisional)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

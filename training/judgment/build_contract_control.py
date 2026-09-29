"""Export the fixed v0.2-B data under the position-free v0.2 contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from training.judgment.data import load_records, validate_records
from training.judgment.export_chatml import export


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "training/judgment/data/pilot_v0.2_b.jsonl"
OUTPUT = ROOT / "training/judgment/data/contract_control_v0.2_b_chatml"
MANIFEST = ROOT / "training/judgment/data/contract_control_v0.2_b.manifest.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    records = load_records(SOURCE)
    validate_records(records, require_reviewed=True)
    if len(records) != 540:
        raise ValueError(f"Expected 540 unchanged v0.2-B records, got {len(records)}")

    chatml = export(SOURCE, OUTPUT, output_contract="v0.2")
    if {split: item["count"] for split, item in chatml.items()} != {
        "pilot_train": 432, "pilot_dev": 108,
    }:
        raise ValueError("Unexpected v0.2-B split counts")
    manifest = {
        "experiment_id": "judgment-qwen3-4b-contract-control-v0.2-b",
        "source_dataset": str(SOURCE.relative_to(ROOT)),
        "source_dataset_sha256": _sha256(SOURCE),
        "output_contract": "judgment-v0.2",
        "gold_labels_changed": False,
        "records": len(records),
        "chatml": chatml,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))

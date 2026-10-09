"""Build a fixed 720-example exposure schedule for v0.2-H.

No labels from holdout v0.4 are read. The source semantics are identical to
v0.2-G; only train-example exposure frequency changes.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from evaluation.judgment.runner import SYSTEM_PROMPT_V2
from training.judgment.data import load_records, validate_records


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "training/judgment/data/pilot_v0.2_g.jsonl"
OUTPUT = ROOT / "training/judgment/data/sampling_focus_v0.2_h_chatml"
MANIFEST = ROOT / "training/judgment/data/sampling_focus_v0.2_h.manifest.json"
TRAIN = OUTPUT / "pilot_train.chatml.jsonl"
DEV = OUTPUT / "pilot_dev.chatml.jsonl"
G_START = 949
EXTRA_ACCEPTABLE = 21


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _id_number(row: dict) -> int:
    return int(row["id"].split("-")[-1])


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _chatml(row: dict) -> dict:
    expected = row["expected"]
    output = {
        "decision": expected["decision"],
        "corrected_text": expected["corrected_text"],
        "error_types": list(dict.fromkeys(edit["error_type"] for edit in expected["edits"])),
        "reason_ko": expected["reason_ko"],
    }
    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT_V2},
        {"role": "user", "content": _canonical(row["input"])},
        {"role": "assistant", "content": _canonical(output)},
    ]}


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(_chatml(row), ensure_ascii=False, separators=(",", ":")) + "\n"
                for row in rows),
        encoding="utf-8",
    )


def _label(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build() -> dict:
    rows = load_records(SOURCE)
    validate_records(rows, require_reviewed=True)
    base_train = [row for row in rows if row["split"] == "pilot_train" and _id_number(row) < G_START]
    g_train = [row for row in rows if row["split"] == "pilot_train" and _id_number(row) >= G_START]
    dev = [row for row in rows if row["split"] == "pilot_dev"]
    g_hold = [row for row in g_train if row["expected"]["decision"] == "insufficient_evidence"]
    g_ok = [row for row in g_train if row["expected"]["decision"] == "acceptable"]
    repeats = g_hold + g_ok[:EXTRA_ACCEPTABLE]
    schedule = base_train + g_train + repeats

    if (len(base_train), len(g_train), len(repeats), len(schedule), len(dev)) != (594, 81, 45, 720, 181):
        raise ValueError("Unexpected v0.2-H exposure counts")
    if len(g_hold) != 24 or len(g_ok) != 39:
        raise ValueError("Unexpected G non-correction distribution")
    train_inputs = {_canonical(row["input"]) for row in schedule}
    dev_inputs = {_canonical(row["input"]) for row in dev}
    if train_inputs & dev_inputs:
        raise ValueError("Train/dev input overlap")

    _write(TRAIN, schedule)
    _write(DEV, dev)
    exposure = Counter(row["expected"]["decision"] for row in schedule)
    repeat_ids = [row["id"] for row in repeats]
    manifest = {
        "dataset_id": "judgment-sampling-focus-v0.2-h",
        "validated_at": "2026-10-04",
        "source_dataset": str(SOURCE.relative_to(ROOT)),
        "source_dataset_sha256": _sha256(SOURCE),
        "output_contract": "judgment-v0.2",
        "sampling_policy": {
            "optimizer_steps": 45,
            "gradient_accumulation_steps": 16,
            "scheduled_microbatches": 720,
            "base_d_train_once": len(base_train),
            "g_train_once": len(g_train),
            "g_extra_insufficient_evidence": len(g_hold),
            "g_extra_acceptable": EXTRA_ACCEPTABLE,
            "extra_needs_correction": 0,
            "repeat_ids": repeat_ids,
            "selection_rule": "all G train insufficient_evidence, then first 21 G train acceptable in canonical order",
        },
        "train": {"path": _label(TRAIN), "count": len(schedule),
                  "unique_inputs": len(train_inputs), "decision_exposures": dict(sorted(exposure.items())),
                  "sha256": _sha256(TRAIN)},
        "dev": {"path": _label(DEV), "count": len(dev),
                "unique_inputs": len(dev_inputs), "sha256": _sha256(DEV)},
        "holdout_policy": {
            "holdout_v0.4_read_by_builder": False,
            "model_inference_before_protocol_freeze": False,
        },
        "limitations": [
            "Repeated examples change exposure frequency but not gold semantics.",
            "The trainer must retain seed 42, shuffle enabled, batch 1, accumulation 16, and max_steps 45.",
            "generated_validated records are not human or expert reviewed.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))

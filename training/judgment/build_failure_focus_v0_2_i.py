"""Build v0.2-I from the v0.2-D base plus only the v0.2-F augmentation.

This is a controlled data-lineage ablation. It creates no new gold semantics and
never reads holdout v0.4 content; the holdout file is hashed only as a protected
artifact.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from evaluation.judgment.runner import SYSTEM_PROMPT_V2
from training.judgment.data import load_records, summary, validate_records


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "training/judgment/data"
BASE = DATA / "pilot_v0.2_d.jsonl"
AUGMENTATION = DATA / "failure_focus_v0.2_f.jsonl"
COMBINED = DATA / "pilot_v0.2_i.jsonl"
OUTPUT = DATA / "failure_focus_v0.2_i_chatml"
TRAIN = OUTPUT / "pilot_train.chatml.jsonl"
DEV = OUTPUT / "pilot_dev.chatml.jsonl"
MANIFEST = DATA / "failure_focus_v0.2_i.manifest.json"
SEALED_HOLDOUT = ROOT / "evaluation/judgment/holdout_v0.4.jsonl"
EXPECTED_HOLDOUT_SHA256 = "904ca090ccd0e209f95fa68a6a3e9fd762a0009c802f7eae7670838f9558221e"
VERSION = "failure-focus-v0.2-i"
VALIDATED_AT = "2026-10-08"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _write_jsonl(path: Path, rows: list[dict], transform=lambda row: row) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(transform(row), ensure_ascii=False, separators=(",", ":")) + "\n"
                for row in rows),
        encoding="utf-8",
    )


def build() -> dict:
    base = load_records(BASE)
    augmentation = load_records(AUGMENTATION)
    validate_records(base, require_reviewed=True)
    validate_records(augmentation, require_reviewed=True)
    if len(base) != 748 or len(augmentation) != 120:
        raise ValueError("Unexpected D or F augmentation size")
    combined = base + augmentation
    validate_records(combined, require_reviewed=True)
    if len({row["id"] for row in combined}) != len(combined):
        raise ValueError("Duplicate record ids")

    base_train = [row for row in base if row["split"] == "pilot_train"]
    base_dev = [row for row in base if row["split"] == "pilot_dev"]
    aug_train = [row for row in augmentation if row["split"] == "pilot_train"]
    aug_dev = [row for row in augmentation if row["split"] == "pilot_dev"]
    safe_acceptable = [row for row in base_train if row["expected"]["decision"] == "acceptable"][:24]
    safe_hold = [row for row in base_train if row["expected"]["decision"] == "insufficient_evidence"][:12]
    repeats = safe_acceptable + safe_hold
    schedule = base_train + aug_train + repeats
    dev = base_dev + aug_dev
    if (len(base_train), len(aug_train), len(repeats), len(schedule), len(dev)) != (594, 90, 36, 720, 184):
        raise ValueError("Unexpected v0.2-I exposure counts")
    train_inputs = {_canonical(row["input"]) for row in schedule}
    dev_inputs = {_canonical(row["input"]) for row in dev}
    if train_inputs & dev_inputs:
        raise ValueError("Train/dev input overlap")
    if _sha256(SEALED_HOLDOUT) != EXPECTED_HOLDOUT_SHA256:
        raise ValueError("Sealed holdout v0.4 hash changed")

    _write_jsonl(COMBINED, combined)
    _write_jsonl(TRAIN, schedule, _chatml)
    _write_jsonl(DEV, dev, _chatml)
    exposure = Counter(row["expected"]["decision"] for row in schedule)
    manifest = {
        "dataset_id": "judgment-failure-focus-v0.2-i",
        "validated_at": VALIDATED_AT,
        "output_contract": "judgment-v0.2",
        "design": "v0.2-D base plus v0.2-F augmentation only; fixed 720-example exposure",
        "sources": {
            str(BASE.relative_to(ROOT)): _sha256(BASE),
            str(AUGMENTATION.relative_to(ROOT)): _sha256(AUGMENTATION),
        },
        "combined": {
            "path": str(COMBINED.relative_to(ROOT)),
            "count": len(combined),
            "summary": summary(combined),
            "sha256": _sha256(COMBINED),
        },
        "train": {
            "path": str(TRAIN.relative_to(ROOT)),
            "count": len(schedule),
            "unique_inputs": len(train_inputs),
            "decision_exposures": dict(sorted(exposure.items())),
            "base_d_once": len(base_train),
            "f_augmentation_once": len(aug_train),
            "repeated_d_acceptable": len(safe_acceptable),
            "repeated_d_insufficient_evidence": len(safe_hold),
            "repeat_ids": [row["id"] for row in repeats],
            "sha256": _sha256(TRAIN),
        },
        "dev": {
            "path": str(DEV.relative_to(ROOT)),
            "count": len(dev),
            "unique_inputs": len(dev_inputs),
            "sha256": _sha256(DEV),
        },
        "sealed_holdout": {
            "path": str(SEALED_HOLDOUT.relative_to(ROOT)),
            "sha256": EXPECTED_HOLDOUT_SHA256,
            "content_read_by_builder": False,
            "model_inference_count": 0,
        },
        "review": {
            "new_gold_examples_created": 0,
            "human_or_expert_review_claimed": False,
            "status": "reviewed_with_generated",
        },
        "limitations": [
            "The F augmentation is generated_validated, not expert reviewed.",
            "Repeated D safety anchors change exposure frequency without adding semantics.",
            "Development-set improvement is not final generalization evidence.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))

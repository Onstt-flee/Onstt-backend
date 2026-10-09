"""Build final v0.2-J from v0.2-D plus the consumed v0.4 holdout.

The v0.4 set was already evaluated and is permanently retired as a benchmark.
This builder deliberately converts its fixed labels into generated-validated
training records. The sealed v0.5 file is hash-checked only and never read.
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
CONSUMED = ROOT / "evaluation/judgment/holdout_v0.4.jsonl"
COMBINED = DATA / "pilot_v0.2_j.jsonl"
OUTPUT = DATA / "final_v0.2_j_chatml"
TRAIN = OUTPUT / "pilot_train.chatml.jsonl"
DEV = OUTPUT / "pilot_dev.chatml.jsonl"
MANIFEST = DATA / "final_v0.2_j.manifest.json"
SEALED_HOLDOUT = ROOT / "evaluation/judgment/holdout_v0.5.jsonl"
EXPECTED_CONSUMED_SHA256 = "904ca090ccd0e209f95fa68a6a3e9fd762a0009c802f7eae7670838f9558221e"
EXPECTED_HOLDOUT_SHA256 = "b4b7ed63ccbd9008a7fa5544a3a494af20843e3accb4f6917700504b32ae6963"
VALIDATED_AT = "2026-10-10"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    path.write_text("".join(
        json.dumps(transform(row), ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    ), encoding="utf-8")


def _convert_consumed(rows: list[dict]) -> list[dict]:
    converted = []
    for number, row in enumerate(rows, 749):
        converted.append({
            "schema_version": row["schema_version"],
            "id": f"JT-{number:04d}",
            "split": "pilot_train",
            "template_family_id": "consumed_v04_" + row["group_id"],
            "tags": list(dict.fromkeys([
                *row["tags"], "source:consumed_holdout_v0.4", "generated_validated",
            ])),
            "input": row["input"],
            "expected": row["expected"],
            "accepted_corrections": row["accepted_corrections"],
            "provenance": {
                "kind": "deterministic_template",
                "source_id": "consumed-holdout-v0.4:" + row["id"],
                "external_text_used": False,
                "generator_model": None,
                "generator_revision": None,
                "generator_prompt_sha256": None,
            },
            "review": {"status": "generated_validated", "reviewed_at": VALIDATED_AT},
        })
    return converted


def build() -> dict:
    if _sha256(CONSUMED) != EXPECTED_CONSUMED_SHA256:
        raise ValueError("Consumed holdout v0.4 hash changed")
    if _sha256(SEALED_HOLDOUT) != EXPECTED_HOLDOUT_SHA256:
        raise ValueError("Sealed holdout v0.5 hash changed")
    base = load_records(BASE)
    consumed_raw = [json.loads(line) for line in CONSUMED.read_text(encoding="utf-8").splitlines() if line]
    if len(base) != 748 or len(consumed_raw) != 120:
        raise ValueError("Unexpected D or consumed v0.4 size")
    converted = _convert_consumed(consumed_raw)
    validate_records(base, require_reviewed=True)
    validate_records(converted, require_reviewed=True)
    base_input_map = {_canonical(row["input"]): row for row in base}
    duplicate_exposures = [row for row in converted if _canonical(row["input"]) in base_input_map]
    novel = [row for row in converted if _canonical(row["input"]) not in base_input_map]
    if len(duplicate_exposures) != 1:
        raise ValueError("Expected exactly one consumed input already present in D")
    duplicate = duplicate_exposures[0]
    prior = base_input_map[_canonical(duplicate["input"])]
    for key in ("decision", "corrected_text", "edits"):
        if duplicate["expected"][key] != prior["expected"][key]:
            raise ValueError(f"Consumed duplicate disagrees on {key}")
    if duplicate["accepted_corrections"] != prior["accepted_corrections"]:
        raise ValueError("Consumed duplicate disagrees on accepted corrections")
    combined = base + novel
    validate_records(combined, require_reviewed=True)

    base_train = [row for row in base if row["split"] == "pilot_train"]
    dev = [row for row in base if row["split"] == "pilot_dev"]
    schedule = base_train + converted
    if (len(base_train), len(converted), len(schedule), len(dev)) != (594, 120, 714, 154):
        raise ValueError("Unexpected v0.2-J exposure counts")
    train_inputs = {_canonical(row["input"]) for row in schedule}
    dev_inputs = {_canonical(row["input"]) for row in dev}
    if train_inputs & dev_inputs:
        raise ValueError("Train/dev input overlap")

    _write_jsonl(COMBINED, combined)
    _write_jsonl(TRAIN, schedule, _chatml)
    _write_jsonl(DEV, dev, _chatml)
    exposure = Counter(row["expected"]["decision"] for row in schedule)
    manifest = {
        "dataset_id": "judgment-final-v0.2-j",
        "validated_at": VALIDATED_AT,
        "output_contract": "judgment-v0.2",
        "design": "v0.2-D base plus the permanently consumed v0.4 benchmark; one pass per source row",
        "sources": {
            str(BASE.relative_to(ROOT)): _sha256(BASE),
            str(CONSUMED.relative_to(ROOT)): EXPECTED_CONSUMED_SHA256,
        },
        "combined": {"path": str(COMBINED.relative_to(ROOT)), "count": len(combined),
                     "summary": summary(combined), "consumed_unique_additions": len(novel),
                     "sha256": _sha256(COMBINED)},
        "train": {"path": str(TRAIN.relative_to(ROOT)), "count": len(schedule),
                  "unique_inputs": len(train_inputs), "decision_exposures": dict(sorted(exposure.items())),
                  "base_d_once": len(base_train), "consumed_v04_once": len(converted),
                  "consumed_duplicate_exposures": [{
                      "consumed_id": row["provenance"]["source_id"].split(":")[-1],
                      "existing_id": base_input_map[_canonical(row["input"])]["id"],
                      "same_semantic_label": True,
                  } for row in duplicate_exposures],
                  "sha256": _sha256(TRAIN)},
        "dev": {"path": str(DEV.relative_to(ROOT)), "count": len(dev),
                "unique_inputs": len(dev_inputs), "sha256": _sha256(DEV)},
        "consumed_benchmark": {"path": str(CONSUMED.relative_to(ROOT)),
                               "sha256": EXPECTED_CONSUMED_SHA256,
                               "permanently_retired_from_evaluation": True},
        "sealed_holdout": {"path": str(SEALED_HOLDOUT.relative_to(ROOT)),
                           "sha256": EXPECTED_HOLDOUT_SHA256,
                           "content_read_by_builder": False, "model_inference_count": 0},
        "review": {"new_gold_examples_created": 0, "human_or_expert_review_claimed": False,
                   "status": "reviewed_with_generated"},
        "limitations": [
            "The consumed v0.4 labels are generated_validated, not human or expert reviewed.",
            "v0.4 can never again be used as independent evaluation evidence.",
            "v0.5 shares broad template families with v0.4 despite lexical de-duplication.",
            "This is the final planned LoRA iteration; failure does not authorize tuning on v0.5.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))

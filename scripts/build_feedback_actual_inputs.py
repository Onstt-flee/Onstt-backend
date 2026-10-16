"""Build a private, label-free 200-row snapshot from stored Japanese STT."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_judgment_shadow import load_shadow_inputs, sha256_file


SAMPLE_SIZE = 200


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build(database: Path, output: Path, manifest_path: Path) -> dict:
    repository_root = Path(__file__).resolve().parents[1]
    try:
        output.resolve().relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise ValueError("content-bearing actual input snapshot must stay outside Git workspace")
    if output.exists() or manifest_path.exists():
        raise FileExistsError("refusing to overwrite actual shadow snapshot artifacts")

    rows = load_shadow_inputs(database, SAMPLE_SIZE)
    if len(rows) != SAMPLE_SIZE:
        raise ValueError(f"expected {SAMPLE_SIZE} stored STT rows, got {len(rows)}")
    payload = [
        {
            "id": f"FAS-{index:04d}",
            "input": {
                "text": row["text"],
                "context": None,
                "learner_level": row["learner_level"],
            },
            "stratum": "stored_stt_unlabeled",
        }
        for index, row in enumerate(rows, 1)
    ]
    raw = "".join(canonical(row) + "\n" for row in payload).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    source_ids = [row["utterance_id"] for row in rows]
    manifest = {
        "schema_version": "actual-feedback-shadow-inputs-v0.1",
        "purpose": "label_free_operational_shadow_only",
        "quality_claim_allowed": False,
        "input_count": SAMPLE_SIZE,
        "source_policy": "latest_eligible_japanese_stt",
        "context_policy": "null_exact_dialogue_context_unavailable",
        "source_database_sha256": sha256_file(database.resolve()),
        "private_inputs_sha256": hashlib.sha256(raw).hexdigest(),
        "source_id_set_sha256": hashlib.sha256(canonical(source_ids).encode()).hexdigest(),
        "contains_source_text": False,
        "contains_user_ids": False,
        "private_input_path_tracked": False,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.database, args.output, args.manifest), indent=2))
    except (OSError, ValueError) as exc:
        print(f"actual input snapshot failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

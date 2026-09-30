"""Run the frozen candidate gate with an explicit derived model name.

The v0.1 selector is retained byte-for-byte for the consumed holdout protocol.
This wrapper only corrects the derived artifact's model identity after applying
that same label-free selection rule.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation.judgment.candidate_selector import build_selected_run
from evaluation.judgment.dataset import DEFAULT_DATASET
from evaluation.judgment.scorer import load_verified_run


SELECTOR_WRAPPER_VERSION = "explicit-model-name-wrapper-v0.2"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_named_selected_run(
    primary_path: Path,
    secondary_path: Path,
    output_path: Path,
    *,
    model_name: str,
    dataset_path: Path = DEFAULT_DATASET,
    overwrite: bool = False,
) -> dict:
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("model_name must be nonblank")
    result = build_selected_run(
        primary_path, secondary_path, output_path,
        dataset_path=dataset_path, overwrite=overwrite,
    )
    output_path = Path(output_path).resolve()
    manifest_path = output_path.with_name(f"{output_path.name}.manifest.json")
    audit_path = output_path.with_name(f"{output_path.name}.selection.json")

    rows = []
    for line in output_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        row["request"]["model"] = model_name
        rows.append(row)
    output_path.write_text(
        "".join(_canonical_json(row) + "\n" for row in rows), encoding="utf-8"
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["model"] = model_name
    manifest["output_sha256"] = _sha256(output_path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["wrapper_version"] = SELECTOR_WRAPPER_VERSION
    audit["derived_model"] = model_name
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    load_verified_run(output_path, dataset_path=dataset_path)
    return {"manifest": manifest, "selection_audit": audit,
            "audit_path": str(audit_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--secondary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    result = build_named_selected_run(
        args.primary, args.secondary, args.output,
        model_name=args.model_name, dataset_path=args.dataset,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

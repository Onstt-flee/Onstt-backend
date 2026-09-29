"""Select a correction candidate without changing the primary model decision.

The selector is label-free. It uses only the learner input and two model outputs,
never dataset gold labels. The primary model owns the decision; the secondary
candidate is considered only when both models request a correction.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import platform
import re
from typing import Any

from evaluation.judgment.dataset import DEFAULT_DATASET
from evaluation.judgment.runner import _artifact_paths, parse_model_output
from evaluation.judgment.scorer import load_verified_run


SELECTOR_VERSION = "primary-decision-candidate-gate-v0.1"
POLITE_ENDING = re.compile(
    r"(?:ませんでした|ません|ました|ます|でした|です|ください|なりません)[。！？!?]?$"
)
MALFORMED_PATTERNS = (
    re.compile(r"いくて"),
    re.compile(r"いかった"),
    re.compile(r"いくない"),
    re.compile(r"いな(?=[一-龯々ぁ-んァ-ン])"),
    re.compile(r"(?:る|む|く|う)ます"),
    re.compile(r"(?:る|む|く|う)ました"),
    re.compile(r"な(?:です|でした)"),
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _malformed_count(text: str) -> int:
    return sum(len(pattern.findall(text)) for pattern in MALFORMED_PATTERNS)


def _edit_magnitude(source: str, candidate: str) -> int:
    total = 0
    for tag, start, end, target_start, target_end in SequenceMatcher(
        None, source, candidate, autojunk=False
    ).get_opcodes():
        if tag != "equal":
            total += max(end - start, target_end - target_start)
    return total


def candidate_score(source: str, candidate: str) -> tuple[int, int, int, int]:
    """Higher is better; style and obvious malformed remnants precede size."""
    request_preserved = int("ください" not in source or "ください" in candidate)
    polite_preserved = int(not POLITE_ENDING.search(source) or POLITE_ENDING.search(candidate) is not None)
    return (
        request_preserved,
        polite_preserved,
        -_malformed_count(candidate),
        -_edit_magnitude(source, candidate),
    )


def _latency_ms(row: dict, *, label: str) -> float:
    value = row["response"]["latency_ms"]
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} latency_ms must be a non-negative number")
    return float(value)


def choose_candidate(source: str, primary: dict, secondary: dict | None) -> tuple[dict, str, dict]:
    """Keep primary decisions; replace only a jointly proposed correction."""
    primary_score = candidate_score(source, primary["corrected_text"])
    audit = {"primary_score": list(primary_score), "secondary_score": None}
    if primary["decision"] != "needs_correction":
        return primary, "primary_decision_locked", audit
    if not secondary or secondary["decision"] != "needs_correction":
        return primary, "secondary_not_correction", audit
    secondary_score = candidate_score(source, secondary["corrected_text"])
    audit["secondary_score"] = list(secondary_score)
    if secondary_score > primary_score:
        return secondary, "secondary_higher_gate_score", audit
    return primary, "primary_tie_or_higher", audit


def build_selected_run(
    primary_path: Path,
    secondary_path: Path,
    output_path: Path,
    *,
    dataset_path: Path = DEFAULT_DATASET,
    overwrite: bool = False,
) -> dict:
    primary = load_verified_run(primary_path, dataset_path=dataset_path)
    secondary = load_verified_run(secondary_path, dataset_path=dataset_path)
    pm, sm = primary["manifest"], secondary["manifest"]
    if pm["dataset_sha256"] != sm["dataset_sha256"]:
        raise ValueError("source runs use different datasets")
    if pm["input_ids"] != sm["input_ids"]:
        raise ValueError("source runs contain different IDs")
    if pm["prompt_version"] != sm["prompt_version"] or pm["prompt_sha256"] != sm["prompt_sha256"]:
        raise ValueError("source runs use different prompts")
    if pm["generation"] != sm["generation"]:
        raise ValueError("source runs use different generation settings")

    output_path = Path(output_path).resolve()
    _, manifest_path = _artifact_paths(output_path)
    audit_path = output_path.with_name(f"{output_path.name}.selection.json")
    existing = [path for path in (output_path, manifest_path, audit_path) if path.exists()]
    if existing and not overwrite:
        raise FileExistsError("output artifacts already exist: " + ", ".join(map(str, existing)))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fingerprint = hashlib.sha256(
        (SELECTOR_VERSION + pm["output_sha256"] + sm["output_sha256"]).encode()
    ).hexdigest()
    run_id = f"selector-v0.1-{fingerprint[:12]}"
    model = "judgment-v02d-gated-v02e"
    rows, selections = [], []
    for p_row, s_row in zip(primary["rows"], secondary["rows"]):
        if p_row["id"] != s_row["id"] or p_row["input"] != s_row["input"]:
            raise ValueError("source run rows do not align")
        source = p_row["input"]["text"]
        p = p_row["response"]["parsed_judgment"]
        s = s_row["response"]["parsed_judgment"]
        if p is None:
            raise ValueError(f"primary contract invalid for {p_row['id']}")
        primary_latency_ms = _latency_ms(p_row, label=f"primary {p_row['id']}")
        secondary_called = p["decision"] == "needs_correction"
        secondary_latency_ms = (
            _latency_ms(s_row, label=f"secondary {s_row['id']}")
            if secondary_called else None
        )
        conditional_latency_ms = primary_latency_ms + (secondary_latency_ms or 0.0)
        selected, reason, score_audit = choose_candidate(source, p, s)
        compact = {
            "decision": selected["decision"],
            "corrected_text": selected["corrected_text"],
            "error_types": selected["error_types"],
            "reason_ko": selected["reason_ko"],
        }
        raw_text = _canonical_json(compact)
        parsed, contract_error = parse_model_output(raw_text, source, pm["prompt_version"])
        if parsed is None:
            raise ValueError(f"selected candidate invalid for {p_row['id']}: {contract_error}")
        row = deepcopy(p_row)
        row["run_id"] = run_id
        row["request"]["model"] = model
        row["response"] = {
            "transport_success": True,
            "http_status": None,
            "raw_text": raw_text,
            "raw_response": _canonical_json({
                "selector_version": SELECTOR_VERSION,
                "primary_model": pm["model"],
                "secondary_model": sm["model"],
                "selection_reason": reason,
            }),
            "usage": None,
            "error": None,
            "latency_ms": round(conditional_latency_ms, 3),
            "contract_valid": True,
            "contract_error": None,
            "parsed_judgment": parsed,
        }
        rows.append(row)
        selections.append({
            "id": p_row["id"],
            "selected": "secondary" if selected is s else "primary",
            "reason": reason,
            "primary_latency_ms": primary_latency_ms,
            "secondary_called": secondary_called,
            "secondary_latency_ms": secondary_latency_ms,
            "conditional_gate_latency_ms": round(conditional_latency_ms, 3),
            **score_audit,
        })

    content = "".join(_canonical_json(row) + "\n" for row in rows)
    output_path.write_text(content, encoding="utf-8")
    manifest = {
        "schema_version": "0.1",
        "run_id": run_id,
        "started_at": pm["completed_at"],
        "completed_at": sm["completed_at"],
        "dataset_path": str(Path(dataset_path).resolve()),
        "dataset_sha256": pm["dataset_sha256"],
        "output_path": str(output_path),
        "output_sha256": _sha256(output_path),
        "input_count": len(rows),
        "input_ids": [row["id"] for row in rows],
        "endpoint": "offline://candidate-selector",
        "model": model,
        "prompt_version": pm["prompt_version"],
        "prompt_sha256": pm["prompt_sha256"],
        "generation": pm["generation"],
        "authentication": "none",
        "transport_success_count": len(rows),
        "transport_failure_count": 0,
        "contract_valid_count": len(rows),
        "contract_invalid_count": 0,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = {
        "selector_version": SELECTOR_VERSION,
        "primary_path": str(Path(primary_path).resolve()),
        "primary_sha256": pm["output_sha256"],
        "secondary_path": str(Path(secondary_path).resolve()),
        "secondary_sha256": sm["output_sha256"],
        "gold_labels_used": False,
        "secondary_selected_count": sum(item["selected"] == "secondary" for item in selections),
        "selections": selections,
        "latency_policy": "primary_plus_secondary_only_when_primary_needs_correction",
        "primary_latency_ms_total": round(sum(
            item["primary_latency_ms"] for item in selections
        ), 3),
        "conditional_gate_latency_ms_total": round(sum(
            item["conditional_gate_latency_ms"] for item in selections
        ), 3),
        "secondary_called_count": sum(item["secondary_called"] for item in selections),
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Prove the derived artifact satisfies the same immutable run contract.
    load_verified_run(output_path, dataset_path=dataset_path)
    return {"manifest": manifest, "selection_audit": audit, "audit_path": str(audit_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--secondary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    result = build_selected_run(
        args.primary, args.secondary, args.output,
        dataset_path=args.dataset, overwrite=args.overwrite,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

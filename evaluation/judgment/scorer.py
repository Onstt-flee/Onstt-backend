"""Verify and score label-free judgment run artifacts without calling a model."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
from typing import Any, Iterable

from evaluation.judgment.dataset import (
    DEFAULT_DATASET,
    ERROR_TYPES,
    REVIEW_CHECK_LABELS,
    load_records,
    validate_records,
)
from evaluation.judgment.runner import _artifact_paths, parse_model_output


LABELS = ("acceptable", "needs_correction", "insufficient_evidence")
FAILURE_LABEL = "system_failure"
TARGETS = {
    "json_contract_success_rate": {"operator": ">=", "value": 0.99},
    "overcorrection_rate": {"operator": "<=", "value": 0.02},
    "correction_detection_precision": {"operator": ">=", "value": 0.95},
    "correction_detection_recall": {"operator": ">=", "value": 0.80},
    "clear_case_handling_rate": {"operator": ">=", "value": 0.85},
}
RUN_KEYS = {
    "schema_version", "run_id", "id", "input", "input_sha256", "request",
    "response",
}
REQUEST_KEYS = {
    "model", "messages", "temperature", "top_p", "max_tokens", "stream",
}
RESPONSE_KEYS = {
    "transport_success", "http_status", "raw_text", "raw_response", "usage",
    "error", "latency_ms", "contract_valid", "contract_error",
    "parsed_judgment",
}
MANIFEST_KEYS = {
    "schema_version", "run_id", "started_at", "completed_at", "dataset_path",
    "dataset_sha256", "output_path", "output_sha256", "input_count",
    "input_ids", "endpoint", "model", "prompt_version", "prompt_sha256",
    "generation", "authentication", "transport_success_count",
    "transport_failure_count", "contract_valid_count",
    "contract_invalid_count", "python_version", "platform",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-standard JSON constant: {value}")


def _load_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
        parse_constant=_reject_constant,
    )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"{path}:{number}: blank JSONL line")
            try:
                value = json.loads(
                    line,
                    object_pairs_hook=_strict_object,
                    parse_constant=_reject_constant,
                )
            except ValueError as exc:
                raise ValueError(f"{path}:{number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{number}: row must be an object")
            rows.append(value)
    if not rows:
        raise ValueError(f"{path}: run is empty")
    return rows


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _exact_keys(value: Any, keys: set[str], name: str) -> None:
    _require(isinstance(value, dict), f"{name} must be an object")
    _require(
        set(value) == keys,
        f"{name} must have exactly: {', '.join(sorted(keys))}",
    )


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _wilson(successes: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    observed = successes / total
    denominator = 1 + z * z / total
    center = (observed + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            observed * (1 - observed) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _rate(successes: int, total: int) -> dict[str, Any]:
    return {
        "numerator": successes,
        "denominator": total,
        "value": successes / total if total else None,
        "ci95_wilson": _wilson(successes, total),
    }


def _nearest_percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _edit_key(edit: dict[str, Any]) -> tuple[Any, ...]:
    return (
        edit["start"],
        edit["end"],
        edit["source"],
        edit["replacement"],
        edit["error_type"],
    )


def _prediction(row: dict[str, Any]) -> dict[str, Any] | None:
    response = row["response"]
    if response["transport_success"] and response["contract_valid"]:
        return response["parsed_judgment"]
    return None


def _validate_manifest(manifest: Any, manifest_path: Path) -> None:
    _exact_keys(manifest, MANIFEST_KEYS, "manifest")
    _require(manifest["schema_version"] == "0.1", "unsupported manifest schema")
    for key in (
        "run_id", "dataset_path", "dataset_sha256", "output_path",
        "output_sha256", "endpoint", "model", "prompt_version",
        "prompt_sha256", "authentication", "python_version", "platform",
    ):
        _require(
            isinstance(manifest[key], str) and bool(manifest[key]),
            f"manifest.{key} must be a nonblank string",
        )
    _require(
        type(manifest["input_count"]) is int and manifest["input_count"] > 0,
        "manifest.input_count must be positive",
    )
    _require(
        isinstance(manifest["input_ids"], list)
        and all(isinstance(value, str) and value for value in manifest["input_ids"]),
        "manifest.input_ids must be nonblank strings",
    )
    _require(
        len(manifest["input_ids"]) == len(set(manifest["input_ids"])),
        "manifest.input_ids contains duplicates",
    )
    _exact_keys(
        manifest["generation"],
        {"temperature", "top_p", "max_tokens"},
        "manifest.generation",
    )
    _require(
        _is_number(manifest["generation"]["temperature"])
        and 0 <= manifest["generation"]["temperature"] <= 2,
        "manifest.generation.temperature is invalid",
    )
    _require(
        _is_number(manifest["generation"]["top_p"])
        and 0 < manifest["generation"]["top_p"] <= 1,
        "manifest.generation.top_p is invalid",
    )
    _require(
        type(manifest["generation"]["max_tokens"]) is int
        and manifest["generation"]["max_tokens"] > 0,
        "manifest.generation.max_tokens is invalid",
    )
    for key in (
        "transport_success_count", "transport_failure_count",
        "contract_valid_count", "contract_invalid_count",
    ):
        _require(
            type(manifest[key]) is int and manifest[key] >= 0,
            f"manifest.{key} must be a nonnegative integer",
        )
    _require(
        manifest["authentication"] in {"none", "bearer_env"},
        "manifest.authentication is invalid",
    )
    for key in ("started_at", "completed_at"):
        try:
            datetime.fromisoformat(manifest[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"manifest.{key} is not ISO-8601") from exc
    _require(
        manifest_path.name.endswith(".manifest.json"),
        "manifest filename must end with .manifest.json",
    )


def load_verified_run(
    run_path: Path,
    *,
    dataset_path: Path = DEFAULT_DATASET,
) -> dict[str, Any]:
    """Load an immutable run pair and prove it still matches the reviewed dataset."""
    run_path = Path(run_path).resolve()
    dataset_path = Path(dataset_path).resolve()
    _require(run_path.is_file(), f"run not found: {run_path}")
    _require(dataset_path.is_file(), f"dataset not found: {dataset_path}")
    _, manifest_path = _artifact_paths(run_path)
    _require(manifest_path.is_file(), f"manifest not found: {manifest_path}")

    manifest = _load_json(manifest_path)
    _validate_manifest(manifest, manifest_path)
    records = load_records(dataset_path)
    validate_records(records)
    _require(
        all(row["review"]["status"] != "provisional" for row in records),
        "scoring requires a dataset without provisional labels",
    )
    dataset_sha256 = _sha256_bytes(dataset_path.read_bytes())
    _require(
        manifest["dataset_sha256"] == dataset_sha256,
        "dataset SHA-256 does not match the run manifest",
    )
    _require(
        manifest["output_sha256"] == _sha256_bytes(run_path.read_bytes()),
        "run output SHA-256 does not match the manifest",
    )

    rows = _load_jsonl(run_path)
    _require(
        manifest["input_count"] == len(rows),
        "manifest input_count does not match run rows",
    )
    _require(
        manifest["input_ids"] == [row.get("id") for row in rows],
        "manifest input_ids do not match run row order",
    )
    dataset_by_id = {row["id"]: row for row in records}
    ids = [row.get("id") for row in rows]
    _require(
        len(ids) == len(set(ids)),
        "run contains duplicate IDs",
    )
    unknown = [value for value in ids if value not in dataset_by_id]
    _require(not unknown, "run contains unknown IDs: " + ", ".join(unknown))
    selected_order = [row["id"] for row in records if row["id"] in set(ids)]
    _require(
        ids == selected_order,
        "run IDs are not in dataset order",
    )

    transport_success_count = 0
    contract_valid_count = 0
    prompt_contents: set[str] = set()
    for number, row in enumerate(rows, 1):
        prefix = f"run row {number} ({row.get('id', '?')})"
        _exact_keys(row, RUN_KEYS, prefix)
        _require(row["schema_version"] == "0.1", f"{prefix}: bad schema")
        _require(
            row["run_id"] == manifest["run_id"],
            f"{prefix}: run_id mismatch",
        )
        gold = dataset_by_id[row["id"]]
        _require(row["input"] == gold["input"], f"{prefix}: input mismatch")
        _require(
            row["input_sha256"] == _sha256_json(row["input"]),
            f"{prefix}: input SHA-256 mismatch",
        )

        request = row["request"]
        _exact_keys(request, REQUEST_KEYS, f"{prefix}.request")
        _require(
            request["model"] == manifest["model"],
            f"{prefix}: model mismatch",
        )
        _require(request["stream"] is False, f"{prefix}: stream must be false")
        for key in ("temperature", "top_p", "max_tokens"):
            _require(
                request[key] == manifest["generation"][key],
                f"{prefix}: generation mismatch for {key}",
            )
        messages = request["messages"]
        _require(
            isinstance(messages, list) and len(messages) == 2,
            f"{prefix}: exactly two messages are required",
        )
        _exact_keys(messages[0], {"role", "content"}, f"{prefix}.system")
        _exact_keys(messages[1], {"role", "content"}, f"{prefix}.user")
        _require(
            messages[0]["role"] == "system"
            and isinstance(messages[0]["content"], str),
            f"{prefix}: invalid system message",
        )
        _require(
            messages[1]["role"] == "user"
            and isinstance(messages[1]["content"], str),
            f"{prefix}: invalid user message",
        )
        prompt_contents.add(messages[0]["content"])
        _require(
            _sha256_bytes(messages[0]["content"].encode("utf-8"))
            == manifest["prompt_sha256"],
            f"{prefix}: prompt SHA-256 mismatch",
        )
        try:
            visible_input = json.loads(
                messages[1]["content"],
                object_pairs_hook=_strict_object,
                parse_constant=_reject_constant,
            )
        except ValueError as exc:
            raise ValueError(f"{prefix}: invalid model-visible JSON: {exc}") from exc
        _require(
            isinstance(visible_input, dict)
            and set(visible_input) == {"text", "context", "learner_level"},
            f"{prefix}: model-visible fields are not allowlisted",
        )
        _require(
            visible_input == gold["input"],
            f"{prefix}: model-visible input mismatch",
        )

        response = row["response"]
        _exact_keys(response, RESPONSE_KEYS, f"{prefix}.response")
        _require(
            type(response["transport_success"]) is bool,
            f"{prefix}: transport_success must be bool",
        )
        _require(
            type(response["contract_valid"]) is bool,
            f"{prefix}: contract_valid must be bool",
        )
        _require(
            isinstance(response["raw_text"], str)
            and isinstance(response["raw_response"], str),
            f"{prefix}: raw response fields must be strings",
        )
        _require(
            response["http_status"] is None
            or type(response["http_status"]) is int,
            f"{prefix}: invalid http_status",
        )
        _require(
            response["latency_ms"] is None
            or (
                _is_number(response["latency_ms"])
                and response["latency_ms"] >= 0
            ),
            f"{prefix}: invalid latency_ms",
        )
        _require(
            response["usage"] is None or isinstance(response["usage"], dict),
            f"{prefix}: usage must be an object or null",
        )
        _require(
            response["error"] is None or isinstance(response["error"], str),
            f"{prefix}: error must be a string or null",
        )
        _require(
            response["contract_error"] is None
            or isinstance(response["contract_error"], str),
            f"{prefix}: contract_error must be a string or null",
        )
        if response["transport_success"]:
            transport_success_count += 1
            parsed, contract_error = parse_model_output(
                response["raw_text"], gold["input"]["text"]
            )
        else:
            parsed = None
            contract_error = "Transport did not return assistant content"
        _require(
            response["contract_valid"] is (parsed is not None),
            f"{prefix}: stored contract_valid disagrees with strict parsing",
        )
        _require(
            response["parsed_judgment"] == parsed,
            f"{prefix}: stored parsed_judgment disagrees with raw_text",
        )
        _require(
            response["contract_error"] == contract_error,
            f"{prefix}: stored contract_error disagrees with strict parsing",
        )
        if parsed is not None:
            contract_valid_count += 1

    _require(len(prompt_contents) == 1, "run mixes multiple system prompts")
    _require(
        manifest["transport_success_count"] == transport_success_count,
        "manifest transport_success_count mismatch",
    )
    _require(
        manifest["transport_failure_count"]
        == len(rows) - transport_success_count,
        "manifest transport_failure_count mismatch",
    )
    _require(
        manifest["contract_valid_count"] == contract_valid_count,
        "manifest contract_valid_count mismatch",
    )
    _require(
        manifest["contract_invalid_count"] == len(rows) - contract_valid_count,
        "manifest contract_invalid_count mismatch",
    )
    return {
        "run_path": str(run_path),
        "manifest_path": str(manifest_path),
        "dataset_path": str(dataset_path),
        "dataset_sha256": dataset_sha256,
        "manifest": manifest,
        "rows": rows,
        "records": [dataset_by_id[value] for value in ids],
    }


def _score_subset(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    valid = sum(case["prediction"] is not None for case in cases)
    correct = sum(
        case["prediction"] is not None
        and case["prediction"]["decision"] == case["gold"]["decision"]
        for case in cases
    )
    acceptable = [
        case for case in cases if case["gold"]["decision"] == "acceptable"
    ]
    corrections = [
        case for case in cases
        if case["gold"]["decision"] == "needs_correction"
    ]
    insufficient = [
        case for case in cases
        if case["gold"]["decision"] == "insufficient_evidence"
    ]
    predicted_corrections = [
        case for case in cases
        if case["prediction"] is not None
        and case["prediction"]["decision"] == "needs_correction"
    ]
    true_positive = sum(
        case["gold"]["decision"] == "needs_correction"
        for case in predicted_corrections
    )
    overcorrected = sum(
        case["prediction"] is not None
        and case["prediction"]["decision"] == "needs_correction"
        for case in acceptable
    )
    withheld = sum(
        case["prediction"] is not None
        and case["prediction"]["decision"] == "insufficient_evidence"
        for case in insufficient
    )
    clear = [
        case for case in cases
        if case["gold"]["decision"] != "insufficient_evidence"
    ]
    handled = sum(
        case["prediction"] is not None
        and case["prediction"]["decision"] != "insufficient_evidence"
        for case in clear
    )
    return {
        "count": total,
        "json_contract_success_rate": _rate(valid, total),
        "decision_accuracy": _rate(correct, total),
        "overcorrection_rate": _rate(overcorrected, len(acceptable)),
        "correction_detection_precision": _rate(
            true_positive, len(predicted_corrections)
        ),
        "correction_detection_recall": _rate(
            true_positive, len(corrections)
        ),
        "correct_withholding_rate": _rate(withheld, len(insufficient)),
        "clear_case_handling_rate": _rate(handled, len(clear)),
    }


def score_verified_run(verified: dict[str, Any]) -> dict[str, Any]:
    """Compute deterministic metrics; invalid responses remain system failures."""
    cases: list[dict[str, Any]] = []
    for row, record in zip(verified["rows"], verified["records"]):
        prediction = _prediction(row)
        cases.append(
            {
                "id": row["id"],
                "tags": record["tags"],
                "level": record["input"]["learner_level"],
                "gold": record["expected"],
                "accepted": record["accepted_corrections"],
                "prediction": prediction,
                "response": row["response"],
            }
        )

    total = len(cases)
    valid = sum(case["prediction"] is not None for case in cases)
    transport = sum(
        case["response"]["transport_success"] for case in cases
    )
    confusion = {
        gold: {predicted: 0 for predicted in (*LABELS, FAILURE_LABEL)}
        for gold in LABELS
    }
    for case in cases:
        predicted = (
            case["prediction"]["decision"]
            if case["prediction"] is not None
            else FAILURE_LABEL
        )
        confusion[case["gold"]["decision"]][predicted] += 1

    decision_correct = sum(
        case["prediction"] is not None
        and case["prediction"]["decision"] == case["gold"]["decision"]
        for case in cases
    )
    acceptable = [
        case for case in cases if case["gold"]["decision"] == "acceptable"
    ]
    gold_corrections = [
        case for case in cases
        if case["gold"]["decision"] == "needs_correction"
    ]
    gold_insufficient = [
        case for case in cases
        if case["gold"]["decision"] == "insufficient_evidence"
    ]
    predicted_corrections = [
        case for case in cases
        if case["prediction"] is not None
        and case["prediction"]["decision"] == "needs_correction"
    ]
    true_positive = [
        case for case in predicted_corrections
        if case["gold"]["decision"] == "needs_correction"
    ]
    overcorrected = [
        case for case in acceptable
        if case["prediction"] is not None
        and case["prediction"]["decision"] == "needs_correction"
    ]
    correction_false_positive = [
        case for case in predicted_corrections
        if case["gold"]["decision"] != "needs_correction"
    ]
    correction_false_negative = [
        case for case in gold_corrections
        if case["prediction"] is None
        or case["prediction"]["decision"] != "needs_correction"
    ]
    correct_withholding = [
        case for case in gold_insufficient
        if case["prediction"] is not None
        and case["prediction"]["decision"] == "insufficient_evidence"
    ]
    clear_cases = [
        case for case in cases
        if case["gold"]["decision"] != "insufficient_evidence"
    ]
    clear_handled = [
        case for case in clear_cases
        if case["prediction"] is not None
        and case["prediction"]["decision"] != "insufficient_evidence"
    ]

    canonical = [
        case for case in gold_corrections
        if case["prediction"] is not None
        and case["prediction"]["decision"] == "needs_correction"
        and case["prediction"]["corrected_text"]
        == case["gold"]["corrected_text"]
    ]
    accepted = [
        case for case in gold_corrections
        if case["prediction"] is not None
        and case["prediction"]["decision"] == "needs_correction"
        and case["prediction"]["corrected_text"] in case["accepted"]
    ]
    exact_edits = [
        case for case in gold_corrections
        if case["prediction"] is not None
        and case["prediction"]["decision"] == "needs_correction"
        and case["prediction"]["edits"] == case["gold"]["edits"]
    ]

    gold_edit_counter: Counter[tuple[Any, ...]] = Counter()
    predicted_edit_counter: Counter[tuple[Any, ...]] = Counter()
    for case in cases:
        for edit in case["gold"]["edits"]:
            gold_edit_counter[(case["id"], *_edit_key(edit))] += 1
        if case["prediction"] is not None:
            for edit in case["prediction"]["edits"]:
                predicted_edit_counter[(case["id"], *_edit_key(edit))] += 1
    edit_true_positive = sum(
        (gold_edit_counter & predicted_edit_counter).values()
    )

    compound = [
        case for case in gold_corrections
        if len(case["gold"]["edits"]) > 1
    ]
    compound_complete = 0
    compound_missing_edits = 0
    for case in compound:
        gold_keys = Counter(_edit_key(edit) for edit in case["gold"]["edits"])
        predicted_keys: Counter[tuple[Any, ...]] = Counter()
        if case["prediction"] is not None:
            predicted_keys.update(
                _edit_key(edit) for edit in case["prediction"]["edits"]
            )
        missing = gold_keys - predicted_keys
        compound_missing_edits += sum(missing.values())
        if not missing:
            compound_complete += 1

    type_metrics: dict[str, Any] = {}
    for error_type in sorted(ERROR_TYPES):
        gold_type = {
            case["id"] for case in cases
            if any(
                edit["error_type"] == error_type
                for edit in case["gold"]["edits"]
            )
        }
        predicted_type = {
            case["id"] for case in cases
            if case["prediction"] is not None
            and any(
                edit["error_type"] == error_type
                for edit in case["prediction"]["edits"]
            )
        }
        intersection = gold_type & predicted_type
        type_metrics[error_type] = {
            "precision": _rate(len(intersection), len(predicted_type)),
            "recall": _rate(len(intersection), len(gold_type)),
            "gold_support": len(gold_type),
            "predicted_count": len(predicted_type),
        }

    levels = sorted({case["level"] for case in cases})
    by_level = {
        level: _score_subset(
            [case for case in cases if case["level"] == level]
        )
        for level in levels
    }
    tag_names = ["boundary_case", *sorted(REVIEW_CHECK_LABELS)]
    by_review_tag = {}
    for tag in tag_names:
        selected = [case for case in cases if tag in case["tags"]]
        if selected:
            by_review_tag[tag] = _score_subset(selected)

    latencies = [
        float(case["response"]["latency_ms"])
        for case in cases
        if _is_number(case["response"]["latency_ms"])
    ]
    usage_totals = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    usage_rows = 0
    for case in cases:
        usage = case["response"]["usage"]
        if not isinstance(usage, dict):
            continue
        found = False
        for key in usage_totals:
            value = usage.get(key)
            if type(value) is int and value >= 0:
                usage_totals[key] += value
                found = True
        usage_rows += int(found)
    total_latency_seconds = sum(latencies) / 1000
    throughput = (
        usage_totals["completion_tokens"] / total_latency_seconds
        if total_latency_seconds and usage_totals["completion_tokens"]
        else None
    )

    metrics = {
        "transport_success_rate": _rate(transport, total),
        "json_contract_success_rate": _rate(valid, total),
        "decision_accuracy": _rate(decision_correct, total),
        "overcorrection_rate": _rate(
            len(overcorrected), len(acceptable)
        ),
        "correction_detection_precision": _rate(
            len(true_positive), len(true_positive) + len(correction_false_positive)
        ),
        "correction_detection_recall": _rate(
            len(true_positive), len(true_positive) + len(correction_false_negative)
        ),
        "correct_withholding_rate": _rate(
            len(correct_withholding), len(gold_insufficient)
        ),
        "clear_case_handling_rate": _rate(
            len(clear_handled), len(clear_cases)
        ),
        "canonical_correction_exact_rate_end_to_end": _rate(
            len(canonical), len(gold_corrections)
        ),
        "accepted_correction_rate_end_to_end": _rate(
            len(accepted), len(gold_corrections)
        ),
        "accepted_correction_rate_given_detected": _rate(
            len(accepted), len(true_positive)
        ),
        "exact_canonical_edits_rate_end_to_end": _rate(
            len(exact_edits), len(gold_corrections)
        ),
        "edit_micro_precision": _rate(
            edit_true_positive, sum(predicted_edit_counter.values())
        ),
        "edit_micro_recall": _rate(
            edit_true_positive, sum(gold_edit_counter.values())
        ),
        "compound_complete_rate": _rate(
            compound_complete, len(compound)
        ),
        "compound_missing_edit_count": compound_missing_edits,
    }

    target_results: dict[str, Any] = {}
    for name, target in TARGETS.items():
        observed = metrics[name]["value"]
        passed = False
        if observed is not None:
            if target["operator"] == ">=":
                passed = observed >= target["value"]
            else:
                passed = observed <= target["value"]
        target_results[name] = {
            **target,
            "observed": observed,
            "passed": passed,
        }

    return {
        "schema_version": "0.1",
        "run": {
            "run_id": verified["manifest"]["run_id"],
            "model": verified["manifest"]["model"],
            "run_path": verified["run_path"],
            "manifest_path": verified["manifest_path"],
            "dataset_sha256": verified["dataset_sha256"],
            "prompt_version": verified["manifest"]["prompt_version"],
            "prompt_sha256": verified["manifest"]["prompt_sha256"],
            "generation": verified["manifest"]["generation"],
            "input_ids": verified["manifest"]["input_ids"],
        },
        "counts": {
            "total": total,
            "gold": dict(Counter(
                case["gold"]["decision"] for case in cases
            )),
            "system_failures": total - valid,
            "transport_failures": total - transport,
            "contract_failures_after_transport": transport - valid,
        },
        "metrics": metrics,
        "confusion_matrix": confusion,
        "error_type_metrics": type_metrics,
        "by_learner_level": by_level,
        "by_review_tag": by_review_tag,
        "performance": {
            "latency_ms": {
                "count": len(latencies),
                "mean": statistics.fmean(latencies) if latencies else None,
                "p50": _nearest_percentile(latencies, 0.50),
                "p95": _nearest_percentile(latencies, 0.95),
            },
            "usage_rows": usage_rows,
            "usage_totals": usage_totals,
            "completion_tokens_per_second_of_request_latency": throughput,
        },
        "targets": target_results,
        "meets_all_targets": all(
            result["passed"] for result in target_results.values()
        ),
        "case_lists": {
            "system_failure_ids": [
                case["id"] for case in cases if case["prediction"] is None
            ],
            "decision_error_ids": [
                case["id"] for case in cases
                if case["prediction"] is None
                or case["prediction"]["decision"] != case["gold"]["decision"]
            ],
            "overcorrection_ids": [case["id"] for case in overcorrected],
            "missed_correction_ids": [
                case["id"] for case in correction_false_negative
            ],
            "noncanonical_but_accepted_ids": [
                case["id"] for case in accepted if case not in canonical
            ],
        },
        "limitations": [
            "reason_ko의 언어학적 타당성과 의미 보존은 자동 채점하지 않습니다.",
            "accepted_corrections는 가능한 정답 표현을 모두 열거한 목록이 아닙니다.",
            "user_reviewed 데이터는 일본어 전문가 인증을 의미하지 않습니다.",
            "Wilson 구간은 표본 불확실성만 나타내며 데이터 대표성은 보장하지 않습니다.",
        ],
    }


def score_run(
    run_path: Path,
    *,
    dataset_path: Path = DEFAULT_DATASET,
) -> dict[str, Any]:
    return score_verified_run(
        load_verified_run(run_path, dataset_path=dataset_path)
    )


def compare_runs(
    run_paths: Iterable[Path],
    *,
    dataset_path: Path = DEFAULT_DATASET,
    allow_mixed_config: bool = False,
) -> dict[str, Any]:
    paths = [Path(path) for path in run_paths]
    _require(bool(paths), "at least one run is required")
    _require(
        len({str(path.resolve()) for path in paths}) == len(paths),
        "duplicate run paths are not allowed",
    )
    scored = [score_run(path, dataset_path=dataset_path) for path in paths]
    reference = scored[0]["run"]
    for item in scored[1:]:
        current = item["run"]
        _require(
            current["dataset_sha256"] == reference["dataset_sha256"],
            "comparison requires the same dataset SHA-256",
        )
        _require(
            current["input_ids"] == reference["input_ids"],
            "comparison requires identical input IDs and order",
        )
        if not allow_mixed_config:
            _require(
                current["prompt_sha256"] == reference["prompt_sha256"],
                "comparison requires the same prompt SHA-256",
            )
            _require(
                current["generation"] == reference["generation"],
                "comparison requires the same generation settings",
            )

    def value(item: dict[str, Any], name: str, default: float) -> float:
        observed = item["metrics"][name]["value"]
        return default if observed is None else observed

    ranked = sorted(
        scored,
        key=lambda item: (
            not item["meets_all_targets"],
            -value(item, "json_contract_success_rate", -1.0),
            value(item, "overcorrection_rate", math.inf),
            -value(item, "correction_detection_precision", -1.0),
            -value(item, "correction_detection_recall", -1.0),
            item["run"]["model"],
            item["run"]["run_id"],
        ),
    )
    leaderboard = []
    for rank, item in enumerate(ranked, 1):
        leaderboard.append({
            "rank": rank,
            "run_id": item["run"]["run_id"],
            "model": item["run"]["model"],
            "meets_all_targets": item["meets_all_targets"],
            **{
                name: item["metrics"][name]["value"]
                for name in (
                    "json_contract_success_rate",
                    "overcorrection_rate",
                    "correction_detection_precision",
                    "correction_detection_recall",
                    "clear_case_handling_rate",
                    "decision_accuracy",
                    "accepted_correction_rate_end_to_end",
                )
            },
        })
    return {
        "schema_version": "0.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(Path(dataset_path).resolve()),
        "dataset_sha256": reference["dataset_sha256"],
        "input_ids": reference["input_ids"],
        "configuration_policy": (
            "mixed configurations explicitly allowed"
            if allow_mixed_config
            else "identical prompt and generation settings required"
        ),
        "leaderboard": leaderboard,
        "runs": scored,
    }


def _format_rate(metric: dict[str, Any]) -> str:
    value = metric["value"]
    if value is None:
        return f"N/A (0/{metric['denominator']})"
    interval = metric["ci95_wilson"]
    return (
        f"{value * 100:.2f}% "
        f"({metric['numerator']}/{metric['denominator']}; "
        f"95% CI {interval[0] * 100:.2f}–{interval[1] * 100:.2f}%)"
    )


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 일본어 판단모델 오프라인 채점 보고서",
        "",
        f"- 생성 시각: {report['created_at']}",
        f"- 데이터 SHA-256: {report['dataset_sha256']}",
        f"- 비교 문항 수: {len(report['input_ids'])}",
        f"- 비교 조건: {report['configuration_policy']}",
        "",
        "## 순위",
        "",
        "| 순위 | 모델 | 전체 목표 | JSON | 과교정 | 탐지 정밀도 | 탐지 재현율 | 명확 문항 처리 | 판단 정확도 |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in report["leaderboard"]:
        def percentage(name: str) -> str:
            value = item[name]
            return "N/A" if value is None else f"{value * 100:.2f}%"
        lines.append(
            "| "
            + " | ".join([
                str(item["rank"]),
                item["model"].replace("|", "&#124;"),
                "통과" if item["meets_all_targets"] else "미통과",
                percentage("json_contract_success_rate"),
                percentage("overcorrection_rate"),
                percentage("correction_detection_precision"),
                percentage("correction_detection_recall"),
                percentage("clear_case_handling_rate"),
                percentage("decision_accuracy"),
            ])
            + " |"
        )

    for item in report["runs"]:
        lines.extend([
            "",
            f"## {item['run']['model']}",
            "",
            f"- run_id: {item['run']['run_id']}",
            f"- 전체 목표: {'통과' if item['meets_all_targets'] else '미통과'}",
            f"- 시스템 실패 ID: {', '.join(item['case_lists']['system_failure_ids']) or '없음'}",
            f"- 판단 오류 ID: {', '.join(item['case_lists']['decision_error_ids']) or '없음'}",
            "",
            "| 지표 | 결과 |",
            "| --- | --- |",
        ])
        labels = {
            "transport_success_rate": "전송 성공률",
            "json_contract_success_rate": "JSON/계약 성공률",
            "decision_accuracy": "3분류 판단 정확도",
            "overcorrection_rate": "과교정률",
            "correction_detection_precision": "교정 탐지 정밀도",
            "correction_detection_recall": "교정 탐지 재현율",
            "correct_withholding_rate": "올바른 보류율",
            "clear_case_handling_rate": "명확 문항 처리율",
            "canonical_correction_exact_rate_end_to_end": "정규 교정문 완전일치",
            "accepted_correction_rate_end_to_end": "허용 교정문 일치",
            "exact_canonical_edits_rate_end_to_end": "정규 edit 완전일치",
            "edit_micro_precision": "edit micro 정밀도",
            "edit_micro_recall": "edit micro 재현율",
            "compound_complete_rate": "복합 오류 완전 탐지율",
        }
        for key, label in labels.items():
            lines.append(f"| {label} | {_format_rate(item['metrics'][key])} |")
        lines.extend([
            "",
            "### 목표 판정",
            "",
            "| 지표 | 기준 | 관측값 | 결과 |",
            "| --- | ---: | ---: | --- |",
        ])
        for name, target in item["targets"].items():
            observed = target["observed"]
            observed_text = "N/A" if observed is None else f"{observed * 100:.2f}%"
            lines.append(
                f"| {name} | {target['operator']} {target['value'] * 100:.2f}% "
                f"| {observed_text} | {'통과' if target['passed'] else '미통과'} |"
            )

        lines.extend([
            "",
            "### 3분류 혼동행렬",
            "",
            "| 정답/예측 | acceptable | needs_correction | insufficient_evidence | system_failure |",
            "| --- | ---: | ---: | ---: | ---: |",
        ])
        for gold in LABELS:
            row = item["confusion_matrix"][gold]
            lines.append(
                f"| {gold} | {row['acceptable']} | {row['needs_correction']} "
                f"| {row['insufficient_evidence']} | {row['system_failure']} |"
            )

        lines.extend([
            "",
            "### 오류 유형별 탐지",
            "",
            "| 오류 유형 | 정밀도 | 재현율 | 정답 수 | 예측 수 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ])
        for error_type, values in item["error_type_metrics"].items():
            lines.append(
                f"| {error_type} | {_format_rate(values['precision'])} "
                f"| {_format_rate(values['recall'])} | {values['gold_support']} "
                f"| {values['predicted_count']} |"
            )

        lines.extend([
            "",
            "### 수준별 결과",
            "",
            "| 수준 | 문항 수 | JSON/계약 | 판단 정확도 | 명확 문항 처리 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ])
        for level, values in item["by_learner_level"].items():
            lines.append(
                f"| {level} | {values['count']} "
                f"| {_format_rate(values['json_contract_success_rate'])} "
                f"| {_format_rate(values['decision_accuracy'])} "
                f"| {_format_rate(values['clear_case_handling_rate'])} |"
            )

        latency = item["performance"]["latency_ms"]
        tokens = item["performance"]["usage_totals"]
        lines.extend([
            "",
            "### 실행 관측값",
            "",
            f"- 지연시간(ms): count={latency['count']}, mean={latency['mean']}, "
            f"p50={latency['p50']}, p95={latency['p95']}",
            f"- 토큰: prompt={tokens['prompt_tokens']}, "
            f"completion={tokens['completion_tokens']}, total={tokens['total_tokens']}",
            f"- 복합 오류에서 누락된 정규 edit 수: "
            f"{item['metrics']['compound_missing_edit_count']}",
        ])

    lines.extend([
        "",
        "## 해석 제한",
        "",
    ])
    for limitation in report["runs"][0]["limitations"]:
        lines.append(f"- {limitation}")
    lines.extend([
        "",
        "모델 크기는 manifest가 신뢰할 수 있게 제공하지 않으므로 자동 순위 기준에 넣지 않았습니다.",
        "동일 성능 후보 중 가장 작은 모델 선택은 실제 파라미터 수와 메모리 측정값을 함께 확인해 결정합니다.",
        "",
    ])
    return "\n".join(lines)


def write_report(
    report: dict[str, Any],
    output_prefix: Path,
    *,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    prefix = Path(output_prefix).resolve()
    json_path = prefix.with_suffix(".json")
    markdown_path = prefix.with_suffix(".md")
    partials = [
        path.with_name(f".{path.name}.partial")
        for path in (json_path, markdown_path)
    ]
    existing = [
        path for path in (json_path, markdown_path, *partials) if path.exists()
    ]
    if existing and not overwrite:
        raise FileExistsError(
            "report artifacts already exist: " + ", ".join(map(str, existing))
        )
    prefix.parent.mkdir(parents=True, exist_ok=True)
    if overwrite:
        for path in existing:
            path.unlink()

    payloads = [
        (
            json_path,
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        ),
        (markdown_path, render_markdown(report)),
    ]
    for (destination, payload), partial in zip(payloads, partials):
        partial.write_text(payload, encoding="utf-8")
        os.replace(partial, destination)
    return json_path, markdown_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--allow-mixed-config", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = compare_runs(
            args.run,
            dataset_path=args.dataset,
            allow_mixed_config=args.allow_mixed_config,
        )
        json_path, markdown_path = write_report(
            report, args.output_prefix, overwrite=args.overwrite
        )
        print(json.dumps({
            "json_report": str(json_path),
            "markdown_report": str(markdown_path),
            "leaderboard": report["leaderboard"],
        }, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        print(f"Scoring failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Validate actual GPU/Pi judgment pairs and emit a content-free intake summary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from evaluation.judgment.runner import PROMPT_VERSION_V2, parse_model_output


SHA256 = re.compile(r"[0-9a-f]{64}")
QUANTIZATIONS = {"Q4_K_M", "Q5_K_M"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_path(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def sha_json(value: Any) -> str:
    return sha_bytes(canonical_json(value).encode("utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path}: expected a JSON object")
    return value


def load_run(path: Path, runtime: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            continue
        row = json.loads(line)
        require(isinstance(row, dict), f"{runtime}:{number}: row must be an object")
        model_input = row.get("input")
        require(isinstance(model_input, dict), f"{runtime}:{number}: input must be an object")
        require(set(model_input) == {"text", "context", "learner_level"},
                f"{runtime}:{number}: invalid input fields")
        require(isinstance(model_input["text"], str), f"{runtime}:{number}: invalid text")
        require(model_input["context"] is None or isinstance(model_input["context"], str),
                f"{runtime}:{number}: invalid context")
        require(model_input["learner_level"] in {"N5", "N4"},
                f"{runtime}:{number}: invalid learner_level")
        input_sha = sha_json(model_input)
        require(row.get("input_sha256") == input_sha,
                f"{runtime}:{number}: input SHA-256 mismatch")
        require(input_sha not in rows, f"{runtime}:{number}: duplicate input")

        response = row.get("response")
        require(isinstance(response, dict), f"{runtime}:{number}: response must be an object")
        require(response.get("transport_success") is True,
                f"{runtime}:{number}: transport did not succeed")
        require(response.get("contract_valid") is True,
                f"{runtime}:{number}: stored contract is invalid")
        parsed, error = parse_model_output(
            response.get("raw_text", ""), model_input["text"], PROMPT_VERSION_V2,
        )
        require(parsed is not None, f"{runtime}:{number}: contract replay failed: {error}")
        require(parsed == response.get("parsed_judgment"),
                f"{runtime}:{number}: parsed judgment differs from raw output")
        rows[input_sha] = parsed
    require(bool(rows), f"{runtime}: run is empty")
    return rows


def valid_sha(value: Any, name: str) -> str:
    require(isinstance(value, str) and SHA256.fullmatch(value) is not None,
            f"{name} must be a lowercase SHA-256")
    return value


def validate_gpu_manifest(manifest: dict[str, Any], run_sha: str) -> None:
    require(manifest.get("output_sha256") == run_sha,
            "GPU run manifest does not match the GPU JSONL")


def validate_pi_attestation(
    summary: dict[str, Any], run_sha: str, quantization: str,
    model_sha: str, adapter_sha: str,
) -> None:
    require(summary.get("schema_version") == "pi5-benchmark-summary-v0.2",
            "unsupported Pi benchmark summary")
    require(summary.get("passed") is True, "Pi benchmark did not pass")
    require(summary.get("sample_count", 0) >= 50, "Pi benchmark needs at least 50 records")
    require(summary.get("contains_request_content") is False,
            "Pi benchmark summary must be content-free")
    artifacts = summary.get("artifacts")
    require(isinstance(artifacts, dict), "Pi benchmark artifacts are missing")
    require(artifacts.get("raw_run_sha256") == run_sha,
            "Pi benchmark summary does not attest the Pi JSONL")
    require(artifacts.get("quantization") == quantization,
            "Pi benchmark quantization mismatch")
    require(artifacts.get("model_sha256") == model_sha, "Pi model SHA-256 mismatch")
    require(artifacts.get("adapter_sha256") == adapter_sha, "Pi adapter SHA-256 mismatch")


def build_summary(
    *, gpu_path: Path, pi_path: Path, gpu_manifest_path: Path,
    pi_benchmark_path: Path, gpu_model_sha256: str, gpu_adapter_sha256: str,
    pi_model_sha256: str, pi_adapter_sha256: str, pi_quantization: str,
    minimum_pairs: int = 50,
) -> dict[str, Any]:
    require(type(minimum_pairs) is int and minimum_pairs >= 50,
            "minimum_pairs must be at least 50")
    require(pi_quantization in QUANTIZATIONS, "unsupported Pi quantization")
    hashes = {
        "gpu_model_sha256": valid_sha(gpu_model_sha256, "gpu_model_sha256"),
        "gpu_adapter_sha256": valid_sha(gpu_adapter_sha256, "gpu_adapter_sha256"),
        "pi_model_sha256": valid_sha(pi_model_sha256, "pi_model_sha256"),
        "pi_adapter_sha256": valid_sha(pi_adapter_sha256, "pi_adapter_sha256"),
    }
    gpu_run_sha, pi_run_sha = sha_path(gpu_path), sha_path(pi_path)
    validate_gpu_manifest(load_json(gpu_manifest_path), gpu_run_sha)
    validate_pi_attestation(
        load_json(pi_benchmark_path), pi_run_sha, pi_quantization,
        hashes["pi_model_sha256"], hashes["pi_adapter_sha256"],
    )
    gpu, pi = load_run(gpu_path, "gpu_bf16") , load_run(pi_path, "pi_gguf")
    require(set(gpu) == set(pi), "GPU and Pi input sets must match exactly")

    ordered = sorted(gpu)
    decision_agreement = sum(gpu[key]["decision"] == pi[key]["decision"] for key in ordered)
    correction_agreement = sum(
        gpu[key]["corrected_text"] == pi[key]["corrected_text"] for key in ordered
    )
    error_type_agreement = sum(
        gpu[key]["error_types"] == pi[key]["error_types"] for key in ordered
    )
    pair_count = len(ordered)
    source_ready = pair_count >= minimum_pairs
    blocking = [] if source_ready else ["insufficient_actual_gpu_pi_pairs"]
    blocking.append("missing_independent_feedback_labels")
    return {
        "schema_version": "feedback-runtime-pair-intake-v0.1",
        "pair_count": pair_count,
        "minimum_pairs": minimum_pairs,
        "input_set_sha256": sha_json(ordered),
        "gpu_run_sha256": gpu_run_sha,
        "pi_run_sha256": pi_run_sha,
        "runtime_artifacts": {**hashes, "pi_quantization": pi_quantization},
        "agreement": {
            "decision_count": decision_agreement,
            "decision_rate": decision_agreement / pair_count,
            "corrected_text_count": correction_agreement,
            "corrected_text_rate": correction_agreement / pair_count,
            "error_types_count": error_type_agreement,
            "error_types_rate": error_type_agreement / pair_count,
        },
        "source_gap_analysis_ready": source_ready,
        "feedback_holdout_ready": False,
        "blocking_reasons": blocking,
        "contains_request_content": False,
        "limitations": [
            "Runtime agreement is not linguistic correctness.",
            "Independent labels are required before sealing a feedback holdout.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu-run", type=Path, required=True)
    parser.add_argument("--pi-run", type=Path, required=True)
    parser.add_argument("--gpu-run-manifest", type=Path, required=True)
    parser.add_argument("--pi-benchmark-summary", type=Path, required=True)
    parser.add_argument("--gpu-model-sha256", required=True)
    parser.add_argument("--gpu-adapter-sha256", required=True)
    parser.add_argument("--pi-model-sha256", required=True)
    parser.add_argument("--pi-adapter-sha256", required=True)
    parser.add_argument("--pi-quantization", choices=sorted(QUANTIZATIONS), required=True)
    parser.add_argument("--minimum-pairs", type=int, default=50)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = build_summary(
            gpu_path=args.gpu_run, pi_path=args.pi_run,
            gpu_manifest_path=args.gpu_run_manifest,
            pi_benchmark_path=args.pi_benchmark_summary,
            gpu_model_sha256=args.gpu_model_sha256,
            gpu_adapter_sha256=args.gpu_adapter_sha256,
            pi_model_sha256=args.pi_model_sha256,
            pi_adapter_sha256=args.pi_adapter_sha256,
            pi_quantization=args.pi_quantization, minimum_pairs=args.minimum_pairs,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

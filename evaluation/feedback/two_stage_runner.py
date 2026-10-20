"""Single-use offline runner for the sealed two-stage feedback evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzer.feedback_contract import canonical_json
from analyzer.feedback_two_stage_contract import (
    CONTRACT_VERSION,
    build_stage1_request,
    build_stage2_request,
    combine_outputs,
    parse_stage1_output,
    parse_stage2_output,
)
from evaluation.judgment.runner import call_endpoint


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_execution(
    seal: dict[str, Any],
    plan: dict[str, Any],
    *,
    dataset_sha256: str,
    seal_sha256: str,
    endpoint: str | None = None,
    output_path: Path | None = None,
) -> None:
    if dataset_sha256 != seal.get("dataset_sha256"):
        raise ValueError("sealed dataset SHA-256 mismatch")
    if plan.get("dataset_sha256") != dataset_sha256:
        raise ValueError("execution-plan dataset SHA-256 mismatch")
    if plan.get("seal_protocol_sha256") != seal_sha256:
        raise ValueError("execution-plan seal SHA-256 mismatch")
    if plan.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("execution-plan contract version mismatch")
    if plan.get("ready_for_inference") is not True:
        raise ValueError("execution plan is not ready for inference")
    if plan.get("single_use") is not True:
        raise ValueError("execution plan must be single-use")
    if plan.get("consumed") is True:
        raise ValueError("execution plan has already been consumed")
    candidate = plan.get("candidate")
    if not isinstance(candidate, dict):
        raise ValueError("execution plan candidate is missing")
    for key in ("stage1_model", "stage2_model", "model_sha256", "adapter_sha256"):
        value = candidate.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"execution plan candidate {key} is missing")
    for key in ("model_sha256", "adapter_sha256"):
        if len(candidate[key]) != 64:
            raise ValueError(f"execution plan candidate {key} is invalid")
    code = plan.get("code_sha256")
    if not isinstance(code, dict) or any(
        not isinstance(code.get(key), str) or len(code[key]) != 64
        for key in ("contract", "runner", "scorer")
    ):
        raise ValueError("execution plan code hashes are incomplete")
    execution = plan.get("execution")
    if not isinstance(execution, dict):
        raise ValueError("execution plan binding is missing")
    for key in ("endpoint", "output_path", "claim_path", "receipt_path"):
        value = execution.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"execution plan {key} is missing")
    if endpoint is not None and endpoint != execution["endpoint"]:
        raise ValueError("endpoint differs from the sealed execution plan")
    if output_path is not None and str(output_path.resolve()) != execution["output_path"]:
        raise ValueError("output path differs from the sealed execution plan")


def claim_execution(plan: dict[str, Any], *, plan_sha256: str) -> Path:
    claim = Path(plan["execution"]["claim_path"])
    receipt = Path(plan["execution"]["receipt_path"])
    if claim.exists() or receipt.exists():
        raise FileExistsError("single-use execution has already been claimed")
    claim.parent.mkdir(parents=True, exist_ok=True)
    with claim.open("x", encoding="utf-8") as stream:
        stream.write(canonical_json({"execution_plan_sha256": plan_sha256, "state": "claimed"}) + "\n")
    return claim


def run_one(
    row: dict[str, Any],
    *,
    endpoint: str,
    stage1_model: str,
    stage2_model: str,
    timeout: float,
    call_fn: Callable[..., dict[str, Any]] = call_endpoint,
) -> dict[str, Any]:
    model_input = {
        "text": row["text"],
        "context": row["context"],
        "learner_level": row["learner_level"],
        "judgment": row["candidate_judgment"],
    }
    response1 = call_fn(
        endpoint=endpoint,
        request_body=build_stage1_request(model_input, stage1_model),
        timeout=timeout,
        api_key=None,
    )
    parsed1, error1 = parse_stage1_output(response1.get("raw_text", ""))
    result: dict[str, Any] = {
        "id": row["id"],
        "stage1_model": stage1_model,
        "stage2_model": stage2_model,
        "stage1_transport_success": response1.get("transport_success", False),
        "stage1_contract_success": parsed1 is not None,
        "stage1_contract_error": error1,
        "stage1_parsed": parsed1,
        "stage1_latency_ms": response1.get("latency_ms"),
        "stage1_raw_text": response1.get("raw_text", ""),
        "stage2_called": False,
        "stage2_transport_success": None,
        "stage2_contract_success": None,
        "stage2_contract_error": None,
        "stage2_parsed": None,
        "stage2_latency_ms": None,
        "stage2_raw_text": None,
        "combined_contract_success": False,
        "combined": None,
    }
    if parsed1 is not None and parsed1["verdict"] == "disagree":
        result["stage2_called"] = True
        response2 = call_fn(
            endpoint=endpoint,
            request_body=build_stage2_request(model_input, parsed1, stage2_model),
            timeout=timeout,
            api_key=None,
        )
        parsed2, error2 = parse_stage2_output(
            response2.get("raw_text", ""), row["text"], parsed1["issue_codes"]
        )
        result.update({
            "stage2_transport_success": response2.get("transport_success", False),
            "stage2_contract_success": parsed2 is not None,
            "stage2_contract_error": error2,
            "stage2_parsed": parsed2,
            "stage2_latency_ms": response2.get("latency_ms"),
            "stage2_raw_text": response2.get("raw_text", ""),
        })
        if parsed2 is not None:
            result["combined"] = combine_outputs(parsed1, parsed2)
            result["combined_contract_success"] = True
    elif parsed1 is not None:
        result["combined"] = combine_outputs(parsed1, None)
        result["combined_contract_success"] = True

    latencies = [
        value for value in (result["stage1_latency_ms"], result["stage2_latency_ms"])
        if isinstance(value, (int, float))
    ]
    result["total_latency_ms"] = sum(latencies) if latencies else None
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    seal = json.loads(args.seal.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    try:
        validate_execution(
            seal,
            plan,
            dataset_sha256=sha256(args.dataset),
            seal_sha256=sha256(args.seal),
            endpoint=args.endpoint,
            output_path=args.output,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise SystemExit("refusing to overwrite an existing or partial run")
    plan_sha256 = sha256(args.plan)
    try:
        claim_path = claim_execution(plan, plan_sha256=plan_sha256)
    except FileExistsError as exc:
        raise SystemExit(str(exc)) from exc
    rows = [json.loads(line) for line in args.dataset.read_text(encoding="utf-8").splitlines() if line]
    candidate = plan["candidate"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with partial.open("x", encoding="utf-8") as stream:
        for row in rows:
            result = run_one(
                row,
                endpoint=args.endpoint,
                stage1_model=candidate["stage1_model"],
                stage2_model=candidate["stage2_model"],
                timeout=args.timeout,
            )
            stream.write(canonical_json(result) + "\n")
            stream.flush()
    partial.rename(args.output)
    manifest = {
        "schema_version": "feedback-two-stage-run-manifest-v0.1",
        "contract_version": CONTRACT_VERSION,
        "dataset_sha256": plan["dataset_sha256"],
        "seal_protocol_sha256": plan["seal_protocol_sha256"],
        "execution_plan_sha256": plan_sha256,
        "execution_claim_path": str(claim_path),
        "candidate": candidate,
        "records": len(rows),
        "result_sha256": sha256(args.output),
    }
    args.output.with_suffix(args.output.suffix + ".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt_path = Path(plan["execution"]["receipt_path"])
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.open("x", encoding="utf-8") as stream:
        stream.write(canonical_json({
            "execution_plan_sha256": plan_sha256,
            "result_sha256": manifest["result_sha256"],
            "state": "completed",
        }) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

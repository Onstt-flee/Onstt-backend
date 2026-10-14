"""One-pass runner for a sealed feedback verifier holdout."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import build_request, canonical_json, parse_output
from evaluation.judgment.runner import call_endpoint


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_sealed_run(protocol, dataset_sha256):
    if protocol.get("single_use") and protocol.get("consumed"):
        raise ValueError("sealed protocol has already been consumed")
    if dataset_sha256 != protocol["dataset_sha256"]:
        raise ValueError("sealed dataset SHA-256 mismatch")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--role", choices=("baseline", "lora"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    try:
        validate_sealed_run(protocol, sha(args.dataset))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.output.exists():
        raise SystemExit("refusing to overwrite an existing run")
    rows = [json.loads(line) for line in args.dataset.read_text(encoding="utf-8").splitlines() if line]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    with partial.open("x", encoding="utf-8") as stream:
        for row in rows:
            model_input = {"text": row["text"], "context": row["context"],
                           "learner_level": row["learner_level"], "judgment": row["candidate_judgment"]}
            response = call_endpoint(endpoint=args.endpoint, request_body=build_request(model_input, args.model),
                                     timeout=args.timeout, api_key=None)
            parsed, contract_error = parse_output(response.get("raw_text", ""), row["text"])
            result = {"id": row["id"], "role": args.role, "model": args.model,
                      "transport_success": response.get("transport_success", False),
                      "contract_success": parsed is not None, "contract_error": contract_error,
                      "parsed": parsed, "latency_ms": response.get("latency_ms"),
                      "raw_text": response.get("raw_text", "")}
            stream.write(canonical_json(result) + "\n"); stream.flush()
    partial.rename(args.output)
    manifest = {"schema_version": "feedback-run-manifest-v0.1", "role": args.role,
                "model": args.model, "dataset_sha256": protocol["dataset_sha256"],
                "records": len(rows), "result_sha256": sha(args.output)}
    args.output.with_suffix(args.output.suffix + ".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__": main()

"""Run judgment -> persistent feedback audit against an isolated SQLite DB.

This is an operational, label-free shadow.  It measures contracts, queue
integrity, immutability and latency; it does not estimate language accuracy.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from analyzer.feedback_store import configuration_error, record_gpu_judgment
from analyzer.feedback_worker import process_one
from analyzer.judgment_service import (
    PRESERVATION_CONTRACT_ERROR,
    RETRY_INSTRUCTION,
)
from database import Base
from evaluation.judgment.runner import (
    PROMPT_VERSION_V2, build_request, call_endpoint, parse_model_output,
)


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * percentile_value + 0.999999)))
    return round(ordered[rank], 3)


def load_inputs(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 200 or len({row["id"] for row in rows}) != 200:
        raise ValueError("synthetic shadow input must contain 200 unique IDs")
    for row in rows:
        if set(row) != {"id", "input", "stratum"}:
            raise ValueError("input row contains unsupported fields")
        if set(row["input"]) != {"text", "context", "learner_level"}:
            raise ValueError("model input contains unsupported fields")
    return rows


def judgment_snapshot(db: Any) -> str:
    rows = db.query(models.JudgmentResult).order_by(models.JudgmentResult.id).all()
    values = [{
        "id": row.id, "utterance_id": row.utterance_id, "decision": row.decision,
        "corrected_text": row.corrected_text, "edits": row.edits,
        "error_types": row.error_types, "reason_ko": row.reason_ko,
        "classification_review_required": row.classification_review_required,
        "strategy": row.strategy, "model_name": row.model_name,
        "adapter_name": row.adapter_name, "selection_reason": row.selection_reason,
        "contract_version": row.contract_version, "latency_ms": row.latency_ms,
        "context": row.context, "learner_level": row.learner_level,
    } for row in rows]
    return sha256_bytes(canonical(values).encode("utf-8"))


def run(args: argparse.Namespace) -> dict[str, Any]:
    scope = getattr(args, "scope", "synthetic_operational_shadow_only")
    if scope not in {
        "synthetic_operational_shadow_only",
        "actual_stored_stt_operational_shadow_only",
    }:
        raise ValueError("unsupported shadow scope")
    inputs_path = args.inputs.resolve()
    raw_dir = args.raw_dir.resolve()
    database_path = args.database.resolve()
    summary_path = args.summary.resolve()
    for path in (database_path, summary_path):
        if path.exists() and not args.overwrite:
            raise FileExistsError(f"refusing to overwrite {path}")
        if path.exists():
            path.unlink()
    raw_dir.mkdir(parents=True, exist_ok=True)
    judgment_raw_path = raw_dir / "judgment.jsonl"
    if judgment_raw_path.exists() and not args.overwrite:
        raise FileExistsError(f"refusing to overwrite {judgment_raw_path}")

    rows = load_inputs(inputs_path)
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    if configuration_error() is not None:
        raise ValueError(f"feedback configuration invalid: {configuration_error()}")

    judgment_transport = judgment_contract = 0
    judgment_latencies: list[float] = []
    judgment_decisions: Counter[str] = Counter()
    retry_attempts = retry_recoveries = retry_failures = 0
    strata_by_utterance: dict[int, str] = {}
    session = None
    with SessionLocal() as db, judgment_raw_path.open("w", encoding="utf-8") as raw:
        session = models.Session(topic=scope)
        db.add(session); db.flush()
        for index, row in enumerate(rows, 1):
            request = build_request(
                row["input"], args.judgment_model, prompt_version=PROMPT_VERSION_V2,
                temperature=0.0, top_p=1.0, max_tokens=512,
            )
            response = call_endpoint(
                endpoint=args.judgment_endpoint, request_body=request,
                timeout=args.timeout, api_key=None,
            )
            parsed = None; contract_error = "transport_failed"
            retry_used = False
            first_contract_error = None
            if response["transport_success"]:
                judgment_transport += 1
                parsed, contract_error = parse_model_output(
                    response["raw_text"], row["input"]["text"], PROMPT_VERSION_V2,
                )
            if parsed is None and contract_error == PRESERVATION_CONTRACT_ERROR:
                retry_used = True
                retry_attempts += 1
                first_contract_error = contract_error
                retry_request = {
                    **request,
                    "messages": [dict(message) for message in request["messages"]],
                }
                retry_request["messages"][0]["content"] += RETRY_INSTRUCTION
                retry_response = call_endpoint(
                    endpoint=args.judgment_endpoint,
                    request_body=retry_request,
                    timeout=args.timeout,
                    api_key=None,
                )
                first_latency = response.get("latency_ms")
                retry_latency = retry_response.get("latency_ms")
                if isinstance(first_latency, (int, float)) and isinstance(
                    retry_latency, (int, float)
                ):
                    retry_response["latency_ms"] = first_latency + retry_latency
                response = retry_response
                if response["transport_success"]:
                    parsed, contract_error = parse_model_output(
                        response["raw_text"],
                        row["input"]["text"],
                        PROMPT_VERSION_V2,
                    )
                else:
                    contract_error = "transport_failed"
                if parsed is not None:
                    retry_recoveries += 1
                else:
                    retry_failures += 1
            raw_record = {
                "id": row["id"], "input": row["input"], "stratum": row["stratum"],
                "response": response, "contract_valid": parsed is not None,
                "contract_error": contract_error, "parsed_judgment": parsed,
                "attempt_count": 2 if retry_used else 1,
                "retry_used": retry_used,
                "first_contract_error": first_contract_error,
            }
            raw.write(canonical(raw_record) + "\n"); raw.flush()
            if parsed is not None:
                judgment_contract += 1
                judgment_decisions[parsed["decision"]] += 1
                if response.get("latency_ms") is not None:
                    judgment_latencies.append(float(response["latency_ms"]))
                utterance = models.Utterance(
                    session_id=session.id, stt_text=row["input"]["text"],
                    language="ja",
                    stt_model=(
                        "synthetic" if scope == "synthetic_operational_shadow_only"
                        else "stored-stt-private-snapshot"
                    ),
                )
                db.add(utterance); db.flush()
                strata_by_utterance[utterance.id] = row["stratum"]
                judgment = models.JudgmentResult(
                    utterance_id=utterance.id, decision=parsed["decision"],
                    corrected_text=parsed["corrected_text"],
                    edits=canonical(parsed["edits"]),
                    error_types=canonical(parsed["error_types"]),
                    reason_ko=parsed["reason_ko"],
                    classification_review_required=parsed["classification_review_required"],
                    strategy="d_only", model_name=args.judgment_model,
                    adapter_name=args.judgment_adapter,
                    selection_reason=(
                        "synthetic_shadow_d_only"
                        if scope == "synthetic_operational_shadow_only"
                        else "actual_stored_stt_shadow_d_only"
                    ),
                    contract_version=PROMPT_VERSION_V2,
                    latency_ms=response.get("latency_ms"),
                    context=row["input"]["context"],
                    learner_level=row["input"]["learner_level"],
                )
                db.add(judgment); db.flush()
                record_gpu_judgment(db, judgment, {
                    "model_sha256": args.judgment_model_sha256,
                    "adapter_sha256": args.judgment_adapter_sha256,
                })
                db.commit()
            if index % 10 == 0:
                print(f"judgment {index}/200", file=sys.stderr, flush=True)

        before_hash = judgment_snapshot(db)
        queued = db.query(models.FeedbackAuditJob).count()

    attempts = 0
    while True:
        with SessionLocal() as db:
            worked = process_one(db)
        if not worked:
            break
        attempts += 1
        if attempts % 10 == 0:
            print(f"feedback {attempts}/{queued}", file=sys.stderr, flush=True)

    with SessionLocal() as db:
        after_hash = judgment_snapshot(db)
        jobs = db.query(models.FeedbackAuditJob).all()
        audits = db.query(models.FeedbackAudit).all()
        job_counts = Counter(job.status for job in jobs)
        verdict_counts = Counter(audit.verdict for audit in audits)
        issue_counts: Counter[str] = Counter()
        audit_latencies: list[float] = []
        stratum_verdicts: dict[str, Counter[str]] = {}
        for audit in audits:
            issue_counts.update(json.loads(audit.issue_codes))
            if audit.latency_ms is not None:
                audit_latencies.append(float(audit.latency_ms))
            judgment = db.get(models.JudgmentResult, audit.judgment_id)
            stratum = strata_by_utterance[judgment.utterance_id]
            stratum_verdicts.setdefault(stratum, Counter())[audit.verdict] += 1
        duplicate_jobs = len(jobs) - len({job.judgment_id for job in jobs})
        duplicate_audits = len(audits) - len({audit.judgment_id for audit in audits})

    raw_bytes = judgment_raw_path.read_bytes()
    summary = {
        "schema_version": (
            "synthetic-feedback-shadow-result-v0.1"
            if scope == "synthetic_operational_shadow_only"
            else "actual-stored-stt-feedback-shadow-result-v0.1"
        ),
        "scope": scope,
        "quality_claim_allowed": False,
        "source_runtime": "gpu_bf16",
        "input_count": len(rows),
        "inputs_sha256": sha256_bytes(inputs_path.read_bytes()),
        "raw_judgment_path": str(judgment_raw_path),
        "raw_judgment_sha256": sha256_bytes(raw_bytes),
        "isolated_database_path": str(database_path),
        "judgment": {
            "model": args.judgment_model, "adapter": args.judgment_adapter,
            "adapter_sha256": args.judgment_adapter_sha256,
            "strategy": "d_only_with_single_preservation_retry",
            "model_calls": len(rows) + retry_attempts,
            "transport_success": judgment_transport,
            "contract_valid": judgment_contract,
            "contract_invalid": len(rows) - judgment_contract,
            "retry_attempts": retry_attempts,
            "retry_recoveries": retry_recoveries,
            "retry_failures": retry_failures,
            "retry_rate": round(retry_attempts / len(rows), 6),
            "decision_counts": dict(sorted(judgment_decisions.items())),
            "latency_ms": {
                "p50": round(statistics.median(judgment_latencies), 3) if judgment_latencies else None,
                "p95": percentile(judgment_latencies, 0.95),
            },
        },
        "feedback": {
            "model": os.environ["FEEDBACK_MODEL"],
            "adapter": os.environ["FEEDBACK_ADAPTER"],
            "adapter_sha256": os.environ["FEEDBACK_MODEL_SHA256"],
            "queued": queued, "attempted_once": attempts,
            "job_status_counts": dict(sorted(job_counts.items())),
            "audit_count": len(audits),
            "verdict_counts": dict(sorted(verdict_counts.items())),
            "issue_counts": dict(sorted(issue_counts.items())),
            "stratum_verdict_counts": {
                key: dict(sorted(value.items())) for key, value in sorted(stratum_verdicts.items())
            },
            "latency_ms": {
                "p50": round(statistics.median(audit_latencies), 3) if audit_latencies else None,
                "p95": percentile(audit_latencies, 0.95),
            },
        },
        "integrity": {
            "judgment_snapshot_before_sha256": before_hash,
            "judgment_snapshot_after_sha256": after_hash,
            "judgments_unchanged": before_hash == after_hash,
            "duplicate_job_count": duplicate_jobs,
            "duplicate_audit_count": duplicate_audits,
            "feedback_input_excludes_runtime_and_model_identity": True,
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--judgment-endpoint", default="http://127.0.0.1:1234/v1/chat/completions")
    parser.add_argument("--judgment-model", default="judgment-v02d")
    parser.add_argument("--judgment-adapter", default="judgment-qwen3-4b-failure-focus-v0.2-d")
    parser.add_argument("--judgment-model-sha256")
    parser.add_argument("--judgment-adapter-sha256")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--scope",
        choices=(
            "synthetic_operational_shadow_only",
            "actual_stored_stt_operational_shadow_only",
        ),
        default="synthetic_operational_shadow_only",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args), ensure_ascii=False, indent=2))
    except (KeyError, OSError, ValueError) as exc:
        print(f"shadow failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

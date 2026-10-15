"""Exercise feedback worker recovery semantics on an isolated DB copy."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Callable

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from analyzer.feedback_service import FeedbackServiceError
from analyzer.feedback_worker import process_one


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def judgment_snapshot(db: Any) -> str:
    rows = db.query(models.JudgmentResult).order_by(models.JudgmentResult.id).all()
    values = [{
        "id": row.id, "utterance_id": row.utterance_id,
        "decision": row.decision, "corrected_text": row.corrected_text,
        "edits": row.edits, "error_types": row.error_types,
        "reason_ko": row.reason_ko,
        "classification_review_required": row.classification_review_required,
        "strategy": row.strategy, "model_name": row.model_name,
        "adapter_name": row.adapter_name, "selection_reason": row.selection_reason,
        "contract_version": row.contract_version, "latency_ms": row.latency_ms,
        "context": row.context, "learner_level": row.learner_level,
    } for row in rows]
    return hashlib.sha256(canonical(values).encode("utf-8")).hexdigest()


def success_runner(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {
        "verdict": "agree", "issue_codes": [], "recommended_judgment": None,
        "review_reason_ko": "격리 복구 훈련 성공 응답", "latency_ms": 1.0,
    }


def failing_runner(category: str) -> Callable[..., dict[str, Any]]:
    def run(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise FeedbackServiceError(category)
    return run


def add_job(
    db: Any, *, judgment_id: int, model_hash: str, status: str = "pending",
    attempts: int = 0, lease_expires_at: datetime | None = None,
) -> models.FeedbackAuditJob:
    job = models.FeedbackAuditJob(
        judgment_id=judgment_id, feedback_model=f"recovery-{model_hash[0]}",
        feedback_adapter="recovery-drill", feedback_model_hash=model_hash,
        contract_version="feedback-v0.1", status=status, attempts=attempts,
        lease_expires_at=lease_expires_at,
        next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    db.add(job); db.commit(); db.refresh(job)
    return job


def force_due(SessionLocal: Any, job_id: int) -> None:
    with SessionLocal() as db:
        job = db.get(models.FeedbackAuditJob, job_id)
        job.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()


def one_process(SessionLocal: Any, runner: Callable[..., dict[str, Any]]) -> bool:
    """A fresh session represents a stopped/restarted worker process boundary."""
    with SessionLocal() as db:
        return process_one(db, runner=runner)


def run(source: Path, database: Path) -> dict[str, Any]:
    source = source.resolve(); database = database.resolve()
    if database.exists():
        database.unlink()
    database.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, database)
    source_hash = sha256_file(source)

    engine = create_engine(
        f"sqlite:///{database}", connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with SessionLocal() as db:
        judgment_ids = [value for (value,) in db.query(models.JudgmentResult.id)
                        .order_by(models.JudgmentResult.id).limit(3).all()]
        if len(judgment_ids) != 3:
            raise ValueError("recovery drill requires at least three judgments")
        before_snapshot = judgment_snapshot(db)
        baseline_jobs = db.query(models.FeedbackAuditJob).count()
        baseline_audits = db.query(models.FeedbackAudit).count()
        expired = add_job(
            db, judgment_id=judgment_ids[0], model_hash="c" * 64,
            status="running", attempts=0,
            lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        recovered = add_job(db, judgment_id=judgment_ids[1], model_hash="d" * 64)
        terminal = add_job(db, judgment_id=judgment_ids[2], model_hash="e" * 64)
        expired_id, recovered_id, terminal_id = expired.id, recovered.id, terminal.id

    if not one_process(SessionLocal, success_runner):
        raise ValueError("expired lease was not reclaimed")
    if not one_process(SessionLocal, failing_runner("contract")):
        raise ValueError("recoverable failure was not attempted")
    force_due(SessionLocal, recovered_id)
    if not one_process(SessionLocal, success_runner):
        raise ValueError("recoverable job was not retried")
    for _ in range(3):
        force_due(SessionLocal, terminal_id)
        if not one_process(SessionLocal, failing_runner("transport")):
            raise ValueError("terminal failure job was not attempted")

    with SessionLocal() as db:
        expired = db.get(models.FeedbackAuditJob, expired_id)
        recovered = db.get(models.FeedbackAuditJob, recovered_id)
        terminal = db.get(models.FeedbackAuditJob, terminal_id)
        after_snapshot = judgment_snapshot(db)
        final_jobs = db.query(models.FeedbackAuditJob).count()
        final_audits = db.query(models.FeedbackAudit).count()
        drill_audits = db.query(models.FeedbackAudit).filter(
            models.FeedbackAudit.feedback_adapter == "recovery-drill"
        ).all()
        result = {
            "schema_version": "feedback-worker-recovery-drill-v0.1",
            "scope": "isolated_synthetic_database_copy",
            "quality_claim_allowed": False,
            "source_database_sha256": source_hash,
            "working_database_sha256": None,
            "judgments_unchanged": before_snapshot == after_snapshot,
            "judgment_snapshot_before_sha256": before_snapshot,
            "judgment_snapshot_after_sha256": after_snapshot,
            "baseline": {"job_count": baseline_jobs, "audit_count": baseline_audits},
            "final": {"job_count": final_jobs, "audit_count": final_audits},
            "expired_lease": {
                "status": expired.status, "attempts": expired.attempts,
                "audit_count": sum(a.judgment_id == expired.judgment_id for a in drill_audits),
            },
            "retry_recovery": {
                "status": recovered.status, "attempts": recovered.attempts,
                "audit_count": sum(a.judgment_id == recovered.judgment_id for a in drill_audits),
            },
            "terminal_failure": {
                "status": terminal.status, "attempts": terminal.attempts,
                "error_category": terminal.error_category,
                "audit_count": sum(a.judgment_id == terminal.judgment_id for a in drill_audits),
            },
            "duplicate_drill_audit_count": len(drill_audits) - len({a.judgment_id for a in drill_audits}),
            "contains_request_content": False,
        }
    engine.dispose()
    result["working_database_sha256"] = sha256_file(database)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        print(f"refusing to overwrite {args.output}", file=sys.stderr); return 1
    try:
        result = run(args.source, args.database)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"recovery drill failed: {exc}", file=sys.stderr); return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

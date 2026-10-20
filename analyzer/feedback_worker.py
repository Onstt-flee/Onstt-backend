"""Single-concurrency persistent worker for feedback audit jobs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import time
from typing import Callable

from sqlalchemy import or_
from sqlalchemy.orm import Session

import models
from analyzer.feedback_contract import canonical_json
from analyzer.feedback_service import FeedbackServiceError, judgment_input, run_feedback
from analyzer.feedback_store import provenance_snapshot


RETRY_DELAYS_SECONDS = (60, 300, 1800)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def claim_next(db: Session, *, lease_seconds: int = 180) -> models.FeedbackAuditJob | None:
    now = utcnow()
    candidate = (
        db.query(models.FeedbackAuditJob)
        .filter(
            models.FeedbackAuditJob.next_attempt_at <= now,
            or_(
                models.FeedbackAuditJob.status == "pending",
                (models.FeedbackAuditJob.status == "running")
                & (models.FeedbackAuditJob.lease_expires_at < now),
            ),
        )
        .order_by(models.FeedbackAuditJob.id)
        .first()
    )
    if candidate is None:
        return None
    updated = (
        db.query(models.FeedbackAuditJob)
        .filter(
            models.FeedbackAuditJob.id == candidate.id,
            or_(
                models.FeedbackAuditJob.status == "pending",
                (models.FeedbackAuditJob.status == "running")
                & (models.FeedbackAuditJob.lease_expires_at < now),
            ),
        )
        .update({
            "status": "running", "attempts": candidate.attempts + 1,
            "lease_expires_at": now + timedelta(seconds=lease_seconds),
            "error_category": None, "updated_at": now,
        }, synchronize_session=False)
    )
    db.commit()
    return db.get(models.FeedbackAuditJob, candidate.id) if updated else None


def _fail(db: Session, job: models.FeedbackAuditJob, category: str) -> None:
    now = utcnow()
    known_categories = {
        "configuration", "transport", "contract", "contract_stage1",
        "contract_stage2", "missing_input",
    }
    job.error_category = category if category in known_categories else "internal"
    job.lease_expires_at = None
    if job.attempts >= 3:
        job.status = "failed"
    else:
        job.status = "pending"
        job.next_attempt_at = now + timedelta(seconds=RETRY_DELAYS_SECONDS[job.attempts - 1])
    job.updated_at = now
    db.commit()


def process_one(db: Session, *, runner: Callable = run_feedback) -> bool:
    job = claim_next(db)
    if job is None:
        return False
    judgment = db.get(models.JudgmentResult, job.judgment_id)
    utterance = db.get(models.Utterance, judgment.utterance_id) if judgment else None
    if judgment is None or utterance is None:
        _fail(db, job, "missing_input")
        return True
    provenance = db.get(models.JudgmentProvenance, judgment.id)
    try:
        result = runner(
            utterance.stt_text, context=judgment.context,
            learner_level=judgment.learner_level, judgment=judgment_input(judgment),
            model_name=job.feedback_model, contract_version=job.contract_version,
        )
        recommended = result["recommended_judgment"]
        edits = recommended.pop("edits", []) if recommended else []
        if recommended:
            recommended.pop("classification_review_required", None)
        audit = models.FeedbackAudit(
            judgment_id=judgment.id, verdict=result["verdict"],
            issue_codes=canonical_json(result["issue_codes"]),
            recommended_judgment=canonical_json(recommended) if recommended else None,
            recommended_edits=canonical_json(edits), review_reason_ko=result["review_reason_ko"],
            feedback_model=job.feedback_model, feedback_adapter=job.feedback_adapter,
            feedback_model_hash=job.feedback_model_hash, contract_version=job.contract_version,
            provenance_snapshot=canonical_json(provenance_snapshot(judgment, provenance)),
            latency_ms=result.get("latency_ms"),
        )
        db.add(audit)
        job.status = "succeeded"; job.error_category = None; job.lease_expires_at = None
        job.updated_at = utcnow()
        db.commit()
    except FeedbackServiceError as exc:
        db.rollback(); job = db.get(models.FeedbackAuditJob, job.id); _fail(db, job, exc.category)
    except Exception:
        db.rollback(); job = db.get(models.FeedbackAuditJob, job.id); _fail(db, job, "internal")
    return True


def run_forever(session_factory: Callable[[], Session], *, poll_seconds: float = 2.0) -> None:
    while True:
        with session_factory() as db:
            worked = process_one(db)
        if not worked:
            time.sleep(poll_seconds)

"""Content-minimized admin queries for feedback audit operations."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json

from sqlalchemy.orm import Session

import models
from analyzer.feedback_store import issue_group_key


def list_audits(db: Session, *, limit: int = 100) -> list[dict]:
    rows = db.query(models.FeedbackAudit).order_by(models.FeedbackAudit.id.desc()).limit(limit).all()
    result = []
    for row in rows:
        provenance = json.loads(row.provenance_snapshot)
        result.append({
            "audit_id": row.id, "judgment_id": row.judgment_id,
            "verdict": row.verdict, "issue_codes": json.loads(row.issue_codes),
            "runtime": provenance.get("runtime", "unknown"),
            "contract_version": row.contract_version, "created_at": row.created_at,
        })
    return result


def audit_detail(db: Session, judgment_id: int) -> dict | None:
    row = (db.query(models.FeedbackAudit).filter_by(judgment_id=judgment_id)
           .order_by(models.FeedbackAudit.id.desc()).first())
    if row is None:
        return None
    return {
        "audit_id": row.id, "judgment_id": row.judgment_id, "verdict": row.verdict,
        "issue_codes": json.loads(row.issue_codes),
        "recommended_judgment": json.loads(row.recommended_judgment) if row.recommended_judgment else None,
        "recommended_edits": json.loads(row.recommended_edits),
        "review_reason_ko": row.review_reason_ko,
        "feedback_model": row.feedback_model, "feedback_adapter": row.feedback_adapter,
        "feedback_model_hash": row.feedback_model_hash, "contract_version": row.contract_version,
        "provenance": json.loads(row.provenance_snapshot), "latency_ms": row.latency_ms,
        "created_at": row.created_at,
    }


def issue_groups(db: Session) -> list[dict]:
    grouped: dict[str, dict] = {}
    audits = db.query(models.FeedbackAudit).filter(models.FeedbackAudit.verdict == "disagree").all()
    for audit in audits:
        judgment = db.get(models.JudgmentResult, audit.judgment_id)
        recommendation = json.loads(audit.recommended_judgment)
        recommendation["edits"] = json.loads(audit.recommended_edits)
        runtime = json.loads(audit.provenance_snapshot).get("runtime", "unknown")
        for code in json.loads(audit.issue_codes):
            key = issue_group_key(code, judgment, recommendation, runtime)
            entry = grouped.setdefault(key, {
                "group_key": key, "issue_code": code, "runtime": runtime,
                "existing_decision": judgment.decision,
                "recommended_decision": recommendation["decision"],
                "count": 0, "judgment_ids": [],
            })
            entry["count"] += 1; entry["judgment_ids"].append(judgment.id)
    for entry in grouped.values():
        count = entry["count"]
        entry["status"] = "emerging" if count <= 2 else "recurrent" if count <= 9 else "systemic"
    return sorted(grouped.values(), key=lambda item: (-item["count"], item["group_key"]))


def monitoring_snapshot(db: Session) -> dict:
    counts = dict(db.query(models.FeedbackAuditJob.status, __import__("sqlalchemy").func.count())
                  .group_by(models.FeedbackAuditJob.status).all())
    return {
        "schema_version": "feedback-monitor-v0.1", "snapshot_at": datetime.now(timezone.utc),
        "job_counts": {name: counts.get(name, 0) for name in ("pending", "running", "succeeded", "failed")},
        "audit_count": db.query(models.FeedbackAudit).count(),
        "disagreement_count": db.query(models.FeedbackAudit).filter_by(verdict="disagree").count(),
        "unreviewable_count": db.query(models.FeedbackAudit).filter_by(verdict="unreviewable").count(),
        "contains_request_content": False,
    }


def retry_job(db: Session, judgment_id: int) -> bool:
    job = (db.query(models.FeedbackAuditJob).filter_by(judgment_id=judgment_id)
           .order_by(models.FeedbackAuditJob.id.desc()).first())
    if job is None or job.status == "succeeded":
        return False
    job.status = "pending"; job.attempts = 0; job.error_category = None
    job.lease_expires_at = None; job.next_attempt_at = datetime.now(timezone.utc)
    db.commit()
    return True

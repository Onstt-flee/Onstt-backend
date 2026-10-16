"""Content-minimized admin queries for feedback audit operations."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
import json

from sqlalchemy.orm import Session

import models
from analyzer.feedback_contract import canonical_json
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


def _status(count: int) -> str:
    return "emerging" if count <= 2 else "recurrent" if count <= 9 else "systemic"


def _operational_group_key(kind: str, **values: object) -> str:
    payload = {"kind": kind, **values}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def issue_groups(db: Session) -> list[dict]:
    grouped: dict[str, dict] = {}
    audits = db.query(models.FeedbackAudit).filter(
        models.FeedbackAudit.verdict.in_(("disagree", "unreviewable")),
    ).all()
    for audit in audits:
        judgment = db.get(models.JudgmentResult, audit.judgment_id)
        runtime = json.loads(audit.provenance_snapshot).get("runtime", "unknown")
        if audit.verdict == "disagree":
            recommendation = json.loads(audit.recommended_judgment)
            recommendation["edits"] = json.loads(audit.recommended_edits)
            for code in json.loads(audit.issue_codes):
                key = issue_group_key(code, judgment, recommendation, runtime)
                entry = grouped.setdefault(key, {
                    "group_key": key, "kind": "model_disagreement",
                    "issue_code": code, "error_category": None, "runtime": runtime,
                    "existing_decision": judgment.decision,
                    "recommended_decision": recommendation["decision"],
                    "count": 0, "judgment_ids": set(),
                })
                entry["judgment_ids"].add(judgment.id)
        else:
            key = _operational_group_key(
                "unreviewable", decision=judgment.decision,
                error_types=sorted(json.loads(judgment.error_types)), runtime=runtime,
            )
            entry = grouped.setdefault(key, {
                "group_key": key, "kind": "unreviewable",
                "issue_code": None, "error_category": None, "runtime": runtime,
                "existing_decision": judgment.decision, "recommended_decision": None,
                "count": 0, "judgment_ids": set(),
            })
            entry["judgment_ids"].add(judgment.id)

    failed_jobs = db.query(models.FeedbackAuditJob).filter_by(status="failed").all()
    for job in failed_jobs:
        judgment = db.get(models.JudgmentResult, job.judgment_id)
        provenance = db.get(models.JudgmentProvenance, job.judgment_id)
        runtime = provenance.runtime if provenance is not None else "unknown"
        error_category = job.error_category or "unknown"
        key = _operational_group_key(
            "audit_failure", error_category=error_category, runtime=runtime,
            feedback_model_hash=job.feedback_model_hash,
        )
        entry = grouped.setdefault(key, {
            "group_key": key, "kind": "audit_failure",
            "issue_code": None, "error_category": error_category, "runtime": runtime,
            "existing_decision": None,
            "recommended_decision": None, "count": 0, "judgment_ids": set(),
        })
        entry["judgment_ids"].add(job.judgment_id)

    for entry in grouped.values():
        entry["judgment_ids"] = sorted(entry["judgment_ids"])
        entry["count"] = len(entry["judgment_ids"])
        entry["status"] = _status(entry["count"])
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

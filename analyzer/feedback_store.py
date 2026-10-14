"""Persistence boundary for immutable judgments and asynchronous audits."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import re
from typing import Any

from sqlalchemy.orm import Session

import models
from analyzer.feedback_contract import CONTRACT_VERSION, canonical_json


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _enabled(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def feedback_enabled() -> bool:
    return _enabled("FEEDBACK_AUDIT_ENABLED")


def feedback_configuration() -> dict[str, str]:
    return {
        "model": os.getenv("FEEDBACK_MODEL", "feedback-qwen3-8b-v01").strip(),
        "adapter": os.getenv("FEEDBACK_ADAPTER", "feedback-verifier-v0.1").strip(),
        "model_hash": os.getenv("FEEDBACK_MODEL_SHA256", "").strip(),
    }


def configuration_error() -> str | None:
    if not feedback_enabled():
        return None
    config = feedback_configuration()
    if not config["model"] or not config["adapter"]:
        return "missing_model_identity"
    if not SHA256_RE.fullmatch(config["model_hash"]):
        return "invalid_feedback_model_hash"
    if len(os.getenv("FEEDBACK_ADMIN_TOKEN", "")) < 32:
        return "invalid_admin_token"
    return None


def _optional_hash(value: Any) -> str | None:
    return value if isinstance(value, str) and SHA256_RE.fullmatch(value) else None


def _enqueue(db: Session, judgment_id: int) -> models.FeedbackAuditJob | None:
    if not feedback_enabled() or configuration_error() is not None:
        return None
    config = feedback_configuration()
    existing = db.query(models.FeedbackAuditJob).filter_by(
        judgment_id=judgment_id,
        feedback_model_hash=config["model_hash"],
        contract_version=CONTRACT_VERSION,
    ).one_or_none()
    if existing is not None:
        return existing
    job = models.FeedbackAuditJob(
        judgment_id=judgment_id,
        feedback_model=config["model"], feedback_adapter=config["adapter"],
        feedback_model_hash=config["model_hash"], contract_version=CONTRACT_VERSION,
        status="pending", attempts=0, next_attempt_at=datetime.now(timezone.utc),
    )
    db.add(job)
    return job


def record_gpu_judgment(db: Session, judgment: models.JudgmentResult, judgment_data: dict[str, Any]) -> None:
    if _enabled("EDGE_MODE"):
        return
    if db.get(models.JudgmentProvenance, judgment.id) is None:
        db.add(models.JudgmentProvenance(
            judgment_id=judgment.id, runtime="gpu_bf16", node_id=None,
            quantization="BF16", judgment_model=judgment.model_name,
            judgment_adapter=judgment.adapter_name,
            model_sha256=_optional_hash(judgment_data.get("model_sha256") or os.getenv("JUDGMENT_MODEL_SHA256")),
            adapter_sha256=_optional_hash(judgment_data.get("adapter_sha256") or os.getenv("JUDGMENT_ADAPTER_SHA256")),
        ))
    _enqueue(db, judgment.id)


def record_edge_judgment(db: Session, judgment: models.JudgmentResult, node_id: str, payload: dict[str, Any]) -> None:
    if db.get(models.JudgmentProvenance, judgment.id) is None:
        db.add(models.JudgmentProvenance(
            judgment_id=judgment.id, runtime="pi_gguf", node_id=node_id,
            quantization=payload.get("quantization"), judgment_model=judgment.model_name,
            judgment_adapter=judgment.adapter_name,
            model_sha256=_optional_hash(payload.get("model_sha256")),
            adapter_sha256=_optional_hash(payload.get("adapter_sha256")),
        ))
    _enqueue(db, judgment.id)


def provenance_snapshot(judgment: models.JudgmentResult, provenance: models.JudgmentProvenance | None) -> dict[str, Any]:
    if provenance is None:
        return {"runtime": "unknown", "node_id": None, "quantization": None,
                "judgment_model": judgment.model_name, "judgment_adapter": judgment.adapter_name,
                "model_sha256": None, "adapter_sha256": None}
    return {"runtime": provenance.runtime, "node_id": provenance.node_id,
            "quantization": provenance.quantization, "judgment_model": provenance.judgment_model,
            "judgment_adapter": provenance.judgment_adapter,
            "model_sha256": provenance.model_sha256, "adapter_sha256": provenance.adapter_sha256}


def diff_shape(edits: list[dict[str, Any]]) -> str:
    parts = []
    for edit in edits:
        source, replacement = edit.get("source", ""), edit.get("replacement", "")
        kind = "insert" if not source else "delete" if not replacement else "replace"
        parts.append(f"{kind}:{len(source)}>{len(replacement)}")
    return ",".join(parts) or "none"


def issue_group_key(issue_code: str, judgment: models.JudgmentResult, recommendation: dict[str, Any], runtime: str) -> str:
    value = {"issue_code": issue_code, "decision": judgment.decision,
             "error_types": sorted(json.loads(judgment.error_types)),
             "recommended_decision": recommendation["decision"],
             "diff_shape": diff_shape(recommendation.get("edits", [])), "runtime": runtime}
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

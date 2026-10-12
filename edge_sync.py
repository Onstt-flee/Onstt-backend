"""Pi edge outbox creation and GPU-side idempotent synchronization."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import case
from sqlalchemy.orm import Session

import models


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EVENT_TYPES = {"session", "utterance", "judgment"}
ERROR_TYPES = {
    "particle_misuse", "verb_conjugation", "adjective_conjugation",
    "copula_conjugation", "modifier_connection", "tense_mismatch",
}


class EdgeConfigurationError(RuntimeError):
    pass


class EdgePayloadConflict(RuntimeError):
    pass


class EdgeEventRejected(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def payload_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def edge_mode_enabled() -> bool:
    return os.getenv("EDGE_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}


def configured_node_id() -> str:
    raw = os.getenv("EDGE_NODE_ID", "").strip()
    try:
        return str(UUID(raw))
    except (ValueError, AttributeError) as exc:
        raise EdgeConfigurationError("EDGE_NODE_ID must be a UUID when EDGE_MODE=true") from exc


def sync_token_valid(authorization: str | None) -> bool:
    expected = os.getenv("EDGE_SYNC_TOKEN", "")
    if len(expected) < 32:
        raise EdgeConfigurationError("EDGE_SYNC_TOKEN must contain at least 32 characters")
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        return False
    return hmac.compare_digest(authorization[len(prefix):], expected)


def _identity(db: Session, entity_type: str, local_id: int, *, create: bool) -> str:
    row = db.query(models.EdgeEntityIdentity).filter_by(
        entity_type=entity_type, local_id=local_id
    ).one_or_none()
    if row is not None:
        return row.event_id
    if not create:
        raise EdgeConfigurationError(
            f"Missing edge identity for {entity_type} local_id={local_id}"
        )
    event_id = str(uuid4())
    db.add(models.EdgeEntityIdentity(
        event_id=event_id, entity_type=entity_type, local_id=local_id
    ))
    return event_id


def _enqueue(db: Session, event_id: str, event_type: str, payload: dict[str, Any]) -> None:
    db.add(models.EdgeOutboxEvent(
        event_id=event_id,
        node_id=configured_node_id(),
        event_type=event_type,
        payload=canonical_json(payload),
        payload_sha256=payload_sha256(payload),
        status="pending",
    ))


def enqueue_session(db: Session, session: models.Session) -> None:
    if not edge_mode_enabled():
        return
    event_id = _identity(db, "session", session.id, create=True)
    _enqueue(db, event_id, "session", {
        "topic": session.topic,
        "description": session.description,
    })


def enqueue_utterance(db: Session, utterance: models.Utterance) -> None:
    if not edge_mode_enabled():
        return
    event_id = _identity(db, "utterance", utterance.id, create=True)
    session_event_id = _identity(db, "session", utterance.session_id, create=False)
    _enqueue(db, event_id, "utterance", {
        "session_event_id": session_event_id,
        "stt_text": utterance.stt_text,
        "language": utterance.language,
        "duration": utterance.duration,
        "stt_model": utterance.stt_model,
        "preprocess_status": utterance.preprocess_status,
        "sample_rate": utterance.sample_rate,
        "channels": utterance.channels,
        "audio_format": utterance.audio_format,
        # Pi-local audio paths and files deliberately never leave the edge node.
    })


def enqueue_judgment(
    db: Session, judgment: models.JudgmentResult, judgment_data: dict[str, Any]
) -> None:
    if not edge_mode_enabled():
        return
    event_id = _identity(db, "judgment", judgment.id, create=True)
    utterance_event_id = _identity(db, "utterance", judgment.utterance_id, create=False)
    utterance = db.get(models.Utterance, judgment.utterance_id)
    input_text = utterance.processed_text or utterance.normalized_text or utterance.stt_text
    model_hash = os.getenv("EDGE_MODEL_SHA256", "").strip()
    adapter_hash = os.getenv("EDGE_ADAPTER_SHA256", "").strip()
    if not SHA256_RE.fullmatch(model_hash) or not SHA256_RE.fullmatch(adapter_hash):
        raise EdgeConfigurationError(
            "EDGE_MODEL_SHA256 and EDGE_ADAPTER_SHA256 must be lowercase SHA-256 values"
        )
    _enqueue(db, event_id, "judgment", {
        "utterance_event_id": utterance_event_id,
        "input_text": input_text,
        "decision": judgment.decision,
        "corrected_text": judgment.corrected_text,
        "edits": json.loads(judgment.edits),
        "error_types": json.loads(judgment.error_types),
        "reason_ko": judgment.reason_ko,
        "classification_review_required": judgment.classification_review_required,
        "strategy": judgment.strategy,
        "model_name": judgment.model_name,
        "adapter_name": judgment.adapter_name,
        "selection_reason": judgment.selection_reason,
        "contract_version": judgment.contract_version,
        "latency_ms": judgment.latency_ms,
        "context": judgment.context,
        "learner_level": judgment.learner_level,
        "quantization": "Q4_K_M",
        "model_sha256": model_hash,
        "adapter_sha256": adapter_hash,
    })


def pending_events(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    rows = (
        db.query(models.EdgeOutboxEvent)
        .filter(models.EdgeOutboxEvent.status == "pending")
        .order_by(
            case(
                (models.EdgeOutboxEvent.event_type == "session", 0),
                (models.EdgeOutboxEvent.event_type == "utterance", 1),
                (models.EdgeOutboxEvent.event_type == "judgment", 2),
                else_=3,
            ),
            models.EdgeOutboxEvent.created_at,
            models.EdgeOutboxEvent.event_id,
        )
        .limit(limit)
        .all()
    )
    return [{
        "event_id": row.event_id,
        "event_type": row.event_type,
        "payload_sha256": row.payload_sha256,
        "payload": json.loads(row.payload),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    } for row in rows]


def apply_sync_results(db: Session, results: list[dict[str, Any]]) -> None:
    now = datetime.now(timezone.utc)
    for result in results:
        row = db.get(models.EdgeOutboxEvent, str(result.get("event_id")))
        if row is None:
            continue
        row.attempts += 1
        if result.get("status") in {"accepted", "duplicate"}:
            row.status = "synced"
            row.remote_id = result.get("remote_id")
            row.last_error = None
            row.synced_at = now
        else:
            row.last_error = str(result.get("error") or "rejected")[:1000]
    db.commit()


def record_sync_failure(db: Session, event_ids: list[str], error: str) -> None:
    message = error[:1000]
    rows = db.query(models.EdgeOutboxEvent).filter(
        models.EdgeOutboxEvent.event_id.in_(event_ids),
        models.EdgeOutboxEvent.status == "pending",
    ).all()
    for row in rows:
        row.attempts += 1
        row.last_error = message
    db.commit()


def _required(payload: dict[str, Any], name: str, expected: type) -> Any:
    value = payload.get(name)
    if not isinstance(value, expected):
        raise EdgeEventRejected(f"{name} must be {expected.__name__}")
    return value


def _dependency(db: Session, node_id: str, event_id: str, event_type: str) -> int:
    try:
        normalized = str(UUID(event_id))
    except (ValueError, AttributeError) as exc:
        raise EdgeEventRejected(f"Invalid {event_type} dependency UUID") from exc
    row = db.query(models.EdgeSyncReceipt).filter_by(
        node_id=node_id, event_id=normalized, event_type=event_type
    ).one_or_none()
    if row is None:
        raise EdgeEventRejected(f"Missing accepted {event_type} dependency")
    return row.remote_id


def _create_remote_entity(
    db: Session, node_id: str, event_type: str, payload: dict[str, Any]
) -> tuple[int, dict[str, Any] | None]:
    if event_type == "session":
        topic = _required(payload, "topic", str).strip()
        if not topic:
            raise EdgeEventRejected("topic must be nonblank")
        description = payload.get("description")
        if description is not None and not isinstance(description, str):
            raise EdgeEventRejected("description must be null or string")
        row = models.Session(user_id=None, topic=topic, description=description)
        db.add(row)
        db.flush()
        return row.id, None

    if event_type == "utterance":
        session_id = _dependency(
            db, node_id, _required(payload, "session_event_id", str), "session"
        )
        stt_text = _required(payload, "stt_text", str)
        if not stt_text.strip():
            raise EdgeEventRejected("stt_text must be nonblank")
        row = models.Utterance(
            session_id=session_id,
            raw_audio_path=None,
            audio_path=None,
            stt_text=stt_text,
            language=payload.get("language") or "ja",
            duration=payload.get("duration"),
            stt_model=payload.get("stt_model"),
            preprocess_status=payload.get("preprocess_status"),
            sample_rate=payload.get("sample_rate"),
            channels=payload.get("channels"),
            audio_format=payload.get("audio_format"),
        )
        db.add(row)
        db.flush()
        return row.id, None

    if event_type != "judgment":
        raise EdgeEventRejected("Unsupported event_type")

    utterance_id = _dependency(
        db, node_id, _required(payload, "utterance_event_id", str), "utterance"
    )
    utterance = db.get(models.Utterance, utterance_id)
    input_text = _required(payload, "input_text", str)
    if not input_text.strip():
        raise EdgeEventRejected("input_text must be nonblank")
    decision = payload.get("decision")
    if decision not in {"acceptable", "needs_correction", "insufficient_evidence"}:
        raise EdgeEventRejected("Invalid decision")
    corrected_text = _required(payload, "corrected_text", str)
    if decision != "needs_correction" and corrected_text != input_text:
        raise EdgeEventRejected("Non-correction decision must preserve model input text")
    edits = payload.get("edits")
    error_types = payload.get("error_types")
    if not isinstance(edits, list) or not isinstance(error_types, list):
        raise EdgeEventRejected("edits and error_types must be arrays")
    if any(value not in ERROR_TYPES for value in error_types):
        raise EdgeEventRejected("Unsupported error type")
    if decision != "needs_correction" and (edits or error_types):
        raise EdgeEventRejected("Non-correction decision must not contain edits")
    cursor = 0
    rebuilt = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise EdgeEventRejected("Each edit must be an object")
        start, end = edit.get("start"), edit.get("end")
        if type(start) is not int or type(end) is not int or not (cursor <= start <= end <= len(input_text)):
            raise EdgeEventRejected("Invalid or overlapping edit range")
        if edit.get("source") != input_text[start:end] or not isinstance(edit.get("replacement"), str):
            raise EdgeEventRejected("Edit source or replacement is invalid")
        rebuilt.extend((input_text[cursor:start], edit["replacement"]))
        cursor = end
    rebuilt.append(input_text[cursor:])
    if "".join(rebuilt) != corrected_text:
        raise EdgeEventRejected("Edits do not reconstruct corrected_text")
    if payload.get("strategy") != "d_only":
        raise EdgeEventRejected("Only d_only edge judgments are accepted")
    if payload.get("model_name") != "judgment-v02d":
        raise EdgeEventRejected("model_name must be judgment-v02d")
    if payload.get("contract_version") != "judgment-v0.2":
        raise EdgeEventRejected("contract_version must be judgment-v0.2")
    if payload.get("learner_level") not in {"N5", "N4"}:
        raise EdgeEventRejected("learner_level must be N5 or N4")
    if payload.get("quantization") != "Q4_K_M":
        raise EdgeEventRejected("quantization must be Q4_K_M")
    for field in ("model_sha256", "adapter_sha256"):
        if not isinstance(payload.get(field), str) or not SHA256_RE.fullmatch(payload[field]):
            raise EdgeEventRejected(f"{field} must be lowercase SHA-256")

    row = models.JudgmentResult(
        utterance_id=utterance_id,
        decision=decision,
        corrected_text=corrected_text,
        edits=canonical_json(edits),
        error_types=canonical_json(error_types),
        reason_ko=_required(payload, "reason_ko", str),
        classification_review_required=bool(payload.get("classification_review_required", False)),
        strategy="d_only",
        model_name=_required(payload, "model_name", str),
        adapter_name=_required(payload, "adapter_name", str),
        selection_reason=_required(payload, "selection_reason", str),
        contract_version=_required(payload, "contract_version", str),
        latency_ms=payload.get("latency_ms"),
        context=payload.get("context"),
        learner_level=payload["learner_level"],
    )
    db.add(row)
    db.flush()
    provenance = {
        "quantization": payload["quantization"],
        "model_sha256": payload["model_sha256"],
        "adapter_sha256": payload["adapter_sha256"],
        "input_text_sha256": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
    }
    return row.id, provenance


def process_sync_event(
    db: Session,
    *,
    node_id: str,
    event_id: str,
    event_type: str,
    claimed_sha256: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if event_type not in EVENT_TYPES:
        return {"event_id": event_id, "status": "rejected", "error": "Unsupported event_type"}
    actual_hash = payload_sha256(payload)
    if not hmac.compare_digest(actual_hash, claimed_sha256):
        return {"event_id": event_id, "status": "rejected", "error": "payload_sha256 mismatch"}

    existing = db.query(models.EdgeSyncReceipt).filter_by(
        node_id=node_id, event_id=event_id
    ).one_or_none()
    if existing is not None:
        if existing.event_type != event_type or not hmac.compare_digest(
            existing.payload_sha256, actual_hash
        ):
            raise EdgePayloadConflict("event_id was already accepted with different content")
        return {"event_id": event_id, "status": "duplicate", "remote_id": existing.remote_id}

    try:
        remote_id, provenance = _create_remote_entity(db, node_id, event_type, payload)
        db.add(models.EdgeSyncReceipt(
            node_id=node_id,
            event_id=event_id,
            event_type=event_type,
            payload_sha256=actual_hash,
            remote_id=remote_id,
            provenance=canonical_json(provenance) if provenance else None,
        ))
        db.commit()
    except EdgeEventRejected as exc:
        db.rollback()
        return {"event_id": event_id, "status": "rejected", "error": str(exc)}
    except Exception:
        db.rollback()
        raise
    return {"event_id": event_id, "status": "accepted", "remote_id": remote_id}

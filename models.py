from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    level = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    topic = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Utterance(Base):
    __tablename__ = "utterances"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)

    raw_audio_path = Column(Text, nullable=True)
    audio_path = Column(Text, nullable=True)

    stt_text = Column(Text, nullable=False)

    processed_text = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=True)
    tokens = Column(Text, nullable=True)

    language = Column(String, default="ja")
    duration = Column(Float, nullable=True)
    stt_model = Column(Text, nullable=True)

    preprocess_status = Column(Text, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    audio_format = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    utterance_id = Column(Integer, ForeignKey("utterances.id"), nullable=False)

    primary_type = Column(String, nullable=True)
    candidate_types = Column(Text, nullable=True)
    classification_reason = Column(Text, nullable=True)
    needs_deep_analysis = Column(Boolean, default=True)

    is_correct = Column(Boolean, nullable=True)
    corrected_text = Column(Text, nullable=True)
    error_types = Column(Text, nullable=True)

    feedback_ko = Column(Text, nullable=True)
    feedback_ja = Column(Text, nullable=True)

    vocab_context = Column(Text, nullable=True)
    grammar_context = Column(Text, nullable=True)
    example_context = Column(Text, nullable=True)
    error_context = Column(Text, nullable=True)

    model_name = Column(String, nullable=True)
    adapter_name = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class JudgmentResult(Base):
    __tablename__ = "judgment_results"

    id = Column(Integer, primary_key=True, index=True)
    utterance_id = Column(Integer, ForeignKey("utterances.id"), nullable=False, index=True)

    decision = Column(String, nullable=False)
    corrected_text = Column(Text, nullable=False)
    edits = Column(Text, nullable=False)
    error_types = Column(Text, nullable=False)
    reason_ko = Column(Text, nullable=False)
    classification_review_required = Column(Boolean, nullable=False, default=False)

    strategy = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    adapter_name = Column(String, nullable=False)
    selection_reason = Column(Text, nullable=False)
    contract_version = Column(String, nullable=False)
    latency_ms = Column(Float, nullable=True)

    context = Column(Text, nullable=True)
    learner_level = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EdgeEntityIdentity(Base):
    """Stable UUID assigned to a local SQLite entity on an edge node."""

    __tablename__ = "edge_entity_identities"
    __table_args__ = (
        UniqueConstraint("entity_type", "local_id", name="uq_edge_entity_local"),
    )

    event_id = Column(String(36), primary_key=True)
    entity_type = Column(String(16), nullable=False)
    local_id = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EdgeOutboxEvent(Base):
    """Pi-local, content-bearing event waiting for explicit synchronization."""

    __tablename__ = "edge_outbox_events"

    event_id = Column(String(36), primary_key=True)
    node_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(16), nullable=False)
    payload = Column(Text, nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    remote_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    synced_at = Column(DateTime(timezone=True), nullable=True)


class EdgeSyncReceipt(Base):
    """GPU-side idempotency receipt and edge-to-server ID mapping."""

    __tablename__ = "edge_sync_receipts"
    __table_args__ = (
        UniqueConstraint("node_id", "event_id", name="uq_edge_sync_node_event"),
    )

    id = Column(Integer, primary_key=True)
    node_id = Column(String(36), nullable=False, index=True)
    event_id = Column(String(36), nullable=False)
    event_type = Column(String(16), nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    remote_id = Column(Integer, nullable=False)
    provenance = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

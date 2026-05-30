from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean
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
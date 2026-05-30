# crud.py

import json
from datetime import datetime
from sqlalchemy.orm import Session

import models
import schemas


def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User(
        name=user.name,
        level=user.level
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def create_session(db: Session, session: schemas.SessionCreate):
    db_session = models.Session(
        user_id=session.user_id,
        topic=session.topic,
        description=session.description
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session


def create_utterance(db: Session, utterance: schemas.UtteranceCreate):
    db_utterance = models.Utterance(
        session_id=utterance.session_id,
        raw_audio_path=utterance.raw_audio_path,
        audio_path=utterance.audio_path,
        stt_text=utterance.stt_text,
        language=utterance.language,
        duration=utterance.duration,
        stt_model=utterance.stt_model,
        preprocess_status=utterance.preprocess_status,
        sample_rate=utterance.sample_rate,
        channels=utterance.channels,
        audio_format=utterance.audio_format
    )

    db.add(db_utterance)
    db.commit()
    db.refresh(db_utterance)
    return db_utterance


def get_utterance(db: Session, utterance_id: int):
    return db.query(models.Utterance).filter(
        models.Utterance.id == utterance_id
    ).first()


def get_session_utterances(db: Session, session_id: int):
    return db.query(models.Utterance).filter(
        models.Utterance.session_id == session_id
    ).all()


def get_user_sessions(db: Session, user_id: int):
    return db.query(models.Session).filter(
        models.Session.user_id == user_id
    ).all()


def update_preprocess(db: Session, utterance_id: int, data: schemas.PreprocessUpdate):
    db_utterance = get_utterance(db, utterance_id)

    if db_utterance is None:
        return None

    if data.processed_text is not None:
        db_utterance.processed_text = data.processed_text

    if data.normalized_text is not None:
        db_utterance.normalized_text = data.normalized_text

    if data.tokens is not None:
        db_utterance.tokens = json.dumps(data.tokens, ensure_ascii=False)

    db_utterance.updated_at = datetime.now()

    db.commit()
    db.refresh(db_utterance)

    return db_utterance


def create_analysis(db: Session, utterance_id: int, analysis_data: dict):
    candidate_types = analysis_data.get("candidate_types")
    error_types = analysis_data.get("error_types")

    if candidate_types is not None and not isinstance(candidate_types, str):
        candidate_types = json.dumps(candidate_types, ensure_ascii=False)

    if error_types is not None and not isinstance(error_types, str):
        error_types = json.dumps(error_types, ensure_ascii=False)

    db_analysis = models.Analysis(
        utterance_id=utterance_id,
        primary_type=analysis_data.get("primary_type"),
        candidate_types=candidate_types,
        classification_reason=analysis_data.get("classification_reason"),
        needs_deep_analysis=analysis_data.get("needs_deep_analysis", True),

        is_correct=analysis_data.get("is_correct"),
        corrected_text=analysis_data.get("corrected_text"),
        error_types=error_types,

        feedback_ko=analysis_data.get("feedback_ko"),
        feedback_ja=analysis_data.get("feedback_ja"),

        vocab_context=analysis_data.get("vocab_context"),
        grammar_context=analysis_data.get("grammar_context"),
        example_context=analysis_data.get("example_context"),
        error_context=analysis_data.get("error_context"),

        model_name=analysis_data.get("model_name"),
        adapter_name=analysis_data.get("adapter_name"),
        confidence=analysis_data.get("confidence"),
    )

    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)

    return db_analysis


def get_analyses_by_utterance(db: Session, utterance_id: int):
    return (
        db.query(models.Analysis)
        .filter(models.Analysis.utterance_id == utterance_id)
        .order_by(models.Analysis.created_at.desc())
        .all()
    )

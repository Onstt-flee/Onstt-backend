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


def get_learner_level_for_utterance(db: Session, utterance_id: int):
    row = (
        db.query(models.User.level)
        .join(models.Session, models.Session.user_id == models.User.id)
        .join(models.Utterance, models.Utterance.session_id == models.Session.id)
        .filter(models.Utterance.id == utterance_id)
        .first()
    )
    if row is None or row[0] not in {"N5", "N4"}:
        return None
    return row[0]


def _judgment_to_response(db_judgment: models.JudgmentResult):
    return {
        "id": db_judgment.id,
        "utterance_id": db_judgment.utterance_id,
        "decision": db_judgment.decision,
        "corrected_text": db_judgment.corrected_text,
        "edits": json.loads(db_judgment.edits),
        "error_types": json.loads(db_judgment.error_types),
        "reason_ko": db_judgment.reason_ko,
        "classification_review_required": db_judgment.classification_review_required,
        "strategy": db_judgment.strategy,
        "model_name": db_judgment.model_name,
        "adapter_name": db_judgment.adapter_name,
        "selection_reason": db_judgment.selection_reason,
        "contract_version": db_judgment.contract_version,
        "latency_ms": db_judgment.latency_ms,
        "context": db_judgment.context,
        "learner_level": db_judgment.learner_level,
        "created_at": db_judgment.created_at,
    }


def create_judgment(db: Session, utterance_id: int, judgment_data: dict):
    db_judgment = models.JudgmentResult(
        utterance_id=utterance_id,
        decision=judgment_data["decision"],
        corrected_text=judgment_data["corrected_text"],
        edits=json.dumps(judgment_data["edits"], ensure_ascii=False),
        error_types=json.dumps(judgment_data["error_types"], ensure_ascii=False),
        reason_ko=judgment_data["reason_ko"],
        classification_review_required=judgment_data["classification_review_required"],
        strategy=judgment_data["strategy"],
        model_name=judgment_data["model_name"],
        adapter_name=judgment_data["adapter_name"],
        selection_reason=judgment_data["selection_reason"],
        contract_version=judgment_data["contract_version"],
        latency_ms=judgment_data.get("latency_ms"),
        context=judgment_data.get("context"),
        learner_level=judgment_data["learner_level"],
    )
    db.add(db_judgment)
    db.commit()
    db.refresh(db_judgment)
    return _judgment_to_response(db_judgment)


def get_judgments_by_utterance(db: Session, utterance_id: int):
    rows = (
        db.query(models.JudgmentResult)
        .filter(models.JudgmentResult.utterance_id == utterance_id)
        .order_by(models.JudgmentResult.created_at.desc(), models.JudgmentResult.id.desc())
        .all()
    )
    return [_judgment_to_response(row) for row in rows]

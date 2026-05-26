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
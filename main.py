# main.py

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
import crud
from database import engine, get_db


models.Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Japanese STT Conversation API",
    description="""
라즈베리파이에서 수행한 일본어 STT 결과를 GPU 서버에 저장하고 조회하기 위한 API입니다.

주요 기능:
- 사용자 생성
- 회화 세션 생성
- STT 발화 저장
- 세션별 발화 조회
- 텍스트 전처리 결과 업데이트

라즈베리파이는 음성 녹음, 음성 전처리, STT 실행을 담당하고,
GPU 서버는 FastAPI를 통해 STT 결과 저장, 조회, 후속 분석을 담당합니다.
""",
    version="1.0.0",
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1
    }
)


@app.get(
    "/health",
    response_model=schemas.HealthResponse,
    tags=["System"],
    summary="서버 상태 확인"
)
def health_check():
    return {
        "status": "ok",
        "message": "STT API server is running"
    }


@app.post(
    "/users",
    tags=["Users"],
    summary="사용자 생성"
)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    db_user = crud.create_user(db, user)

    return {
        "user_id": db_user.id,
        "name": db_user.name,
        "level": db_user.level,
        "created_at": db_user.created_at
    }


@app.post(
    "/sessions",
    tags=["Sessions"],
    summary="회화 세션 생성"
)
def create_session(
    session: schemas.SessionCreate,
    db: Session = Depends(get_db)
):
    db_session = crud.create_session(db, session)

    return {
        "session_id": db_session.id,
        "user_id": db_session.user_id,
        "topic": db_session.topic,
        "description": db_session.description,
        "created_at": db_session.created_at
    }


@app.get(
    "/users/{user_id}/sessions",
    tags=["Sessions"],
    summary="사용자별 세션 목록 조회"
)
def read_user_sessions(
    user_id: int,
    db: Session = Depends(get_db)
):
    sessions = crud.get_user_sessions(db, user_id)

    return {
        "user_id": user_id,
        "sessions": [
            {
                "session_id": s.id,
                "topic": s.topic,
                "description": s.description,
                "created_at": s.created_at
            }
            for s in sessions
        ]
    }


@app.post(
    "/utterances",
    tags=["Utterances"],
    summary="STT 발화 저장"
)
def create_utterance(
    utterance: schemas.UtteranceCreate,
    db: Session = Depends(get_db)
):
    db_utterance = crud.create_utterance(db, utterance)

    return {
        "utterance_id": db_utterance.id,
        "session_id": db_utterance.session_id,
        "raw_audio_path": db_utterance.raw_audio_path,
        "audio_path": db_utterance.audio_path,
        "stt_text": db_utterance.stt_text,
        "language": db_utterance.language,
        "duration": db_utterance.duration,
        "stt_model": db_utterance.stt_model,
        "preprocess_status": db_utterance.preprocess_status,
        "sample_rate": db_utterance.sample_rate,
        "channels": db_utterance.channels,
        "audio_format": db_utterance.audio_format,
        "status": "saved",
        "created_at": db_utterance.created_at
    }


@app.get(
    "/utterances/{utterance_id}",
    tags=["Utterances"],
    summary="특정 발화 조회"
)
def read_utterance(
    utterance_id: int,
    db: Session = Depends(get_db)
):
    db_utterance = crud.get_utterance(db, utterance_id)

    if db_utterance is None:
        raise HTTPException(status_code=404, detail="Utterance not found")

    return {
        "utterance_id": db_utterance.id,
        "session_id": db_utterance.session_id,
        "raw_audio_path": db_utterance.raw_audio_path,
        "audio_path": db_utterance.audio_path,
        "stt_text": db_utterance.stt_text,
        "processed_text": db_utterance.processed_text,
        "normalized_text": db_utterance.normalized_text,
        "tokens": db_utterance.tokens,
        "language": db_utterance.language,
        "duration": db_utterance.duration,
        "stt_model": db_utterance.stt_model,
        "preprocess_status": db_utterance.preprocess_status,
        "sample_rate": db_utterance.sample_rate,
        "channels": db_utterance.channels,
        "audio_format": db_utterance.audio_format,
        "created_at": db_utterance.created_at,
        "updated_at": db_utterance.updated_at
    }


@app.get(
    "/utterances/{utterance_id}/analysis",
    response_model=List[schemas.AnalysisResponse],
    tags=["Analysis"],
    summary="특정 발화의 분석 결과 조회"
)
def read_utterance_analysis(
    utterance_id: int,
    db: Session = Depends(get_db)
):
    db_utterance = crud.get_utterance(db, utterance_id)

    if db_utterance is None:
        raise HTTPException(status_code=404, detail="Utterance not found")

    analyses = crud.get_analyses_by_utterance(db, utterance_id)

    return analyses


@app.post(
    "/utterances/{utterance_id}/analyze",
    response_model=schemas.AnalysisResponse,
    tags=["Analysis"],
    summary="특정 발화 임시 분석 실행"
)
def analyze_utterance_temp(
    utterance_id: int,
    db: Session = Depends(get_db)
):
    db_utterance = crud.get_utterance(db, utterance_id)

    if db_utterance is None:
        raise HTTPException(status_code=404, detail="Utterance not found")

    analysis_data = {
        "primary_type": "statement",
        "candidate_types": "[{\"type\":\"statement\",\"score\":0.8}]",
        "classification_reason": "임시 분석: 일반 평서문으로 처리했습니다.",
        "needs_deep_analysis": True,

        "is_correct": False,
        "corrected_text": "今日は学校に行きました",
        "error_types": "[\"particle_omission\"]",

        "feedback_ko": "임시 분석 결과입니다. 장소 뒤에는 조사 に가 필요할 수 있습니다.",
        "feedback_ja": "これは一時的な分析結果です。場所の後には「に」を使うことがあります。",

        "vocab_context": None,
        "grammar_context": None,
        "example_context": None,
        "error_context": None,

        "model_name": "rule_based_temp",
        "adapter_name": None,
        "confidence": 0.5,
    }

    db_analysis = crud.create_analysis(
        db=db,
        utterance_id=utterance_id,
        analysis_data=analysis_data
    )

    return db_analysis
    

@app.get(
    "/sessions/{session_id}/utterances",
    tags=["Utterances"],
    summary="세션별 발화 목록 조회"
)
def read_session_utterances(
    session_id: int,
    db: Session = Depends(get_db)
):
    utterances = crud.get_session_utterances(db, session_id)

    return {
        "session_id": session_id,
        "utterances": [
            {
                "utterance_id": u.id,
                "raw_audio_path": u.raw_audio_path,
                "audio_path": u.audio_path,
                "stt_text": u.stt_text,
                "processed_text": u.processed_text,
                "normalized_text": u.normalized_text,
                "tokens": u.tokens,
                "duration": u.duration,
                "preprocess_status": u.preprocess_status,
                "sample_rate": u.sample_rate,
                "channels": u.channels,
                "audio_format": u.audio_format,
                "created_at": u.created_at
            }
            for u in utterances
        ]
    }


@app.patch(
    "/utterances/{utterance_id}/preprocess",
    tags=["Preprocess"],
    summary="텍스트 전처리 결과 업데이트"
)
def update_utterance_preprocess(
    utterance_id: int,
    data: schemas.PreprocessUpdate,
    db: Session = Depends(get_db)
):
    db_utterance = crud.update_preprocess(db, utterance_id, data)

    if db_utterance is None:
        raise HTTPException(status_code=404, detail="Utterance not found")

    return {
        "utterance_id": db_utterance.id,
        "processed_text": db_utterance.processed_text,
        "normalized_text": db_utterance.normalized_text,
        "tokens": db_utterance.tokens,
        "status": "updated",
        "updated_at": db_utterance.updated_at
    }
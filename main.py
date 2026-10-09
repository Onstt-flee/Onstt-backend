# main.py

import asyncio
import os

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
import crud
from database import engine, get_db
from analyzer.pipeline import analyze as run_analysis
from analyzer.judgment_service import (
    JudgmentServiceError,
    judgment_enabled,
    run_judgment,
)
from analyzer.judgment_monitor import (
    record_failure,
    record_internal_failure,
    record_model_invocation,
    record_rejection,
    record_request,
    record_success,
    snapshot as judgment_monitor_snapshot,
)
from analyzer.judgment_shadow import (
    schedule_shadow as schedule_judgment_shadow,
    snapshot as judgment_shadow_snapshot,
    start_worker as start_judgment_shadow_worker,
    stop_worker as stop_judgment_shadow_worker,
)
from analyzer.judgment_runtime import (
    JudgmentOverloadedError,
    JudgmentRuntimeConfigurationError,
    JudgmentShuttingDownError,
    readiness_snapshot,
    reserve_capacity,
    set_accepting,
    wait_for_idle,
)

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


@app.get(
    "/health/judgment",
    response_model=schemas.JudgmentMonitoringResponse,
    tags=["System"],
    summary="판단모델 staging 집계 상태 확인"
)
def judgment_health_check():
    result = judgment_monitor_snapshot()
    result["shadow"] = judgment_shadow_snapshot()
    return result


@app.get(
    "/ready/judgment",
    response_model=schemas.JudgmentReadinessResponse,
    tags=["System"],
    summary="판단모델 readiness 확인",
)
def judgment_readiness_check(response: Response):
    result = readiness_snapshot()
    if not result["ready"]:
        response.status_code = 503
    return result


@app.on_event("startup")
def judgment_runtime_startup():
    set_accepting(True)
    start_judgment_shadow_worker()


@app.on_event("shutdown")
async def judgment_runtime_shutdown():
    try:
        grace = float(os.getenv("JUDGMENT_SHUTDOWN_GRACE_SECONDS", "30"))
    except ValueError:
        grace = 0.0
    grace = max(0.0, grace)
    started = asyncio.get_running_loop().time()
    await asyncio.to_thread(stop_judgment_shadow_worker, grace)
    set_accepting(False)
    remaining = max(0.0, grace - (asyncio.get_running_loop().time() - started))
    await asyncio.to_thread(wait_for_idle, remaining)


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
    summary="특정 발화 분석 실행"
)
def analyze_utterance(
    utterance_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    db_utterance = crud.get_utterance(db, utterance_id)

    if db_utterance is None:
        raise HTTPException(status_code=404, detail="Utterance not found")

    input_text = db_utterance.processed_text or db_utterance.normalized_text or db_utterance.stt_text

    if input_text is None:
        raise HTTPException(status_code=400, detail="Utterance text is empty")

    analysis_data = run_analysis(input_text)

    db_analysis = crud.create_analysis(
        db=db,
        utterance_id=utterance_id,
        analysis_data=analysis_data
    )

    learner_level = crud.get_learner_level_for_utterance(db, utterance_id) or "N5"
    schedule_judgment_shadow(background_tasks, input_text, learner_level)
    return db_analysis


@app.post(
    "/utterances/{utterance_id}/judgment",
    response_model=schemas.JudgmentResponse,
    tags=["Judgment"],
    summary="판단모델로 특정 발화 판단 실행"
)
def judge_utterance(
    utterance_id: int,
    data: schemas.JudgmentRequest | None = None,
    db: Session = Depends(get_db)
):
    record_request()
    db_utterance = crud.get_utterance(db, utterance_id)
    if db_utterance is None:
        record_rejection("not_found")
        raise HTTPException(status_code=404, detail="Utterance not found")

    input_text = db_utterance.processed_text or db_utterance.normalized_text or db_utterance.stt_text
    if not isinstance(input_text, str) or not input_text.strip():
        record_rejection("empty_input")
        raise HTTPException(status_code=400, detail="Utterance text is empty")
    if not judgment_enabled():
        record_rejection("disabled")
        raise HTTPException(status_code=503, detail="Judgment model is disabled")

    data = data or schemas.JudgmentRequest()
    learner_level = (
        data.learner_level
        or crud.get_learner_level_for_utterance(db, utterance_id)
        or "N5"
    )
    try:
        with reserve_capacity():
            record_model_invocation()
            try:
                result = run_judgment(
                    input_text,
                    context=data.context,
                    learner_level=learner_level,
                )
            except JudgmentServiceError as exc:
                record_failure(exc)
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            try:
                stored = crud.create_judgment(db, utterance_id, result)
            except Exception:
                record_internal_failure("persistence_failure")
                raise
            record_success(result)
            return stored
    except JudgmentOverloadedError as exc:
        record_rejection("overloaded")
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": "1"},
        ) from exc
    except JudgmentShuttingDownError as exc:
        record_rejection("shutting_down")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except JudgmentRuntimeConfigurationError as exc:
        record_rejection("runtime_configuration")
        raise HTTPException(status_code=503, detail=str(exc)) from exc



@app.get(
    "/utterances/{utterance_id}/judgments",
    response_model=List[schemas.JudgmentResponse],
    tags=["Judgment"],
    summary="특정 발화의 판단모델 결과 조회"
)
def read_utterance_judgments(
    utterance_id: int,
    db: Session = Depends(get_db)
):
    if crud.get_utterance(db, utterance_id) is None:
        raise HTTPException(status_code=404, detail="Utterance not found")
    return crud.get_judgments_by_utterance(db, utterance_id)


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
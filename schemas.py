# schemas.py

from pydantic import BaseModel, Field
from typing import Any, Dict, Literal, Optional, List
from datetime import datetime
from uuid import UUID


class UserCreate(BaseModel):
    name: str = Field(..., example="minsung")
    level: Optional[str] = Field(None, example="N5")


class SessionCreate(BaseModel):
    user_id: Optional[int] = Field(None, example=1)
    topic: str = Field(..., example="일상 대화")
    description: Optional[str] = Field(
        None,
        example="라즈베리파이 기반 일본어 STT 테스트 세션"
    )


class UtteranceCreate(BaseModel):
    session_id: int = Field(..., example=1)

    raw_audio_path: Optional[str] = Field(
        None,
        example="/home/pi/audio/raw/utt_001.wav"
    )
    audio_path: Optional[str] = Field(
        None,
        example="/home/pi/audio/processed/utt_001.wav"
    )

    stt_text: str = Field(..., example="今日学校行きました")
    language: str = Field("ja", example="ja")
    duration: Optional[float] = Field(None, example=3.42)
    stt_model: Optional[str] = Field(None, example="faster-whisper-small")

    preprocess_status: Optional[str] = Field(None, example="done")
    sample_rate: Optional[int] = Field(None, example=16000)
    channels: Optional[int] = Field(None, example=1)
    audio_format: Optional[str] = Field(None, example="wav")


class PreprocessUpdate(BaseModel):
    processed_text: Optional[str] = Field(None, example="今日 学校 行きました")
    normalized_text: Optional[str] = Field(None, example="今日学校行きました")
    tokens: Optional[List[str]] = Field(
        None,
        example=["今日", "学校", "行きました"]
    )


class HealthResponse(BaseModel):
    status: str
    message: str


class AnalysisResponse(BaseModel):
    id: int
    utterance_id: int

    primary_type: Optional[str] = None
    candidate_types: Optional[str] = None
    classification_reason: Optional[str] = None
    needs_deep_analysis: Optional[bool] = None

    is_correct: Optional[bool] = None
    corrected_text: Optional[str] = None
    error_types: Optional[str] = None

    feedback_ko: Optional[str] = None
    feedback_ja: Optional[str] = None

    vocab_context: Optional[str] = None
    grammar_context: Optional[str] = None
    example_context: Optional[str] = None
    error_context: Optional[str] = None

    model_name: Optional[str] = None
    adapter_name: Optional[str] = None
    confidence: Optional[float] = None

    created_at: datetime

    class Config:
        from_attributes = True


class JudgmentRequest(BaseModel):
    context: Optional[str] = Field(None, example="어제 무엇을 했는지 답하는 상황")
    learner_level: Optional[Literal["N5", "N4"]] = Field(None, example="N5")


class JudgmentEdit(BaseModel):
    start: int
    end: int
    source: str
    replacement: str
    error_type: Optional[str] = None


class JudgmentResponse(BaseModel):
    id: int
    utterance_id: int
    decision: Literal["acceptable", "needs_correction", "insufficient_evidence"]
    corrected_text: str
    edits: List[JudgmentEdit]
    error_types: List[str]
    reason_ko: str
    classification_review_required: bool
    strategy: Literal["d_only"]
    model_name: str
    adapter_name: str
    selection_reason: str
    contract_version: str
    latency_ms: Optional[float] = None
    context: Optional[str] = None
    learner_level: Literal["N5", "N4"]
    created_at: datetime


class JudgmentLatencySummary(BaseModel):
    sample_count: int
    p50: Optional[float] = None
    p95: Optional[float] = None
    max: Optional[float] = None


class JudgmentShadowMonitoring(BaseModel):
    schema_version: Literal["judgment-shadow-monitor-v0.3"]
    enabled: bool
    configuration_valid: bool
    accepting: bool
    worker_running: bool
    worker_active: bool
    queue_capacity: Optional[int] = None
    queue_depth: int
    item_ttl_seconds: Optional[float] = None
    admission_rate_per_second: Optional[float] = None
    admission_burst: Optional[int] = None
    admission_tokens: float
    admission_jitter_tolerance_seconds: float
    scheduled_total: int
    enqueued_total: int
    model_invocation_total: int
    success_total: int
    failure_total: int
    dropped_total: int
    expired_total: int
    shutdown_dropped_total: int
    sampled_out_total: int
    decision_counts: Dict[str, int]
    failure_categories: Dict[str, int]
    retry_used_total: int
    retry_recovered_total: int
    latency_ms: JudgmentLatencySummary
    queue_wait_latency_ms: JudgmentLatencySummary
    persists_results: Literal[False]
    affects_analyze_response: Literal[False]
    contains_request_content: Literal[False]


class JudgmentMonitoringResponse(BaseModel):
    schema_version: Literal["judgment-monitor-v0.2"]
    enabled: bool
    operational_state: Literal["disabled", "ready", "degraded"]
    process_started_at: datetime
    snapshot_at: datetime
    uptime_seconds: float
    request_total: int
    model_invocation_total: int
    success_total: int
    failure_total: int
    rejection_counts: Dict[str, int]
    decision_counts: Dict[str, int]
    failure_categories: Dict[str, int]
    retry_used_total: int
    retry_recovered_total: int
    latency_ms: JudgmentLatencySummary
    last_outcome: Optional[str] = None
    last_event_at: Optional[datetime] = None
    contains_request_content: Literal[False]
    shadow: JudgmentShadowMonitoring


class JudgmentReadinessResponse(BaseModel):
    schema_version: Literal["judgment-readiness-v0.1"]
    ready: bool
    reason: Literal[
        "ready", "disabled", "invalid_configuration", "shutting_down",
        "model_unavailable", "model_alias_missing",
    ]
    enabled: bool
    accepting: bool
    active_requests: int
    max_concurrency: Optional[int] = None
    model_health: bool
    model_alias_present: bool
    contains_request_content: Literal[False]


class EdgeSyncEvent(BaseModel):
    event_id: UUID
    event_type: Literal["session", "utterance", "judgment"]
    payload_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    payload: Dict[str, Any]
    created_at: Optional[datetime] = None


class EdgeSyncRequest(BaseModel):
    node_id: UUID
    events: List[EdgeSyncEvent] = Field(..., min_length=1, max_length=100)


class EdgeSyncEventResult(BaseModel):
    event_id: UUID
    status: Literal["accepted", "duplicate", "rejected"]
    remote_id: Optional[int] = None
    error: Optional[str] = None


class EdgeSyncResponse(BaseModel):
    node_id: UUID
    results: List[EdgeSyncEventResult]

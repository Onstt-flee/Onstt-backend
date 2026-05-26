# schemas.py

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


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
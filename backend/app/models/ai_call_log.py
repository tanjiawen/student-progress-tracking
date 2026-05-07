from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, JSON, Numeric
from sqlmodel import Field, SQLModel


class AITaskType(str, Enum):
    """AI 任务类型枚举."""

    OCR = "ocr"
    GRADING = "grading"
    REPORT = "report"
    EXERCISE = "exercise"
    EMBEDDING = "embedding"


class AICallStatus(str, Enum):
    """AI 调用状态枚举."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class AICallLog(SQLModel, table=True):
    """AI 调用日志表（成本追踪）."""

    __tablename__ = "ai_call_logs"

    id: int | None = Field(default=None, primary_key=True)
    task_type: AITaskType = Field(
        sa_column=Column(SAEnum(AITaskType), nullable=False)
    )
    model: str = Field(max_length=100)
    provider: str = Field(max_length=50)
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float = Field(sa_column=Column(Numeric(10, 6), nullable=False))
    latency_ms: int
    status: AICallStatus = Field(
        sa_column=Column(SAEnum(AICallStatus), nullable=False)
    )
    request_payload: dict = Field(sa_column=Column(JSON, nullable=False))
    response_payload: dict | None = Field(
        default=None, sa_column=Column(JSON)
    )
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, JSON, Numeric
from sqlmodel import Field, Relationship, SQLModel


class ErrorType(str, Enum):
    """错误类型枚举."""

    CORRECT = "correct"
    CONCEPT_ERROR = "concept_error"
    CALCULATION_ERROR = "calculation_error"
    MISREADING = "misreading"
    MISSING_STEP = "missing_step"
    LOGIC_BREAK = "logic_break"
    FORMULA_ERROR = "formula_error"
    NOTATION_ERROR = "notation_error"
    INCOMPLETE = "incomplete"
    UNCLEAR = "unclear"
    UNKNOWN = "unknown"


class GradingResult(SQLModel, table=True):
    """判卷结果表."""

    __tablename__ = "grading_results"

    id: int | None = Field(default=None, primary_key=True)
    submission_id: int = Field(foreign_key="submissions.id", unique=True)
    is_correct: bool
    score: float = Field(sa_column=Column(Numeric(5, 2), nullable=False))
    max_score: float = Field(sa_column=Column(Numeric(5, 2), nullable=False))
    error_type: ErrorType = Field(
        sa_column=Column(SAEnum(ErrorType), nullable=False)
    )
    error_type_detail: str | None = Field(default=None)
    knowledge_point_ids: list | None = Field(
        default=None, sa_column=Column(JSON)
    )
    suggestion: str | None = Field(default=None)
    confidence: float = Field(ge=0.0, le=1.0)
    ai_model: str = Field(max_length=100)
    raw_response: dict | None = Field(default=None, sa_column=Column(JSON))
    reviewed_by: int | None = Field(
        default=None, foreign_key="users.id"
    )
    reviewed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    submission: Submission = Relationship(back_populates="grading_result")

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, JSON, Numeric
from sqlmodel import Field, Relationship, SQLModel


class QuestionType(str, Enum):
    """题目类型枚举."""

    CHOICE = "choice"
    FILL_BLANK = "fill_blank"
    SHORT_ANSWER = "short_answer"
    CALCULATION = "calculation"
    PROOF = "proof"


class QuestionTemplate(SQLModel, table=True):
    """题目模板表（母题库）."""

    __tablename__ = "question_templates"

    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subjects.id")
    knowledge_point_ids: list | None = Field(
        default=None, sa_column=Column(JSON), description="知识点 ID 数组"
    )
    question_type: QuestionType = Field(
        sa_column=Column(SAEnum(QuestionType), nullable=False)
    )
    content: str = Field(description="题干文本")
    content_latex: str | None = Field(default=None)
    options: dict | None = Field(default=None, sa_column=Column(JSON))
    standard_answer: str | None = Field(default=None)
    standard_answer_latex: str | None = Field(default=None)
    scoring_criteria: str | None = Field(
        default=None, description="评分标准文本"
    )
    difficulty: int = Field(default=1, ge=1, le=5)
    source: str | None = Field(default=None, max_length=200)
    vector_id: str | None = Field(
        default=None, max_length=100, description="Qdrant vector ID"
    )
    usage_count: int = Field(default=0)
    created_by: int = Field(foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    exam_questions: ExamQuestion = Relationship(
        back_populates="question_template"
    )
    exercise_questions: ExerciseQuestion = Relationship(
        back_populates="question_template"
    )
    error_book_items: ErrorBookItem = Relationship(
        back_populates="question_template"
    )

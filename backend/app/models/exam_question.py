from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, JSON, Numeric
from sqlmodel import Field, Relationship, SQLModel


class ExamQuestionStatus(str, Enum):
    """试卷题目实例状态枚举."""

    PENDING = "pending"
    VERIFIED = "verified"
    CORRECTED = "corrected"


class QuestionType(str, Enum):
    """题目类型枚举."""

    CHOICE = "choice"
    FILL_BLANK = "fill_blank"
    SHORT_ANSWER = "short_answer"
    CALCULATION = "calculation"
    PROOF = "proof"


class ExamQuestion(SQLModel, table=True):
    """试卷题目实例表（一张试卷上的具体题目）."""

    __tablename__ = "exam_questions"

    id: int | None = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exams.id")
    question_template_id: int | None = Field(
        default=None, foreign_key="question_templates.id"
    )
    sequence_number: int = Field(description="题号")
    question_type: QuestionType = Field(
        sa_column=Column(SAEnum(QuestionType), nullable=False)
    )
    content: str = Field(description="题干文本")
    content_latex: str | None = Field(default=None)
    options: dict | None = Field(default=None, sa_column=Column(JSON))
    score: float = Field(
        sa_column=Column(Numeric(5, 2), nullable=False),
        description="本题满分",
    )
    answer_area: dict | None = Field(
        default=None, sa_column=Column(JSON), description="作答区坐标 bbox"
    )
    ocr_confidence: float | None = Field(default=None)
    status: ExamQuestionStatus = Field(
        default=ExamQuestionStatus.PENDING,
        sa_column=Column(SAEnum(ExamQuestionStatus), nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    exam: Exam = Relationship(back_populates="questions")
    question_template: QuestionTemplate = Relationship(
        back_populates="exam_questions"
    )
    submissions: Submission = Relationship(back_populates="exam_question")
    error_book_items: ErrorBookItem = Relationship(
        back_populates="exam_question"
    )

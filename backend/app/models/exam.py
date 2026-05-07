from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, Numeric
from sqlmodel import Field, Relationship, SQLModel


class ExamStatus(str, Enum):
    """考试状态枚举."""

    DRAFT = "draft"
    PROCESSING = "processing"
    READY = "ready"
    GRADING = "grading"
    GRADED = "graded"
    ARCHIVED = "archived"


class ExamType(str, Enum):
    """考试类型枚举."""

    MIDTERM = "midterm"
    FINAL = "final"
    QUIZ = "quiz"
    PRACTICE = "practice"


class Exam(SQLModel, table=True):
    """考试表."""

    __tablename__ = "exams"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(index=True, max_length=200)
    subject_id: int = Field(foreign_key="subjects.id")
    class_id: int = Field(foreign_key="classes.id")
    exam_type: ExamType = Field(
        sa_column=Column(SAEnum(ExamType), nullable=False)
    )
    total_score: float = Field(
        sa_column=Column(Numeric(5, 2), nullable=False)
    )
    status: ExamStatus = Field(
        default=ExamStatus.DRAFT,
        sa_column=Column(SAEnum(ExamStatus), nullable=False),
    )
    exam_date: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_by: int = Field(foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    archived_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    questions: ExamQuestion = Relationship(back_populates="exam")
    submissions: Submission = Relationship(back_populates="exam")
    error_book_items: ErrorBookItem = Relationship(
        back_populates="exam"
    )
    reports: Report = Relationship(back_populates="exam")

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, JSON
from sqlmodel import Field, Relationship, SQLModel


class GradingStatus(str, Enum):
    """批改状态枚举."""

    PENDING = "pending"
    GRADING = "grading"
    GRADED = "graded"
    MANUAL_REVIEW = "manual_review"


class Submission(SQLModel, table=True):
    """学生作答提交表."""

    __tablename__ = "submissions"

    id: int | None = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exams.id")
    student_id: int = Field(foreign_key="students.id")
    exam_question_id: int = Field(foreign_key="exam_questions.id")
    answer_text: str | None = Field(default=None)
    answer_latex: str | None = Field(default=None)
    answer_image_urls: list | None = Field(
        default=None, sa_column=Column(JSON), description="作答图片 URL 数组"
    )
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    grading_status: GradingStatus = Field(
        default=GradingStatus.PENDING,
        sa_column=Column(SAEnum(GradingStatus), nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    exam: Exam = Relationship(back_populates="submissions")
    exam_question: ExamQuestion = Relationship(back_populates="submissions")
    grading_result: GradingResult = Relationship(
        back_populates="submission"
    )

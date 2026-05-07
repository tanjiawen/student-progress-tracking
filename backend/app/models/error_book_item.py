from __future__ import annotations

"""错题本条目表."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Numeric
from sqlmodel import Field, Relationship, SQLModel


class ErrorBookItem(SQLModel, table=True):
    """错题本条目表.

    记录学生的错题信息，支持间隔重复复习调度。
    """

    __tablename__ = "error_book_items"

    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id", nullable=False)
    exam_id: int | None = Field(default=None, foreign_key="exams.id", nullable=True)
    exam_question_id: int | None = Field(
        default=None, foreign_key="exam_questions.id", nullable=True
    )
    question_template_id: int | None = Field(
        default=None, foreign_key="question_templates.id", nullable=True
    )

    error_type: str = Field(nullable=False)
    error_count: int = Field(default=1, nullable=False)

    last_error_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    is_resolved: bool = Field(default=False, nullable=False)
    resolved_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    review_count: int = Field(default=0, nullable=False)
    next_review_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # SM-2 间隔重复参数
    sm2_easiness_factor: float = Field(
        default=2.5,
        sa_column=Column(Numeric(4, 2), nullable=False),
    )
    sm2_interval_days: int = Field(default=0, nullable=False)
    sm2_repetition_count: int = Field(default=0, nullable=False)

    notes: str | None = Field(default=None, nullable=True)

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    student: Student = Relationship(back_populates="error_book_items")
    exam: Exam = Relationship(back_populates="error_book_items")
    exam_question: ExamQuestion = Relationship(back_populates="error_book_items")
    question_template: QuestionTemplate = Relationship(
        back_populates="error_book_items"
    )

from __future__ import annotations

"""练习题目表."""

from datetime import datetime

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field, Relationship, SQLModel


class ExerciseQuestion(SQLModel, table=True):
    """练习题目表.

    存储练习卷中的具体题目内容、学生作答、批改结果及 AI 解析。
    """

    __tablename__ = "exercise_questions"

    id: int | None = Field(default=None, primary_key=True)
    exercise_id: int = Field(foreign_key="exercises.id", nullable=False)
    question_template_id: int | None = Field(
        default=None, foreign_key="question_templates.id", nullable=True
    )

    sequence_number: int = Field(nullable=False)
    content: str = Field(nullable=False)
    content_latex: str | None = Field(default=None, nullable=True)

    options: dict | list | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )

    standard_answer: str = Field(nullable=False)
    student_answer: str | None = Field(default=None, nullable=True)
    is_correct: bool | None = Field(default=None, nullable=True)
    score: float | None = Field(default=None, nullable=True)
    max_score: float = Field(nullable=False)
    ai_explanation: str | None = Field(default=None, nullable=True)

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    exercise: Exercise = Relationship(back_populates="questions")
    question_template: QuestionTemplate = Relationship(
        back_populates="exercise_questions"
    )

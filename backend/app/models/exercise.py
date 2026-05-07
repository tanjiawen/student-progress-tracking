from __future__ import annotations

"""练习卷表."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, JSON
from sqlmodel import Field, Relationship, SQLModel


class ExerciseStatus(str, Enum):
    """练习卷状态枚举."""

    draft = "draft"
    assigned = "assigned"
    completed = "completed"


class Exercise(SQLModel, table=True):
    """练习卷表.

    存储为学生生成的个性化练习卷信息，包括目标知识点、目标错题类型、
    难度范围等元数据，以及状态与时间安排。
    """

    __tablename__ = "exercises"

    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id", nullable=False)

    title: str = Field(nullable=False)

    target_knowledge_point_ids: list[int] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    target_error_types: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    difficulty_range: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )

    status: ExerciseStatus = Field(
        default=ExerciseStatus.draft,
        sa_column=Column(SAEnum(ExerciseStatus), nullable=False),
    )

    assigned_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    due_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    student: Student = Relationship(back_populates="exercises")
    questions: ExerciseQuestion = Relationship(back_populates="exercise")

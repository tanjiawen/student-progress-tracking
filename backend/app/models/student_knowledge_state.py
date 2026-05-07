from __future__ import annotations

"""学生知识点掌握状态表（BKT + ELO 核心数据）."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, Numeric, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class MasteryStatus(str, Enum):
    """掌握状态枚举."""

    mastered = "mastered"
    normal = "normal"
    weak = "weak"


class StudentKnowledgeState(SQLModel, table=True):
    """学生知识点掌握状态表.

    存储 BKT (Bayesian Knowledge Tracing) 与 ELO 评级相关的核心数据，
    用于追踪每个学生在每个知识点上的掌握程度。
    """

    __tablename__ = "student_knowledge_states"
    __table_args__ = (UniqueConstraint("student_id", "knowledge_point_id"),)

    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id", nullable=False)
    knowledge_point_id: int = Field(foreign_key="knowledge_points.id", nullable=False)

    mastery_probability: float = Field(
        default=0.5,
        sa_column=Column(Numeric(4, 3), nullable=False),
        ge=0.0,
        le=1.0,
    )
    total_attempts: int = Field(default=0, nullable=False)
    correct_count: int = Field(default=0, nullable=False)
    consecutive_correct: int = Field(default=0, nullable=False)
    last_error_type: str | None = Field(default=None, nullable=True)

    last_graded_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    decayed_mastery: float | None = Field(
        default=None,
        sa_column=Column(Numeric(4, 3), nullable=True),
    )

    status: MasteryStatus = Field(
        default=MasteryStatus.normal,
        sa_column=Column(SAEnum(MasteryStatus), nullable=False),
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
    student: Student = Relationship(back_populates="knowledge_states")
    knowledge_point: KnowledgePoint = Relationship(back_populates="student_states")

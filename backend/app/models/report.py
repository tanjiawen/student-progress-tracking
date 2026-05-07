from __future__ import annotations

"""诊断报告表."""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Column, DateTime, Enum as SAEnum, JSON
from sqlmodel import Field, Relationship, SQLModel


class ReportType(str, Enum):
    """报告类型枚举."""

    single_exam = "single_exam"
    weekly = "weekly"
    monthly = "monthly"


class GeneratedBy(str, Enum):
    """报告生成方式枚举."""

    ai = "ai"
    manual = "manual"


class Report(SQLModel, table=True):
    """诊断报告表.

    存储学生诊断报告，包括单次考试、周报告、月报告等多种类型。
    报告数据以 JSON 形式存储灵活的结构化内容。
    """

    __tablename__ = "reports"

    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id", nullable=False)
    exam_id: int | None = Field(default=None, foreign_key="exams.id", nullable=True)

    report_type: ReportType = Field(
        sa_column=Column(SAEnum(ReportType), nullable=False),
    )
    title: str = Field(nullable=False)
    overall_comment: str | None = Field(default=None, nullable=True)

    total_score: float | None = Field(default=None, nullable=True)
    max_score: float | None = Field(default=None, nullable=True)
    rank: int | None = Field(default=None, nullable=True)

    weak_points: list[dict] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    error_distribution: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    trend_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    radar_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    recommendations: list[dict] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )

    generated_by: GeneratedBy = Field(
        sa_column=Column(SAEnum(GeneratedBy), nullable=False),
    )
    ai_model: str | None = Field(default=None, nullable=True)
    usage: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
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
    student: Student = Relationship(back_populates="reports")
    exam: Exam = Relationship(back_populates="reports")

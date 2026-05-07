from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExerciseCreate(BaseModel):
    """创建练习卷请求."""

    student_id: int = Field(..., description="目标学生 ID")
    title: str = Field(..., min_length=1, max_length=200)
    target_knowledge_point_ids: list[int] = Field(default_factory=list)
    target_error_types: list[str] = Field(default_factory=list)
    difficulty_range: tuple[int, int] = Field(default=(1, 5))
    question_count: int = Field(default=10, ge=1, le=50)
    due_at: datetime | None = None


class ExerciseRead(BaseModel):
    """练习卷响应."""

    id: int
    student_id: int
    title: str
    target_knowledge_point_ids: list[int]
    target_error_types: list[str]
    difficulty_range: dict[str, Any]
    status: str
    assigned_at: datetime | None
    due_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExerciseQuestionRead(BaseModel):
    """练习题目响应."""

    id: int
    exercise_id: int
    sequence_number: int
    content: str
    content_latex: str | None
    options: dict | list | None
    max_score: float
    ai_explanation: str | None

    model_config = ConfigDict(from_attributes=True)


class ExerciseQuestionSubmit(BaseModel):
    """提交作答请求."""

    answer: str = Field(..., description="学生作答内容")


class ExerciseResultRead(BaseModel):
    """练习结果响应."""

    exercise_id: int
    student_id: int
    total_score: float
    max_score: float
    correct_count: int
    question_count: int
    questions: list[dict[str, Any]]
    ai_summary: str | None


class DailyPlanRead(BaseModel):
    """每日练习计划响应."""

    student_id: int
    date: str
    exercise_id: int | None
    target_knowledge_points: list[int]
    target_error_types: list[str]
    question_count: int
    reason: str

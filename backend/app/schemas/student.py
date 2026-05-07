from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StudentBase(BaseModel):
    user_id: int
    student_number: str = Field(..., max_length=50)
    class_id: int | None = None
    enrollment_year: int | None = None


class StudentCreate(StudentBase):
    pass


class StudentRead(StudentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
class StudentDetail(StudentRead):
    name: str | None = None
    student_no: str | None = None
    user_name: str | None = None
    class_name: str | None = None
    recent_exams: list[dict[str, Any]] = []


class KnowledgeStateItem(BaseModel):
    knowledge_point_id: int
    knowledge_point_name: str
    mastery_probability: float
    status: str
    total_attempts: int = 0
    correct_count: int = 0


class StudentKnowledgeStateGrouped(BaseModel):
    subject_id: int
    subject_name: str
    items: list[KnowledgeStateItem] = []

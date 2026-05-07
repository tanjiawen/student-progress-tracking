from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClassBase(BaseModel):
    name: str = Field(..., max_length=100)
    grade: str = Field(..., max_length=20)
    subject_id: int | None = None
    teacher_id: int
    academic_year: str = Field(..., max_length=20)
    semester: str = Field(..., max_length=20)


class ClassCreate(ClassBase):
    pass


class ClassRead(ClassBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
class ClassDetail(ClassRead):
    students: list[dict[str, Any]] = []
    student_count: int = 0

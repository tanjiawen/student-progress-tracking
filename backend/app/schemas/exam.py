from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExamBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    subject: str = Field(..., max_length=50)
    grade_level: str | None = Field(default=None, max_length=50)
    total_score: float = Field(default=100.0, ge=0)
    duration_minutes: int | None = Field(default=None, ge=1)
    exam_date: datetime | None = None
    status: str = "draft"  # draft, published, closed


class ExamCreate(ExamBase):
    pass


class ExamRead(ExamBase):
    id: int
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
class ExamUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    subject: str | None = Field(default=None, max_length=50)
    grade_level: str | None = Field(default=None, max_length=50)
    total_score: float | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, ge=1)
    exam_date: datetime | None = None
    status: str | None = None


class ExamList(BaseModel):
    id: int
    title: str
    subject: str
    grade_level: str | None
    exam_date: datetime | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

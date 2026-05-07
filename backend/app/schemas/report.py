from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    report_type: str = Field(..., max_length=50)  # student, class, exam
    student_id: int | None = None
    exam_id: int | None = None
    class_id: int | None = None
    content: dict  # JSON structured report data
    summary: str | None = None


class ReportCreate(ReportBase):
    pass


class ReportRead(ReportBase):
    id: int
    generated_by: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

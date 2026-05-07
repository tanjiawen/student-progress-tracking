from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SubmissionBase(BaseModel):
    exam_id: int
    student_id: int
    answer_sheet_image_url: str | None = None
    answers: dict | None = None  # JSON: {question_id: student_answer}
    status: str = "submitted"  # submitted, grading, graded


class SubmissionCreate(SubmissionBase):
    pass


class SubmissionRead(SubmissionBase):
    id: int
    total_score: float | None = None
    graded_by: int | None = None
    graded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
class GradingResultRead(BaseModel):
    id: int
    submission_id: int
    question_id: int
    score: float
    feedback: str | None = None
    graded_by_ai: bool = False
    confidence: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

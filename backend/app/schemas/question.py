from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuestionBase(BaseModel):
    exam_id: int
    question_number: str = Field(..., max_length=20)
    question_type: str = Field(..., max_length=20)  # single_choice, multi_choice, fill_blank, short_answer, essay
    content: str
    options: dict | None = None  # JSON for choices
    answer: str | None = None
    explanation: str | None = None
    score: float = Field(default=0.0, ge=0)
    difficulty: str | None = Field(default=None, max_length=20)  # easy, medium, hard
    knowledge_point: str | None = None
    order_index: int = 0


class QuestionCreate(QuestionBase):
    pass


class QuestionRead(QuestionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
class QuestionUpdate(BaseModel):
    question_number: str | None = Field(default=None, max_length=20)
    question_type: str | None = Field(default=None, max_length=20)
    content: str | None = None
    options: dict | None = None
    answer: str | None = None
    explanation: str | None = None
    score: float | None = Field(default=None, ge=0)
    difficulty: str | None = Field(default=None, max_length=20)
    knowledge_point: str | None = None
    order_index: int | None = None

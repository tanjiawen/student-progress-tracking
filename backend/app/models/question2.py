from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class QuestionTemplate(SQLModel, table=True):
    __tablename__ = "question_templates"

    id: int | None = Field(default=None, primary_key=True)
    subject: str = Field(default="数学")
    question_type: str = Field(default="choice")
    content: str = Field(default="")
    standard_answer: str = Field(default="")
    score: float = Field(default=0.0)
    knowledge_points: list[str] | None = Field(default=None, sa_column=Column(JSON))
    difficulty: float = Field(default=0.5)
    created_at: datetime = Field(default_factory=datetime.utcnow)

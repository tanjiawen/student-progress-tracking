"""Subject model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field, Relationship, SQLModel


class Subject(SQLModel, table=True):
    """学科表."""

    __tablename__ = "subjects"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    code: str = Field(index=True, unique=True, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    grade_levels: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    sort_order: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    knowledge_points: KnowledgePoint = Relationship(back_populates="subject")
    classes: Class = Relationship(back_populates="subject")

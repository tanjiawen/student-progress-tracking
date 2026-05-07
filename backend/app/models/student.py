"""Student model (extends user info)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel


class Student(SQLModel, table=True):
    """学生表（扩展用户信息）."""

    __tablename__ = "students"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)
    student_number: str = Field(index=True, unique=True, max_length=50)
    class_id: int | None = Field(default=None, foreign_key="classes.id")
    enrollment_year: int | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    user: User = Relationship(back_populates="student_profile")
    class_: Class = Relationship(back_populates="students")
    class_students: ClassStudent = Relationship(back_populates="student")
    exercises: Exercise = Relationship(back_populates="student")
    knowledge_states: StudentKnowledgeState = Relationship(back_populates="student")
    error_book_items: ErrorBookItem = Relationship(back_populates="student")
    reports: Report = Relationship(back_populates="student")

"""Class model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel


class Class(SQLModel, table=True):
    """班级表."""

    __tablename__ = "classes"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    grade: str = Field(max_length=20)
    subject_id: int | None = Field(default=None, foreign_key="subjects.id")
    teacher_id: int = Field(foreign_key="users.id")
    academic_year: str = Field(max_length=20)
    semester: str = Field(max_length=20)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    teacher: User = Relationship(back_populates="taught_classes")
    subject: Subject = Relationship(back_populates="classes")
    class_students: ClassStudent = Relationship(back_populates="class_")
    students: Student = Relationship(back_populates="class_")

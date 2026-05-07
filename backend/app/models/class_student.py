"""Class-Student association model (many-to-many)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class ClassStudent(SQLModel, table=True):
    """班级学生关联表（多对多）.

    联合唯一约束：(class_id, student_id)
    """

    __tablename__ = "class_students"

    id: int | None = Field(default=None, primary_key=True)
    class_id: int = Field(foreign_key="classes.id")
    student_id: int = Field(foreign_key="students.id")
    joined_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    class_: Class = Relationship(back_populates="class_students")
    student: Student = Relationship(back_populates="class_students")

    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uix_class_student"),
    )

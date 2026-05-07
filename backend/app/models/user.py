"""User model with RBAC support."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel


class UserRole(str, Enum):
    """User roles for RBAC."""

    admin = "admin"
    teacher = "teacher"
    student = "student"
    parent = "parent"


class User(SQLModel, table=True):
    """用户表，支持 RBAC 四角色：admin, teacher, student, parent.

    student/parent/teacher 角色的额外信息通过 user_id 外键关联到各自的扩展表，
    不在本表内冗余存储。
    """

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=50)
    email: str = Field(index=True, unique=True, max_length=100)
    hashed_password: str = Field(max_length=255)
    real_name: str | None = Field(default=None, max_length=50)
    role: UserRole = Field(sa_column=Column(SAEnum(UserRole), nullable=False))
    phone: str | None = Field(default=None, max_length=20)
    avatar_url: str | None = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    student_profile: Student = Relationship(back_populates="user")
    taught_classes: Class = Relationship(back_populates="teacher")

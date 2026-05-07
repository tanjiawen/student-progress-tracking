"""Notification model."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field, SQLModel


class NotificationType(str, Enum):
    """通知类型枚举."""

    SYSTEM = "system"
    EXAM = "exam"
    EXERCISE = "exercise"
    ERROR_BOOK = "error_book"


class Notification(SQLModel, table=True):
    """通知表."""

    __tablename__ = "notifications"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    title: str = Field(max_length=200)
    content: str
    notification_type: str = Field(default=NotificationType.SYSTEM.value, max_length=50)
    data: dict | None = Field(default=None, sa_column=Column(JSON))
    is_read: bool = Field(default=False)
    read_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

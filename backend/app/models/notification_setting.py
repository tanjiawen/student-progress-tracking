"""Notification setting model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class NotificationSetting(SQLModel, table=True):
    """用户通知设置表."""

    __tablename__ = "notification_settings"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    enable_web_socket: bool = Field(default=True)
    enable_webhook: bool = Field(default=False)
    webhook_url: str | None = Field(default=None, max_length=500)
    webhook_type: str | None = Field(default=None, max_length=20)  # feishu / dingtalk
    notify_system: bool = Field(default=True)
    notify_exam: bool = Field(default=True)
    notify_exercise: bool = Field(default=True)
    notify_error_book: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

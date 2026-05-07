"""Notification schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: int
    user_id: int
    title: str
    content: str
    notification_type: str
    data: dict | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationSettingsRead(BaseModel):
    user_id: int
    enable_web_socket: bool
    enable_webhook: bool
    webhook_url: str | None
    webhook_type: str | None
    notify_system: bool
    notify_exam: bool
    notify_exercise: bool
    notify_error_book: bool


class NotificationSettingsUpdate(BaseModel):
    enable_web_socket: bool | None = None
    enable_webhook: bool | None = None
    webhook_url: str | None = None
    webhook_type: str | None = None
    notify_system: bool | None = None
    notify_exam: bool | None = None
    notify_exercise: bool | None = None
    notify_error_book: bool | None = None

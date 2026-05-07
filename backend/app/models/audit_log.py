"""审计日志模型."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    """审计日志表，记录敏感操作与异常请求."""

    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id")
    action: str = Field(max_length=50)  # create/update/delete/grade_review/login/logout
    resource_type: str = Field(max_length=50)  # exam/student/grading_result/user
    resource_id: int | None = Field(default=None)
    ip_address: str = Field(max_length=45)
    user_agent: str = Field(default="", max_length=255)
    request_method: str = Field(default="", max_length=10)
    request_path: str = Field(default="", max_length=500)
    request_body: dict | None = Field(default=None, sa_column=Column(JSON))
    response_status: int | None = Field(default=None)
    before_value: dict | None = Field(default=None, sa_column=Column(JSON))
    after_value: dict | None = Field(default=None, sa_column=Column(JSON))
    duration_ms: int | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

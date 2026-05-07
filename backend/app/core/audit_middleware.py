"""审计日志中间件 —— 异步记录敏感操作与异常请求."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import async_session
from app.core.security import decode_token
from app.models.audit_log import AuditLog

# 需要脱敏的字段名（大小写不敏感）
_SENSITIVE_FIELDS = {
    "password",
    "hashed_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "credit_card",
    "id_card",
    "phone",
}


def _mask_sensitive_data(data: Any) -> Any:
    """递归脱敏敏感字段."""
    if isinstance(data, dict):
        return {
            k: "***" if k.lower() in _SENSITIVE_FIELDS else _mask_sensitive_data(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_mask_sensitive_data(item) for item in data]
    return data


class AuditMiddleware(BaseHTTPMiddleware):
    """审计日志中间件.

    - 记录所有 DELETE/PUT/判卷相关 POST 的请求与响应信息
    - 记录状态码 >= 400 的异常请求
    - 敏感字段自动脱敏
    - 使用 asyncio.create_task 异步写入数据库，避免阻塞主请求
    """

    SENSITIVE_METHODS = {"DELETE", "PUT", "PATCH"}
    SENSITIVE_PATH_PATTERNS = {"grade", "grading", "review", "audit"}

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()

        # 尝试读取并脱敏 JSON 请求体（Starlette 会缓存 body，不影响后续路由）
        body: dict | None = None
        if request.method in self.SENSITIVE_METHODS or request.method == "POST":
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body_bytes = await request.body()
                    if body_bytes:
                        body = _mask_sensitive_data(json.loads(body_bytes))
                except Exception:
                    body = None

        # 从 Authorization Header 解析 user_id（避免在中间件中走完整的 Depends 链）
        user_id: int | None = None
        try:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                payload = decode_token(auth_header[7:])
                if payload and payload.get("sub"):
                    user_id = int(payload["sub"])
        except Exception:
            user_id = None

        # 执行实际请求
        response = await call_next(request)

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # 判断是否敏感操作
        is_sensitive = self._is_sensitive_request(request, response)

        if is_sensitive:
            asyncio.create_task(
                self._save_audit_log(
                    user_id=user_id,
                    action=request.method.lower(),
                    resource_type=self._infer_resource_type(request.url.path),
                    ip_address=request.client.host if request.client else "",
                    user_agent=request.headers.get("user-agent", ""),
                    request_method=request.method,
                    request_path=str(request.url.path),
                    request_body=body,
                    response_status=response.status_code,
                    duration_ms=duration_ms,
                )
            )

        return response

    def _is_sensitive_request(self, request: Request, response) -> bool:
        """判断是否为需要记录的敏感请求."""
        if request.method in self.SENSITIVE_METHODS:
            return True
        if request.method == "POST" and any(
            pat in request.url.path for pat in self.SENSITIVE_PATH_PATTERNS
        ):
            return True
        if response.status_code >= 400:
            return True
        return False

    @staticmethod
    def _infer_resource_type(path: str) -> str:
        segments = [s for s in path.split("/") if s]
        for segment in segments:
            if segment in {"exams", "students", "classes", "users", "submissions", "grading"}:
                return segment
        return "unknown"

    @staticmethod
    async def _save_audit_log(**kwargs: Any) -> None:
        """异步写入审计日志，失败时不影响主请求."""
        try:
            async with async_session() as session:
                log = AuditLog(**kwargs)
                session.add(log)
                await session.commit()
        except Exception:
            # 审计日志写入失败绝不应影响主业务
            pass

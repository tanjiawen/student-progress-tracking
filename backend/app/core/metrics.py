"""Prometheus metrics for production monitoring."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# HTTP 指标
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# AI 调用指标
AI_CALLS_TOTAL = Counter(
    "ai_calls_total",
    "Total AI API calls",
    ["model", "task_type"],
)

AI_TOKENS_TOTAL = Counter(
    "ai_tokens_total",
    "Total AI tokens consumed",
    ["model", "token_type"],  # token_type: prompt / completion
)

AI_REQUEST_DURATION_SECONDS = Histogram(
    "ai_request_duration_seconds",
    "AI API request duration in seconds",
    ["model", "task_type"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

# 业务指标
GRADING_ACCURACY = Gauge(
    "grading_accuracy",
    "Current grading accuracy ratio (0-1)",
    ["subject"],
)

GRADING_TOTAL = Counter(
    "grading_total",
    "Total grading operations",
    ["status"],  # status: correct / incorrect / partial
)

OCR_REQUEST_DURATION_SECONDS = Histogram(
    "ocr_request_duration_seconds",
    "OCR processing duration in seconds",
    ["engine"],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)

ACTIVE_USERS = Gauge(
    "active_users",
    "Number of active users in the last 5 minutes",
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware to collect Prometheus metrics."""

    async def dispatch(self, request: Request, call_next) -> Response:
        method = request.method
        # 使用路由模板而非实际路径，避免路径参数爆炸
        route = request.scope.get("route")
        path = route.path if route else request.url.path

        # 跳过指标端点本身，避免递归
        if path == "/metrics":
            return await call_next(request)

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception:
            status_code = "500"
            raise
        finally:
            duration = time.perf_counter() - start_time
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=path).observe(duration)
            HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=path, status_code=status_code).inc()

        return response


@contextmanager
def ai_call_timer(model: str, task_type: str) -> Generator[None, None, None]:
    """Context manager to time AI calls and record metrics."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        AI_REQUEST_DURATION_SECONDS.labels(model=model, task_type=task_type).observe(duration)
        AI_CALLS_TOTAL.labels(model=model, task_type=task_type).inc()


def record_ai_tokens(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Record AI token consumption."""
    AI_TOKENS_TOTAL.labels(model=model, token_type="prompt").inc(prompt_tokens)
    AI_TOKENS_TOTAL.labels(model=model, token_type="completion").inc(completion_tokens)


def set_grading_accuracy(subject: str, accuracy: float) -> None:
    """Set grading accuracy gauge."""
    GRADING_ACCURACY.labels(subject=subject).set(accuracy)


def increment_grading(status: str) -> None:
    """Increment grading counter."""
    GRADING_TOTAL.labels(status=status).inc()


@contextmanager
def ocr_timer(engine: str) -> Generator[None, None, None]:
    """Context manager to time OCR operations."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        OCR_REQUEST_DURATION_SECONDS.labels(engine=engine).observe(duration)


def metrics_endpoint() -> Response:
    """Return Prometheus metrics in the expected format."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

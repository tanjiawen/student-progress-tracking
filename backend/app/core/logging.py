"""Structured logging with JSON output and trace ID correlation."""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Trace ID context variable
TRACE_ID: ContextVar[str] = ContextVar("trace_id", default="")

LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def get_trace_id() -> str:
    """Get current trace ID or generate a new one."""
    tid = TRACE_ID.get("")
    if not tid:
        tid = str(uuid.uuid4())
        TRACE_ID.set(tid)
    return tid


def _add_trace_id(logger, method_name, event_dict):
    """structlog processor to inject trace_id."""
    event_dict["trace_id"] = get_trace_id()
    return event_dict


def _add_environment(logger, method_name, event_dict):
    """structlog processor to inject environment info."""
    event_dict["environment"] = "production"
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structured JSON logging for production."""
    # Standard library logging setup
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Rotating file handlers by level
    info_handler = RotatingFileHandler(
        LOG_DIR / "app_info.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    info_handler.setLevel(logging.INFO)
    info_handler.addFilter(lambda record: record.levelno < logging.WARNING)

    warn_handler = RotatingFileHandler(
        LOG_DIR / "app_warn.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    warn_handler.setLevel(logging.WARNING)
    warn_handler.addFilter(lambda record: record.levelno < logging.ERROR)

    error_handler = RotatingFileHandler(
        LOG_DIR / "app_error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)

    # Stdout handler (Docker best practice)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Root logger configuration
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[console_handler, info_handler, warn_handler, error_handler],
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _add_trace_id,
            _add_environment,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Middleware to extract or generate trace ID for each request."""

    async def dispatch(self, request: Request, call_next):
        # Extract trace ID from header or generate new one
        trace_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        TRACE_ID.set(trace_id)

        # Add trace ID to response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = trace_id
        return response

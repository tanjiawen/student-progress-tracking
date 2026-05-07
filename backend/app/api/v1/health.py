"""Health check endpoints for production monitoring."""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import engine
from app.core.redis_client import redis_client
from app.core.config import settings

router = APIRouter(tags=["Health"])


async def _check_db() -> dict:
    """Check PostgreSQL connectivity."""
    try:
        async with engine.connect() as conn:
            start = time.perf_counter()
            await conn.execute(text("SELECT 1"))
            latency = round((time.perf_counter() - start) * 1000, 2)
            return {"status": "ok", "latency_ms": latency}
    except SQLAlchemyError as e:
        return {"status": "error", "detail": str(e)}


async def _check_redis() -> dict:
    """Check Redis connectivity."""
    try:
        start = time.perf_counter()
        await redis_client.ping()
        latency = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


async def _check_qdrant() -> dict:
    """Check Qdrant connectivity."""
    try:
        import httpx
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.QDRANT_URL}/healthz")
            latency = round((time.perf_counter() - start) * 1000, 2)
            if response.status_code == 200:
                return {"status": "ok", "latency_ms": latency}
            return {"status": "error", "detail": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


async def _check_minio() -> dict:
    """Check MinIO connectivity."""
    try:
        from minio import Minio
        start = time.perf_counter()
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        client.list_buckets()
        latency = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


async def _check_deepseek_gateway() -> dict:
    """Check DeepSeek Gateway connectivity."""
    try:
        import httpx
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.DEEPSEEK_GATEWAY_URL}/healthz")
            latency = round((time.perf_counter() - start) * 1000, 2)
            if response.status_code == 200:
                return {"status": "ok", "latency_ms": latency}
            return {"status": "error", "detail": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict:
    """Liveness probe: check core dependencies (DB + Redis)."""
    db_result, redis_result = await asyncio.gather(
        _check_db(), _check_redis(), return_exceptions=True
    )

    all_ok = (
        isinstance(db_result, dict) and db_result.get("status") == "ok"
        and isinstance(redis_result, dict) and redis_result.get("status") == "ok"
    )

    return {
        "status": "ok" if all_ok else "degraded",
        "version": "0.0.1",
        "environment": settings.APP_ENV,
        "checks": {
            "database": db_result if isinstance(db_result, dict) else {"status": "error", "detail": str(db_result)},
            "redis": redis_result if isinstance(redis_result, dict) else {"status": "error", "detail": str(redis_result)},
        },
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check() -> dict:
    """Readiness probe: check all external dependencies are ready.
    
    In development mode, Qdrant and MinIO are optional and do not block readiness.
    """
    results = await asyncio.gather(
        _check_db(),
        _check_redis(),
        _check_qdrant(),
        _check_minio(),
        _check_deepseek_gateway(),
        return_exceptions=True,
    )

    labels = ["database", "redis", "qdrant", "minio", "deepseek_gateway"]
    # In development, Qdrant and MinIO are optional
    optional_in_dev = {"qdrant", "minio"}
    is_dev = settings.APP_ENV == "development"

    checks = {}
    all_ok = True

    for label, result in zip(labels, results):
        if isinstance(result, dict) and result.get("status") == "ok":
            checks[label] = result
        elif is_dev and label in optional_in_dev:
            # Mark optional services as skipped in development
            if isinstance(result, dict):
                checks[label] = {**result, "status": "skipped"}
            else:
                checks[label] = {"status": "skipped", "detail": str(result)}
        else:
            all_ok = False
            checks[label] = (
                result if isinstance(result, dict) else {"status": "error", "detail": str(result)}
            )

    status_code = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if all_ok else "not_ready",
        "checks": checks,
    }

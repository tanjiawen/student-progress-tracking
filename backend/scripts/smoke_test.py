#!/usr/bin/env python3
"""Smoke test script for student-progress-tracking."""

from __future__ import annotations

import asyncio
import sys

import httpx


def print_result(name: str, ok: bool, detail: str = "") -> None:
    icon = "✅" if ok else "❌"
    print(f"{icon} {name}" + (f" — {detail}" if detail else ""))


async def check_database() -> bool:
    try:
        from app.core.config import settings
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        engine = create_async_engine(settings.DATABASE_URL, future=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception as e:
        print_result("Database", False, str(e))
        return False


async def check_redis() -> bool:
    try:
        from app.core.config import settings
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.close()
        return True
    except Exception as e:
        print_result("Redis", False, str(e))
        return False


async def check_qdrant() -> bool:
    try:
        from app.core.config import settings
        from qdrant_client import QdrantClient

        client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
        client.get_collections()
        return True
    except Exception as e:
        print_result("Qdrant", False, str(e))
        return False


async def check_minio() -> bool:
    try:
        from app.services.storage_service import storage_service

        storage_service.client.list_buckets()
        return True
    except Exception as e:
        print_result("MinIO", False, str(e))
        return False


async def check_deepseek_api() -> bool:
    try:
        from app.core.config import settings
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.DEEPSEEK_BASE_URL}/models",
                headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY or ''}"},
            )
            return response.status_code in (200, 401)
    except Exception as e:
        print_result("DeepSeek API", False, str(e))
        return False


async def check_api_endpoints() -> bool:
    ok = True
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Health check
            response = await client.get("http://localhost:8000/health")
            if response.status_code != 200:
                print_result("API /health", False, f"status={response.status_code}")
                ok = False
            else:
                print_result("API /health", True)

            # Login
            response = await client.post(
                "http://localhost:8000/api/v1/auth/login",
                data={"username": "admin", "password": "admin"},
            )
            if response.status_code != 200:
                print_result("API /auth/login", False, f"status={response.status_code}")
                ok = False
            else:
                print_result("API /auth/login", True)
    except Exception as e:
        print_result("API endpoints", False, str(e))
        ok = False
    return ok


async def check_celery() -> bool:
    try:
        from celery_worker import celery_app

        inspector = celery_app.control.inspect()
        stats = inspector.stats()
        if stats:
            print_result("Celery Worker", True)
            return True
        else:
            print_result("Celery Worker", False, "No workers found")
            return False
    except Exception as e:
        print_result("Celery Worker", False, str(e))
        return False


async def main() -> int:
    print("=" * 50)
    print("🚀 Student Progress Tracking Smoke Test")
    print("=" * 50)

    results = []

    print("\n📡 External Services")
    results.append(("Database", await check_database()))
    results.append(("Redis", await check_redis()))
    results.append(("Qdrant", await check_qdrant()))
    results.append(("MinIO", await check_minio()))
    results.append(("DeepSeek API", await check_deepseek_api()))

    print("\n🔌 API Endpoints")
    results.append(("API Endpoints", await check_api_endpoints()))

    print("\n⚙️  Celery")
    results.append(("Celery Worker", await check_celery()))

    print("\n" + "=" * 50)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"Results: {passed}/{total} passed")
    print("=" * 50)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

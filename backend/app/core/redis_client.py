"""Async Redis client with fakeredis fallback for development."""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def _init_redis_client():
    """Synchronously test Redis connection and return appropriate client."""
    import redis.asyncio as redis

    client = redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )

    # Test connection synchronously (module import has no running loop yet)
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(client.ping())
        loop.close()
        logger.info("Using real Redis: %s", settings.REDIS_URL)
        return client
    except Exception:
        try:
            loop.close()
        except Exception:
            pass

        # Fallback to fakeredis
        try:
            import fakeredis.aioredis as fake_redis

            fake_client = fake_redis.FakeRedis(decode_responses=True)
            logger.warning(
                "Redis unavailable at %s, using fakeredis (in-memory). "
                "Token blacklist will not persist across restarts.",
                settings.REDIS_URL,
            )
            return fake_client
        except Exception:
            logger.error("fakeredis not installed, using dummy Redis client")

            class _DummyRedis:
                async def get(self, key): return None
                async def setex(self, key, seconds, value): return True
                async def set(self, key, value, ex=None): return True
                async def delete(self, *keys): return 1
                async def exists(self, *keys): return 0
                async def sadd(self, key, *members): return 1
                async def smembers(self, key): return set()
                async def srem(self, key, *members): return 1
                async def ping(self): return True
                async def scan_iter(self, match=None, count=None):
                    return iter([])

            return _DummyRedis()


redis_client = _init_redis_client()

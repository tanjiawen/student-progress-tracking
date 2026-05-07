"""基于 Redis 的令牌桶限流器."""

from __future__ import annotations

import time

from fastapi import Depends, Request

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.exceptions import RateLimitException
from app.core.redis_client import redis_client
from app.schemas.user import UserRead

# Lua 脚本实现原子性令牌桶
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local burst = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call('HMGET', key, 'tokens', 'last_time')
local tokens = tonumber(bucket[1])
local last_time = tonumber(bucket[2])

if tokens == nil then
    tokens = burst
    last_time = now
end

local delta = math.max(0, now - last_time)
tokens = math.min(burst, tokens + delta * rate)

local allowed = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
end

redis.call('HMSET', key, 'tokens', tokens, 'last_time', now)
redis.call('EXPIRE', key, math.ceil(burst / rate) + 60)
return allowed
"""


class RateLimiter:
    """基于 Redis 的令牌桶限流器."""

    def __init__(self, redis_client):
        self.redis = redis_client
        self._lua_sha: str | None = None

    async def _get_lua_sha(self) -> str:
        if self._lua_sha is None:
            self._lua_sha = await self.redis.script_load(TOKEN_BUCKET_LUA)
        return self._lua_sha

    async def is_allowed(self, key: str, rate: float, burst: int) -> bool:
        """检查给定 key 是否允许通过.

        Args:
            key: 限流键（如 user_id 或 ip）
            rate: 每秒产生的令牌数
            burst: 桶容量（最大突发请求数）
        """
        now = time.time()
        sha = await self._get_lua_sha()
        result = await self.redis.evalsha(
            sha, 1, key, str(rate), str(burst), str(now)
        )
        return bool(result)

    async def limit_by_user(self, user_id: int, tier: str = "default") -> bool:
        """根据用户等级设置不同限流策略.

        Tiers:
            free:     10 req/min
            standard: 100 req/min
            premium:  1000 req/min
        """
        tier_rates = {
            "free": (settings.RATE_LIMIT_FREE / 60.0, settings.RATE_LIMIT_FREE),
            "standard": (settings.RATE_LIMIT_STANDARD / 60.0, settings.RATE_LIMIT_STANDARD),
            "premium": (settings.RATE_LIMIT_PREMIUM / 60.0, settings.RATE_LIMIT_PREMIUM),
        }
        rate, burst = tier_rates.get(tier, tier_rates["free"])
        key = f"rate_limit:user:{user_id}"
        return await self.is_allowed(key, rate, burst)

    async def limit_by_ip(self, ip: str, rate: float = 1.0, burst: int = 30) -> bool:
        """基于 IP 的限流（用于未登录用户）."""
        key = f"rate_limit:ip:{ip}"
        return await self.is_allowed(key, rate, burst)


async def rate_limit_dependency(
    request: Request,
    current_user: UserRead | None = Depends(get_current_user),
) -> None:
    """FastAPI dependency：为路由提供限流保护.

    已登录用户按 tier 限流，未登录用户按 IP 限流.
    """
    limiter = RateLimiter(redis_client)

    if current_user is not None:
        allowed = await limiter.limit_by_user(current_user.id, current_user.tier)
    else:
        ip = request.client.host if request.client else "unknown"
        allowed = await limiter.limit_by_ip(ip)

    if not allowed:
        raise RateLimitException()

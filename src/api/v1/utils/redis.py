"""Redis connection helper for pub/sub."""

from __future__ import annotations

import redis.asyncio as aioredis
from functools import lru_cache

from config.settings import settings


@lru_cache(maxsize=1)
def get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)

import math
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings


async def get_redis():
    async with Redis.from_url(
        settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
    ) as redis:
        try:
            yield redis
        except RedisError:
            raise HTTPException(503, "Session service unavailable") from None


# All workers use the Redis clock and reserve a slot atomically.
_WINDOW = """
local t = redis.call('TIME')
local now = t[1] * 1000 + math.floor(t[2] / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - 60000)
if redis.call('ZCARD', KEYS[1]) >= 10 then
    local first = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return first[2] + 60000 - now
end
redis.call('ZADD', KEYS[1], now, ARGV[1])
redis.call('PEXPIRE', KEYS[1], 60000)
return 0
"""


async def limit(redis: Redis, bucket: str) -> None:
    wait_ms = await redis.eval(_WINDOW, 1, "contest:limit:" + bucket, secrets.token_hex(16))
    if wait_ms:
        raise HTTPException(
            429, "Too many requests", headers={"Retry-After": str(math.ceil(wait_ms / 1000))}
        )


async def limit_ip(request: Request, redis: Annotated[Redis, Depends(get_redis)]) -> None:
    peer = request.client.host if request.client else "unknown"
    await limit(redis, "ip:" + peer)

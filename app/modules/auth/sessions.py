import hashlib
import re
import secrets
import uuid

from fastapi import HTTPException, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import User
from app.modules.auth.schemas import TokenResponse
from app.modules.auth.security import create_access_token

LIFETIME = 7 * 24 * 3600
_TOKEN = re.compile(r"([0-9a-f]{32})\.[A-Za-z0-9_-]{43}")

# Remember spent hashes until the family's original expiry. A known spent token
# revokes the family; guessing a token for a known family must have no effect.
_ROTATE = """
local current = redis.call('HGET', KEYS[1], 'active')
if not current then return 0 end
if current ~= ARGV[1] then
    if redis.call('HEXISTS', KEYS[1], ARGV[1]) == 1 then redis.call('DEL', KEYS[1]) end
    return 0
end
if ARGV[2] == '' then
    redis.call('DEL', KEYS[1])
else
    redis.call('HSET', KEYS[1], ARGV[1], 'used', 'active', ARGV[2])
end
return 1
"""


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def session_key(family: str) -> str:
    return "contest:refresh:" + family


def token_for(family: str) -> str:
    return family + "." + secrets.token_urlsafe(32)


def invalid_refresh():
    return HTTPException(401, "Invalid or expired refresh token")


def parse_family(token: str) -> str:
    match = _TOKEN.fullmatch(token)
    if not match:
        raise invalid_refresh()
    return match[1]


def token_response(response: Response, user_id: uuid.UUID, refresh: str) -> TokenResponse:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=refresh,
        expires_in=settings.JWT_ACCESS_TOKEN_MINUTES * 60,
    )


async def start_session(redis: Redis, response: Response, user_id: uuid.UUID) -> TokenResponse:
    family = secrets.token_hex(16)
    token = token_for(family)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.hset(session_key(family), mapping={"user": str(user_id), "active": digest(token)})
        pipe.expire(session_key(family), LIFETIME)
        await pipe.execute()
    return token_response(response, user_id, token)


async def refresh_session(
    redis: Redis, db: AsyncSession, response: Response, token: str
) -> TokenResponse:
    family = parse_family(token)
    key = session_key(family)
    stored = await redis.hget(key, "user")
    if not stored or await db.get(User, uuid.UUID(stored)) is None:
        raise invalid_refresh()
    replacement = token_for(family)
    if not await redis.eval(_ROTATE, 1, key, digest(token), digest(replacement)):
        raise invalid_refresh()
    return token_response(response, uuid.UUID(stored), replacement)


async def end_session(redis: Redis, token: str) -> None:
    key = session_key(parse_family(token))
    if not await redis.eval(_ROTATE, 1, key, digest(token), ""):
        raise invalid_refresh()

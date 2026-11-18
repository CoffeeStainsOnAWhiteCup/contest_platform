import uuid
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import settings


password_hasher = PasswordHash.recommended()
# An unknown email still performs password verification.
DUMMY_PASSWORD_HASH = password_hasher.hash("not-a-real-account-password")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except (UnknownHashError, ValueError):
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_MINUTES),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "type": "access",
        },
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str) -> uuid.UUID:
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithms=["HS256"],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
        options={"require": ["sub", "iat", "exp", "iss", "aud", "type"]},
    )
    if payload["type"] != "access":
        raise InvalidTokenError("Wrong token type")
    try:
        return uuid.UUID(payload["sub"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidTokenError("Invalid token subject") from exc

import uuid
from typing import cast
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
from passlib.hash import bcrypt_sha256
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import settings


legacy_password_hasher = PasswordHash.recommended()
# The salted SHA-256 prehash preserves every byte of long UTF-8 passwords.
password_hasher = bcrypt_sha256.using(rounds=12)
# An unknown email still performs password verification.
DUMMY_PASSWORD_HASH = password_hasher.hash("not-a-real-account-password")


def hash_password(password: str) -> str:
    return cast(str, password_hasher.hash(password))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        if password_hasher.identify(password_hash):
            return cast(bool, password_hasher.verify(password, password_hash))
        return legacy_password_hasher.verify(password, password_hash)
    except (UnknownHashError, ValueError):
        return False


def create_access_token(user_id: uuid.UUID, version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "ver": version,
            "jti": uuid.uuid4().hex,
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
    return access_identity(token)[0]


def access_identity(token: str) -> tuple[uuid.UUID, int]:
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
        return uuid.UUID(payload["sub"]), int(payload.get("ver", 0))
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidTokenError("Invalid token subject") from exc

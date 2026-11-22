from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import User, UserRole
from app.modules.auth.security import access_identity

bearer = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        if request.headers.get("Authorization") is not None:
            raise unauthorized
        return None
    try:
        user_id, version = access_identity(credentials.credentials)
    except InvalidTokenError:
        raise unauthorized from None
    user = await db.get(User, user_id)
    if user is None:
        raise unauthorized
    if user.is_blocked:
        raise HTTPException(403, "Account blocked")
    if version != (user.auth_version or 0):
        raise unauthorized
    return user


async def get_current_user(user: Annotated[User | None, Depends(get_current_user_optional)]) -> User:
    if user is None:
        raise HTTPException(401, "Invalid or missing access token", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_roles(*roles: UserRole):
    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency

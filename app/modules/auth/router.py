from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limit import get_redis, limit_ip
from app.models.models import User
from app.modules.auth.github import router as github_router
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from app.modules.auth.service import authenticate_user, register_user
from app.modules.auth.sessions import end_session, refresh_session, start_session

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(limit_ip)])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    return await register_user(db, payload)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> TokenResponse:
    user = await authenticate_user(db, payload)
    return await start_session(redis, response, user.id)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> TokenResponse:
    return await refresh_session(redis, db, response, payload.refresh_token.get_secret_value())


@router.post("/logout", status_code=204)
async def logout(payload: RefreshRequest, redis: Annotated[Redis, Depends(get_redis)]) -> Response:
    await end_session(redis, payload.refresh_token.get_secret_value())
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/me", response_model=UserRead, deprecated=True)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Compatibility endpoint; use GET /api/v1/users/me for new clients."""
    return user


router.include_router(github_router)

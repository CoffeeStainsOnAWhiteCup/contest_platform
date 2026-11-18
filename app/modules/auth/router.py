from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.models import User
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.modules.auth.security import create_access_token
from app.modules.auth.service import authenticate_user, register_user


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    return await register_user(db, payload)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    user = await authenticate_user(db, payload)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.JWT_ACCESS_TOKEN_MINUTES * 60,
    )


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> User:
    return user

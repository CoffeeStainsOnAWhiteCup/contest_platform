from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.models import User, UserRole
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.auth.security import DUMMY_PASSWORD_HASH, hash_password, verify_password


def invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    # Also finds legacy mixed-case values. New registrations are normalized.
    return await db.scalar(select(User).where(func.lower(User.email) == email))


async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    if await get_user_by_email(db, str(payload.email)) is not None:
        raise HTTPException(status_code=409, detail="Email is already registered")

    user = User(
        email=str(payload.email),
        name=payload.name,
        password_hash=await run_in_threadpool(hash_password, payload.password.get_secret_value()),
        role=UserRole.PARTICIPANT,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # A concurrent registration can win after the initial lookup.
        if await get_user_by_email(db, str(payload.email)) is not None:
            raise HTTPException(status_code=409, detail="Email is already registered") from None
        raise
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, payload: LoginRequest) -> User:
    user = await get_user_by_email(db, str(payload.email))
    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    valid = await run_in_threadpool(verify_password, payload.password.get_secret_value(), password_hash)
    if user is None or not valid:
        raise invalid_credentials()
    return user

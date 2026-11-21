import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.core.database import get_db
from app.core.rate_limit import get_redis
from app.models.models import User
from app.modules.rating.service import scores, with_names

router = APIRouter(tags=["rating"])
DB = Annotated[AsyncSession, Depends(get_db)]
Cache = Annotated[Redis, Depends(get_redis)]
Viewer = Annotated[User | None, Depends(get_current_user_optional)]
Page = Annotated[int, Query(ge=1)]
Size = Annotated[int, Query(ge=1, le=100)]


class Entry(BaseModel):
    place: int
    user_id: uuid.UUID
    name: str
    solved: int
    penalty: int


class Board(BaseModel):
    items: list[Entry]
    total: int
    page: int
    size: int


async def page_of(
    db: AsyncSession,
    redis: Redis,
    contest_id: uuid.UUID | None,
    user: User | None,
    page: int,
    size: int,
) -> Board:
    rows = await scores(db, redis, contest_id, user)
    offset = (page - 1) * size
    return Board(
        items=[
            Entry.model_validate(item)
            for item in await with_names(db, rows[offset : offset + size])
        ],
        total=len(rows),
        page=page,
        size=size,
    )


@router.get("/contests/{contest_id}/leaderboard", response_model=Board)
async def leaderboard(
    contest_id: uuid.UUID, db: DB, redis: Cache, user: Viewer, page: Page = 1, size: Size = 20
) -> Board:
    return await page_of(db, redis, contest_id, user, page, size)


@router.get("/rating/global", response_model=Board)
async def global_board(db: DB, redis: Cache, page: Page = 1, size: Size = 20) -> Board:
    return await page_of(db, redis, None, None, page, size)


@router.get("/rating/me", response_model=Entry | None)
async def personal(
    db: DB,
    redis: Cache,
    user: Annotated[User, Depends(get_current_user)],
    contest_id: uuid.UUID | None = None,
) -> Entry | None:
    rows = await scores(db, redis, contest_id, user)
    return next(
        (Entry.model_validate(dict(row, name=user.name)) for row in rows if row["user_id"] == str(user.id)), None
    )

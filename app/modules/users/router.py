"""Profile and administrator endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.models import User, UserAudit, UserRole
from app.modules.auth.schemas import UserRead

router = APIRouter(prefix="/users", tags=["users"])
Current = Annotated[User, Depends(get_current_user)]
Admin = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
DB = Annotated[AsyncSession, Depends(get_db)]


class Profile(UserRead):
    avatar_url: str | None = None


class AdminView(Profile):
    is_blocked: bool


class Edit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    avatar_url: HttpUrl | None = None

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set or ("name" in self.model_fields_set and self.name is None):
            raise ValueError("Supply a name or an avatar URL (null clears the avatar)")
        if self.avatar_url and len(str(self.avatar_url)) > 2048:
            raise ValueError("Avatar URL is too long")
        return self


class RoleChange(BaseModel):
    role: UserRole


class BlockChange(BaseModel):
    is_blocked: bool


@router.get("/me", response_model=Profile, response_model_exclude_none=True)
async def me(user: Current):
    return user


@router.patch("/me", response_model=Profile)
async def update_profile(payload: Edit, user: Current, db: DB):
    if payload.name is not None:
        user.name = payload.name
        user.name_customized = True
    if "avatar_url" in payload.model_fields_set:
        user.avatar_url = str(payload.avatar_url) if payload.avatar_url else None
    await db.commit()
    return user


@router.get("", response_model=list[AdminView])
async def list_users(
    admin: Admin, db: DB, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)
):
    query = select(User).order_by(User.created_at, User.id).offset((page - 1) * size).limit(size)
    return (await db.scalars(query)).all()


async def record_change(db: AsyncSession, actor: User, user_id: uuid.UUID, field: str, value):
    user = await db.get(User, user_id, with_for_update=True, populate_existing=True)
    if user is None:
        raise HTTPException(404, "User not found")
    old = getattr(user, field)
    if old != value:
        db.add(
            UserAudit(
                actor_id=actor.id,
                user_id=user.id,
                field=field,
                old_value=str(getattr(old, "value", old)),
                new_value=str(getattr(value, "value", value)),
            )
        )
        setattr(user, field, value)
        if field == "is_blocked" and value:
            user.auth_version += 1
    await db.commit()
    return user


@router.patch("/{user_id}/role", response_model=AdminView)
async def change_role(user_id: uuid.UUID, payload: RoleChange, admin: Admin, db: DB):
    return await record_change(db, admin, user_id, "role", payload.role)


@router.patch("/{user_id}/block", response_model=AdminView)
async def change_block(user_id: uuid.UUID, payload: BlockChange, admin: Admin, db: DB):
    return await record_change(db, admin, user_id, "is_blocked", payload.is_blocked)

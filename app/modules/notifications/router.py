"""Telegram account linking through a short-lived, single-use code."""

import hashlib
import hmac
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import get_redis
from app.models.models import Notification, User, utcnow

router = APIRouter(prefix="/telegram", tags=["telegram"])
Cache = Annotated[Redis, Depends(get_redis)]
DB = Annotated[AsyncSession, Depends(get_db)]


class Chat(BaseModel):
    id: int
    type: str


class Message(BaseModel):
    chat: Chat
    text: str = ""


class Update(BaseModel):
    message: Message | None = None


class Link(BaseModel):
    code: uuid.UUID
    expires_in: int
    url: str | None


def link_key(code: uuid.UUID) -> str:
    return "contest:telegram:link:" + hashlib.sha256(code.bytes).hexdigest()


@router.post("/link", response_model=Link)
async def link(user: Annotated[User, Depends(get_current_user)], redis: Cache):
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(503, "Telegram is not configured")
    code = uuid.uuid4()
    await redis.set(link_key(code), str(user.id), ex=600)
    username = settings.TELEGRAM_BOT_USERNAME
    return Link(
        code=code, expires_in=600, url=f"https://t.me/{username}?start={code}" if username else None
    )


@router.post("/webhook")
async def webhook(
    update: Update,
    redis: Cache,
    db: DB,
    secret: Annotated[str, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = "",
):
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    if not expected or not hmac.compare_digest(
        secret.encode(), expected.get_secret_value().encode()
    ):
        raise HTTPException(403, "Invalid webhook secret")
    message = update.message
    if message is None or message.chat.type != "private":
        return {"ok": True}
    command, _, argument = message.text.strip().partition(" ")
    if command != "/start":
        return {"ok": True}
    try:
        key = link_key(uuid.UUID(argument))
    except ValueError:
        return {"ok": True}
    owner = await redis.get(key)
    if owner is None:
        return {"ok": True}
    user = await db.get(User, uuid.UUID(owner), with_for_update=True)
    if user is None or user.is_blocked:
        return {"ok": True}
    # Serialize redeliveries even if a process dies after commit, before Redis DEL.
    event = "link:" + key.rsplit(":", 1)[1]
    used = await db.scalar(
        select(Notification.id).where(
            Notification.user_id == user.id, Notification.event_key == event
        )
    )
    if used is None:
        chat_id = str(message.chat.id)
        user.telegram_chat_id = chat_id
        user.telegram_linked_at = utcnow()
        db.add(
            Notification(
                user_id=user.id, chat_id=chat_id, event_key=event, message="Аккаунт привязан"
            )
        )
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            if getattr(exc.orig, "sqlstate", None) != "23505":
                raise
            # A chat already linked to another platform account cannot be reassigned here.
    await redis.delete(key)
    return {"ok": True}

"""Telegram account linking through a short-lived, single-use code."""

import hashlib
import hmac
import uuid
from datetime import datetime
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
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None

    def update_identity(self, user: User) -> None:
        user.telegram_name = " ".join(part for part in (self.first_name, self.last_name) if part) or None
        user.telegram_username = self.username


class Message(BaseModel):
    chat: Chat
    text: str = ""


class Update(BaseModel):
    update_id: int | None = None
    message: Message | None = None


class Link(BaseModel):
    code: uuid.UUID
    expires_in: int
    url: str | None


def link_key(code: uuid.UUID) -> str:
    return "contest:telegram:link:" + hashlib.sha256(code.bytes).hexdigest()


class LinkStatus(BaseModel):
    linked: bool
    linked_at: datetime | None
    name: str | None
    username: str | None


@router.get("/status")
async def link_status(user: Annotated[User, Depends(get_current_user)]) -> LinkStatus:
    return LinkStatus(
        linked=user.telegram_chat_id is not None, linked_at=user.telegram_linked_at,
        name=user.telegram_name, username=user.telegram_username,
    )


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


async def command_reply(redis: Redis, update_id: int | None, chat: Chat, text: str) -> dict:
    # Telegram may retry the same incoming message; give each update one reply.
    if update_id is not None and not await redis.set(
        f"contest:telegram:reply:{update_id}", "1", nx=True, ex=86400
    ):
        return {"ok": True}
    return {"method": "sendMessage", "chat_id": chat.id, "text": text}


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
    chat_id = str(message.chat.id)
    if command in ("/start", "/profile") and not argument:
        linked = await db.scalar(select(User).where(User.telegram_chat_id == chat_id).with_for_update())
        if linked is None or linked.is_blocked:
            reply = "Откройте свой профиль на сайте, нажмите «Получить код привязки» и перейдите по ссылке в Telegram."
        else:
            message.chat.update_identity(linked)
            reply = f"Этот чат привязан к профилю «{linked.name}». Сюда приходят вердикты и уведомления о конкурсах."
            await db.commit()
        return await command_reply(redis, update.update_id, message.chat, reply)
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
        message.chat.update_identity(user)
        user.telegram_chat_id = chat_id
        user.telegram_linked_at = utcnow()
        db.add(
            Notification(
                user_id=user.id, chat_id=chat_id, event_key=event,
                message=(
                    f"✅ Telegram подключён к профилю «{user.name}».\n"
                    "Сюда придут результаты решений и уведомления о начале и завершении конкурсов.\n"
                    "Проверить привязку — /profile."
                ),
            )
        )
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            if getattr(exc.orig, "sqlstate", None) != "23505":
                raise
            await redis.delete(key)
            return await command_reply(
                redis, update.update_id, message.chat,
                "Этот чат уже привязан к другому профилю. Для новой привязки выберите другой аккаунт Telegram.",
            )
    await redis.delete(key)
    return {"ok": True}

import uuid
from datetime import timedelta

import pytest
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.models.models import Notification, utcnow
from app.modules.auth.security import create_access_token
from app.modules.notifications.router import link_key
from app.modules.notifications.tasks import dispatch
from tests.conftest import create_contest_and_problem


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", SecretStr("test-bot"))
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", SecretStr("test-webhook"))
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "test_bot")
    return {"X-Telegram-Bot-Api-Secret-Token": "test-webhook"}


async def test_link_one_time_private_chat_and_ack(client, db_session, participant, bot):
    path = "/api/v1/telegram"
    assert (await client.post(path + "/link")).status_code == 401
    result = (
        await client.post(
            path + "/link",
            headers={"Authorization": f"Bearer {create_access_token(participant.id)}"},
        )
    ).json()
    assert result["url"].endswith(result["code"])
    key = link_key(uuid.UUID(result["code"]))
    async with Redis.from_url(settings.REDIS_URL) as cache:
        assert 595 < await cache.ttl(key) <= 600
    message = {
        "message": {"chat": {"id": 123, "type": "group"}, "text": "/start " + result["code"]}
    }
    assert (await client.post(path + "/webhook", json=message)).status_code == 403
    await client.post(path + "/webhook", json=message, headers=bot)
    assert participant.telegram_chat_id is None
    message["message"]["chat"]["type"] = "private"
    assert (await client.post(path + "/webhook", headers=bot, json=message)).status_code == 200
    message["message"]["chat"]["id"] = 456
    assert (await client.post(path + "/webhook", headers=bot, json=message)).status_code == 200
    await db_session.refresh(participant)
    assert participant.telegram_chat_id == "123"
    records = (await db_session.scalars(select(Notification))).all()
    assert len(records) == 1 and records[0].message == "Аккаунт привязан"
    async with Redis.from_url(settings.REDIS_URL) as cache:
        assert not await cache.exists(key)


class Reply:
    def __init__(self, status, **data):
        self.status_code = status
        self.data = {"ok": status == 200, **data}

    def json(self):
        return self.data


async def test_contest_events_delivered_once(db_session, participant, bot, monkeypatch):
    now = utcnow()
    participant.telegram_linked_at = now - timedelta(days=2)
    participant.telegram_chat_id = "123"
    contest, _, _ = await create_contest_and_problem(db_session)
    contest.start_at = now - timedelta(hours=2)
    contest.end_at = now - timedelta(hours=1)
    await db_session.commit()
    sent = []

    def send(url, *, json, **kwargs):
        sent.append(json)
        return Reply(200)

    monkeypatch.setattr("app.modules.notifications.tasks.requests.post", send)
    for _ in range(2):
        await run_in_threadpool(dispatch.run)
    assert sorted(row["text"] for row in sent) == sorted(
        [f"Контест «{contest.title}» начался.", f"Контест «{contest.title}» завершён."]
    )
    records = (await db_session.scalars(select(Notification))).all()
    assert all(item.delivered_at and item.status == "sent" for item in records)


@pytest.mark.parametrize(
    "status,description,unlinked",
    [
        (400, "Bad Request: chat not found", True),
        (400, "Bad Request: invalid text", False),
        (403, "Forbidden", True),
        (429, "Too many requests", False),
        (503, "Unavailable", False),
    ],
)
async def test_telegram_failure_policy(
    db_session, participant, monkeypatch, bot, status, description, unlinked
):
    participant.telegram_chat_id = "123"
    item = Notification(user_id=participant.id, chat_id="123", event_key="test", message="message")
    db_session.add(item)
    await db_session.commit()
    reply = Reply(
        status, error_code=status, description=description, parameters={"retry_after": 90}
    )
    monkeypatch.setattr("app.modules.notifications.tasks.requests.post", lambda *a, **kw: reply)
    before = utcnow()
    if status == 503:
        # Several rate limits must not exhaust the independent network retry budget.
        item.attempts = 5
        await db_session.commit()
    await run_in_threadpool(dispatch.run)
    await db_session.refresh(item)
    await db_session.refresh(participant)
    assert (participant.telegram_chat_id is None) == unlinked
    if status in (400, 403):
        assert item.status == "failed"
    elif status == 429:
        assert item.status == "pending" and item.available_at >= before + timedelta(seconds=90)
    else:
        assert item.status == "pending"
        for _ in range(3):
            item.available_at = before
            await db_session.commit()
            await run_in_threadpool(dispatch.run)
            await db_session.refresh(item)
        assert item.status == "failed" and item.transient_failures == 4 and item.attempts == 9

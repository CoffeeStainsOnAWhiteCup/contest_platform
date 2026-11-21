"""Deliver committed events independently of Judge. No request URL is logged."""

import logging
from datetime import timedelta

import requests
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.celery_app import celery
from app.core.config import settings
from app.core.database import SyncSessionLocal
from app.models.models import Notification, User, utcnow
from app.modules.notifications.events import CONTEST_EVENTS

logger = logging.getLogger(__name__)


def send_one(db: Session, item: Notification, token: str) -> None:
    user = db.get(User, item.user_id)
    if user is None or user.is_blocked or user.telegram_chat_id != item.chat_id:
        item.status = "cancelled"
        return
    item.attempts += 1
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": item.chat_id, "text": item.message},
            timeout=(3, 5),
            allow_redirects=False,
        )
        data = response.json()
        if not isinstance(data, dict):
            raise TypeError("Unexpected response")
    except (requests.RequestException, ValueError, TypeError):
        data = {}
        code = 503
    else:
        if response.status_code == 200 and data.get("ok") is True:
            item.status = "sent"
            item.delivered_at = utcnow()
            item.last_error = None
            logger.info("Telegram notification %s delivered", item.id)
            return
        code = data.get("error_code", response.status_code)
        if not isinstance(code, int):
            code = 503

    item.last_error = f"telegram:{code}"
    if code == 403 or (
        code == 400 and "chat not found" in str(data.get("description", "")).lower()
    ):
        db.execute(
            update(User)
            .where(User.id == item.user_id, User.telegram_chat_id == item.chat_id)
            .values(telegram_chat_id=None, telegram_linked_at=None)
        )
        item.status = "failed"
    elif code == 429:
        parameters = data.get("parameters")
        retry_after = parameters.get("retry_after") if isinstance(parameters, dict) else None
        delay = max(1, retry_after) if isinstance(retry_after, int) else 60
        item.available_at = utcnow() + timedelta(seconds=delay)
    elif code >= 500:
        item.transient_failures += 1
        if item.transient_failures <= 3:
            item.available_at = utcnow() + timedelta(seconds=2**item.transient_failures)
        else:
            item.status = "failed"
    else:
        item.status = "failed"
    logger.warning("Telegram notification %s: %s (%s)", item.id, item.status, item.last_error)


@celery.task(name="notifications.dispatch")
def dispatch() -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    with SyncSessionLocal.begin() as db:
        db.execute(CONTEST_EVENTS)
    for _ in range(20):
        with SyncSessionLocal.begin() as db:
            item = db.scalar(
                select(Notification)
                .where(Notification.status == "pending", Notification.available_at <= utcnow())
                .order_by(Notification.available_at, Notification.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if item is None:
                return
            send_one(db, item, token.get_secret_value())

"""Record Telegram events in the transaction that changes application state."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.models import Notification, Submission, User, VerdictStatus


def enqueue_verdict(db: Session, submission: Submission, status: VerdictStatus) -> None:
    """Queue one result for the linked account as part of the verdict transaction."""
    user = db.get(User, submission.user_id)
    if user and user.telegram_chat_id and not user.is_blocked:
        db.add(
            Notification(
                user_id=user.id,
                chat_id=user.telegram_chat_id,
                event_key=f"verdict:{submission.id}:{submission.judge_attempt}",
                message=f"Ваше решение задачи «{submission.problem.title}» получило вердикт: {status.value}.",
            )
        )


# A repeated scheduler tick inserts only previously unseen events. Users who link
# later don't receive old announcements. An archive transition supplies archived_id
# to record the final eligible events before the periodic scan loses visibility.
CONTEST_EVENTS = text("""
    WITH due AS (
        SELECT u.id AS user_id, u.telegram_chat_id AS chat_id, 'contest:' || c.id || ':' || e.kind AS event_key,
               'Контест «' || c.title || '» ' || e.label AS message
        FROM contests c
        CROSS JOIN LATERAL (VALUES ('start', c.start_at, 'начался.'),
                                   ('end', c.end_at, 'завершён.')) e(kind, due, label)
        JOIN users u ON u.telegram_chat_id IS NOT NULL AND NOT u.is_blocked
                    AND coalesce(u.telegram_linked_at, u.created_at) <= e.due
        WHERE (
            (CAST(:archived_id AS uuid) IS NULL AND c.status IN ('PUBLISHED','ACTIVE','FINISHED'))
            OR (c.id = :archived_id AND c.status = 'ARCHIVED')
        ) AND e.due <= statement_timestamp()
    ), claimed AS (
        INSERT INTO contest_notification_keys (user_id, event_key)
        SELECT user_id, event_key FROM due
        ON CONFLICT DO NOTHING
        RETURNING user_id, event_key
    )
    INSERT INTO notifications (user_id, chat_id, event_key, message, status, attempts, available_at)
    SELECT user_id, chat_id, event_key, message, 'pending', 0, now()
    FROM claimed JOIN due USING (user_id, event_key)
    ON CONFLICT (user_id, event_key) DO NOTHING
""").bindparams(archived_id=None)

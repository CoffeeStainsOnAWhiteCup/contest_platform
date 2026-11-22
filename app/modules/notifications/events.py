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
    INSERT INTO notifications (user_id, chat_id, event_key, message, status, attempts, available_at)
    SELECT u.id, u.telegram_chat_id, 'contest:' || c.id || ':' || e.kind,
           'Контест «' || c.title || '» ' || e.label, 'pending', 0, now()
    FROM contests c
    CROSS JOIN LATERAL (VALUES ('start', c.start_at, 'начался.'),
                               ('end', c.end_at, 'завершён.')) e(kind, due, label)
    JOIN users u ON u.telegram_chat_id IS NOT NULL AND NOT u.is_blocked
                AND coalesce(u.telegram_linked_at, u.created_at) <= e.due
    WHERE (
        (CAST(:archived_id AS uuid) IS NULL AND c.status IN ('PUBLISHED','ACTIVE','FINISHED'))
        OR (c.id = :archived_id AND c.status = 'ARCHIVED')
    ) AND e.due <= statement_timestamp()
    ON CONFLICT (user_id, event_key) DO NOTHING
""").bindparams(archived_id=None)

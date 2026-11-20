from datetime import datetime, timezone

from app.models.models import Contest, ContestStatus, User, UserRole


PRIVILEGED_ROLES = {UserRole.ADMIN, UserRole.JUDGE}
PARTICIPANT_VISIBLE_STATUSES = {
    ContestStatus.PUBLISHED,
    ContestStatus.ACTIVE,
    ContestStatus.FINISHED,
}


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_privileged(user: User) -> bool:
    return user.role in PRIVILEGED_ROLES


def can_view_contest(user: User, contest: Contest) -> bool:
    return is_privileged(user) or contest.status in PARTICIPANT_VISIBLE_STATUSES


def can_manage_contest(user: User) -> bool:
    return user.role == UserRole.ADMIN


def can_manage_problems(user: User) -> bool:
    return user.role in PRIVILEGED_ROLES


def submission_denial_reason(
    contest: Contest, now: datetime | None = None
) -> str | None:
    if contest.status != ContestStatus.ACTIVE:
        return "Contest is not open"

    current = as_utc(now or datetime.now(timezone.utc))
    if current < as_utc(contest.start_at):
        return "Contest has not started"
    if current > as_utc(contest.end_at):
        return "Contest has finished"
    return None


def can_submit_to_contest(contest: Contest, now: datetime | None = None) -> bool:
    return submission_denial_reason(contest, now) is None

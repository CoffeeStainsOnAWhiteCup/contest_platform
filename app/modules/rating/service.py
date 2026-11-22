"""Competition ranking. Persisted revisions isolate cache reads from concurrent writes."""

import hashlib
import json
import uuid

from fastapi import HTTPException
from pydantic import TypeAdapter
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import Update
from typing_extensions import TypedDict

from app.models.models import Contest, ContestStatus, Problem, User, UserRole

PUBLIC = (ContestStatus.PUBLISHED, ContestStatus.ACTIVE)
# Completed contests contribute to the historical global table.
GLOBAL = (*PUBLIC, ContestStatus.FINISHED, ContestStatus.ARCHIVED)


class Score(TypedDict):
    user_id: str
    place: int
    solved: int
    penalty: int


class NamedScore(Score):
    name: str


_SCORE_LIST = TypeAdapter(list[Score])


def revision_update(problem_id: uuid.UUID) -> Update:
    """Bump the contest revision in the same transaction as its submission."""
    return (
        update(Contest)
        .where(
            Contest.id
            == select(Problem.contest_id).where(Problem.id == problem_id).scalar_subquery()
        )
        .values(rating_revision=Contest.rating_revision + 1)
    )


# Order attempts by submission time, including rejudged submissions.
SCORES = text("""
    WITH attempts AS (
        SELECT s.user_id, s.problem_id, s.status,
               greatest(0, floor(extract(epoch FROM s.created_at - c.start_at) / 60)) AS minutes,
               count(*) FILTER (WHERE s.status IN ('WRONG_ANSWER', 'RUNTIME_ERROR',
                   'TIME_LIMIT_EXCEEDED', 'MEMORY_LIMIT_EXCEEDED')) OVER attempt_order AS failures,
               count(*) FILTER (WHERE s.status = 'ACCEPTED') OVER attempt_order AS accepts
        FROM submissions s
        JOIN problems p ON p.id = s.problem_id
        JOIN contests c ON c.id = p.contest_id
        WHERE c.id = ANY(CAST(:ids AS uuid[]))
        WINDOW attempt_order AS (PARTITION BY s.user_id, s.problem_id
            ORDER BY s.created_at, s.id ROWS UNBOUNDED PRECEDING)
    ), totals AS (
        SELECT user_id, count(*) FILTER (WHERE status = 'ACCEPTED' AND accepts = 1) AS solved,
               coalesce(sum(minutes + 20 * failures)
                   FILTER (WHERE status = 'ACCEPTED' AND accepts = 1), 0)::bigint AS penalty
        FROM attempts GROUP BY user_id
    )
    SELECT user_id::text, solved, penalty, rank() OVER (ORDER BY solved DESC, penalty) AS place
    FROM totals ORDER BY solved DESC, penalty, user_id
""")


async def scores(
    db: AsyncSession, redis: Redis, contest_id: uuid.UUID | None, viewer: User | None
) -> list[Score]:
    """Read ranked scores for the visible contest or aggregate standings."""
    query = select(Contest.id, Contest.rating_revision, Contest.start_at).order_by(Contest.id)
    if contest_id is None:
        query = query.where(Contest.status.in_(GLOBAL))
    else:
        query = query.where(Contest.id == contest_id)
        if viewer is None or viewer.role == UserRole.PARTICIPANT:
            query = query.where(Contest.status.in_(PUBLIC))
    contests = (await db.execute(query)).all()
    if not contests:
        if contest_id is not None:
            raise HTTPException(404, "Contest not found")
        return []
    signature = hashlib.sha256(
        str((db.get_bind().engine.url.database, [tuple(row) for row in contests])).encode()
    ).hexdigest()
    key = f"contest:rating:v1:{signature}"
    try:
        cached = await redis.get(key)
        if cached:
            return _SCORE_LIST.validate_json(cached)
    except (RedisError, ValueError):
        pass
    result = await db.execute(SCORES, {"ids": [row.id for row in contests]})
    rows = _SCORE_LIST.validate_python([dict(row) for row in result.mappings()])
    try:
        await redis.set(key, json.dumps(rows), ex=60)
    except RedisError:
        pass
    return rows


async def with_names(db: AsyncSession, rows: list[Score]) -> list[NamedScore]:
    """Resolve current profile names only for the requested page."""
    ids = [uuid.UUID(row["user_id"]) for row in rows]
    if not ids:
        return []
    result = await db.execute(select(User.id, User.name).where(User.id.in_(ids)))
    names = {uid: name for uid, name in result.tuples()}
    return [NamedScore(**row, name=names[uid]) for row, uid in zip(rows, ids) if uid in names]

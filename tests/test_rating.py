import uuid
from datetime import timedelta

from redis.asyncio import Redis
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.models.models import (
    ContestStatus,
    Language,
    Notification,
    Submission,
    SubmissionStatus,
    VerdictStatus,
)
from app.modules.auth.security import create_access_token
from app.modules.judge.service import _finalize
from app.modules.submissions.repository import reset_for_rejudge
from tests.conftest import create_contest_and_problem, create_user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def attempt(user, problem, minutes, status, start):
    return Submission(
        user_id=user.id,
        problem_id=problem.id,
        language=Language.PYTHON,
        code="",
        created_at=start + timedelta(minutes=minutes),
        status=status,
    )


async def test_ranking_and_personal_history(client, db_session, participant, judge_user):
    contest, problem, _ = await create_contest_and_problem(db_session)
    other, second, _ = await create_contest_and_problem(db_session)
    rival = await create_user(db_session)
    beginner = await create_user(db_session)
    for user, task, minutes, status, start in (
        (participant, problem, 1, SubmissionStatus.WRONG_ANSWER, contest.start_at),
        (participant, problem, 2, SubmissionStatus.SYSTEM_ERROR, contest.start_at),
        (participant, problem, 5, SubmissionStatus.ACCEPTED, contest.start_at),
        (participant, problem, 9, SubmissionStatus.ACCEPTED, contest.start_at),
        (participant, second, 4, SubmissionStatus.ACCEPTED, other.start_at),
        (rival, problem, 25, SubmissionStatus.ACCEPTED, contest.start_at),
        (beginner, problem, 10, SubmissionStatus.WRONG_ANSWER, contest.start_at),
    ):
        db_session.add(attempt(user, task, minutes, status, start))
    await db_session.commit()
    url = f"/api/v1/contests/{contest.id}/leaderboard"
    board = (await client.get(url)).json()
    assert board["total"] == 3
    assert [(row["place"], row["solved"], row["penalty"]) for row in board["items"]] == [
        (1, 1, 25),
        (1, 1, 25),
        (3, 0, 0),
    ]
    assert (await client.get(url, params={"page": 2, "size": 1})).json()["items"] == board["items"][
        1:2
    ]
    mine = await client.get("/api/v1/rating/me", headers=auth(participant))
    assert (mine.json()["solved"], mine.json()["penalty"]) == (2, 29)
    assert (await client.get("/api/v1/rating/global")).json()["items"][0] == mine.json()
    assert (await client.get("/api/v1/rating/me", headers=auth(judge_user))).json() is None
    assert (await client.get("/api/v1/submissions", headers=auth(participant))).json()["total"] == 5
    contest.status = ContestStatus.DRAFT
    await db_session.commit()
    assert (await client.get(url)).status_code == 404
    assert (await client.get(url, headers=auth(judge_user))).status_code == 200
    assert (await client.get("/api/v1/rating/global")).json()["items"][0]["solved"] == 1


async def test_verdict_commit_and_rejudge_replace_warm_board(client, db_session, participant):
    contest, problem, _ = await create_contest_and_problem(db_session)
    participant.telegram_chat_id = "12345"
    submission = attempt(participant, problem, 4, SubmissionStatus.RUNNING, contest.start_at)
    db_session.add(submission)
    await db_session.commit()
    url = f"/api/v1/contests/{contest.id}/leaderboard"
    assert (await client.get(url)).json()["items"][0]["solved"] == 0
    async with Redis.from_url(settings.REDIS_URL) as cache:
        keys = [k async for k in cache.scan_iter(match="contest:rating:v1:*")]
        assert any(0 < ttl <= 60 for ttl in [await cache.ttl(k) for k in keys])
    await run_in_threadpool(_finalize, submission.id, VerdictStatus.ACCEPTED, expected_attempt=0)
    assert (await client.get(url)).json()["items"][0]["solved"] == 1
    item = await db_session.scalar(
        select(Notification).where(Notification.user_id == participant.id)
    )
    assert item.chat_id == "12345" and "ACCEPTED" in item.message
    await db_session.refresh(submission)
    await reset_for_rejudge(db_session, submission)
    assert (await client.get(url)).json()["items"][0]["solved"] == 0


async def test_board_survives_cache_outage(client, db_session, monkeypatch):
    contest, _, _ = await create_contest_and_problem(db_session)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:1/0")
    assert (await client.get(f"/api/v1/contests/{contest.id}/leaderboard")).json()["items"] == []


async def test_board_rebuilds_corrupt_cache(client, db_session, participant):
    contest, problem, _ = await create_contest_and_problem(db_session)
    db_session.add(
        attempt(participant, problem, 1, SubmissionStatus.ACCEPTED, contest.start_at)
    )
    await db_session.commit()
    url = f"/api/v1/contests/{contest.id}/leaderboard"
    assert (await client.get(url)).json()["items"][0]["solved"] == 1
    async with Redis.from_url(settings.REDIS_URL, decode_responses=True) as cache:
        keys = [key async for key in cache.scan_iter(match="contest:rating:v1:*")]
        assert keys
        for key in keys:
            await cache.set(key, "not-json")
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json()["items"][0]["solved"] == 1


async def test_submit_verdict_rating_and_notification(
    client, db_session, participant, judge_user, fake_judge_task, monkeypatch
):
    """API-to-worker flow using deterministic sandbox output and a local bot transport."""
    from types import SimpleNamespace

    from pydantic import SecretStr

    from app.modules.judge.service import judge_submission_sync
    from app.modules.notifications.tasks import dispatch
    from tests.test_judge_service import FakeSandbox, result

    contest, problem, _ = await create_contest_and_problem(db_session)
    participant.telegram_chat_id = "321"
    await db_session.commit()
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", SecretStr("local-only"))
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)
    monkeypatch.setattr(FakeSandbox, "execution_results", [result()])
    messages = []

    def send(url, *, json, **kwargs):
        messages.append(json["text"])
        return SimpleNamespace(status_code=200, json=lambda: {"ok": True})

    monkeypatch.setattr("app.modules.notifications.tasks.requests.post", send)
    submissions = "/api/v1/submissions"
    board = f"/api/v1/contests/{contest.id}/leaderboard"
    response = await client.post(
        submissions,
        headers=auth(participant),
        json={"language": "python", "code": "print(3)", "problem_id": str(problem.id)},
    )
    assert response.status_code == 202
    submission_id = response.json()["id"]
    assert fake_judge_task.calls == [submission_id]
    assert (await client.get(board)).json()["items"][0]["solved"] == 0
    judge_headers = auth(judge_user)
    participant_headers = auth(participant)
    await run_in_threadpool(judge_submission_sync, uuid.UUID(submission_id))
    db_session.expire_all()
    assert (await client.get(board)).json()["items"][0]["solved"] == 1
    await run_in_threadpool(dispatch.run)
    assert len(messages) == 1 and "ACCEPTED" in messages[0]

    first = await client.get(f"{submissions}/{submission_id}", headers=participant_headers)
    assert first.json()["status"] == "ACCEPTED"
    repeat = await client.post(f"{submissions}/{submission_id}/rejudge", headers=judge_headers)
    assert repeat.status_code == 202
    assert (await client.get(board)).json()["items"][0]["solved"] == 0
    monkeypatch.setattr(FakeSandbox, "execution_results", [result(stdout="incorrect")])
    await run_in_threadpool(judge_submission_sync, uuid.UUID(submission_id))
    await run_in_threadpool(dispatch.run)
    assert (await client.get(board)).json()["items"][0]["solved"] == 0
    assert len(messages) == 2 and "WRONG_ANSWER" in messages[1]

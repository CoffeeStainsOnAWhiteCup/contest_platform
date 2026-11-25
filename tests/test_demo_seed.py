import uuid
from datetime import timedelta

from pydantic import SecretStr
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import SyncSessionLocal
from app.models.models import Contest, Problem, Submission, User, utcnow
from app.modules.judge.service import judge_submission_sync
from app.modules.notifications.tasks import dispatch
from tests.conftest import auth_headers
from tests.test_judge_service import FakeSandbox, result
from tests.test_telegram import Reply
from tools.seed_demo import SUM_CODE, populate


def seed(run):
    with SyncSessionLocal.begin() as db:
        return populate(db, run)


async def test_repeated_demo_keeps_accounts_schedule_and_rankings(client, db_session, participant):
    participant.telegram_chat_id = "123"
    await db_session.commit()
    credentials, _ = seed(None)
    assert len(credentials) == 4
    _, first = seed("show-1")
    again, same = seed("show-1")
    assert again == [] and same.id == first.id and same.start_at == first.start_at
    _, second = seed("show-2")
    assert second.id != first.id
    assert await db_session.scalar(select(func.count()).select_from(Contest)) == 4
    assert await db_session.scalar(select(func.count()).select_from(Submission)) == 3
    assert await db_session.scalar(select(func.count()).select_from(User)) == 5
    await db_session.refresh(participant)
    assert participant.telegram_chat_id == "123"
    board = (await client.get("/api/v1/rating/global")).json()
    assert [(row["name"], row["solved"], row["penalty"]) for row in board["items"]] == [
        ("Анна Демо", 1, 5),
        ("Иван Демо", 1, 30),
    ]


async def test_demo_start_verdicts_end(client, db_session, participant, fake_judge_task, monkeypatch):
    participant.telegram_chat_id = "123"
    participant.telegram_linked_at = utcnow() - timedelta(minutes=1)
    await db_session.commit()
    _, demo = seed("show")
    contest = await db_session.get(Contest, demo.id)
    problem_id = await db_session.scalar(select(Problem.id).where(Problem.contest_id == demo.id))
    payload = {"language": "python", "problem_id": str(problem_id), "code": "print(0)"}
    headers = auth_headers(participant)
    url = "/api/v1/submissions"
    assert (await client.post(url, headers=headers, json=payload)).status_code == 400

    sent = []

    def send(url, *, json, **kwargs):
        assert json["chat_id"] == "123"
        sent.append(json["text"])
        return Reply(200)

    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", SecretStr("test-bot"))
    monkeypatch.setattr("app.modules.notifications.tasks.requests.post", send)
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)
    await run_in_threadpool(dispatch.run)
    assert sent == []
    contest.start_at = utcnow() - timedelta(seconds=1)
    await db_session.commit()
    await run_in_threadpool(dispatch.run)
    for code, outputs, expected in (
        ("print(0)", ["0"], "WRONG_ANSWER"),
        (SUM_CODE, ["5", "6", "0"], "ACCEPTED"),
    ):
        payload["code"] = code
        response = await client.post(url, headers=headers, json=payload)
        assert response.status_code == 202
        sid = response.json()["id"]
        assert fake_judge_task.calls[-1] == sid
        monkeypatch.setattr(FakeSandbox, "execution_results", [result(stdout=value + "\n") for value in outputs])
        await run_in_threadpool(judge_submission_sync, uuid.UUID(sid))
        detail = await client.get(f"{url}/{sid}", headers=headers)
        assert detail.json()["status"] == expected
        await run_in_threadpool(dispatch.run)

    contest.end_at = utcnow()
    await db_session.commit()
    await run_in_threadpool(dispatch.run)
    await run_in_threadpool(dispatch.run)
    assert (await client.post(url, headers=headers, json=payload)).status_code == 400
    assert sent == [
        f"Контест «{demo.title}» начался.",
        "Ваше решение задачи «Сумма двух чисел» получило вердикт: WRONG_ANSWER.",
        "Ваше решение задачи «Сумма двух чисел» получило вердикт: ACCEPTED.",
        f"Контест «{demo.title}» завершён.",
    ]

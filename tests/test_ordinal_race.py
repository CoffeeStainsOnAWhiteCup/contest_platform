import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import models as model
from app.modules.contests import repository, schemas, service
from tests.conftest import create_contest_and_problem


def _session_factory(db_engine):
    return async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )


def _racing_ordinal_source():
    calls = 0
    release = asyncio.Event()

    async def next_ordinal(db, parent_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            await asyncio.wait_for(release.wait(), 1)
            return 1
        if calls == 2:
            release.set()
            return 1
        return 2

    return next_ordinal


async def test_concurrent_problem_creation_resolves_ordinal(
    db_engine, db_session, monkeypatch
):
    now = datetime.now(timezone.utc)
    contest = model.Contest(
        title="Race contest",
        description=None,
        start_at=now - timedelta(hours=1),
        end_at=now + timedelta(hours=1),
        status=model.ContestStatus.ACTIVE,
    )
    db_session.add(contest)
    await db_session.commit()
    await db_session.refresh(contest)

    monkeypatch.setattr(
        repository, "next_problem_ordinal", _racing_ordinal_source()
    )
    payload = schemas.ProblemCreate(title="Problem", statement="statement")
    session_factory = _session_factory(db_engine)

    async def create_problem(session):
        return await service.create_problem(session, contest.id, payload)

    async with session_factory() as first, session_factory() as second:
        await asyncio.gather(
            create_problem(first),
            create_problem(second),
        )

    async with session_factory() as session:
        problems = (
            await session.scalars(
                select(model.Problem).where(model.Problem.contest_id == contest.id)
            )
        ).all()

    assert sorted(problem.ordinal for problem in problems) == [1, 2]


async def test_concurrent_test_creation_resolves_ordinal(
    db_engine, db_session, monkeypatch
):
    _, problem, _ = await create_contest_and_problem(db_session, tests=[])

    monkeypatch.setattr(
        repository, "next_test_ordinal", _racing_ordinal_source()
    )
    payload = schemas.TestCreate(input_data="1", expected_output="1")
    session_factory = _session_factory(db_engine)

    async def create_test(session):
        return await service.create_test(session, problem.id, payload)

    async with session_factory() as first, session_factory() as second:
        await asyncio.gather(
            create_test(first),
            create_test(second),
        )

    async with session_factory() as session:
        tests = (
            await session.scalars(
                select(model.Test).where(model.Test.problem_id == problem.id)
            )
        ).all()

    assert sorted(test.ordinal for test in tests) == [1, 2]

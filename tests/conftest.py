import asyncio
import os
import uuid
from types import SimpleNamespace
from urllib.parse import urlparse

import asyncpg
import pytest
import pytest_asyncio
from dotenv import dotenv_values
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

BASE_DATABASE_URL = os.environ.get("DATABASE_URL") or dotenv_values(".env").get("DATABASE_URL")
assert BASE_DATABASE_URL, "DATABASE_URL is required for tests"

TEST_DB_NAME = os.environ.get("TEST_POSTGRES_DB", "contest_test")
_parsed = urlparse(BASE_DATABASE_URL)
TEST_DATABASE_URL = _parsed._replace(path=f"/{TEST_DB_NAME}").geturl()
TEST_SYNC_DATABASE_URL = TEST_DATABASE_URL.replace("+asyncpg", "+psycopg")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SYNC_DATABASE_URL"] = TEST_SYNC_DATABASE_URL

from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import Base, Contest, ContestStatus, Problem, Test, User, UserRole  # noqa: E402


async def _ensure_database() -> None:
    if TEST_DB_NAME == _parsed.path.lstrip("/") or TEST_DB_NAME in {"postgres", "template0", "template1"}:
        raise ValueError("Use a separate database for Judge tests")
    if not TEST_DB_NAME.isidentifier():
        raise ValueError("Invalid test database name")
    connection = await asyncpg.connect(
        user=_parsed.username,
        password=_parsed.password,
        host=_parsed.hostname,
        port=_parsed.port or 5432,
        database="postgres",
    )
    try:
        exists = await connection.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME)
        if not exists:
            await connection.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await connection.close()


async def _prepare_schema() -> None:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def prepare_database():
    asyncio.run(_ensure_database())
    asyncio.run(_prepare_schema())
    yield


@pytest_asyncio.fixture
async def db_engine(prepare_database):
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    async with db_engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE submission_test_results, verdicts, submissions, tests, problems, contests, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


async def create_user(
    db: AsyncSession,
    *,
    role: UserRole = UserRole.PARTICIPANT,
    email: str | None = None,
) -> User:
    user = User(
        email=email or f"{uuid.uuid4().hex}@example.com",
        password_hash="hash",
        name="Test User",
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_contest_and_problem(
    db: AsyncSession,
    *,
    contest_status: ContestStatus = ContestStatus.ACTIVE,
    time_limit_ms: int = 1000,
    memory_limit_mb: int = 128,
    tests: list[tuple[str, str]] | None = None,
) -> tuple[Contest, Problem, list[Test]]:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    contest = Contest(
        title="Test contest",
        description="Test",
        start_at=now - timedelta(hours=1),
        end_at=now + timedelta(hours=1),
        status=contest_status,
    )
    problem = Problem(
        contest=contest,
        title="A+B",
        statement="Read two numbers",
        time_limit_ms=time_limit_ms,
        memory_limit_mb=memory_limit_mb,
    )
    test_specs = tests if tests is not None else [("1 2\n", "3\n")]
    test_rows = [
        Test(problem=problem, input_data=input_data, expected_output=output, ordinal=index)
        for index, (input_data, output) in enumerate(test_specs, start=1)
    ]
    db.add(contest)
    db.add(problem)
    db.add_all(test_rows)
    await db.commit()
    await db.refresh(contest)
    await db.refresh(problem)
    for test_row in test_rows:
        await db.refresh(test_row)
    return contest, problem, test_rows


@pytest.fixture
def fake_judge_task(monkeypatch):
    class FakeTask:
        def __init__(self):
            self.calls: list[str] = []

        def delay(self, submission_id: str):
            self.calls.append(submission_id)
            return SimpleNamespace(id=f"fake-task-{len(self.calls)}")

    task = FakeTask()
    monkeypatch.setattr("app.modules.submissions.service.judge_submission", task)
    return task


@pytest_asyncio.fixture
async def participant(db_session) -> User:
    return await create_user(db_session, role=UserRole.PARTICIPANT)


@pytest_asyncio.fixture
async def judge_user(db_session) -> User:
    return await create_user(db_session, role=UserRole.JUDGE)


@pytest_asyncio.fixture
async def admin_user(db_session) -> User:
    return await create_user(db_session, role=UserRole.ADMIN)

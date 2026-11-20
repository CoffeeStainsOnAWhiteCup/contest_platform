import asyncio
import os
import subprocess
import sys
import uuid
from urllib.parse import urlparse

import asyncpg
import psycopg


BASE_DATABASE_URL = os.environ["DATABASE_URL"]
_PARSED = urlparse(BASE_DATABASE_URL)
MIGRATION_DB_NAME = f"contest_migration_{uuid.uuid4().hex[:8]}"


def _connection_kwargs() -> dict:
    return {
        "user": _PARSED.username,
        "password": _PARSED.password,
        "host": _PARSED.hostname,
        "port": _PARSED.port or 5432,
        "database": "postgres",
    }


async def _create_database() -> None:
    connection = await asyncpg.connect(**_connection_kwargs())
    try:
        await connection.execute(f'CREATE DATABASE "{MIGRATION_DB_NAME}"')
    finally:
        await connection.close()


async def _drop_database() -> None:
    connection = await asyncpg.connect(**_connection_kwargs())
    try:
        await connection.execute(
            f'DROP DATABASE IF EXISTS "{MIGRATION_DB_NAME}" WITH (FORCE)'
        )
    finally:
        await connection.close()


def _migration_url() -> str:
    return _PARSED._replace(path=f"/{MIGRATION_DB_NAME}").geturl()


def _sync_url() -> str:
    return _migration_url().replace("+asyncpg", "")


def _alembic_env() -> dict:
    env = os.environ.copy()
    env["DATABASE_URL"] = _migration_url()
    env["SYNC_DATABASE_URL"] = _migration_url().replace("+asyncpg", "+psycopg")
    return env


def _run_alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=os.getcwd(),
        env=_alembic_env(),
        check=True,
        capture_output=True,
        text=True,
    )


def test_problem_ordinals_are_backfilled_during_migration():
    asyncio.run(_create_database())
    try:
        _run_alembic("upgrade", "6d233f26b0ba")

        contest_id = uuid.uuid4()
        problem_ids = [uuid.uuid4(), uuid.uuid4()]
        with psycopg.connect(_sync_url()) as connection:
            connection.execute(
                """
                INSERT INTO contests
                    (id, title, description, start_at, end_at, status, created_at)
                VALUES (%s, %s, NULL, now(), now(), 'DRAFT', now())
                """,
                (contest_id, "migration contest"),
            )
            for problem_id in problem_ids:
                connection.execute(
                    """
                    INSERT INTO problems
                        (id, contest_id, title, statement, time_limit_ms, memory_limit_mb)
                    VALUES (%s, %s, %s, %s, 1000, 128)
                    """,
                    (problem_id, contest_id, "problem", "statement"),
                )
            connection.commit()

        _run_alembic("upgrade", "head")

        with psycopg.connect(_sync_url()) as connection:
            rows = connection.execute(
                "SELECT ordinal FROM problems WHERE contest_id = %s ORDER BY ordinal",
                (contest_id,),
            ).fetchall()

        assert [row[0] for row in rows] == [1, 2]
    finally:
        asyncio.run(_drop_database())

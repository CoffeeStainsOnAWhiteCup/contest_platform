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


def _insert_contest(connection, contest_id: uuid.UUID) -> None:
    connection.execute(
        """
        INSERT INTO contests
            (id, title, description, start_at, end_at, status, created_at)
        VALUES (%s, %s, NULL, now(), now(), 'DRAFT', now())
        """,
        (contest_id, "migration contest"),
    )


def _insert_problem(
    connection,
    problem_id: uuid.UUID,
    contest_id: uuid.UUID,
    *,
    ordinal: int | None = None,
) -> None:
    columns = "id, contest_id, title, statement, time_limit_ms, memory_limit_mb"
    values = [problem_id, contest_id, "problem", "statement", 1000, 128]
    if ordinal is not None:
        columns += ", ordinal"
        values.append(ordinal)
    placeholders = ", ".join(["%s"] * len(values))
    connection.execute(
        f"INSERT INTO problems ({columns}) VALUES ({placeholders})",
        values,
    )


def _insert_test(
    connection,
    problem_id: uuid.UUID,
    *,
    ordinal: int,
) -> None:
    connection.execute(
        """
        INSERT INTO tests
            (id, problem_id, input_data, expected_output, is_sample, ordinal)
        VALUES (%s, %s, '1', '1', false, %s)
        """,
        (uuid.uuid4(), problem_id, ordinal),
    )


def _constraint_names() -> set[str]:
    with psycopg.connect(_sync_url()) as connection:
        rows = connection.execute(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conname IN ('uq_problems_contest_ordinal', 'uq_tests_problem_ordinal')
            """
        ).fetchall()
    return {row[0] for row in rows}


def test_problem_ordinals_are_backfilled_from_initial_revision():
    asyncio.run(_create_database())
    try:
        _run_alembic("upgrade", "6d233f26b0ba")

        contest_id = uuid.uuid4()
        problem_ids = [uuid.uuid4(), uuid.uuid4()]
        with psycopg.connect(_sync_url()) as connection:
            _insert_contest(connection, contest_id)
            for problem_id in problem_ids:
                _insert_problem(connection, problem_id, contest_id)
            connection.commit()

        _run_alembic("upgrade", "head")

        with psycopg.connect(_sync_url()) as connection:
            rows = connection.execute(
                "SELECT ordinal FROM problems WHERE contest_id = %s ORDER BY ordinal",
                (contest_id,),
            ).fetchall()

        assert [row[0] for row in rows] == [1, 2]
        assert _constraint_names() == {
            "uq_problems_contest_ordinal",
            "uq_tests_problem_ordinal",
        }
    finally:
        asyncio.run(_drop_database())


def test_ordinals_are_reindexed_from_previous_revision():
    asyncio.run(_create_database())
    try:
        _run_alembic("upgrade", "b7e4c9a1f2d3")

        contest_id = uuid.uuid4()
        problem_ids = [uuid.uuid4(), uuid.uuid4()]
        with psycopg.connect(_sync_url()) as connection:
            _insert_contest(connection, contest_id)
            for problem_id in problem_ids:
                _insert_problem(connection, problem_id, contest_id, ordinal=0)
            _insert_test(connection, problem_ids[0], ordinal=0)
            _insert_test(connection, problem_ids[0], ordinal=0)
            connection.commit()

        _run_alembic("upgrade", "head")

        with psycopg.connect(_sync_url()) as connection:
            problem_rows = connection.execute(
                "SELECT ordinal FROM problems WHERE contest_id = %s ORDER BY ordinal",
                (contest_id,),
            ).fetchall()
            test_rows = connection.execute(
                "SELECT ordinal FROM tests WHERE problem_id = %s ORDER BY ordinal",
                (problem_ids[0],),
            ).fetchall()

        assert [row[0] for row in problem_rows] == [1, 2]
        assert [row[0] for row in test_rows] == [1, 2]
        assert _constraint_names() == {
            "uq_problems_contest_ordinal",
            "uq_tests_problem_ordinal",
        }
    finally:
        asyncio.run(_drop_database())

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


def _insert_contest(connection, contest_id: uuid.UUID, title: str) -> None:
    connection.execute(
        """
        INSERT INTO contests
            (id, title, description, start_at, end_at, status, created_at)
        VALUES (%s, %s, NULL, now(), now(), 'DRAFT', now())
        """,
        (contest_id, title),
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


def _insert_test(connection, problem_id: uuid.UUID, ordinal: int) -> None:
    connection.execute(
        """
        INSERT INTO tests
            (id, problem_id, input_data, expected_output, is_sample, ordinal)
        VALUES (%s, %s, '1', '1', false, %s)
        """,
        (uuid.uuid4(), problem_id, ordinal),
    )


def _ordinals_by_id(table: str, parent_column: str, parent_id: uuid.UUID) -> dict:
    with psycopg.connect(_sync_url()) as connection:
        rows = connection.execute(
            f"""
            SELECT id, ordinal
            FROM {table}
            WHERE {parent_column} = %s
            ORDER BY id
            """,
            (parent_id,),
        ).fetchall()
    return {row[0]: row[1] for row in rows}


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


def _assert_ordinals(table, parent_column, parent_id, expected):
    assert _ordinals_by_id(table, parent_column, parent_id) == expected


def test_problem_ordinals_are_backfilled_from_initial_revision():
    asyncio.run(_create_database())
    try:
        _run_alembic("upgrade", "6d233f26b0ba")

        contest_id = uuid.uuid4()
        first_problem = uuid.UUID(int=1)
        second_problem = uuid.UUID(int=2)
        with psycopg.connect(_sync_url()) as connection:
            _insert_contest(connection, contest_id, "migration contest")
            _insert_problem(connection, first_problem, contest_id)
            _insert_problem(connection, second_problem, contest_id)
            connection.commit()

        _run_alembic("upgrade", "head")

        _assert_ordinals(
            "problems",
            "contest_id",
            contest_id,
            {first_problem: 1, second_problem: 2},
        )
        assert _constraint_names() == {
            "uq_problems_contest_ordinal",
            "uq_tests_problem_ordinal",
        }
    finally:
        asyncio.run(_drop_database())


def test_ordinals_preserve_existing_values_and_resolve_conflicts():
    asyncio.run(_create_database())
    try:
        _run_alembic("upgrade", "b7e4c9a1f2d3")

        preserve_contest = uuid.uuid4()
        preserved_first_id = uuid.UUID(int=1)
        preserved_second_id = uuid.UUID(int=2)
        zeros_contest = uuid.uuid4()
        first_zero = uuid.UUID(int=3)
        second_zero = uuid.UUID(int=4)
        duplicates_contest = uuid.uuid4()
        first_duplicate = uuid.UUID(int=5)
        second_duplicate = uuid.UUID(int=6)
        gap_contest = uuid.uuid4()
        gap_start = uuid.UUID(int=7)
        gap_end = uuid.UUID(int=8)
        mixed_contest = uuid.uuid4()
        mixed_zero = uuid.UUID(int=9)
        mixed_duplicate_first = uuid.UUID(int=10)
        mixed_duplicate_second = uuid.UUID(int=11)

        with psycopg.connect(_sync_url()) as connection:
            _insert_contest(connection, preserve_contest, "preserve")
            _insert_problem(connection, preserved_first_id, preserve_contest, ordinal=2)
            _insert_problem(connection, preserved_second_id, preserve_contest, ordinal=1)

            _insert_contest(connection, zeros_contest, "zeros")
            _insert_problem(connection, first_zero, zeros_contest, ordinal=0)
            _insert_problem(connection, second_zero, zeros_contest, ordinal=0)

            _insert_contest(connection, duplicates_contest, "duplicates")
            _insert_problem(connection, first_duplicate, duplicates_contest, ordinal=1)
            _insert_problem(connection, second_duplicate, duplicates_contest, ordinal=1)

            _insert_contest(connection, gap_contest, "gap")
            _insert_problem(connection, gap_start, gap_contest, ordinal=0)
            _insert_problem(connection, gap_end, gap_contest, ordinal=5)

            _insert_contest(connection, mixed_contest, "mixed")
            _insert_problem(connection, mixed_zero, mixed_contest, ordinal=0)
            _insert_problem(
                connection, mixed_duplicate_first, mixed_contest, ordinal=1
            )
            _insert_problem(
                connection, mixed_duplicate_second, mixed_contest, ordinal=1
            )

            _insert_test(connection, preserved_first_id, 1)
            _insert_test(connection, preserved_first_id, 5)
            _insert_test(connection, preserved_second_id, 0)
            _insert_test(connection, preserved_second_id, 0)
            connection.commit()

        _run_alembic("upgrade", "head")

        _assert_ordinals(
            "problems",
            "contest_id",
            preserve_contest,
            {preserved_first_id: 2, preserved_second_id: 1},
        )
        _assert_ordinals(
            "problems",
            "contest_id",
            zeros_contest,
            {first_zero: 1, second_zero: 2},
        )
        _assert_ordinals(
            "problems",
            "contest_id",
            duplicates_contest,
            {first_duplicate: 1, second_duplicate: 2},
        )
        _assert_ordinals(
            "problems",
            "contest_id",
            gap_contest,
            {gap_start: 1, gap_end: 5},
        )
        _assert_ordinals(
            "problems",
            "contest_id",
            mixed_contest,
            {
                mixed_zero: 2,
                mixed_duplicate_first: 1,
                mixed_duplicate_second: 3,
            },
        )
        assert sorted(
            _ordinals_by_id("tests", "problem_id", preserved_first_id).values()
        ) == [1, 5]
        assert sorted(
            _ordinals_by_id("tests", "problem_id", preserved_second_id).values()
        ) == [1, 2]
        assert _constraint_names() == {
            "uq_problems_contest_ordinal",
            "uq_tests_problem_ordinal",
        }
    finally:
        asyncio.run(_drop_database())

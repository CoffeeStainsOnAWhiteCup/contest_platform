import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import models
from app.modules.contests.importer import append_tests, parse_file
from tests.conftest import auth_headers, create_contest_and_problem

EXAMPLES = Path(__file__).resolve().parents[1] / "docs/examples"


@pytest.mark.parametrize("suffix", ["csv", "json"])
async def test_example_upload(client, db_session, participant, judge_user, suffix):
    _, problem, _ = await create_contest_and_problem(db_session, tests=[])
    path = EXAMPLES / f"sum-tests.{suffix}"
    files = {"file": (path.name, path.read_bytes())}
    url = f"/api/v1/problems/{problem.id}/tests"
    assert (await client.post(url + "/import", files=files)).status_code == 401
    assert (await client.post(url + "/import", headers=auth_headers(participant), files=files)).status_code == 403
    response = await client.post(url + "/import", headers=auth_headers(judge_user), files=files)
    assert response.status_code == 201 and response.json() == {"imported": 2}
    saved = (await client.get(url, headers=auth_headers(judge_user))).json()
    assert [(row["ordinal"], row["input_data"], row["expected_output"], row["is_sample"]) for row in saved] == [
        (1, "1 2\n", "3\n", True),
        (2, "-1 1\n", "0\n", False),
    ]


@pytest.mark.parametrize(
    ("content", "status"),
    [
        (b"input_data,expected_output,ordinal\n,ok,2\nx,y,0", 422),
        (b"input_data,expected_output,ordinal\n,ok,2\nx,y,1", 409),
        (b"input_data,expected_output,ordinal\n,ok,2\nx,y,2", 409),
    ],
)
async def test_import_is_atomic(client, db_session, admin_user, content, status):
    _, problem, existing = await create_contest_and_problem(db_session)
    response = await client.post(
        f"/api/v1/problems/{problem.id}/tests/import",
        headers=auth_headers(admin_user),
        files={"file": ("tests.csv", content)},
    )
    assert response.status_code == status
    assert list(await db_session.scalars(select(models.Test.id))) == [existing[0].id]


async def test_concurrent_imports(db_engine, db_session):
    _, problem, _ = await create_contest_and_problem(db_session, tests=[])
    rows = parse_file("valid.csv", b"input_data,expected_output\n,ok\n")
    factory = async_sessionmaker(db_engine)
    async with factory() as a, factory() as b:
        await asyncio.gather(append_tests(a, problem.id, rows), append_tests(b, problem.id, rows))
    assert sorted(await db_session.scalars(select(models.Test.ordinal))) == [1, 2]


@pytest.mark.parametrize(
    ("name", "body", "status"),
    [
        ("bad.csv", b"input_data,input_data\nx,y\n", 422),
        ("bad.json", b'[{"input_data":"a","expected_output":"\\u0000"}]', 422),
        ("bad.json", b"[]", 422),
        ("bad.txt", b"", 415),
    ],
)
def test_invalid_import(name, body, status):
    with pytest.raises(HTTPException) as error:
        parse_file(name, body)
    assert error.value.status_code == status


async def test_import_limits_and_missing_problem(client, admin_user, db_session):
    import uuid
    from app.modules.contests.importer import MAX_BYTES, MAX_ROWS

    path = f"/api/v1/problems/{uuid.uuid4()}/tests/import"
    for body, expected in [
        (b"input_data,expected_output\na,b", 404),
        (b"x" * (MAX_BYTES + 1), 413),
        (b"input_data,expected_output\n" + b"a,b\n" * (MAX_ROWS + 1), 413),
    ]:
        response = await client.post(path, headers=auth_headers(admin_user), files={"file": ("t.csv", body)})
        assert response.status_code == expected

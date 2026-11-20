from datetime import datetime, timedelta, timezone

from app.models import models as model
from app.models.models import (
    ContestStatus,
    Language,
    Submission,
    SubmissionTestResult,
    VerdictStatus,
)
from tests.conftest import auth_headers, create_contest_and_problem


async def create_contest(client, admin) -> dict:
    now = datetime.now(timezone.utc)
    response = await client.post(
        "/api/v1/contests",
        headers=auth_headers(admin),
        json={
            "title": "Problem contest",
            "description": "Test contest",
            "start_at": (now - timedelta(hours=1)).isoformat(),
            "end_at": (now + timedelta(hours=1)).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_judge_creates_problems_with_auto_ordinal(
    client, admin_user, judge_user, participant
):
    contest = await create_contest(client, admin_user)
    payload = {
        "title": "A plus B",
        "statement": "Read two numbers",
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
    }

    first = await client.post(
        f"/api/v1/contests/{contest['id']}/problems",
        headers=auth_headers(judge_user),
        json=payload,
    )
    second = await client.post(
        f"/api/v1/contests/{contest['id']}/problems",
        headers=auth_headers(judge_user),
        json={**payload, "title": "Second problem"},
    )
    forbidden = await client.post(
        f"/api/v1/contests/{contest['id']}/problems",
        headers=auth_headers(participant),
        json={**payload, "title": "Nope"},
    )

    assert first.status_code == 201
    assert first.json()["ordinal"] == 1
    assert second.status_code == 201
    assert second.json()["ordinal"] == 2
    assert forbidden.status_code == 403


async def test_problem_detail_returns_only_samples(
    client, db_session, participant, judge_user
):
    _, problem, _ = await create_contest_and_problem(db_session)
    db_session.add_all(
        [
            model.Test(
                problem_id=problem.id,
                input_data="sample input",
                expected_output="sample output",
                is_sample=True,
                ordinal=2,
            ),
            model.Test(
                problem_id=problem.id,
                input_data="SECRET INPUT",
                expected_output="SECRET OUTPUT",
                ordinal=3,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/problems/{problem.id}",
        headers=auth_headers(participant),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["statement"] == "Read two numbers"
    assert [sample["input_data"] for sample in body["samples"]] == [
        "sample input"
    ]
    assert "SECRET INPUT" not in response.text

    tests = await client.get(
        f"/api/v1/problems/{problem.id}/tests",
        headers=auth_headers(judge_user),
    )
    assert tests.status_code == 200
    assert len(tests.json()) == 3

    forbidden = await client.get(
        f"/api/v1/problems/{problem.id}/tests",
        headers=auth_headers(participant),
    )
    assert forbidden.status_code == 403


async def test_participant_cannot_open_problem_in_draft_contest(
    client, db_session, participant, admin_user
):
    _, problem, _ = await create_contest_and_problem(
        db_session, contest_status=ContestStatus.DRAFT
    )

    participant_response = await client.get(
        f"/api/v1/problems/{problem.id}",
        headers=auth_headers(participant),
    )
    assert participant_response.status_code == 404

    admin_response = await client.get(
        f"/api/v1/problems/{problem.id}",
        headers=auth_headers(admin_user),
    )
    assert admin_response.status_code == 200


async def test_participant_cannot_open_problem_in_finished_contest(
    client, db_session, participant, admin_user
):
    _, problem, _ = await create_contest_and_problem(
        db_session, contest_status=ContestStatus.FINISHED
    )

    participant_response = await client.get(
        f"/api/v1/problems/{problem.id}",
        headers=auth_headers(participant),
    )
    assert participant_response.status_code == 404

    admin_response = await client.get(
        f"/api/v1/problems/{problem.id}",
        headers=auth_headers(admin_user),
    )
    assert admin_response.status_code == 200


async def test_duplicate_ordinals_conflict(client, admin_user):
    contest = await create_contest(client, admin_user)
    contest_id = contest["id"]
    problem_payload = {
        "title": "Duplicated problem",
        "statement": "Statement",
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
    }

    first = await client.post(
        f"/api/v1/contests/{contest_id}/problems",
        headers=auth_headers(admin_user),
        json={**problem_payload, "ordinal": 1},
    )
    assert first.status_code == 201

    duplicate_problem = await client.post(
        f"/api/v1/contests/{contest_id}/problems",
        headers=auth_headers(admin_user),
        json={**problem_payload, "title": "Duplicate", "ordinal": 1},
    )
    assert duplicate_problem.status_code == 409

    problem_id = first.json()["id"]
    first_test = await client.post(
        f"/api/v1/problems/{problem_id}/tests",
        headers=auth_headers(admin_user),
        json={"input_data": "1", "expected_output": "2", "ordinal": 1},
    )
    assert first_test.status_code == 201

    duplicate_test = await client.post(
        f"/api/v1/problems/{problem_id}/tests",
        headers=auth_headers(admin_user),
        json={"input_data": "3", "expected_output": "4", "ordinal": 1},
    )
    assert duplicate_test.status_code == 409


async def test_judge_updates_problem(client, db_session, judge_user):
    _, problem, _ = await create_contest_and_problem(db_session)

    response = await client.patch(
        f"/api/v1/problems/{problem.id}",
        headers=auth_headers(judge_user),
        json={"title": "Renamed problem", "time_limit_ms": 2000},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Renamed problem"
    assert response.json()["time_limit_ms"] == 2000


async def test_participant_cannot_manage_problem_or_tests(
    client, db_session, participant
):
    _, problem, _ = await create_contest_and_problem(db_session)

    updated = await client.patch(
        f"/api/v1/problems/{problem.id}",
        headers=auth_headers(participant),
        json={"title": "Nope"},
    )
    created = await client.post(
        f"/api/v1/problems/{problem.id}/tests",
        headers=auth_headers(participant),
        json={"input_data": "1", "expected_output": "2"},
    )
    deleted = await client.delete(
        f"/api/v1/problems/{problem.id}",
        headers=auth_headers(participant),
    )

    assert updated.status_code == 403
    assert created.status_code == 403
    assert deleted.status_code == 403


async def test_problem_delete_with_submissions_conflicts(
    client, db_session, participant, judge_user
):
    _, problem, _ = await create_contest_and_problem(db_session)
    db_session.add(
        Submission(
            user_id=participant.id,
            problem_id=problem.id,
            language=Language.PYTHON,
            code="print(1)",
        )
    )
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/problems/{problem.id}",
        headers=auth_headers(judge_user),
    )
    assert response.status_code == 409


async def test_problem_delete_without_submissions_cascades_tests(
    client, admin_user
):
    contest = await create_contest(client, admin_user)
    problem = await client.post(
        f"/api/v1/contests/{contest['id']}/problems",
        headers=auth_headers(admin_user),
        json={
            "title": "Temporary problem",
            "statement": "Statement",
            "time_limit_ms": 1000,
            "memory_limit_mb": 128,
        },
    )
    problem_id = problem.json()["id"]
    created_test = await client.post(
        f"/api/v1/problems/{problem_id}/tests",
        headers=auth_headers(admin_user),
        json={"input_data": "1", "expected_output": "2"},
    )
    assert created_test.status_code == 201

    deleted = await client.delete(
        f"/api/v1/problems/{problem_id}",
        headers=auth_headers(admin_user),
    )
    assert deleted.status_code == 204

    missing = await client.get(
        f"/api/v1/problems/{problem_id}/tests",
        headers=auth_headers(admin_user),
    )
    assert missing.status_code == 404


async def test_test_crud_and_auto_ordinal(client, admin_user, judge_user):
    contest = await create_contest(client, admin_user)
    problem = await client.post(
        f"/api/v1/contests/{contest['id']}/problems",
        headers=auth_headers(admin_user),
        json={
            "title": "Problem",
            "statement": "Statement",
            "time_limit_ms": 1000,
            "memory_limit_mb": 128,
        },
    )
    problem_id = problem.json()["id"]

    first = await client.post(
        f"/api/v1/problems/{problem_id}/tests",
        headers=auth_headers(judge_user),
        json={"input_data": "1 2\n", "expected_output": "3\n"},
    )
    second = await client.post(
        f"/api/v1/problems/{problem_id}/tests",
        headers=auth_headers(judge_user),
        json={
            "input_data": "4 5\n",
            "expected_output": "9\n",
            "is_sample": True,
        },
    )

    assert first.status_code == 201
    assert first.json()["ordinal"] == 1
    assert second.status_code == 201
    assert second.json()["ordinal"] == 2

    listed = await client.get(
        f"/api/v1/problems/{problem_id}/tests",
        headers=auth_headers(judge_user),
    )
    assert listed.status_code == 200
    assert [item["ordinal"] for item in listed.json()] == [1, 2]

    updated = await client.patch(
        f"/api/v1/problems/{problem_id}/tests/{first.json()['id']}",
        headers=auth_headers(judge_user),
        json={"expected_output": "3\n", "is_sample": True},
    )
    assert updated.status_code == 200
    assert updated.json()["is_sample"] is True

    deleted = await client.delete(
        f"/api/v1/problems/{problem_id}/tests/{second.json()['id']}",
        headers=auth_headers(judge_user),
    )
    assert deleted.status_code == 204

    remaining = await client.get(
        f"/api/v1/problems/{problem_id}/tests",
        headers=auth_headers(judge_user),
    )
    assert remaining.status_code == 200
    assert len(remaining.json()) == 1


async def test_delete_test_with_results_conflicts(
    client, db_session, participant, judge_user
):
    _, problem, tests = await create_contest_and_problem(db_session)
    submission = Submission(
        user_id=participant.id,
        problem_id=problem.id,
        language=Language.PYTHON,
        code="print(1)",
    )
    db_session.add(submission)
    await db_session.flush()
    db_session.add(
        SubmissionTestResult(
            submission_id=submission.id,
            test_id=tests[0].id,
            ordinal=1,
            status=VerdictStatus.ACCEPTED,
        )
    )
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/problems/{problem.id}/tests/{tests[0].id}",
        headers=auth_headers(judge_user),
    )
    assert response.status_code == 409


async def test_patch_rejects_null_required_fields(
    client, db_session, judge_user
):
    _, problem, tests = await create_contest_and_problem(db_session)

    for field in (
        "title",
        "statement",
        "time_limit_ms",
        "memory_limit_mb",
        "ordinal",
    ):
        response = await client.patch(
            f"/api/v1/problems/{problem.id}",
            headers=auth_headers(judge_user),
            json={field: None},
        )
        assert response.status_code == 422, (field, response.text)

    for field in ("input_data", "expected_output", "is_sample", "ordinal"):
        response = await client.patch(
            f"/api/v1/problems/{problem.id}/tests/{tests[0].id}",
            headers=auth_headers(judge_user),
            json={field: None},
        )
        assert response.status_code == 422, (field, response.text)


async def test_problem_and_test_validation(client, admin_user):
    contest = await create_contest(client, admin_user)
    invalid_problem = await client.post(
        f"/api/v1/contests/{contest['id']}/problems",
        headers=auth_headers(admin_user),
        json={
            "title": "Invalid",
            "statement": "Statement",
            "time_limit_ms": 0,
            "memory_limit_mb": 128,
        },
    )
    assert invalid_problem.status_code == 422

    problem = await client.post(
        f"/api/v1/contests/{contest['id']}/problems",
        headers=auth_headers(admin_user),
        json={
            "title": "Valid",
            "statement": "Statement",
            "time_limit_ms": 1000,
            "memory_limit_mb": 128,
        },
    )
    invalid_test = await client.post(
        f"/api/v1/problems/{problem.json()['id']}/tests",
        headers=auth_headers(admin_user),
        json={"input_data": "1", "expected_output": "2", "ordinal": 0},
    )
    assert invalid_test.status_code == 422

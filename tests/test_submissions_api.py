import uuid

from app.models.models import (
    ContestStatus,
    Language,
    Submission,
    SubmissionStatus,
    SubmissionTestResult,
    UserRole,
    Verdict,
    VerdictStatus,
)
from app.modules.auth.security import create_access_token
from tests.conftest import create_contest_and_problem, create_user


def auth_headers(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


async def test_legacy_user_header_cannot_authenticate(client, participant):
    response = await client.get("/api/v1/submissions", headers={"X-User-Id": str(participant.id)})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_create_submission_returns_202(
    client, db_session, participant, fake_judge_task
):
    _, problem, _ = await create_contest_and_problem(db_session)

    response = await client.post(
        "/api/v1/submissions",
        headers=auth_headers(participant),
        json={"problem_id": str(problem.id), "language": "python", "code": "print(1)"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["problem_id"] == str(problem.id)
    assert fake_judge_task.calls == [body["id"]]


async def test_create_submission_rejects_closed_contest(
    client, db_session, participant, fake_judge_task
):
    _, problem, _ = await create_contest_and_problem(db_session, contest_status=ContestStatus.FINISHED)

    response = await client.post(
        "/api/v1/submissions",
        headers=auth_headers(participant),
        json={"problem_id": str(problem.id), "language": "python", "code": "print(1)"},
    )

    assert response.status_code == 400
    assert fake_judge_task.calls == []


async def test_create_submission_rejects_unknown_problem(
    client, participant, fake_judge_task
):
    response = await client.post(
        "/api/v1/submissions",
        headers=auth_headers(participant),
        json={"problem_id": str(uuid.uuid4()), "language": "python", "code": "print(1)"},
    )

    assert response.status_code == 404


async def test_participant_cannot_view_foreign_submission(
    client, db_session, participant, fake_judge_task
):
    other = await create_user(db_session, role=UserRole.PARTICIPANT)
    _, problem, _ = await create_contest_and_problem(db_session)
    submission = Submission(
        user_id=other.id,
        problem_id=problem.id,
        language=Language.PYTHON,
        code="print(1)",
    )
    db_session.add(submission)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/submissions/{submission.id}",
        headers=auth_headers(participant),
    )

    assert response.status_code == 403


async def test_participant_does_not_see_hidden_test_results(
    client, db_session, participant
):
    _, problem, tests = await create_contest_and_problem(db_session)
    submission = Submission(
        user_id=participant.id,
        problem_id=problem.id,
        language=Language.PYTHON,
        code="print(1)",
        status=SubmissionStatus.ACCEPTED,
        total_tests=1,
        passed_tests=1,
    )
    db_session.add(submission)
    await db_session.flush()
    db_session.add(
        Verdict(
            submission_id=submission.id,
            status=VerdictStatus.ACCEPTED,
            time_ms=10,
            memory_kb=1024,
        )
    )
    db_session.add(
        SubmissionTestResult(
            submission_id=submission.id,
            test_id=tests[0].id,
            ordinal=1,
            status=VerdictStatus.ACCEPTED,
            time_ms=10,
            memory_kb=1024,
        )
    )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/submissions/{submission.id}",
        headers=auth_headers(participant),
    )

    assert response.status_code == 200
    assert response.json()["test_results"] == []
    assert response.json()["verdict"]["status"] == "ACCEPTED"


async def test_judge_sees_test_results(client, db_session, judge_user):
    _, problem, tests = await create_contest_and_problem(db_session)
    submission = Submission(
        user_id=judge_user.id,
        problem_id=problem.id,
        language=Language.PYTHON,
        code="print(1)",
        status=SubmissionStatus.ACCEPTED,
        total_tests=1,
        passed_tests=1,
    )
    db_session.add(submission)
    await db_session.flush()
    db_session.add(
        SubmissionTestResult(
            submission_id=submission.id,
            test_id=tests[0].id,
            ordinal=1,
            status=VerdictStatus.ACCEPTED,
            time_ms=10,
            memory_kb=1024,
        )
    )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/submissions/{submission.id}",
        headers=auth_headers(judge_user),
    )

    assert response.status_code == 200
    assert len(response.json()["test_results"]) == 1


async def test_participant_list_contains_only_own_submissions(
    client, db_session, participant, fake_judge_task
):
    other = await create_user(db_session, role=UserRole.PARTICIPANT)
    _, problem, _ = await create_contest_and_problem(db_session)
    own = Submission(
        user_id=participant.id,
        problem_id=problem.id,
        language=Language.PYTHON,
        code="print(1)",
    )
    foreign = Submission(
        user_id=other.id,
        problem_id=problem.id,
        language=Language.PYTHON,
        code="print(2)",
    )
    db_session.add_all([own, foreign])
    await db_session.commit()

    response = await client.get(
        "/api/v1/submissions",
        headers=auth_headers(participant),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == str(own.id)


async def test_judge_list_contains_all_submissions(
    client, db_session, participant, judge_user, fake_judge_task
):
    _, problem, _ = await create_contest_and_problem(db_session)
    db_session.add_all(
        [
            Submission(
                user_id=participant.id,
                problem_id=problem.id,
                language=Language.PYTHON,
                code="print(1)",
            ),
            Submission(
                user_id=judge_user.id,
                problem_id=problem.id,
                language=Language.CPP,
                code="int main(){}",
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/submissions",
        headers=auth_headers(judge_user),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2


async def test_judge_can_rejudge(
    client, db_session, participant, judge_user, fake_judge_task
):
    _, problem, _ = await create_contest_and_problem(db_session)
    submission = Submission(
        user_id=participant.id,
        problem_id=problem.id,
        language=Language.PYTHON,
        code="print(1)",
        status=SubmissionStatus.ACCEPTED,
        total_tests=1,
        passed_tests=1,
    )
    db_session.add(submission)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/submissions/{submission.id}/rejudge",
        headers=auth_headers(judge_user),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "PENDING"
    assert fake_judge_task.calls == [str(submission.id)]


async def test_participant_cannot_rejudge(
    client, db_session, participant, fake_judge_task
):
    _, problem, _ = await create_contest_and_problem(db_session)
    submission = Submission(
        user_id=participant.id,
        problem_id=problem.id,
        language=Language.PYTHON,
        code="print(1)",
        status=SubmissionStatus.ACCEPTED,
    )
    db_session.add(submission)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/submissions/{submission.id}/rejudge",
        headers=auth_headers(participant),
    )

    assert response.status_code == 403


async def test_rejudge_rejects_running_submission(
    client, db_session, participant, judge_user, fake_judge_task
):
    _, problem, _ = await create_contest_and_problem(db_session)
    submission = Submission(
        user_id=participant.id,
        problem_id=problem.id,
        language=Language.PYTHON,
        code="print(1)",
        status=SubmissionStatus.RUNNING,
    )
    db_session.add(submission)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/submissions/{submission.id}/rejudge",
        headers=auth_headers(judge_user),
    )

    assert response.status_code == 409

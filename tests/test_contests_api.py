import uuid
from datetime import datetime, timedelta, timezone

from app.models.models import Contest, ContestStatus, Language, Submission
from tests.conftest import auth_headers


def contest_payload(**overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "title": "Autumn Cup",
        "description": "Programming contest",
        "start_at": (now - timedelta(hours=1)).isoformat(),
        "end_at": (now + timedelta(hours=1)).isoformat(),
    }
    payload.update(overrides)
    return payload


async def create_contest_row(
    db,
    *,
    status: ContestStatus,
    title: str,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> Contest:
    now = datetime.now(timezone.utc)
    contest = Contest(
        title=title,
        description="Test contest",
        start_at=start_at or now - timedelta(hours=1),
        end_at=end_at or now + timedelta(hours=1),
        status=status,
    )
    db.add(contest)
    await db.commit()
    await db.refresh(contest)
    return contest


async def test_participant_sees_only_published_and_active(
    client, db_session, participant
):
    for status in ContestStatus:
        await create_contest_row(
            db_session, status=status, title=status.value
        )

    response = await client.get(
        "/api/v1/contests", headers=auth_headers(participant)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["status"] for item in body["items"]} == {
        "published",
        "active",
    }


async def test_guest_can_list_and_open_published_active_contests(
    client, db_session
):
    published = await create_contest_row(
        db_session, status=ContestStatus.PUBLISHED, title="Public"
    )
    draft = await create_contest_row(
        db_session, status=ContestStatus.DRAFT, title="Draft"
    )
    finished = await create_contest_row(
        db_session, status=ContestStatus.FINISHED, title="Finished"
    )

    listed = await client.get("/api/v1/contests")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == str(published.id)

    detail = await client.get(f"/api/v1/contests/{published.id}")
    assert detail.status_code == 200

    for contest in (draft, finished):
        hidden = await client.get(f"/api/v1/contests/{contest.id}")
        assert hidden.status_code == 404


async def test_admin_sees_all_contests_and_filters_by_status(
    client, db_session, admin_user
):
    for status in ContestStatus:
        await create_contest_row(
            db_session, status=status, title=status.value
        )

    response = await client.get(
        "/api/v1/contests", headers=auth_headers(admin_user)
    )
    assert response.status_code == 200
    assert response.json()["total"] == 5

    filtered = await client.get(
        "/api/v1/contests?status=active",
        headers=auth_headers(admin_user),
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["status"] == "active"


async def test_admin_creates_updates_and_deletes_contest(client, admin_user):
    created = await client.post(
        "/api/v1/contests",
        headers=auth_headers(admin_user),
        json=contest_payload(),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "draft"
    assert body["can_submit"] is False

    updated = await client.patch(
        f"/api/v1/contests/{body['id']}",
        headers=auth_headers(admin_user),
        json={"title": "Renamed Cup", "status": "active"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Renamed Cup"
    assert updated.json()["status"] == "active"
    assert updated.json()["can_submit"] is True

    deleted = await client.delete(
        f"/api/v1/contests/{body['id']}",
        headers=auth_headers(admin_user),
    )
    assert deleted.status_code == 204

    missing = await client.get(
        f"/api/v1/contests/{body['id']}",
        headers=auth_headers(admin_user),
    )
    assert missing.status_code == 404


async def test_participant_and_judge_cannot_manage_contest(
    client, db_session, participant, judge_user
):
    contest = await create_contest_row(
        db_session, status=ContestStatus.DRAFT, title="Draft"
    )

    for user in (participant, judge_user):
        created = await client.post(
            "/api/v1/contests",
            headers=auth_headers(user),
            json=contest_payload(title=f"By {user.role.value}"),
        )
        assert created.status_code == 403

        updated = await client.patch(
            f"/api/v1/contests/{contest.id}",
            headers=auth_headers(user),
            json={"title": "Nope"},
        )
        assert updated.status_code == 403

        deleted = await client.delete(
            f"/api/v1/contests/{contest.id}",
            headers=auth_headers(user),
        )
        assert deleted.status_code == 403


async def test_contest_date_validation(client, db_session, admin_user):
    now = datetime.now(timezone.utc)
    invalid = await client.post(
        "/api/v1/contests",
        headers=auth_headers(admin_user),
        json=contest_payload(
            start_at=(now + timedelta(hours=1)).isoformat(),
            end_at=now.isoformat(),
        ),
    )
    assert invalid.status_code == 422

    contest = await create_contest_row(
        db_session, status=ContestStatus.DRAFT, title="Valid"
    )
    updated = await client.patch(
        f"/api/v1/contests/{contest.id}",
        headers=auth_headers(admin_user),
        json={"start_at": (now + timedelta(hours=2)).isoformat()},
    )
    assert updated.status_code == 422


async def test_contest_patch_rejects_null_required_fields(
    client, db_session, admin_user
):
    contest = await create_contest_row(
        db_session, status=ContestStatus.DRAFT, title="Valid"
    )

    for field in ("title", "start_at", "end_at", "status"):
        response = await client.patch(
            f"/api/v1/contests/{contest.id}",
            headers=auth_headers(admin_user),
            json={field: None},
        )
        assert response.status_code == 422, (field, response.text)


async def test_participant_cannot_open_draft_contest(
    client, db_session, participant, admin_user
):
    contest = await create_contest_row(
        db_session, status=ContestStatus.DRAFT, title="Hidden draft"
    )

    participant_response = await client.get(
        f"/api/v1/contests/{contest.id}",
        headers=auth_headers(participant),
    )
    assert participant_response.status_code == 404

    admin_response = await client.get(
        f"/api/v1/contests/{contest.id}",
        headers=auth_headers(admin_user),
    )
    assert admin_response.status_code == 200


async def test_finished_contest_hidden_from_participant(
    client, db_session, participant, admin_user
):
    contest = await create_contest_row(
        db_session, status=ContestStatus.FINISHED, title="Finished"
    )

    participant_response = await client.get(
        f"/api/v1/contests/{contest.id}",
        headers=auth_headers(participant),
    )
    assert participant_response.status_code == 404

    admin_response = await client.get(
        f"/api/v1/contests/{contest.id}",
        headers=auth_headers(admin_user),
    )
    assert admin_response.status_code == 200
    assert admin_response.json()["can_submit"] is False


async def test_contest_detail_includes_sorted_problems(
    client, admin_user, participant
):
    contest = (
        await client.post(
            "/api/v1/contests",
            headers=auth_headers(admin_user),
            json=contest_payload(status="active"),
        )
    ).json()

    first = await client.post(
        f"/api/v1/contests/{contest['id']}/problems",
        headers=auth_headers(admin_user),
        json={
            "title": "A plus B",
            "statement": "Read two numbers",
            "time_limit_ms": 1000,
            "memory_limit_mb": 128,
        },
    )
    second = await client.post(
        f"/api/v1/contests/{contest['id']}/problems",
        headers=auth_headers(admin_user),
        json={
            "title": "Reverse string",
            "statement": "Reverse the input",
            "time_limit_ms": 2000,
            "memory_limit_mb": 256,
        },
    )

    assert first.status_code == 201
    assert first.json()["ordinal"] == 1
    assert second.status_code == 201
    assert second.json()["ordinal"] == 2

    response = await client.get(
        f"/api/v1/contests/{contest['id']}",
        headers=auth_headers(participant),
    )
    assert response.status_code == 200
    assert [item["title"] for item in response.json()["problems"]] == [
        "A plus B",
        "Reverse string",
    ]


async def test_delete_contest_with_submissions_conflicts(
    client, db_session, admin_user, participant
):
    contest = await create_contest_row(
        db_session, status=ContestStatus.ACTIVE, title="With submission"
    )
    problem = await client.post(
        f"/api/v1/contests/{contest.id}/problems",
        headers=auth_headers(admin_user),
        json={
            "title": "Problem",
            "statement": "Statement",
            "time_limit_ms": 1000,
            "memory_limit_mb": 128,
        },
    )
    submission = Submission(
        user_id=participant.id,
        problem_id=uuid.UUID(problem.json()["id"]),
        language=Language.PYTHON,
        code="print(1)",
    )
    db_session.add(submission)
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/contests/{contest.id}",
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 409

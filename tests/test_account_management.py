from sqlalchemy import select

from app.models.models import UserAudit, UserRole
from app.modules.auth.security import create_access_token
from tests.conftest import create_user
from tests.test_auth_sessions import AUTH, CREDS, login, rotate


def auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_profile_role_block_and_audit(client, db_session, admin_user):
    await client.post(AUTH + "/register", json={**CREDS, "name": "Local name"})
    registered = await login(client)
    headers = auth(registered["access_token"])
    admin = auth(create_access_token(admin_user.id))
    profile = (await client.get("/api/v1/users/me", headers=headers)).json()
    path = "/api/v1/users/" + profile["id"]
    assert (await client.get("/api/v1/users", headers=headers)).status_code == 403
    assert (
        await client.patch(path + "/role", json={"role": "admin"}, headers=headers)
    ).status_code == 403
    result = await client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"name": " Changed ", "avatar_url": "https://example.org/a.png"},
    )
    assert result.json()["name"] == "Changed" and result.json()["avatar_url"].endswith("a.png")
    assert (
        await client.patch("/api/v1/users/me", headers=headers, json={"role": "admin"})
    ).status_code == 422
    assert (
        await client.patch("/api/v1/users/me", headers=headers, json={"avatar_url": None})
    ).json()["avatar_url"] is None
    assert (await client.get("/api/v1/users", headers=admin)).status_code == 200
    assert (await client.patch(path + "/role", headers=admin, json={"role": "judge"})).json()[
        "role"
    ] == "judge"
    assert (await client.get("/api/v1/users/me", headers=headers)).json()["role"] == "judge"
    assert (await client.patch(path + "/block", headers=admin, json={"is_blocked": True})).json()[
        "is_blocked"
    ]
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 403
    assert (await client.post(AUTH + "/login", json=CREDS)).status_code == 403
    assert (await rotate(client, registered["refresh_token"])).status_code == 403
    assert not (
        await client.patch(path + "/block", headers=admin, json={"is_blocked": False})
    ).json()["is_blocked"]
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 401
    assert (await rotate(client, registered["refresh_token"])).status_code == 401
    assert (await client.post(AUTH + "/login", json=CREDS)).status_code == 200
    changes = (await db_session.scalars(select(UserAudit).order_by(UserAudit.id))).all()
    assert [row.field for row in changes] == ["role", "is_blocked", "is_blocked"]
    assert all(row.actor_id == admin_user.id for row in changes)


async def test_admin_cannot_block_or_demote_self(client, db_session, admin_user):
    admin_id = admin_user.id
    admin = auth(create_access_token(admin_id))
    blocked = await client.patch(
        f"/api/v1/users/{admin_id}/block", headers=admin, json={"is_blocked": True}
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Cannot block your own account"
    demoted = await client.patch(
        f"/api/v1/users/{admin_id}/role", headers=admin, json={"role": "participant"}
    )
    assert demoted.status_code == 409
    assert demoted.json()["detail"] == "Cannot remove the last active administrator"


async def test_admin_can_demote_self_when_another_admin_exists(
    client, db_session, admin_user
):
    second_id = (await create_user(db_session, role=UserRole.ADMIN)).id
    admin_id = admin_user.id
    response = await client.patch(
        f"/api/v1/users/{admin_id}/role",
        headers=auth(create_access_token(admin_id)),
        json={"role": "participant"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "participant"
    second = auth(create_access_token(second_id))
    assert (await client.get("/api/v1/users", headers=second)).status_code == 200
    last = await client.patch(
        f"/api/v1/users/{second_id}/role", headers=second, json={"role": "participant"}
    )
    assert last.status_code == 409
    assert last.json()["detail"] == "Cannot remove the last active administrator"


async def test_admin_can_demote_another_admin(client, db_session, admin_user):
    other_id = (await create_user(db_session, role=UserRole.ADMIN)).id
    admin_id = admin_user.id
    response = await client.patch(
        f"/api/v1/users/{other_id}/role",
        headers=auth(create_access_token(admin_id)),
        json={"role": "participant"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "participant"

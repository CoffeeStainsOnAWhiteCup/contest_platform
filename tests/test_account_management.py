from sqlalchemy import select

from app.models.models import UserAudit
from app.modules.auth.security import create_access_token
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

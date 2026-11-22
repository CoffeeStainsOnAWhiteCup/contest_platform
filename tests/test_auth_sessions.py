import asyncio
import base64
import hashlib
import uuid
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.modules.auth.github import github_client
from app.modules.auth.sessions import LIFETIME, session_key

AUTH = "/api/v1/auth"
GITHUB = AUTH + "/github"
CREDS = {"email": "first@example.com", "password": "Password123!"}


async def login(client):
    res = await client.post(AUTH + "/login", json=CREDS)
    assert res.status_code == 200
    return res.json()


@pytest.fixture
async def registered(client):
    res = await client.post(AUTH + "/register", json={**CREDS, "name": "First"})
    assert res.status_code == 201
    return await login(client)


async def rotate(client, token):
    return await client.post(AUTH + "/refresh", json={"refresh_token": token})


async def test_refresh_and_logout(client, registered):
    original = registered["refresh_token"]
    async with Redis.from_url(settings.REDIS_URL, decode_responses=True) as redis:
        key = session_key(original.split(".")[0])
        assert LIFETIME - 5 <= await redis.ttl(key) <= LIFETIME
        assert original not in str(await redis.hgetall(key))
    rotated = await rotate(client, original)
    assert rotated.status_code == 200
    renewed = rotated.json()
    assert renewed["access_token"] != registered["access_token"]
    assert renewed["refresh_token"] != original
    assert rotated.headers["cache-control"] == "no-store"
    result = await client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer " + renewed["access_token"]}
    )
    assert result.json()["email"] == CREDS["email"]
    independent = await login(client)
    assert (
        await client.post(AUTH + "/logout", json={"refresh_token": renewed["refresh_token"]})
    ).status_code == 204
    assert (await rotate(client, renewed["refresh_token"])).status_code == 401
    assert (await rotate(client, independent["refresh_token"])).status_code == 200


async def test_concurrent_refresh_replay_revokes_family(client, registered, db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def separate_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = separate_session
    attempts = await asyncio.gather(
        rotate(client, registered["refresh_token"]), rotate(client, registered["refresh_token"])
    )
    assert sorted(r.status_code for r in attempts) == [200, 401]
    winner = next(r for r in attempts if r.status_code == 200)
    assert (await rotate(client, winner.json()["refresh_token"])).status_code == 401


async def test_invalid_secret_and_expiry(client, registered):
    family = registered["refresh_token"].split(".")[0]
    assert (await rotate(client, family + "." + "z" * 43)).status_code == 401
    rotated = await rotate(client, registered["refresh_token"])
    assert rotated.status_code == 200
    async with Redis.from_url(settings.REDIS_URL) as redis:
        await redis.pexpire(session_key(family), 1)
    await asyncio.sleep(0.02)
    assert (await rotate(client, rotated.json()["refresh_token"])).status_code == 401


async def test_ip_limit_covers_auth_and_submissions(client):
    for i in range(10):
        path = GITHUB + "/exchange" if i % 2 else "/api/v1/submissions"
        res = await client.request("POST" if i % 2 else "GET", path)
        assert res.status_code == 401
    blocked = await client.get("/api/v1/submissions")
    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["retry-after"]) <= 60


async def test_user_submission_limit_across_peers(client, registered):
    headers = {"Authorization": "Bearer " + registered["access_token"]}
    body = {"language": "python", "code": "print(1)", "problem_id": str(uuid.uuid4())}
    for i in range(11):
        transport = httpx.ASGITransport(app=app, client=(uuid.uuid4().hex, 12345))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as peer:
            result = await peer.post("/api/v1/submissions", headers=headers, json=body)
        assert result.status_code == (429 if i == 10 else 404)


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "example-client")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_SECRET", SecretStr("fixture-secret"))
    scenario = {
        "email": "example@example.com",
        "verified": True,
        "name": "Student",
        "challenge": "",
    }

    def respond(request):
        if request.url.path == "/login/oauth/access_token":
            args = parse_qs(request.content.decode())
            hashed = hashlib.sha256(args["code_verifier"][0].encode()).digest()
            assert base64.urlsafe_b64encode(hashed).decode().rstrip("=") == scenario["challenge"]
            if "error" in scenario:
                return httpx.Response(
                    scenario.get("status", 200), json={"error": scenario["error"]}
                )
            return httpx.Response(200, json={"access_token": "provider-token"})
        assert request.headers["Authorization"] == "Bearer provider-token"
        if request.url.path == "/user":
            return httpx.Response(
                200, json={"id": 1234, "login": "student", "name": scenario["name"]}
            )
        assert request.url.path == "/user/emails"
        return httpx.Response(
            200,
            json=[{"email": scenario["email"], "verified": scenario["verified"], "primary": True}],
        )

    async def mock_client():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as upstream:
            yield upstream

    app.dependency_overrides[github_client] = mock_client
    yield scenario
    app.dependency_overrides.pop(github_client, None)


async def begin(client, provider):
    res = await client.get(GITHUB)
    assert res.status_code == 302
    location = urlsplit(res.headers["location"])
    assert location.hostname == "github.com"
    args = parse_qs(location.query)
    assert args["code_challenge_method"] == ["S256"]
    assert args["scope"] == ["read:user user:email"]
    provider["challenge"] = args["code_challenge"][0]
    return {"state": args["state"][0], "code": "code"}


async def test_oauth_callback_and_frontend_exchange(client, provider):
    async def signin():
        flow = await begin(client, provider)
        callback = await client.get(GITHUB + "/callback", params=flow)
        assert callback.status_code == 303
        assert callback.headers["location"] == settings.GITHUB_FRONTEND_URL
        assert "HttpOnly" in callback.headers["set-cookie"]
        pair = await client.post(GITHUB + "/exchange")
        assert pair.status_code == 200 and pair.json()["refresh_token"]
        me = await client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer " + pair.json()["access_token"]}
        )
        return me.json()

    first = await signin()
    assert first["email"] == provider["email"] and first["role"] == "participant"
    assert (await client.post(GITHUB + "/exchange")).status_code == 401
    provider["name"] = "New name"
    second = await signin()
    assert second["name"] == "New name" and second["id"] == first["id"]


async def test_oauth_denial_and_state_binding(client, provider):
    flow = await begin(client, provider)
    transport = httpx.ASGITransport(app=app, client=(uuid.uuid4().hex, 12345))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as other_browser:
        assert (await other_browser.get(GITHUB + "/callback", params=flow)).status_code == 400
    denied = await client.get(GITHUB + "/callback", params={**flow, "error": "access_denied"})
    assert denied.status_code == 403
    assert (await client.get(GITHUB + "/callback", params=flow)).status_code == 400


@pytest.mark.parametrize(
    "scenario,status,detail",
    [
        ({"error": "bad_verification_code"}, 400, "INVALID_OAUTH_CODE"),
        ({"error": "incorrect_client_credentials"}, 401, "OAUTH_CONFIG_ERROR"),
        ({"status": 503, "error": "unavailable"}, 502, "OAUTH_PROVIDER_UNAVAILABLE"),
        ({"verified": False}, 403, "OAUTH_VERIFIED_EMAIL_REQUIRED"),
        ({"email": CREDS["email"]}, 409, "OAUTH_EMAIL_CONFLICT"),
    ],
)
async def test_oauth_errors(client, provider, registered, scenario, status, detail):
    provider.update(scenario)
    flow = await begin(client, provider)
    res = await client.get(GITHUB + "/callback", params=flow)
    assert res.status_code == status
    assert res.json()["detail"] == detail
    assert (await client.post(GITHUB + "/exchange")).status_code == 401


async def test_redis_outage_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "REDIS_URL", "redis://127.0.0.1:1/0")
    response = await client.post(AUTH + "/login", json=CREDS)
    assert response.status_code == 503


async def test_old_requests_leave_sliding_window():
    import time

    from app.core.rate_limit import limit

    bucket = "test:" + uuid.uuid4().hex
    key = "contest:limit:" + bucket
    async with Redis.from_url(settings.REDIS_URL) as redis:
        try:
            now = int(time.time() * 1000)
            await redis.zadd(key, {str(i): now - 61000 for i in range(10)})
            await limit(redis, bucket)
            assert await redis.zcard(key) == 1
        finally:
            await redis.delete(key)


async def test_oauth_block_between_callback_and_exchange(client, provider, admin_user):
    from app.modules.auth.security import create_access_token

    admin = {"Authorization": f"Bearer {create_access_token(admin_user.id)}"}
    flow = await begin(client, provider)
    assert (await client.get(GITHUB + "/callback", params=flow)).status_code == 303
    accounts = (await client.get("/api/v1/users", headers=admin)).json()
    uid = next(a["id"] for a in accounts if a["email"] == provider["email"])
    await client.patch(f"/api/v1/users/{uid}/block", headers=admin, json={"is_blocked": True})
    assert (await client.post(GITHUB + "/exchange")).status_code == 403
    flow = await begin(client, provider)
    assert (await client.get(GITHUB + "/callback", params=flow)).status_code == 403

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.config import Settings, settings
from app.core.database import get_db
from app.core.rate_limit import get_redis, limit_ip
from app.models.models import User, UserRole
from app.modules.auth.router import router
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.security import create_access_token, decode_access_token, hash_password, verify_password
from app.modules.auth.service import register_user
from app.modules.users.router import router as users_router


def user(role=UserRole.PARTICIPANT):
    return User(id=uuid.uuid4(), email="student@example.com", name="Student", role=role,
                password_hash=hash_password("Password123!"))


@pytest.fixture
def api():
    db = AsyncMock(spec=AsyncSession)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")

    async def override_db():
        yield db

    redis = MagicMock()
    pipe = MagicMock()
    redis.pipeline.return_value.__aenter__.return_value = pipe
    pipe.execute = AsyncMock()
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[limit_ip] = lambda: None
    app.dependency_overrides[get_db] = override_db

    @app.get("/admin-only")
    async def admin_only(current_user=Depends(require_roles(UserRole.ADMIN))):
        return {"id": str(current_user.id)}

    with TestClient(app) as client:
        yield client, db


def test_password_hashing():
    first = hash_password("Password123!")
    second = hash_password("Password123!")
    assert first.startswith("$argon2id$")
    assert first != second
    assert verify_password("Password123!", first)
    assert not verify_password("wrong", first)
    assert not verify_password("wrong", "legacy-invalid-hash")


def test_token_roundtrip():
    identity = uuid.uuid4()
    assert decode_access_token(create_access_token(identity)) == identity


@pytest.mark.parametrize("change", ["expired", "signature", "algorithm", "subject", "type", "audience", "issuer", "missing_exp"])
def test_invalid_tokens_are_rejected(change):
    now = datetime.now(timezone.utc)
    payload = {"sub": str(uuid.uuid4()), "iat": now, "exp": now + timedelta(minutes=5),
               "iss": settings.JWT_ISSUER, "aud": settings.JWT_AUDIENCE, "type": "access"}
    key = settings.JWT_SECRET_KEY.get_secret_value()
    algorithm = "HS256"
    if change == "expired":
        payload["exp"] = now - timedelta(minutes=1)
    elif change == "signature":
        key = "another-test-key-with-more-than-32-characters"
    elif change == "algorithm":
        algorithm = "HS384"
    elif change == "subject":
        payload["sub"] = "not-a-uuid"
    elif change == "type":
        payload["type"] = "refresh"
    elif change == "audience":
        payload["aud"] = "another-api"
    elif change == "issuer":
        payload["iss"] = "another-issuer"
    else:
        del payload["exp"]
    with pytest.raises(InvalidTokenError):
        decode_access_token(jwt.encode(payload, key, algorithm=algorithm))


def test_short_secret_rejected():
    with pytest.raises(ValidationError):
        Settings(JWT_SECRET_KEY="short")


@pytest.fixture(params=["/api/v1/users/me", "/api/v1/auth/me"])
def profile_url(request):
    return request.param


def test_me_missing_token_and_spoofed_header(api, profile_url):
    client, db = api
    response = client.get(profile_url, headers={"X-User-Id": str(uuid.uuid4())})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    db.get.assert_not_awaited()


@pytest.mark.parametrize("header", ["Bearer invalid", "Basic abc", "Bearer"])
def test_me_bad_credentials(api, header, profile_url):
    client, db = api
    assert client.get(profile_url, headers={"Authorization": header}).status_code == 401
    db.get.assert_not_awaited()


def test_me_reads_user_from_database(api, profile_url):
    client, db = api
    current = user()
    db.get.return_value = current
    response = client.get(profile_url, headers={"Authorization": f"Bearer {create_access_token(current.id)}"})
    assert response.status_code == 200
    assert response.json() == {"id": str(current.id), "email": current.email, "name": current.name, "role": "participant"}
    db.get.assert_awaited_once_with(User, current.id)


def test_deleted_user_token_rejected(api, profile_url):
    client, db = api
    db.get.return_value = None
    assert client.get(profile_url, headers={"Authorization": f"Bearer {create_access_token(uuid.uuid4())}"}).status_code == 401


@pytest.mark.parametrize("role, expected", [(UserRole.PARTICIPANT, 403), (UserRole.JUDGE, 403), (UserRole.ADMIN, 200)])
def test_roles_use_database_role(api, role, expected):
    client, db = api
    current = user(role)
    db.get.return_value = current
    response = client.get("/admin-only", headers={"Authorization": f"Bearer {create_access_token(current.id)}"})
    assert response.status_code == expected


def test_login_success(api):
    client, db = api
    current = user()
    db.scalar.return_value = current
    response = client.post("/api/v1/auth/login", json={"email": " Student@Example.com ", "password": "Password123!"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert decode_access_token(response.json()["access_token"]) == current.id
    assert response.json()["expires_in"] == 1800


@pytest.mark.parametrize("exists", [True, False])
def test_wrong_password_and_unknown_email_same_response(api, exists):
    client, db = api
    db.scalar.return_value = user() if exists else None
    response = client.post("/api/v1/auth/login", json={"email": "student@example.com", "password": "wrong"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


@pytest.mark.parametrize("update", [
    {"role": "admin"}, {"password": "short"}, {"email": "bad"}, {"name": "   "},
    {"password": "abcdefgh"}, {"password": "12345678"}, {"password": "!!!!!!!!"},
    {"password": "a" + "1" * 128},
])
def test_registration_validation(api, update):
    client, db = api
    payload = {"email": "student@example.com", "name": "Student", "password": "Password123!", **update}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 422
    db.add.assert_not_called()


@pytest.mark.parametrize("password", ["abcdefg1", "a" + "1" * 127, "Пароль123", "abc 1234"])
def test_password_policy_accepts_valid_boundaries_and_preserves_value(password):
    payload = RegisterRequest(email="student@example.com", name="Student", password=password)
    assert payload.password.get_secret_value() == password


def test_openapi_exposes_canonical_and_compatibility_profile_routes(api):
    client, _ = api
    paths = client.get("/openapi.json").json()["paths"]
    assert paths["/api/v1/users/me"]["get"]["security"] == [{"HTTPBearer": []}]
    assert paths["/api/v1/auth/me"]["get"]["deprecated"] is True


def test_registration_success(api):
    client, db = api
    db.scalar.return_value = None

    async def assign_id(value):
        value.id = uuid.uuid4()

    db.refresh.side_effect = assign_id
    response = client.post("/api/v1/auth/register", json={"email": " Student@Example.com ", "name": " Student ", "password": "Password123!"})
    assert response.status_code == 201
    saved = db.add.call_args.args[0]
    assert saved.email == "student@example.com"
    assert saved.name == "Student"
    assert saved.role == UserRole.PARTICIPANT
    assert verify_password("Password123!", saved.password_hash)
    assert set(response.json()) == {"id", "email", "name", "role"}
    db.commit.assert_awaited_once()


def test_duplicate_registration(api):
    client, db = api
    db.scalar.return_value = user()
    response = client.post("/api/v1/auth/register", json={"email": "student@example.com", "name": "Student", "password": "Password123!"})
    assert response.status_code == 409
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_concurrent_duplicate_rolls_back():
    db = AsyncMock(spec=AsyncSession)
    db.scalar.side_effect = [None, user()]
    db.commit.side_effect = IntegrityError("insert", {}, Exception("unique constraint"))
    payload = RegisterRequest(email="student@example.com", name="Student", password="Password123!")
    with pytest.raises(HTTPException) as error:
        await register_user(db, payload)
    assert error.value.status_code == 409
    db.rollback.assert_awaited_once()

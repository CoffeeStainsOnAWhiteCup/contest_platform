"""Real PostgreSQL tests. Each test owns a new randomly named schema.

Set AUTH_TEST_DATABASE_URL to a local development PostgreSQL connection URL.
Existing application tables and schemas are not modified.
"""
import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import get_db
from app.main import app
from app.models.models import Base, User
from app.modules.auth.security import verify_password


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def postgres_api():
    url = os.environ.get("AUTH_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set AUTH_TEST_DATABASE_URL to run real PostgreSQL tests")
    schema = "auth_test_" + uuid.uuid4().hex
    control = create_async_engine(url, poolclass=NullPool)
    scoped = create_async_engine(url, poolclass=NullPool, connect_args={"server_settings": {"search_path": schema}})
    factory = async_sessionmaker(scoped, expire_on_commit=False)
    async with control.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        async with scoped.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async def override_db():
            async with factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        async with AsyncClient(transport=ASGITransport(app=app, client=(f"test-{uuid.uuid4().hex}", 12345)), base_url="http://test") as client:
            yield client, factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        await scoped.dispose()
        async with control.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await control.dispose()


async def test_register_login_me_and_duplicate(postgres_api):
    client, factory = postgres_api
    credentials = {"email": "Student@Example.com", "password": "Password123!"}
    registered = await client.post("/api/v1/auth/register", json={**credentials, "name": "Student"})
    assert registered.status_code == 201
    identity = registered.json()["id"]
    async with factory() as session:
        saved = await session.scalar(select(User).where(User.email == "student@example.com"))
        assert saved is not None
        assert verify_password("Password123!", saved.password_hash)
    duplicate = await client.post("/api/v1/auth/register", json={**credentials, "email": "student@example.com", "name": "Other"})
    assert duplicate.status_code == 409
    login = await client.post("/api/v1/auth/login", json=credentials)
    assert login.status_code == 200
    me = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer " + login.json()["access_token"]})
    assert me.status_code == 200
    assert me.json()["id"] == identity
    assert me.json()["role"] == "participant"
    assert "password_hash" not in me.json()
    compatibility = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + login.json()["access_token"]})
    assert compatibility.status_code == 200
    assert compatibility.json() == me.json()


async def test_two_users_receive_their_own_profile(postgres_api):
    client, _ = postgres_api
    for name in ["first", "second"]:
        credentials = {"email": f"{name}@example.com", "password": "Password123!"}
        registered = await client.post("/api/v1/auth/register", json={**credentials, "name": name})
        assert registered.status_code == 201
        login = await client.post("/api/v1/auth/login", json=credentials)
        me = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer " + login.json()["access_token"]})
        assert me.status_code == 200
        assert me.json()["id"] == registered.json()["id"]


async def test_old_hash_upgrades_only_after_successful_login(postgres_api):
    from pwdlib import PasswordHash

    client, factory = postgres_api
    email, password = "legacy@example.com", "LegacyPass123"
    old_hash = PasswordHash.recommended().hash(password)
    async with factory.begin() as db:
        db.add(User(email=email, name="Legacy", password_hash=old_hash))
    for candidate, expected_status in [("wrong", 401), (password, 200)]:
        response = await client.post("/api/v1/auth/login", json={"email": email, "password": candidate})
        assert response.status_code == expected_status
        async with factory() as db:
            saved = await db.scalar(select(User.password_hash).where(User.email == email))
        if expected_status == 401:
            assert saved == old_hash
        else:
            assert saved.startswith("$bcrypt-sha256$v=2,t=2b,r=12$")
            assert verify_password(password, saved)

import base64
import hashlib
import logging
import secrets
import uuid
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import get_redis
from app.models.models import User, UserRole
from app.modules.auth.schemas import TokenResponse
from app.modules.auth.service import get_user_by_email
from app.modules.auth.sessions import digest, start_session

router = APIRouter(prefix="/github")
logger = logging.getLogger(__name__)
STATE_COOKIE = "contest_oauth_browser"
TICKET_COOKIE = "contest_oauth_ticket"
CALLBACK = "/api/v1/auth/github/callback"
EXCHANGE = "/api/v1/auth/github/exchange"
PRIVATE_HEADERS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}


class Identity(BaseModel):
    id: int = Field(gt=0)
    login: str = Field(min_length=1)
    name: str | None = None


class Address(BaseModel):
    email: EmailStr = Field(max_length=255)
    primary: bool
    verified: bool


def configured():
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(503, "OAUTH_CONFIG_ERROR")


def set_cookie(response: Response, name: str, value: str, path: str, ttl: int):
    response.set_cookie(
        name,
        value,
        path=path,
        max_age=ttl,
        httponly=True,
        samesite="lax",
        secure=settings.GITHUB_CALLBACK_URL.startswith("https://"),
    )


def state_key(state: str, browser: str) -> str:
    return "contest:github:state:" + digest(state + "." + browser)


@router.get("", response_class=RedirectResponse, status_code=302)
async def authorize(redis: Annotated[Redis, Depends(get_redis)]):
    configured()
    state, browser, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    await redis.set(state_key(state, browser), verifier, ex=600)
    query = urlencode(
        {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_CALLBACK_URL,
            "scope": "read:user user:email",
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
    )
    response = RedirectResponse(
        "https://github.com/login/oauth/authorize?" + query, 302, headers=PRIVATE_HEADERS
    )
    set_cookie(response, STATE_COOKIE, browser, CALLBACK, 600)
    return response


async def github_client():
    async with httpx.AsyncClient(timeout=8, headers={"Accept": "application/json"}) as client:
        yield client


async def fetch_identity(
    client: httpx.AsyncClient, code: str, verifier: str
) -> tuple[Identity, str]:
    try:
        token = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET.get_secret_value(),
                "redirect_uri": settings.GITHUB_CALLBACK_URL,
                "code": code,
                "code_verifier": verifier,
            },
        )
        if token.status_code >= 500:
            token.raise_for_status()
        data = token.json()
        if token.status_code == 401 or data.get("error") == "incorrect_client_credentials":
            logger.error("GitHub rejected the configured OAuth credentials")
            raise HTTPException(401, "OAUTH_CONFIG_ERROR")
        if data.get("error") == "bad_verification_code":
            raise HTTPException(400, "INVALID_OAUTH_CODE")
        token.raise_for_status()
        headers = {"Authorization": "Bearer " + data["access_token"]}
        profile = await client.get("https://api.github.com/user", headers=headers)
        profile.raise_for_status()
        identity = Identity.model_validate(profile.json())
        page = 1
        while True:
            emails = await client.get(
                "https://api.github.com/user/emails",
                headers=headers,
                params={"per_page": 100, "page": page},
            )
            emails.raise_for_status()
            for item in emails.json():
                if item.get("primary") is True and item.get("verified") is True:
                    address = Address.model_validate(item)
                    return identity, str(address.email).lower()
            if "next" not in emails.links:
                break
            page += 1
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(502, "OAUTH_PROVIDER_UNAVAILABLE") from None
    raise HTTPException(403, "OAUTH_VERIFIED_EMAIL_REQUIRED")


async def save_identity(db: AsyncSession, profile: Identity, email: str) -> User:
    by_id = select(User).where(User.github_id == str(profile.id))
    user = await db.scalar(by_id)
    owner = await get_user_by_email(db, email)
    if owner and (user is None or owner.id != user.id):
        raise HTTPException(409, "OAUTH_EMAIL_CONFLICT")
    if user is None:
        # This value can never authenticate through the password endpoint.
        user = User(github_id=str(profile.id), role=UserRole.PARTICIPANT, password_hash="!github")
        db.add(user)
    user.name = ((profile.name or "").strip() or profile.login)[:100]
    user.email = email
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # A second callback can create the same GitHub account concurrently.
        winner = await db.scalar(by_id)
        if winner and winner.email == email:
            return winner
        raise HTTPException(409, "OAUTH_EMAIL_CONFLICT") from None
    await db.refresh(user)
    return user


@router.get("/callback", response_class=RedirectResponse, status_code=303)
async def callback(
    request: Request,
    redis: Annotated[Redis, Depends(get_redis)],
    db: Annotated[AsyncSession, Depends(get_db)],
    client: Annotated[httpx.AsyncClient, Depends(github_client)],
    state: str = "",
    code: str = "",
    error: str = "",
):
    configured()
    browser = request.cookies.get(STATE_COOKIE)
    if not browser or len(state) != 43:
        raise HTTPException(400, "INVALID_OAUTH_STATE")
    verifier = await redis.getdel(state_key(state, browser))
    if not verifier:
        raise HTTPException(400, "INVALID_OAUTH_STATE")
    if error == "access_denied":
        raise HTTPException(403, "OAUTH_ACCESS_DENIED")
    if not code or error:
        raise HTTPException(400, "INVALID_OAUTH_CODE")
    profile, email = await fetch_identity(client, code, verifier)
    user = await save_identity(db, profile, email)
    ticket = secrets.token_urlsafe(32)
    await redis.set("contest:github:ticket:" + digest(ticket), str(user.id), ex=60)
    response = RedirectResponse(settings.GITHUB_FRONTEND_URL, 303, headers=PRIVATE_HEADERS)
    response.delete_cookie(STATE_COOKIE, path=CALLBACK)
    set_cookie(response, TICKET_COOKIE, ticket, EXCHANGE, 60)
    return response


@router.post("/exchange", response_model=TokenResponse)
async def exchange(
    request: Request,
    response: Response,
    redis: Annotated[Redis, Depends(get_redis)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    ticket = request.cookies.get(TICKET_COOKIE)
    subject = await redis.getdel("contest:github:ticket:" + digest(ticket)) if ticket else None
    if not subject or await db.get(User, uuid.UUID(subject)) is None:
        raise HTTPException(401, "INVALID_OAUTH_TICKET")
    response.delete_cookie(TICKET_COOKIE, path=EXCHANGE)
    return await start_session(redis, response, uuid.UUID(subject))

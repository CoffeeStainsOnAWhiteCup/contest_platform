from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.core import monitoring
from app.modules.auth.github import CALLBACK, PRIVATE_HEADERS
from app.modules.auth.router import router as auth_router
from app.modules.contests.router import contests_router, problems_router
from app.modules.notifications.router import router as telegram_router
from app.modules.rating.router import router as rating_router
from app.modules.submissions.router import router as submissions_router
from app.modules.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    monitoring.configure_http_logging()
    yield
    await engine.dispose()


app = FastAPI(title="Contest Platform", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def browser_oauth_error(request: Request, exc: HTTPException):
    github_navigation = request.method == "GET" and request.url.path in {
        "/api/v1/auth/github", CALLBACK,
    }
    if github_navigation and "text/html" in request.headers.get("accept", ""):
        codes = {
            "INVALID_OAUTH_STATE", "INVALID_OAUTH_CODE", "OAUTH_ACCESS_DENIED",
            "OAUTH_CONFIG_ERROR", "OAUTH_PROVIDER_UNAVAILABLE",
            "OAUTH_EMAIL_CONFLICT", "OAUTH_VERIFIED_EMAIL_REQUIRED",
        }
        if isinstance(exc.detail, str) and exc.detail in codes:
            return RedirectResponse(
                f"{settings.GITHUB_FRONTEND_URL}?error={exc.detail}", 303, headers=PRIVATE_HEADERS
            )
    return await http_exception_handler(request, exc)


app.middleware("http")(monitoring.observe)
app.include_router(monitoring.router)
frontend = urlsplit(settings.GITHUB_FRONTEND_URL)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"{frontend.scheme}://{frontend.netloc}"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Retry-After"],
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(rating_router, prefix="/api/v1")
app.include_router(telegram_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(contests_router, prefix="/api/v1")
app.include_router(problems_router, prefix="/api/v1")
app.include_router(submissions_router, prefix="/api/v1")

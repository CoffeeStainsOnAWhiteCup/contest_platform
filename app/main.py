from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.models.models import Base
from app.modules.auth.router import router as auth_router
from app.modules.submissions.router import router as submissions_router
from app.modules.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Contest Platform", lifespan=lifespan)
frontend = urlsplit(settings.GITHUB_FRONTEND_URL)
app.add_middleware(CORSMiddleware, allow_origins=[f"{frontend.scheme}://{frontend.netloc}"],
                   allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                   allow_headers=["Authorization", "Content-Type"])
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(submissions_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}

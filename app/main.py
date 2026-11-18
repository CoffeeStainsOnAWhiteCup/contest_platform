from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.database import engine
from app.models.models import Base 
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title="Contest Platform", lifespan=lifespan)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok"}



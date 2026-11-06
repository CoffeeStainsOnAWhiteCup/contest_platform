from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.database import engine
from app.models.models import Base 

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title="Contest Platform", lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}



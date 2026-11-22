"""Dependency readiness, low-cardinality HTTP metrics and redacted request logs."""

import asyncio
import json
import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.core.database import get_db
from app.core.rate_limit import get_redis

router = APIRouter()
requests_total = Counter("contest_http_requests", "Completed requests", ["method", "route", "status"])
latency = Histogram("contest_http_seconds", "Request duration", ["route"])
logger = logging.getLogger("contest.http")


def configure_http_logging() -> None:
    """Emit one JSON access record per request and optionally keep daily files."""
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(logging.StreamHandler())
    directory = os.getenv("HTTP_LOG_DIR")
    if directory:
        Path(directory).mkdir(parents=True, exist_ok=True)
        logger.addHandler(
            TimedRotatingFileHandler(Path(directory) / "http.jsonl", when="midnight", backupCount=30, utc=True)
        )


async def observe(request: Request, call_next):
    """Record route templates without query strings, headers or request bodies."""
    started = time.perf_counter()
    status = 500
    failure = None
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    except Exception as exc:
        failure = type(exc).__name__
        raise
    finally:
        seconds = time.perf_counter() - started
        route = getattr(request.scope.get("route"), "path", "unmatched")
        method = (
            request.method
            if request.method in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
            else "OTHER"
        )
        requests_total.labels(method, route, str(status)).inc()
        latency.labels(route).observe(seconds)
        logger.info(
            json.dumps(
                dict(
                    timestamp=time.time(),
                    method=method,
                    route=route,
                    status=status,
                    duration_ms=round(seconds * 1000, 2),
                    error=failure,
                )
            )
        )


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)):
    """Return 200 only while PostgreSQL and Redis are reachable."""
    try:
        async with asyncio.timeout(3):
            await db.execute(text("SELECT 1"))
            await redis.ping()
    except (TimeoutError, OSError, SQLAlchemyError, RedisError):
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ok"}


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Expose Prometheus text format."""
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})

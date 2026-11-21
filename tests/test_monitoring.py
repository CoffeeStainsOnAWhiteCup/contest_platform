from unittest.mock import AsyncMock

from redis.exceptions import ConnectionError
from sqlalchemy.exc import OperationalError

from app.core.database import get_db
from app.core.rate_limit import get_redis
from app.main import app


async def test_readiness_and_metrics(client):
    assert (await client.get("/health")).json() == {"status": "ok"}
    assert "contest_http_requests_total" in (await client.get("/metrics")).text

    bad_redis = AsyncMock()
    bad_redis.ping.side_effect = ConnectionError()
    app.dependency_overrides[get_redis] = lambda: bad_redis
    assert (await client.get("/health")).status_code == 503
    app.dependency_overrides.pop(get_redis)
    bad_db = AsyncMock()
    bad_db.execute.side_effect = OperationalError("SELECT 1", {}, Exception())
    app.dependency_overrides[get_db] = lambda: bad_db
    assert (await client.get("/health")).status_code == 503

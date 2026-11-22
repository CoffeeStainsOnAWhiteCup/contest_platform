from urllib.parse import urlsplit

from app.core.config import settings

frontend = urlsplit(settings.GITHUB_FRONTEND_URL)
ORIGIN = f"{frontend.scheme}://{frontend.netloc}"


async def test_cors_preflight_allows_frontend(client):
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "POST" in response.headers["access-control-allow-methods"]


async def test_cors_exposes_retry_after(client):
    response = await client.get("/health", headers={"Origin": ORIGIN})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "Retry-After" in response.headers["access-control-expose-headers"]
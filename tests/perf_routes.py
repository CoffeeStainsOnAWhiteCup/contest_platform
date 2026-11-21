"""Explicit local benchmark: python -m pytest -s tests/perf_routes.py."""

import asyncio
import math
import socket
import subprocess
import sys
import time

import httpx
import pytest

from app.models.models import Language, Problem, Submission, SubmissionStatus, User
from tests.conftest import auth_headers, create_contest_and_problem


async def measure(client, method, url, *, rps, seconds=10, **kwargs):
    async def request_at(scheduled):
        await asyncio.sleep(max(0, scheduled - time.perf_counter()))
        start = time.perf_counter()
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
        return 1000 * (time.perf_counter() - start)

    start = time.perf_counter()
    timings = sorted(await asyncio.gather(*[request_at(start + i / rps) for i in range(rps * seconds)]))
    p95 = timings[math.ceil(len(timings) * 0.95) - 1]
    print(f"{method} {len(timings)} requests, target {rps} RPS, p95={p95:.2f} ms, max={timings[-1]:.2f} ms")
    return p95


@pytest.mark.asyncio
async def test_populated_contest(db_session, admin_user):
    contest, _, _ = await create_contest_and_problem(db_session, tests=[])
    users = [User(name=f"Perf {i}", email=f"perf{i}@example.test", password_hash="!") for i in range(100)]
    problems = [Problem(contest_id=contest.id, title="Sum", statement="Sum", ordinal=i + 2) for i in range(5)]
    db_session.add_all(users + problems)
    await db_session.flush()
    db_session.add_all(
        [
            Submission(
                user_id=u.id,
                problem_id=p.id,
                code="print(0)",
                language=Language.PYTHON,
                status=SubmissionStatus.ACCEPTED,
            )
            for u in users
            for p in problems
        ]
    )
    await db_session.commit()
    # Select a local port for the isolated test server.
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=10, trust_env=False) as client:
            for _ in range(100):
                if server.poll() is not None:
                    pytest.fail("Uvicorn failed to start")
                try:
                    if (await client.get("/health")).is_success:
                        break
                except httpx.ConnectError:
                    pass
                await asyncio.sleep(0.1)
            board = f"/api/v1/contests/{contest.id}/leaderboard"
            assert (await client.get(board)).json()["total"] == 100
            get_ms = await measure(client, "GET", board, rps=50)
            post_ms = await measure(
                client,
                "POST",
                f"/api/v1/contests/{contest.id}/problems",
                rps=20,
                headers=auth_headers(admin_user),
                json={"title": "Benchmark problem", "statement": "Sum"},
            )
            assert get_ms <= 50
            assert post_ms <= 500
    finally:
        server.terminate()
        server.wait(timeout=15)

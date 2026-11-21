"""Exercise Docker SDK protocol handling even when no local daemon is available."""

import uuid
from unittest.mock import MagicMock

import pytest
from docker.errors import DockerException, ImageNotFound

from app.core.config import settings
from app.models.models import Language
from app.modules.judge.sandbox.languages import get_language_config
from app.modules.judge.sandbox.runner import SandboxOutputLimitExceeded, SandboxSession, SandboxUnavailable


@pytest.fixture
def engine(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr("app.modules.judge.sandbox.runner.docker.from_env", lambda: client)
    client.api.exec_create.return_value = {"Id": "exec"}
    client.api.exec_inspect.return_value = {"ExitCode": 0}
    return client


def session():
    return SandboxSession(uuid.uuid4(), get_language_config(Language.PYTHON), 1000, 128)


@pytest.mark.parametrize("fail_at", ["ping", "pull", "create"])
def test_engine_failure_closes_client(engine, fail_at):
    if fail_at == "ping":
        engine.ping.side_effect = DockerException("offline")
    elif fail_at == "pull":
        engine.images.get.side_effect = ImageNotFound("missing")
        engine.images.pull.side_effect = DockerException("offline")
    else:
        engine.containers.create.side_effect = DockerException("busy")
    with pytest.raises(SandboxUnavailable):
        with session():
            pytest.fail("start must fail")
    engine.close.assert_called_once()


def test_docker_output_and_cleanup(engine):
    container = engine.containers.create.return_value
    container.stats.return_value = {"memory_stats": {"usage": 4096}}
    engine.api.exec_start.side_effect = [
        (chunk for chunk in []),
        (chunk for chunk in []),
        (chunk for chunk in []),
        (chunk for chunk in [(b"3\n", None), (None, b"log")]),
    ]
    with session() as sandbox:
        assert sandbox.compile("print(3)") == (True, "", "")
        result = sandbox.run_test("")
        assert (result.stdout, result.stderr, result.memory_kb) == ("3\n", "log", 4)
        assert engine.api.exec_create.call_args.kwargs["user"] == "nobody"
    container.remove.assert_called_once_with(force=True, v=True)
    engine.close.assert_called_once()


def test_output_limit_closes_stream(engine, monkeypatch):
    monkeypatch.setattr(settings, "SANDBOX_MAX_OUTPUT_BYTES", 4)
    chunks = MagicMock()
    chunks.__iter__.return_value = iter([(b"abc", None), (None, b"def")])
    engine.api.exec_start.return_value = chunks
    with session() as sandbox, pytest.raises(SandboxOutputLimitExceeded):
        sandbox.run_test("")
    chunks.close.assert_called_once()
    engine.containers.create.return_value.kill.assert_called_once()

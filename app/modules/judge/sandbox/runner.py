import base64
import logging
import shlex
import time
import uuid
from dataclasses import dataclass

import docker
from docker.errors import DockerException, ImageNotFound

from app.core.config import settings
from app.modules.judge.sandbox.languages import LanguageConfig

logger = logging.getLogger(__name__)


class SandboxError(Exception):
    pass


class SandboxUnavailable(SandboxError):
    pass


@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    time_ms: int
    timed_out: bool
    memory_kb: int | None


def _decode(value: bytes | None, limit: int) -> str:
    if not value:
        return ""
    if len(value) > limit:
        value = value[:limit] + b"\n...[truncated]"
    return value.decode("utf-8", errors="replace")


class SandboxSession:
    def __init__(
        self,
        submission_id: uuid.UUID,
        config: LanguageConfig,
        time_limit_ms: int,
        memory_limit_mb: int,
    ):
        self.submission_id = submission_id
        self.config = config
        self.time_limit_ms = time_limit_ms
        self.memory_limit_mb = memory_limit_mb
        self.client: docker.DockerClient | None = None
        self.container = None

    def __enter__(self) -> "SandboxSession":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()

    def start(self) -> None:
        try:
            self.client = docker.from_env()
            self.client.ping()
        except DockerException as exc:
            raise SandboxUnavailable(f"Docker daemon is unavailable: {exc}") from exc

        try:
            self.client.images.get(self.config.image)
        except ImageNotFound:
            try:
                self.client.images.pull(self.config.image)
            except DockerException as exc:
                raise SandboxUnavailable(f"Cannot pull image {self.config.image}: {exc}") from exc
        except DockerException as exc:
            raise SandboxUnavailable(f"Cannot access image {self.config.image}: {exc}") from exc

        tmpfs_size = settings.SANDBOX_TMPFS_MB
        try:
            self.container = self.client.containers.create(
                image=self.config.image,
                command=["sleep", "infinity"],
                detach=True,
                network_mode="none",
                mem_limit=f"{self.config.container_memory_mb(self.memory_limit_mb)}m",
                nano_cpus=int(settings.SANDBOX_CPUS * 1_000_000_000),
                pids_limit=settings.SANDBOX_PIDS_LIMIT,
                read_only=True,
                tmpfs={"/work": f"rw,exec,size={tmpfs_size}m"},
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                working_dir="/work",
                user="root",
                labels={
                    "contest-judge": "1",
                    "submission_id": str(self.submission_id),
                },
            )
            self.container.start()
            self.container.exec_run(["chmod", "777", "/work"], user="root")
        except DockerException as exc:
            self.cleanup()
            raise SandboxUnavailable(f"Cannot create sandbox container: {exc}") from exc

    def cleanup(self) -> None:
        if self.container is not None:
            try:
                self.container.remove(force=True, v=True)
            except DockerException:
                logger.exception("Failed to remove sandbox container", extra={"submission_id": str(self.submission_id)})
            finally:
                self.container = None
        if self.client is not None:
            try:
                self.client.close()
            except DockerException:
                pass
            finally:
                self.client = None

    def _write_file(self, filename: str, content: bytes) -> None:
        payload = base64.b64encode(content).decode("ascii")
        command = (
            f"printf %s {shlex.quote(payload)} | base64 -d > {shlex.quote(filename)}"
        )
        exit_code, _, stderr = self._exec(["sh", "-c", command], user="root")
        if exit_code != 0:
            raise SandboxUnavailable(f"Failed to copy source code into sandbox: {stderr}")

    def _exec(self, command: list[str], *, user: str) -> tuple[int, str, str]:
        if self.container is None:
            raise SandboxError("Sandbox container is not started")

        result = self.container.exec_run(
            command,
            stdout=True,
            stderr=True,
            demux=True,
            workdir="/work",
            user=user,
        )
        if isinstance(result.output, tuple):
            stdout_raw, stderr_raw = result.output
        else:
            stdout_raw, stderr_raw = result.output, b""
        limit = settings.SANDBOX_MAX_OUTPUT_BYTES
        return result.exit_code, _decode(stdout_raw, limit), _decode(stderr_raw, limit)

    def _memory_kb(self) -> int | None:
        if self.container is None:
            return None
        try:
            stats = self.container.stats(stream=False)
            memory = stats.get("memory_stats", {})
            usage = memory.get("max_usage") or memory.get("usage")
            if usage is None:
                return None
            return int(usage // 1024)
        except (DockerException, KeyError, TypeError):
            return None

    def compile(self, code: str) -> tuple[bool, str, str]:
        self._write_file(self.config.source_filename, code.encode("utf-8"))
        if not self.config.compile_command:
            return True, "", ""

        timeout_s = settings.SANDBOX_COMPILE_TIMEOUT_S
        command = [
            "sh",
            "-c",
            f"timeout -s KILL {timeout_s}s {self.config.compile_command}",
        ]
        exit_code, stdout, stderr = self._exec(command, user="root")
        return exit_code == 0, stdout, stderr

    def run_test(self, input_data: str) -> ExecutionResult:
        timeout_s = max(0.001, self.time_limit_ms / 1000)
        run_command = self.config.build_run_command(self.memory_limit_mb)
        self._write_file("input.txt", input_data.encode("utf-8"))
        command = [
            "sh",
            "-c",
            f"timeout -s KILL {timeout_s:.3f}s {run_command} < input.txt",
        ]

        started = time.perf_counter()
        exit_code, stdout, stderr = self._exec(command, user="nobody")
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        memory_kb = self._memory_kb()
        timed_out = exit_code == 124 or (exit_code == 137 and elapsed_ms >= self.time_limit_ms)
        return ExecutionResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            time_ms=elapsed_ms,
            timed_out=timed_out,
            memory_kb=memory_kb,
        )

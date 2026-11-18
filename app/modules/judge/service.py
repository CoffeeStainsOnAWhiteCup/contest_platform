import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import SyncSessionLocal
from app.models.models import (
    Problem,
    Submission,
    SubmissionStatus,
    SubmissionTestResult,
    Verdict,
    VerdictStatus,
)
from app.modules.judge.sandbox.languages import get_language_config
from app.modules.judge.sandbox.runner import (
    SandboxOutputLimitExceeded,
    SandboxSession,
    SandboxUnavailable,
)
from app.modules.judge.sandbox.verdicts import (
    aggregate_verdict,
    status_for_test,
    submission_status_for_verdict,
)

logger = logging.getLogger(__name__)


class JudgeBusy(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _claim_submission(submission_id: uuid.UUID) -> bool:
    now = _now()
    stale_before = now - timedelta(seconds=settings.JUDGE_STALE_TIMEOUT_S)
    with SyncSessionLocal() as session:
        claimed_id = session.execute(
            update(Submission)
            .where(
                Submission.id == submission_id,
                or_(
                    Submission.status == SubmissionStatus.PENDING,
                    and_(
                        Submission.status == SubmissionStatus.RUNNING,
                        or_(
                            Submission.judge_started_at.is_(None),
                            Submission.judge_started_at < stale_before,
                        ),
                    ),
                ),
            )
            .values(
                status=SubmissionStatus.RUNNING,
                judge_started_at=now,
                judge_attempt=Submission.judge_attempt + 1,
                error_message=None,
            )
            .returning(Submission.id)
        ).scalar_one_or_none()
        session.commit()
        if claimed_id is not None:
            return True
        current_status = session.scalar(select(Submission.status).where(Submission.id == submission_id))

    if current_status == SubmissionStatus.RUNNING:
        raise JudgeBusy(f"Submission {submission_id} is already running")
    return False


def _finalize(
    submission_id: uuid.UUID,
    status: VerdictStatus,
    *,
    time_ms: int | None = None,
    memory_kb: int | None = None,
    compile_output: str | None = None,
    runtime_output: str | None = None,
    total_tests: int = 0,
    passed_tests: int = 0,
    message: str | None = None,
    test_results: list[dict] | None = None,
) -> None:
    with SyncSessionLocal() as session:
        submission = session.scalar(select(Submission).where(Submission.id == submission_id))
        if submission is None:
            return

        session.execute(delete(SubmissionTestResult).where(SubmissionTestResult.submission_id == submission_id))
        session.execute(delete(Verdict).where(Verdict.submission_id == submission_id))

        session.add(
            Verdict(
                submission_id=submission_id,
                status=status,
                time_ms=time_ms,
                memory_kb=memory_kb,
                message=message,
            )
        )
        for item in test_results or []:
            session.add(SubmissionTestResult(submission_id=submission_id, **item))

        submission.status = submission_status_for_verdict(status)
        submission.time_ms = time_ms
        submission.memory_kb = memory_kb
        submission.compile_output = compile_output
        submission.runtime_output = runtime_output
        submission.total_tests = total_tests
        submission.passed_tests = passed_tests
        submission.judged_at = _now()
        submission.error_message = message
        session.commit()


def mark_submission_system_error(submission_id: uuid.UUID, message: str) -> None:
    with SyncSessionLocal() as session:
        submission = session.scalar(select(Submission).where(Submission.id == submission_id))
        if submission is None:
            return
        total_tests = submission.total_tests
    _finalize(
        submission_id,
        VerdictStatus.SYSTEM_ERROR,
        total_tests=total_tests,
        message=message,
    )


def _reset_for_retry(submission_id: uuid.UUID, message: str) -> None:
    with SyncSessionLocal() as session:
        session.execute(
            update(Submission)
            .where(
                Submission.id == submission_id,
                Submission.status == SubmissionStatus.RUNNING,
            )
            .values(status=SubmissionStatus.PENDING, error_message=message)
        )
        session.commit()


def judge_submission_sync(submission_id: uuid.UUID) -> None:
    if not _claim_submission(submission_id):
        return

    with SyncSessionLocal() as session:
        submission = session.scalar(
            select(Submission)
            .options(selectinload(Submission.problem).selectinload(Problem.tests))
            .where(Submission.id == submission_id)
        )
        if submission is None:
            return
        tests = sorted(submission.problem.tests, key=lambda item: (item.ordinal, str(item.id)))
        language = submission.language
        code = submission.code
        time_limit_ms = submission.problem.time_limit_ms
        memory_limit_mb = submission.problem.memory_limit_mb

    if not tests:
        _finalize(
            submission_id,
            VerdictStatus.SYSTEM_ERROR,
            total_tests=0,
            message="Problem has no tests",
        )
        return

    config = get_language_config(language)
    test_results: list[dict] = []
    runtime_output = ""
    compile_output = ""

    try:
        with SandboxSession(submission_id, config, time_limit_ms, memory_limit_mb) as sandbox:
            compiled, compile_stdout, compile_stderr = sandbox.compile(code)
            compile_output = "\n".join(part for part in (compile_stdout, compile_stderr) if part).strip()
            if not compiled:
                _finalize(
                    submission_id,
                    VerdictStatus.COMPILE_ERROR,
                    compile_output=compile_output,
                    total_tests=len(tests),
                    message=compile_output or "Compilation failed",
                )
                return

            statuses: list[VerdictStatus] = []
            time_values: list[int] = []
            memory_values: list[int] = []
            first_failed_test: int | None = None

            for index, test in enumerate(tests, start=1):
                try:
                    execution = sandbox.run_test(test.input_data)
                except SandboxOutputLimitExceeded as exc:
                    statuses.append(VerdictStatus.RUNTIME_ERROR)
                    runtime_output = exc.stderr.decode("utf-8", errors="replace")[:2000]
                    test_results.append(
                        {
                            "test_id": test.id,
                            "ordinal": index,
                            "status": VerdictStatus.RUNTIME_ERROR,
                            "time_ms": None,
                            "memory_kb": None,
                            "exit_code": None,
                            "stderr_excerpt": runtime_output or str(exc)[:2000],
                        }
                    )
                    _finalize(
                        submission_id,
                        VerdictStatus.RUNTIME_ERROR,
                        time_ms=max(time_values) if time_values else None,
                        memory_kb=max(memory_values) if memory_values else None,
                        compile_output=compile_output or None,
                        runtime_output=runtime_output or str(exc),
                        total_tests=len(tests),
                        passed_tests=sum(1 for status in statuses if status == VerdictStatus.ACCEPTED),
                        message=f"Output limit exceeded on test {index}",
                        test_results=test_results,
                    )
                    return

                test_status = status_for_test(execution, test.expected_output)
                statuses.append(test_status)
                if test_status != VerdictStatus.ACCEPTED and first_failed_test is None:
                    first_failed_test = index
                time_values.append(execution.time_ms)
                if execution.memory_kb is not None:
                    memory_values.append(execution.memory_kb)
                if execution.stderr:
                    runtime_output = execution.stderr

                test_results.append(
                    {
                        "test_id": test.id,
                        "ordinal": index,
                        "status": test_status,
                        "time_ms": execution.time_ms,
                        "memory_kb": execution.memory_kb,
                        "exit_code": execution.exit_code,
                        "stderr_excerpt": execution.stderr[:2000] if execution.stderr else None,
                    }
                )

            verdict = aggregate_verdict(statuses)
            passed_tests = sum(1 for status in statuses if status == VerdictStatus.ACCEPTED)
            message = None
            if verdict != VerdictStatus.ACCEPTED:
                message = f"Failed on test {first_failed_test}" if first_failed_test is not None else "Failed"
            _finalize(
                submission_id,
                verdict,
                time_ms=max(time_values) if time_values else None,
                memory_kb=max(memory_values) if memory_values else None,
                compile_output=compile_output or None,
                runtime_output=runtime_output or None,
                total_tests=len(tests),
                passed_tests=passed_tests,
                message=message,
                test_results=test_results,
            )
    except SandboxUnavailable as exc:
        logger.warning("Sandbox unavailable for submission %s: %s", submission_id, exc)
        _reset_for_retry(submission_id, str(exc))
        raise
    except Exception as exc:
        logger.exception("Unexpected judge error for submission %s", submission_id)
        _finalize(
            submission_id,
            VerdictStatus.SYSTEM_ERROR,
            total_tests=len(tests),
            message=f"Judge error: {exc}",
        )

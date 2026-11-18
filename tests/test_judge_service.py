from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.models.models import (
    Language,
    Submission,
    SubmissionStatus,
    SubmissionTestResult,
    Verdict,
    VerdictStatus,
)
from app.modules.judge.sandbox.runner import (
    ExecutionResult,
    SandboxOutputLimitExceeded,
    SandboxUnavailable,
)
from app.modules.judge.service import (
    JudgeBusy,
    _finalize,
    _reset_for_retry,
    judge_submission_sync,
    mark_stale_submission_system_error,
    mark_submission_system_error,
)
from tests.conftest import create_contest_and_problem


class FakeSandbox:
    compile_ok = True
    compile_stderr = ""
    execution_results: list[ExecutionResult] = []
    unavailable = False
    output_limit_exceeded = False
    output_limit_after = 0

    def __init__(self, *args, **kwargs):
        self.results = list(self.execution_results)

    def __enter__(self):
        if self.unavailable:
            raise SandboxUnavailable("docker unavailable")
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def compile(self, code):
        return self.compile_ok, "", self.compile_stderr

    def run_test(self, input_data):
        if self.output_limit_after:
            self.output_limit_after -= 1
        elif self.output_limit_exceeded:
            raise SandboxOutputLimitExceeded(
                "Output limit of 65536 bytes exceeded",
                stdout=b"x" * 128,
                stderr=b"too much output",
            )
        if not self.results:
            return ExecutionResult(0, "", "", 0, False, 0)
        return self.results.pop(0)


def result(exit_code=0, stdout="3\n", stderr="", timed_out=False, memory_kb=1024):
    return ExecutionResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        time_ms=10,
        timed_out=timed_out,
        memory_kb=memory_kb,
    )


async def make_submission(db, participant, *, tests=None, code="print(3)"):
    _, problem, test_rows = await create_contest_and_problem(db, tests=tests)
    submission = Submission(
        user_id=participant.id,
        problem_id=problem.id,
        language=Language.PYTHON,
        code=code,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return submission, test_rows


async def fetch_state(db, submission_id):
    db.expire_all()
    submission = await db.get(Submission, submission_id)
    verdict = await db.scalar(select(Verdict).where(Verdict.submission_id == submission_id))
    results = list(
        await db.scalars(
            select(SubmissionTestResult)
            .where(SubmissionTestResult.submission_id == submission_id)
            .order_by(SubmissionTestResult.ordinal)
        )
    )
    return submission, verdict, results


async def test_accepted_submission(db_session, participant, monkeypatch):
    FakeSandbox.execution_results = [result()]
    submission, _ = await make_submission(db_session, participant)
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)

    judge_submission_sync(submission.id)

    submission, verdict, results = await fetch_state(db_session, submission.id)
    assert submission.status == SubmissionStatus.ACCEPTED
    assert submission.passed_tests == 1
    assert submission.total_tests == 1
    assert submission.judge_attempt == 1
    assert verdict.status == VerdictStatus.ACCEPTED
    assert len(results) == 1
    assert results[0].status == VerdictStatus.ACCEPTED


@pytest.mark.parametrize(
    ("execution", "expected_verdict", "expected_submission_status"),
    [
        (result(stdout="4\n"), VerdictStatus.WRONG_ANSWER, SubmissionStatus.WRONG_ANSWER),
        (result(exit_code=1, stderr="boom"), VerdictStatus.RUNTIME_ERROR, SubmissionStatus.RUNTIME_ERROR),
        (result(timed_out=True), VerdictStatus.TIME_LIMIT_EXCEEDED, SubmissionStatus.TIME_LIMIT_EXCEEDED),
        (result(exit_code=137), VerdictStatus.MEMORY_LIMIT_EXCEEDED, SubmissionStatus.MEMORY_LIMIT_EXCEEDED),
    ],
)
async def test_failed_verdicts(
    db_session,
    participant,
    monkeypatch,
    execution,
    expected_verdict,
    expected_submission_status,
):
    FakeSandbox.execution_results = [execution]
    submission, _ = await make_submission(db_session, participant)
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)

    judge_submission_sync(submission.id)

    submission, verdict, results = await fetch_state(db_session, submission.id)
    assert submission.status == expected_submission_status
    assert verdict.status == expected_verdict
    assert len(results) == 1


async def test_compile_error(db_session, participant, monkeypatch):
    FakeSandbox.compile_ok = False
    FakeSandbox.compile_stderr = "syntax error"
    submission, _ = await make_submission(db_session, participant)
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)

    judge_submission_sync(submission.id)

    submission, verdict, results = await fetch_state(db_session, submission.id)
    assert submission.status == SubmissionStatus.COMPILE_ERROR
    assert "syntax error" in submission.compile_output
    assert verdict.status == VerdictStatus.COMPILE_ERROR
    assert results == []


async def test_multiple_tests_aggregate_first_failure(db_session, participant, monkeypatch):
    FakeSandbox.execution_results = [result(stdout="3\n"), result(stdout="5\n")]
    submission, _ = await make_submission(
        db_session,
        participant,
        tests=[("1 2\n", "3\n"), ("2 2\n", "4\n")],
    )
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)

    judge_submission_sync(submission.id)

    submission, verdict, results = await fetch_state(db_session, submission.id)
    assert submission.status == SubmissionStatus.WRONG_ANSWER
    assert submission.passed_tests == 1
    assert submission.total_tests == 2
    assert len(results) == 2
    assert verdict.status == VerdictStatus.WRONG_ANSWER


async def test_message_reports_first_failed_test(db_session, participant, monkeypatch):
    FakeSandbox.execution_results = [
        result(stdout="4\n"),
        result(stdout="4\n"),
        result(stdout="6\n"),
    ]
    submission, _ = await make_submission(
        db_session,
        participant,
        tests=[("1 2\n", "3\n"), ("2 2\n", "4\n"), ("3 3\n", "6\n")],
    )
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)

    judge_submission_sync(submission.id)

    submission, verdict, results = await fetch_state(db_session, submission.id)
    assert submission.status == SubmissionStatus.WRONG_ANSWER
    assert submission.passed_tests == 2
    assert submission.total_tests == 3
    assert submission.error_message == "Failed on test 1"
    assert verdict.status == VerdictStatus.WRONG_ANSWER
    assert results[0].status == VerdictStatus.WRONG_ANSWER
    assert results[1].status == VerdictStatus.ACCEPTED
    assert results[2].status == VerdictStatus.ACCEPTED


async def test_output_limit_marks_test_as_runtime_error(db_session, participant, monkeypatch):
    FakeSandbox.output_limit_exceeded = True
    submission, _ = await make_submission(
        db_session,
        participant,
        tests=[("1 2\n", "3\n"), ("2 2\n", "4\n")],
    )
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)

    judge_submission_sync(submission.id)

    submission, verdict, results = await fetch_state(db_session, submission.id)
    assert submission.status == SubmissionStatus.RUNTIME_ERROR
    assert submission.total_tests == 2
    assert submission.passed_tests == 0
    assert submission.error_message == "Output limit exceeded on test 1"
    assert verdict.status == VerdictStatus.RUNTIME_ERROR
    assert len(results) == 1
    assert results[0].status == VerdictStatus.RUNTIME_ERROR
    assert results[0].stderr_excerpt == "too much output"


async def test_output_limit_reports_current_test_after_earlier_failure(
    db_session, participant, monkeypatch
):
    FakeSandbox.execution_results = [result(stdout="4\n")]
    FakeSandbox.output_limit_exceeded = True
    FakeSandbox.output_limit_after = 1
    submission, _ = await make_submission(
        db_session,
        participant,
        tests=[("1 2\n", "3\n"), ("2 2\n", "4\n")],
    )
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)

    judge_submission_sync(submission.id)

    submission, verdict, results = await fetch_state(db_session, submission.id)
    assert submission.status == SubmissionStatus.RUNTIME_ERROR
    assert submission.error_message == "Output limit exceeded on test 2"
    assert verdict.status == VerdictStatus.RUNTIME_ERROR
    assert len(results) == 2
    assert results[0].status == VerdictStatus.WRONG_ANSWER
    assert results[1].status == VerdictStatus.RUNTIME_ERROR


async def test_no_tests_is_system_error(db_session, participant, monkeypatch):
    submission, _ = await make_submission(db_session, participant, tests=[])
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)

    judge_submission_sync(submission.id)

    submission, verdict, _ = await fetch_state(db_session, submission.id)
    assert submission.status == SubmissionStatus.SYSTEM_ERROR
    assert verdict.status == VerdictStatus.SYSTEM_ERROR


async def test_second_run_is_idempotent(db_session, participant, monkeypatch):
    FakeSandbox.execution_results = [result()]
    submission, _ = await make_submission(db_session, participant)
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)

    judge_submission_sync(submission.id)
    judge_submission_sync(submission.id)

    submission, verdict, results = await fetch_state(db_session, submission.id)
    assert submission.judge_attempt == 1
    assert len(results) == 1
    verdict_count = await db_session.scalar(
        select(func.count()).select_from(Verdict).where(Verdict.submission_id == submission.id)
    )
    assert verdict_count == 1


async def test_sandbox_unavailable_resets_to_pending(db_session, participant, monkeypatch):
    FakeSandbox.unavailable = True
    submission, _ = await make_submission(db_session, participant)
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)

    with pytest.raises(SandboxUnavailable):
        judge_submission_sync(submission.id)

    submission, verdict, results = await fetch_state(db_session, submission.id)
    assert submission.status == SubmissionStatus.PENDING
    assert submission.error_message == "docker unavailable"
    assert verdict is None
    assert results == []


async def test_stale_running_submission_is_reclaimed(db_session, participant, monkeypatch):
    FakeSandbox.execution_results = [result()]
    submission, _ = await make_submission(db_session, participant)
    submission.status = SubmissionStatus.RUNNING
    submission.judge_attempt = 1
    submission.judge_started_at = datetime.now(timezone.utc) - timedelta(
        seconds=settings.JUDGE_STALE_TIMEOUT_S + 1
    )
    await db_session.commit()
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)

    judge_submission_sync(submission.id)

    submission, verdict, results = await fetch_state(db_session, submission.id)
    assert submission.status == SubmissionStatus.ACCEPTED
    assert submission.judge_attempt == 2
    assert verdict.status == VerdictStatus.ACCEPTED
    assert len(results) == 1


async def test_fresh_running_submission_is_not_reclaimed(db_session, participant, monkeypatch):
    submission, _ = await make_submission(db_session, participant)
    submission.status = SubmissionStatus.RUNNING
    submission.judge_attempt = 1
    submission.judge_started_at = datetime.now(timezone.utc)
    await db_session.commit()
    monkeypatch.setattr("app.modules.judge.service.SandboxSession", FakeSandbox)

    with pytest.raises(JudgeBusy):
        judge_submission_sync(submission.id)

    submission, verdict, results = await fetch_state(db_session, submission.id)
    assert submission.status == SubmissionStatus.RUNNING
    assert submission.judge_attempt == 1
    assert verdict is None
    assert results == []


async def test_old_attempt_cannot_overwrite_newer_attempt(db_session, participant):
    submission, test_rows = await make_submission(db_session, participant)
    submission.status = SubmissionStatus.RUNNING
    submission.judge_attempt = 2
    submission.judge_started_at = datetime.now(timezone.utc)
    submission.total_tests = 1
    submission.passed_tests = 1
    db_session.add(Verdict(submission_id=submission.id, status=VerdictStatus.ACCEPTED))
    db_session.add(
        SubmissionTestResult(
            submission_id=submission.id,
            test_id=test_rows[0].id,
            ordinal=1,
            status=VerdictStatus.ACCEPTED,
            time_ms=10,
            memory_kb=1024,
            exit_code=0,
        )
    )
    await db_session.commit()

    _finalize(
        submission.id,
        VerdictStatus.WRONG_ANSWER,
        expected_attempt=1,
        total_tests=1,
        passed_tests=0,
        message="stale result",
    )
    _reset_for_retry(submission.id, "stale reset", expected_attempt=1)
    mark_submission_system_error(submission.id, "stale error", expected_attempt=1)
    mark_stale_submission_system_error(submission.id, "stale recovery")

    submission, verdict, results = await fetch_state(db_session, submission.id)
    assert submission.status == SubmissionStatus.RUNNING
    assert submission.judge_attempt == 2
    assert submission.total_tests == 1
    assert submission.passed_tests == 1
    assert submission.error_message is None
    assert verdict.status == VerdictStatus.ACCEPTED
    assert len(results) == 1
    assert results[0].status == VerdictStatus.ACCEPTED


async def test_preflight_db_error_marks_system_error_for_attempt(
    db_session, participant, monkeypatch
):
    submission, _ = await make_submission(db_session, participant)

    def fail_load(submission_id):
        raise OperationalError("select submission", {}, Exception("connection lost"))

    monkeypatch.setattr(
        "app.modules.judge.service._load_submission_for_judging",
        fail_load,
    )

    judge_submission_sync(submission.id)

    submission, verdict, results = await fetch_state(db_session, submission.id)
    assert submission.status == SubmissionStatus.SYSTEM_ERROR
    assert submission.judge_attempt == 1
    assert submission.error_message.startswith("Judge error:")
    assert "connection lost" in submission.error_message
    assert verdict.status == VerdictStatus.SYSTEM_ERROR
    assert results == []


@pytest.fixture(autouse=True)
def reset_fake_sandbox():
    FakeSandbox.compile_ok = True
    FakeSandbox.compile_stderr = ""
    FakeSandbox.execution_results = []
    FakeSandbox.unavailable = False
    FakeSandbox.output_limit_exceeded = False
    FakeSandbox.output_limit_after = 0
    yield

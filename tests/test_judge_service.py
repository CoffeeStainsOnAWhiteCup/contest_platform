import pytest
from sqlalchemy import func, select

from app.models.models import (
    Language,
    Submission,
    SubmissionStatus,
    SubmissionTestResult,
    Verdict,
    VerdictStatus,
)
from app.modules.judge.sandbox.runner import ExecutionResult, SandboxUnavailable
from app.modules.judge.service import judge_submission_sync
from tests.conftest import create_contest_and_problem


class FakeSandbox:
    compile_ok = True
    compile_stderr = ""
    execution_results: list[ExecutionResult] = []
    unavailable = False

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


@pytest.fixture(autouse=True)
def reset_fake_sandbox():
    FakeSandbox.compile_ok = True
    FakeSandbox.compile_stderr = ""
    FakeSandbox.execution_results = []
    FakeSandbox.unavailable = False
    yield

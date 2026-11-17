from app.models.models import SubmissionStatus, VerdictStatus
from app.modules.judge.sandbox.runner import ExecutionResult
from app.modules.judge.sandbox.verdicts import (
    aggregate_verdict,
    status_for_test,
    submission_status_for_verdict,
)


def make_result(exit_code=0, stdout="3\n", stderr="", timed_out=False):
    return ExecutionResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        time_ms=10,
        timed_out=timed_out,
        memory_kb=1024,
    )


def test_accepted():
    assert status_for_test(make_result(), "3\n") == VerdictStatus.ACCEPTED


def test_wrong_answer():
    assert status_for_test(make_result(stdout="4\n"), "3\n") == VerdictStatus.WRONG_ANSWER


def test_runtime_error():
    assert status_for_test(make_result(exit_code=1), "3\n") == VerdictStatus.RUNTIME_ERROR


def test_time_limit():
    assert status_for_test(make_result(timed_out=True), "3\n") == VerdictStatus.TIME_LIMIT_EXCEEDED


def test_memory_limit():
    assert status_for_test(make_result(exit_code=137), "3\n") == VerdictStatus.MEMORY_LIMIT_EXCEEDED


def test_aggregate_first_failure():
    statuses = [VerdictStatus.ACCEPTED, VerdictStatus.WRONG_ANSWER, VerdictStatus.RUNTIME_ERROR]
    assert aggregate_verdict(statuses) == VerdictStatus.WRONG_ANSWER


def test_aggregate_all_accepted():
    assert aggregate_verdict([VerdictStatus.ACCEPTED, VerdictStatus.ACCEPTED]) == VerdictStatus.ACCEPTED


def test_aggregate_empty_is_system_error():
    assert aggregate_verdict([]) == VerdictStatus.SYSTEM_ERROR


def test_submission_status_mapping():
    assert submission_status_for_verdict(VerdictStatus.ACCEPTED) == SubmissionStatus.ACCEPTED

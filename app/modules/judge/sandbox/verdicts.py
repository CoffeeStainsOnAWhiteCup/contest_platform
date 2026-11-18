from app.models.models import SubmissionStatus, VerdictStatus
from app.modules.judge.sandbox.comparator import compare_output
from app.modules.judge.sandbox.runner import ExecutionResult


def status_for_test(execution: ExecutionResult, expected_output: str) -> VerdictStatus:
    if execution.timed_out:
        return VerdictStatus.TIME_LIMIT_EXCEEDED
    if execution.exit_code == 137:
        return VerdictStatus.MEMORY_LIMIT_EXCEEDED
    if execution.exit_code != 0:
        return VerdictStatus.RUNTIME_ERROR
    if not compare_output(execution.stdout, expected_output):
        return VerdictStatus.WRONG_ANSWER
    return VerdictStatus.ACCEPTED


def aggregate_verdict(statuses: list[VerdictStatus]) -> VerdictStatus:
    if not statuses:
        return VerdictStatus.SYSTEM_ERROR
    for status in statuses:
        if status != VerdictStatus.ACCEPTED:
            return status
    return VerdictStatus.ACCEPTED


def submission_status_for_verdict(status: VerdictStatus) -> SubmissionStatus:
    return SubmissionStatus(status.value)

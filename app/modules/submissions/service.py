import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Submission, SubmissionStatus, User, UserRole, Verdict, VerdictStatus, utcnow
from app.modules.contests.policy import submission_denial_reason
from app.modules.judge.tasks import judge_submission
from app.modules.notifications.events import enqueue_verdict
from app.modules.submissions import repository
from app.modules.submissions.schemas import (
    RejudgeResponse,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionRead,
)

PRIVILEGED_ROLES = {UserRole.JUDGE, UserRole.ADMIN}


def _is_privileged(user: User) -> bool:
    return user.role in PRIVILEGED_ROLES


async def _enqueue(db: AsyncSession, submission: Submission) -> None:
    attempt = submission.judge_attempt
    try:
        task = judge_submission.delay(str(submission.id))
    except Exception as exc:
        # A broker can lose its acknowledgement after a worker has claimed the job.
        current = await db.get(Submission, submission.id, with_for_update=True, populate_existing=True)
        if current is not None and current.status == SubmissionStatus.PENDING and current.judge_attempt == attempt:
            current.judge_attempt += 1
            current.status = SubmissionStatus.SYSTEM_ERROR
            current.error_message = "Judge queue is unavailable"
            current.judged_at = utcnow()
            db.add(Verdict(
                submission_id=current.id,
                status=VerdictStatus.SYSTEM_ERROR,
                message=current.error_message,
            ))
            await db.run_sync(enqueue_verdict, current, VerdictStatus.SYSTEM_ERROR)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Judge queue is unavailable",
        ) from exc
    submission.celery_task_id = task.id
    await db.commit()


async def create_submission(
    db: AsyncSession,
    user: User,
    payload: SubmissionCreate,
) -> SubmissionDetail:
    problem = await repository.get_problem_with_contest(db, payload.problem_id)
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found")

    denial_reason = submission_denial_reason(problem.contest)
    if denial_reason is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=denial_reason
        )

    submission = await repository.create_submission(
        db,
        user_id=user.id,
        problem_id=payload.problem_id,
        language=payload.language,
        code=payload.code,
    )
    await _enqueue(db, submission)
    loaded = await repository.get_submission(db, submission.id)
    return SubmissionDetail.model_validate(loaded)


async def get_submission(
    db: AsyncSession,
    user: User,
    submission_id: uuid.UUID,
) -> SubmissionDetail:
    submission = await repository.get_submission(db, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    if submission.user_id != user.id and not _is_privileged(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    detail = SubmissionDetail.model_validate(submission)
    if not _is_privileged(user):
        detail.test_results = []
    return detail


async def list_submissions(
    db: AsyncSession,
    user: User,
    *,
    user_id: uuid.UUID | None,
    problem_id: uuid.UUID | None,
    submission_status: SubmissionStatus | None,
    page: int,
    size: int,
) -> tuple[list[SubmissionRead], int]:
    if not _is_privileged(user):
        user_id = user.id

    submissions, total = await repository.list_submissions(
        db,
        user_id=user_id,
        problem_id=problem_id,
        status=submission_status,
        page=page,
        size=size,
    )
    return [SubmissionRead.model_validate(item) for item in submissions], total


async def rejudge_submission(
    db: AsyncSession,
    user: User,
    submission_id: uuid.UUID,
) -> RejudgeResponse:
    if not _is_privileged(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    submission = await repository.get_submission(db, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    if submission.status in {SubmissionStatus.PENDING, SubmissionStatus.RUNNING}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Submission is already queued or running",
        )

    submission = await repository.reset_for_rejudge(db, submission)
    await _enqueue(db, submission)
    return RejudgeResponse(id=submission.id, status=submission.status)

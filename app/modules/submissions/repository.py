import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Language, Problem, Submission, SubmissionStatus, SubmissionTestResult, Verdict


async def get_problem_with_contest(db: AsyncSession, problem_id: uuid.UUID) -> Problem | None:
    return await db.scalar(
        select(Problem).options(selectinload(Problem.contest)).where(Problem.id == problem_id)
    )


async def create_submission(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    problem_id: uuid.UUID,
    language: Language,
    code: str,
) -> Submission:
    submission = Submission(
        user_id=user_id,
        problem_id=problem_id,
        language=language,
        code=code,
        status=SubmissionStatus.PENDING,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return submission


async def get_submission(db: AsyncSession, submission_id: uuid.UUID) -> Submission | None:
    return await db.scalar(
        select(Submission)
        .options(
            selectinload(Submission.verdict),
            selectinload(Submission.test_results),
            selectinload(Submission.problem),
        )
        .where(Submission.id == submission_id)
    )


async def list_submissions(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    problem_id: uuid.UUID | None = None,
    status: SubmissionStatus | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Submission], int]:
    conditions = []
    if user_id is not None:
        conditions.append(Submission.user_id == user_id)
    if problem_id is not None:
        conditions.append(Submission.problem_id == problem_id)
    if status is not None:
        conditions.append(Submission.status == status)

    total = await db.scalar(select(func.count()).select_from(Submission).where(*conditions))
    result = await db.scalars(
        select(Submission)
        .options(selectinload(Submission.verdict))
        .where(*conditions)
        .order_by(Submission.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return list(result), int(total or 0)


async def reset_for_rejudge(db: AsyncSession, submission: Submission) -> Submission:
    await db.execute(delete(SubmissionTestResult).where(SubmissionTestResult.submission_id == submission.id))
    await db.execute(delete(Verdict).where(Verdict.submission_id == submission.id))
    await db.execute(
        update(Submission)
        .where(Submission.id == submission.id)
        .values(
            status=SubmissionStatus.PENDING,
            time_ms=None,
            memory_kb=None,
            compile_output=None,
            runtime_output=None,
            judge_started_at=None,
            judged_at=None,
            total_tests=0,
            passed_tests=0,
            error_message=None,
            celery_task_id=None,
        )
    )
    await db.commit()
    await db.refresh(submission)
    return submission

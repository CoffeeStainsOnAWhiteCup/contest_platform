import uuid
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    Contest,
    ContestStatus,
    Problem,
    Submission,
    SubmissionTestResult,
    Test,
)


async def list_contests(
    db: AsyncSession,
    *,
    status: ContestStatus | None,
    visible_statuses: Iterable[ContestStatus] | None,
    page: int,
    size: int,
) -> tuple[list[Contest], int]:
    conditions = []
    if status is not None:
        conditions.append(Contest.status == status)
    if visible_statuses is not None:
        conditions.append(Contest.status.in_(list(visible_statuses)))

    total = await db.scalar(
        select(func.count()).select_from(Contest).where(*conditions)
    )
    contests = await db.scalars(
        select(Contest)
        .where(*conditions)
        .order_by(Contest.start_at.desc(), Contest.id)
        .offset((page - 1) * size)
        .limit(size)
    )
    return list(contests), int(total or 0)


async def get_contest(
    db: AsyncSession,
    contest_id: uuid.UUID,
    *,
    with_problems: bool = False,
) -> Contest | None:
    statement = select(Contest)
    if with_problems:
        statement = statement.options(selectinload(Contest.problems))
    return await db.scalar(statement.where(Contest.id == contest_id))


async def create_contest(db: AsyncSession, values: dict) -> Contest:
    contest = Contest(**values)
    db.add(contest)
    await db.commit()
    await db.refresh(contest)
    return contest


async def update_contest(
    db: AsyncSession, contest: Contest, values: dict
) -> Contest:
    for field, value in values.items():
        setattr(contest, field, value)
    await db.commit()
    await db.refresh(contest)
    return contest


async def delete_contest(db: AsyncSession, contest: Contest) -> None:
    await db.delete(contest)
    await db.commit()


async def count_submissions_for_contest(
    db: AsyncSession, contest_id: uuid.UUID
) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(Submission)
        .join(Problem, Submission.problem_id == Problem.id)
        .where(Problem.contest_id == contest_id)
    )
    return int(count or 0)


async def get_problem(
    db: AsyncSession,
    problem_id: uuid.UUID,
    *,
    with_contest: bool = False,
    with_tests: bool = False,
) -> Problem | None:
    statement = select(Problem)
    if with_contest:
        statement = statement.options(selectinload(Problem.contest))
    if with_tests:
        statement = statement.options(selectinload(Problem.tests))
    return await db.scalar(statement.where(Problem.id == problem_id))


async def list_problems(db: AsyncSession, contest_id: uuid.UUID) -> list[Problem]:
    problems = await db.scalars(
        select(Problem)
        .where(Problem.contest_id == contest_id)
        .order_by(Problem.ordinal, Problem.id)
    )
    return list(problems)


async def next_problem_ordinal(db: AsyncSession, contest_id: uuid.UUID) -> int:
    current = await db.scalar(
        select(func.max(Problem.ordinal)).where(Problem.contest_id == contest_id)
    )
    return int(current or 0) + 1


async def create_problem(db: AsyncSession, values: dict) -> Problem:
    problem = Problem(**values)
    db.add(problem)
    await db.commit()
    await db.refresh(problem)
    return problem


async def update_problem(
    db: AsyncSession, problem: Problem, values: dict
) -> Problem:
    for field, value in values.items():
        setattr(problem, field, value)
    await db.commit()
    await db.refresh(problem)
    return problem


async def delete_problem(db: AsyncSession, problem: Problem) -> None:
    await db.delete(problem)
    await db.commit()


async def count_submissions_for_problem(
    db: AsyncSession, problem_id: uuid.UUID
) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(Submission)
        .where(Submission.problem_id == problem_id)
    )
    return int(count or 0)


async def list_tests(db: AsyncSession, problem_id: uuid.UUID) -> list[Test]:
    tests = await db.scalars(
        select(Test)
        .where(Test.problem_id == problem_id)
        .order_by(Test.ordinal, Test.id)
    )
    return list(tests)


async def get_test(
    db: AsyncSession, problem_id: uuid.UUID, test_id: uuid.UUID
) -> Test | None:
    return await db.scalar(
        select(Test).where(Test.id == test_id, Test.problem_id == problem_id)
    )


async def next_test_ordinal(db: AsyncSession, problem_id: uuid.UUID) -> int:
    current = await db.scalar(
        select(func.max(Test.ordinal)).where(Test.problem_id == problem_id)
    )
    return int(current or 0) + 1


async def create_test(db: AsyncSession, values: dict) -> Test:
    test = Test(**values)
    db.add(test)
    await db.commit()
    await db.refresh(test)
    return test


async def update_test(db: AsyncSession, test: Test, values: dict) -> Test:
    for field, value in values.items():
        setattr(test, field, value)
    await db.commit()
    await db.refresh(test)
    return test


async def delete_test(db: AsyncSession, test: Test) -> None:
    await db.delete(test)
    await db.commit()


async def count_test_results(db: AsyncSession, test_id: uuid.UUID) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(SubmissionTestResult)
        .where(SubmissionTestResult.test_id == test_id)
    )
    return int(count or 0)

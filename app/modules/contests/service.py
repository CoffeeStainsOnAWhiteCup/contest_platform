import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Contest, ContestStatus, Problem, Test, User
from app.modules.contests import repository
from app.modules.contests.policy import (
    PARTICIPANT_VISIBLE_STATUSES,
    as_utc,
    can_submit_to_contest,
    can_view_contest,
    is_privileged,
)
from app.modules.contests.schemas import (
    ContestCreate,
    ContestDetail,
    ContestListResponse,
    ContestRead,
    ContestUpdate,
    ProblemCreate,
    ProblemDetail,
    ProblemSummary,
    ProblemUpdate,
    SampleTestRead,
    TestCreate,
    TestRead,
    TestUpdate,
)


def _contest_read(contest: Contest) -> ContestRead:
    return ContestRead.model_validate(contest).model_copy(
        update={"can_submit": can_submit_to_contest(contest)}
    )


def _sorted_problems(problems: list[Problem]) -> list[Problem]:
    return sorted(problems, key=lambda item: (item.ordinal, str(item.id)))


def _sorted_tests(tests: list[Test]) -> list[Test]:
    return sorted(tests, key=lambda item: (item.ordinal, str(item.id)))


def _problem_detail(problem: Problem, tests: list[Test]) -> ProblemDetail:
    summary = ProblemSummary.model_validate(problem)
    samples = [
        SampleTestRead.model_validate(test)
        for test in _sorted_tests(tests)
        if test.is_sample
    ]
    return ProblemDetail(
        **summary.model_dump(),
        contest_id=problem.contest_id,
        statement=problem.statement,
        samples=samples,
    )


async def _get_contest(db: AsyncSession, contest_id: uuid.UUID) -> Contest:
    contest = await repository.get_contest(db, contest_id)
    if contest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )
    return contest


async def _get_visible_contest(
    db: AsyncSession, user: User | None, contest_id: uuid.UUID
) -> Contest:
    contest = await _get_contest(db, contest_id)
    if not can_view_contest(user, contest):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )
    return contest


async def _get_problem(
    db: AsyncSession,
    problem_id: uuid.UUID,
    *,
    with_contest: bool = False,
    with_tests: bool = False,
) -> Problem:
    problem = await repository.get_problem(
        db,
        problem_id,
        with_contest=with_contest,
        with_tests=with_tests,
    )
    if problem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found"
        )
    return problem


async def _get_visible_problem(
    db: AsyncSession, user: User, problem_id: uuid.UUID
) -> Problem:
    problem = await _get_problem(
        db, problem_id, with_contest=True, with_tests=True
    )
    if not can_view_contest(user, problem.contest):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found"
        )
    return problem


async def list_contests(
    db: AsyncSession,
    user: User | None,
    *,
    status_filter: ContestStatus | None,
    page: int,
    size: int,
) -> ContestListResponse:
    visible_statuses = (
        None if is_privileged(user) else PARTICIPANT_VISIBLE_STATUSES
    )
    contests, total = await repository.list_contests(
        db,
        status=status_filter,
        visible_statuses=visible_statuses,
        page=page,
        size=size,
    )
    return ContestListResponse(
        items=[_contest_read(contest) for contest in contests],
        total=total,
        page=page,
        size=size,
    )


async def get_contest(
    db: AsyncSession, user: User | None, contest_id: uuid.UUID
) -> ContestDetail:
    contest = await repository.get_contest(db, contest_id, with_problems=True)
    if contest is None or not can_view_contest(user, contest):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )
    base = _contest_read(contest)
    problems = [
        ProblemSummary.model_validate(problem)
        for problem in _sorted_problems(contest.problems)
    ]
    return ContestDetail(**base.model_dump(), problems=problems)


async def create_contest(
    db: AsyncSession, payload: ContestCreate
) -> ContestRead:
    contest = await repository.create_contest(db, payload.model_dump())
    return _contest_read(contest)


async def update_contest(
    db: AsyncSession, contest_id: uuid.UUID, payload: ContestUpdate
) -> ContestRead:
    contest = await _get_contest(db, contest_id)
    values = payload.model_dump(exclude_unset=True)
    if not values:
        return _contest_read(contest)

    start_at = values.get("start_at", contest.start_at)
    end_at = values.get("end_at", contest.end_at)
    if as_utc(end_at) <= as_utc(start_at):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_at must be after start_at",
        )

    contest = await repository.update_contest(db, contest, values)
    return _contest_read(contest)


async def delete_contest(db: AsyncSession, contest_id: uuid.UUID) -> None:
    contest = await _get_contest(db, contest_id)
    submission_count = await repository.count_submissions_for_contest(
        db, contest.id
    )
    if submission_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contest has submissions and cannot be deleted",
        )
    await repository.delete_contest(db, contest)


async def create_problem(
    db: AsyncSession, contest_id: uuid.UUID, payload: ProblemCreate
) -> ProblemDetail:
    contest = await _get_contest(db, contest_id)
    contest_key = contest.id
    values = payload.model_dump()
    requested_ordinal = values.pop("ordinal")
    if requested_ordinal is not None and await repository.problem_ordinal_exists(
        db, contest_key, requested_ordinal
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Problem ordinal already exists in this contest",
        )

    for attempt in range(2):
        ordinal = requested_ordinal
        if ordinal is None:
            ordinal = await repository.next_problem_ordinal(db, contest_key)
        try:
            problem = await repository.create_problem(
                db,
                {
                    **values,
                    "contest_id": contest_key,
                    "ordinal": ordinal,
                },
            )
            return _problem_detail(problem, [])
        except IntegrityError:
            await db.rollback()
            if requested_ordinal is not None or attempt == 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Problem ordinal already exists in this contest",
                ) from None

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Problem ordinal already exists in this contest",
    )


async def get_problem(
    db: AsyncSession, user: User, problem_id: uuid.UUID
) -> ProblemDetail:
    problem = await _get_visible_problem(db, user, problem_id)
    return _problem_detail(problem, list(problem.tests))


async def update_problem(
    db: AsyncSession, problem_id: uuid.UUID, payload: ProblemUpdate
) -> ProblemDetail:
    problem = await _get_problem(db, problem_id, with_contest=True)
    values = payload.model_dump(exclude_unset=True)
    if not values:
        tests = await repository.list_tests(db, problem.id)
        return _problem_detail(problem, tests)

    if "ordinal" in values and await repository.problem_ordinal_exists(
        db,
        problem.contest_id,
        values["ordinal"],
        exclude_problem_id=problem.id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Problem ordinal already exists in this contest",
        )

    try:
        await repository.update_problem(db, problem, values)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Problem ordinal already exists in this contest",
        ) from None

    updated = await _get_problem(
        db, problem_id, with_contest=True, with_tests=True
    )
    return _problem_detail(updated, list(updated.tests))


async def delete_problem(db: AsyncSession, problem_id: uuid.UUID) -> None:
    problem = await _get_problem(db, problem_id)
    submission_count = await repository.count_submissions_for_problem(
        db, problem.id
    )
    if submission_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Problem has submissions and cannot be deleted",
        )
    await repository.delete_problem(db, problem)


async def list_tests(
    db: AsyncSession, problem_id: uuid.UUID
) -> list[TestRead]:
    await _get_problem(db, problem_id)
    tests = await repository.list_tests(db, problem_id)
    return [TestRead.model_validate(test) for test in tests]


async def create_test(
    db: AsyncSession, problem_id: uuid.UUID, payload: TestCreate
) -> TestRead:
    problem = await _get_problem(db, problem_id)
    problem_key = problem.id
    values = payload.model_dump()
    requested_ordinal = values.pop("ordinal")
    if requested_ordinal is not None and await repository.test_ordinal_exists(
        db, problem_key, requested_ordinal
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Test ordinal already exists in this problem",
        )

    for attempt in range(2):
        ordinal = requested_ordinal
        if ordinal is None:
            ordinal = await repository.next_test_ordinal(db, problem_key)
        try:
            test = await repository.create_test(
                db,
                {
                    **values,
                    "problem_id": problem_key,
                    "ordinal": ordinal,
                },
            )
            return TestRead.model_validate(test)
        except IntegrityError:
            await db.rollback()
            if requested_ordinal is not None or attempt == 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Test ordinal already exists in this problem",
                ) from None

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Test ordinal already exists in this problem",
    )


async def update_test(
    db: AsyncSession,
    problem_id: uuid.UUID,
    test_id: uuid.UUID,
    payload: TestUpdate,
) -> TestRead:
    await _get_problem(db, problem_id)
    test = await repository.get_test(db, problem_id, test_id)
    if test is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test not found"
        )
    values = payload.model_dump(exclude_unset=True)
    if not values:
        return TestRead.model_validate(test)

    if "ordinal" in values and await repository.test_ordinal_exists(
        db,
        test.problem_id,
        values["ordinal"],
        exclude_test_id=test.id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Test ordinal already exists in this problem",
        )

    try:
        test = await repository.update_test(db, test, values)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Test ordinal already exists in this problem",
        ) from None
    return TestRead.model_validate(test)


async def delete_test(
    db: AsyncSession, problem_id: uuid.UUID, test_id: uuid.UUID
) -> None:
    await _get_problem(db, problem_id)
    test = await repository.get_test(db, problem_id, test_id)
    if test is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test not found"
        )
    result_count = await repository.count_test_results(db, test.id)
    if result_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Test has submission results and cannot be deleted",
        )
    await repository.delete_test(db, test)

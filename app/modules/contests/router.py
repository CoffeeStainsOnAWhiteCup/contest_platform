import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional, require_roles
from app.core.database import get_db
from app.models.models import ContestStatus, User, UserRole
from app.modules.contests import service
from app.modules.contests.schemas import (
    ContestCreate,
    ContestDetail,
    ContestListResponse,
    ContestRead,
    ContestUpdate,
    ProblemCreate,
    ProblemDetail,
    ProblemUpdate,
    TestCreate,
    TestRead,
    TestUpdate,
)


contests_router = APIRouter(prefix="/contests", tags=["contests"])
problems_router = APIRouter(prefix="/problems", tags=["problems"])


@contests_router.get("", response_model=ContestListResponse)
async def list_contests(
    contest_status: ContestStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> ContestListResponse:
    return await service.list_contests(
        db,
        current_user,
        status_filter=contest_status,
        page=page,
        size=size,
    )


@contests_router.post(
    "", response_model=ContestRead, status_code=status.HTTP_201_CREATED
)
async def create_contest(
    payload: ContestCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> ContestRead:
    return await service.create_contest(db, payload)


@contests_router.get("/{contest_id}", response_model=ContestDetail)
async def get_contest(
    contest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> ContestDetail:
    return await service.get_contest(db, current_user, contest_id)


@contests_router.patch("/{contest_id}", response_model=ContestRead)
async def update_contest(
    contest_id: uuid.UUID,
    payload: ContestUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> ContestRead:
    return await service.update_contest(db, contest_id, payload)


@contests_router.delete(
    "/{contest_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_contest(
    contest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> None:
    await service.delete_contest(db, contest_id)


@contests_router.post(
    "/{contest_id}/problems",
    response_model=ProblemDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_problem(
    contest_id: uuid.UUID,
    payload: ProblemCreate,
    db: AsyncSession = Depends(get_db),
    _editor: User = Depends(require_roles(UserRole.ADMIN, UserRole.JUDGE)),
) -> ProblemDetail:
    return await service.create_problem(db, contest_id, payload)


@problems_router.get("/{problem_id}", response_model=ProblemDetail)
async def get_problem(
    problem_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProblemDetail:
    return await service.get_problem(db, current_user, problem_id)


@problems_router.patch("/{problem_id}", response_model=ProblemDetail)
async def update_problem(
    problem_id: uuid.UUID,
    payload: ProblemUpdate,
    db: AsyncSession = Depends(get_db),
    _editor: User = Depends(require_roles(UserRole.ADMIN, UserRole.JUDGE)),
) -> ProblemDetail:
    return await service.update_problem(db, problem_id, payload)


@problems_router.delete(
    "/{problem_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_problem(
    problem_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _editor: User = Depends(require_roles(UserRole.ADMIN, UserRole.JUDGE)),
) -> None:
    await service.delete_problem(db, problem_id)


@problems_router.get("/{problem_id}/tests", response_model=list[TestRead])
async def list_tests(
    problem_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _editor: User = Depends(require_roles(UserRole.ADMIN, UserRole.JUDGE)),
) -> list[TestRead]:
    return await service.list_tests(db, problem_id)


@problems_router.post(
    "/{problem_id}/tests",
    response_model=TestRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_test(
    problem_id: uuid.UUID,
    payload: TestCreate,
    db: AsyncSession = Depends(get_db),
    _editor: User = Depends(require_roles(UserRole.ADMIN, UserRole.JUDGE)),
) -> TestRead:
    return await service.create_test(db, problem_id, payload)


@problems_router.patch(
    "/{problem_id}/tests/{test_id}", response_model=TestRead
)
async def update_test(
    problem_id: uuid.UUID,
    test_id: uuid.UUID,
    payload: TestUpdate,
    db: AsyncSession = Depends(get_db),
    _editor: User = Depends(require_roles(UserRole.ADMIN, UserRole.JUDGE)),
) -> TestRead:
    return await service.update_test(db, problem_id, test_id, payload)


@problems_router.delete(
    "/{problem_id}/tests/{test_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_test(
    problem_id: uuid.UUID,
    test_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _editor: User = Depends(require_roles(UserRole.ADMIN, UserRole.JUDGE)),
) -> None:
    await service.delete_test(db, problem_id, test_id)

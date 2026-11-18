import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import SubmissionStatus, User
from app.modules.submissions import service
from app.modules.submissions.schemas import (
    RejudgeResponse,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionListResponse,
)

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionDetail, status_code=status.HTTP_202_ACCEPTED)
async def create_submission(
    payload: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmissionDetail:
    return await service.create_submission(db, current_user, payload)


@router.get("/{submission_id}", response_model=SubmissionDetail)
async def get_submission(
    submission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmissionDetail:
    return await service.get_submission(db, current_user, submission_id)


@router.get("", response_model=SubmissionListResponse)
async def list_submissions(
    user_id: uuid.UUID | None = None,
    problem_id: uuid.UUID | None = None,
    submission_status: SubmissionStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmissionListResponse:
    items, total = await service.list_submissions(
        db,
        current_user,
        user_id=user_id,
        problem_id=problem_id,
        submission_status=submission_status,
        page=page,
        size=size,
    )
    return SubmissionListResponse(items=items, total=total, page=page, size=size)


@router.post("/{submission_id}/rejudge", response_model=RejudgeResponse, status_code=status.HTTP_202_ACCEPTED)
async def rejudge_submission(
    submission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RejudgeResponse:
    return await service.rejudge_submission(db, current_user, submission_id)

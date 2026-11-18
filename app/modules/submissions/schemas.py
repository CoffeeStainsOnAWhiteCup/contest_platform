import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.models import Language, SubmissionStatus, VerdictStatus


class SubmissionCreate(BaseModel):
    problem_id: uuid.UUID
    language: Language
    code: str = Field(min_length=1, max_length=65536)


class VerdictRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: VerdictStatus
    time_ms: int | None = None
    memory_kb: int | None = None
    message: str | None = None
    created_at: datetime


class SubmissionTestResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    test_id: uuid.UUID
    ordinal: int
    status: VerdictStatus
    time_ms: int | None = None
    memory_kb: int | None = None
    exit_code: int | None = None
    stderr_excerpt: str | None = None


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    problem_id: uuid.UUID
    language: Language
    status: SubmissionStatus
    time_ms: int | None = None
    memory_kb: int | None = None
    compile_output: str | None = None
    runtime_output: str | None = None
    total_tests: int
    passed_tests: int
    error_message: str | None = None
    created_at: datetime
    judged_at: datetime | None = None
    verdict: VerdictRead | None = None


class SubmissionDetail(SubmissionRead):
    test_results: list[SubmissionTestResultRead] = Field(default_factory=list)


class SubmissionListResponse(BaseModel):
    items: list[SubmissionRead]
    total: int
    page: int
    size: int


class RejudgeResponse(BaseModel):
    id: uuid.UUID
    status: SubmissionStatus

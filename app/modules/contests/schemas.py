import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from app.models.models import ContestStatus


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _trim_optional(value):
    return value.strip() if isinstance(value, str) else value


def _reject_null(value, info: ValidationInfo):
    if value is None:
        raise ValueError(f"{info.field_name} cannot be null")
    return value


class ContestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    start_at: datetime
    end_at: datetime
    status: ContestStatus = ContestStatus.DRAFT

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value, info: ValidationInfo):
        return _trim_optional(_reject_null(value, info))

    @field_validator("start_at", "end_at")
    @classmethod
    def normalize_datetimes(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class ContestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: ContestStatus | None = None

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value, info: ValidationInfo):
        return _trim_optional(_reject_null(value, info))

    @field_validator("start_at", "end_at")
    @classmethod
    def normalize_datetimes(cls, value, info: ValidationInfo) -> datetime:
        return _as_utc(_reject_null(value, info))

    @field_validator("status", mode="before")
    @classmethod
    def reject_null_status(cls, value, info: ValidationInfo):
        return _reject_null(value, info)


class ContestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None = None
    start_at: datetime
    end_at: datetime
    status: ContestStatus
    created_at: datetime
    can_submit: bool = False


class ProblemSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    ordinal: int
    time_limit_ms: int
    memory_limit_mb: int


class ContestDetail(ContestRead):
    problems: list[ProblemSummary] = Field(default_factory=list)


class ContestListResponse(BaseModel):
    items: list[ContestRead]
    total: int
    page: int
    size: int


class ProblemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    statement: str = Field(min_length=1)
    time_limit_ms: int = Field(default=1000, ge=1)
    memory_limit_mb: int = Field(default=256, ge=1)
    ordinal: int | None = Field(default=None, ge=1)

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value, info: ValidationInfo):
        return _trim_optional(_reject_null(value, info))


class ProblemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    statement: str | None = Field(default=None, min_length=1)
    time_limit_ms: int | None = Field(default=None, ge=1)
    memory_limit_mb: int | None = Field(default=None, ge=1)
    ordinal: int | None = Field(default=None, ge=1)

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value, info: ValidationInfo):
        return _trim_optional(_reject_null(value, info))

    @field_validator(
        "statement",
        "time_limit_ms",
        "memory_limit_mb",
        "ordinal",
        mode="before",
    )
    @classmethod
    def reject_null_fields(cls, value, info: ValidationInfo):
        return _reject_null(value, info)


class SampleTestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ordinal: int
    input_data: str
    expected_output: str


class ProblemDetail(ProblemSummary):
    contest_id: uuid.UUID
    statement: str
    samples: list[SampleTestRead] = Field(default_factory=list)


class TestCreate(BaseModel):
    input_data: str = Field(max_length=1_000_000)
    expected_output: str = Field(max_length=1_000_000)
    is_sample: bool = False
    ordinal: int | None = Field(default=None, ge=1)


class TestUpdate(BaseModel):
    input_data: str | None = Field(default=None, max_length=1_000_000)
    expected_output: str | None = Field(default=None, max_length=1_000_000)
    is_sample: bool | None = None
    ordinal: int | None = Field(default=None, ge=1)

    @field_validator(
        "input_data", "expected_output", "is_sample", "ordinal", mode="before"
    )
    @classmethod
    def reject_null_fields(cls, value, info: ValidationInfo):
        return _reject_null(value, info)


class TestRead(SampleTestRead):
    id: uuid.UUID
    is_sample: bool

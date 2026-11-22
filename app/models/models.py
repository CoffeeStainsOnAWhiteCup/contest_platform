import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UserRole(str, PyEnum):
    PARTICIPANT = "participant"
    JUDGE = "judge"
    ADMIN = "admin"


class ContestStatus(str, PyEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ACTIVE = "active"
    FINISHED = "finished"
    ARCHIVED = "archived"


class Language(str, PyEnum):
    PYTHON = "python"
    CPP = "cpp"
    JAVA = "java"


class SubmissionStatus(str, PyEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    ACCEPTED = "ACCEPTED"
    WRONG_ANSWER = "WRONG_ANSWER"
    COMPILE_ERROR = "COMPILE_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
    MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED"
    SYSTEM_ERROR = "SYSTEM_ERROR"


class VerdictStatus(str, PyEnum):
    ACCEPTED = "ACCEPTED"
    WRONG_ANSWER = "WRONG_ANSWER"
    COMPILE_ERROR = "COMPILE_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
    MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED"
    SYSTEM_ERROR = "SYSTEM_ERROR"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.PARTICIPANT, nullable=False)

    name_customized: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    auth_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    telegram_linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    github_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    submissions: Mapped[list["Submission"]] = relationship(back_populates="user")


class Contest(Base):
    __tablename__ = "contests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ContestStatus] = mapped_column(Enum(ContestStatus), default=ContestStatus.DRAFT, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    rating_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    problems: Mapped[list["Problem"]] = relationship(back_populates="contest", cascade="all, delete-orphan")


class Problem(Base):
    __tablename__ = "problems"
    __table_args__ = (
        UniqueConstraint("contest_id", "ordinal", name="uq_problems_contest_ordinal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contest_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contests.id"), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)

    time_limit_ms: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256, nullable=False)

    contest: Mapped["Contest"] = relationship(back_populates="problems")
    tests: Mapped[list["Test"]] = relationship(back_populates="problem", cascade="all, delete-orphan")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="problem")


class Test(Base):
    __tablename__ = "tests"
    __table_args__ = (
        UniqueConstraint("problem_id", "ordinal", name="uq_tests_problem_ordinal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("problems.id"), nullable=False, index=True)
    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    problem: Mapped["Problem"] = relationship(back_populates="tests")
    test_results: Mapped[list["SubmissionTestResult"]] = relationship(back_populates="test")


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        Index("ix_submissions_status_created_at", "status", "created_at"),
        Index("ix_submissions_user_created_at", "user_id", "created_at"),
        Index("ix_submissions_problem_created_at", "problem_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    problem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("problems.id"), nullable=False, index=True)

    language: Mapped[Language] = mapped_column(Enum(Language), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus), default=SubmissionStatus.PENDING, nullable=False
    )

    time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_kb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compile_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_output: Mapped[str | None] = mapped_column(Text, nullable=True)

    judge_attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    judge_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    judged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_tests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_tests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="submissions")
    problem: Mapped["Problem"] = relationship(back_populates="submissions")
    verdict: Mapped["Verdict | None"] = relationship(
        back_populates="submission", cascade="all, delete-orphan", uselist=False
    )
    test_results: Mapped[list["SubmissionTestResult"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan", order_by="SubmissionTestResult.ordinal"
    )


class Verdict(Base):
    __tablename__ = "verdicts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[VerdictStatus] = mapped_column(Enum(VerdictStatus), nullable=False)
    time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_kb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    submission: Mapped["Submission"] = relationship(back_populates="verdict")


class SubmissionTestResult(Base):
    __tablename__ = "submission_test_results"
    __table_args__ = (
        UniqueConstraint("submission_id", "test_id", name="uq_submission_test_result"),
        Index("ix_submission_test_results_submission_ordinal", "submission_id", "ordinal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[VerdictStatus] = mapped_column(Enum(VerdictStatus), nullable=False)
    time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_kb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stderr_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    submission: Mapped["Submission"] = relationship(back_populates="test_results")
    test: Mapped["Test"] = relationship(back_populates="test_results")


class UserAudit(Base):
    __tablename__ = "user_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    field: Mapped[str] = mapped_column(String(24))
    old_value: Mapped[str] = mapped_column(String(48))
    new_value: Mapped[str] = mapped_column(String(48))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    """Durable queue and delivery log, one message per user and event."""
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "event_key", name="uq_notification_event"),
        Index("ix_notification_due", "status", "available_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    chat_id: Mapped[str] = mapped_column(String(100))
    event_key: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    transient_failures: Mapped[int] = mapped_column(default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(80))

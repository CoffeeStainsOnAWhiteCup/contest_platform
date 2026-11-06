import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

# --- Перечисления (Enums) ---
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

# --- Модели ---
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.PARTICIPANT, nullable=False)
    
    # Для GitHub OAuth
    github_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    
    # Для Telegram
    telegram_chat_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    submissions: Mapped[list["Submission"]] = relationship(back_populates="user")

class Contest(Base):
    __tablename__ = "contests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[ContestStatus] = mapped_column(Enum(ContestStatus), default=ContestStatus.DRAFT, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    problems: Mapped[list["Problem"]] = relationship(back_populates="contest", cascade="all, delete-orphan")

class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contest_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contests.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    
    time_limit_ms: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256, nullable=False)

    # Связи
    contest: Mapped["Contest"] = relationship(back_populates="problems")
    tests: Mapped[list["Test"]] = relationship(back_populates="problem", cascade="all, delete-orphan")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="problem")

class Test(Base):
    __tablename__ = "tests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("problems.id"), nullable=False)
    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False) # Для примеров в условии

    # Связи
    problem: Mapped["Problem"] = relationship(back_populates="tests")

class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    problem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("problems.id"), nullable=False)
    
    language: Mapped[str] = mapped_column(String(50), nullable=False) # python, cpp, java
    code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(Enum(SubmissionStatus), default=SubmissionStatus.PENDING, nullable=False)
    
    # Результаты проверки (заполняются воркером)
    time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_kb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compile_output: Mapped[str | None] = mapped_column(Text, nullable=True) # Ошибки компиляции
    runtime_output: Mapped[str | None] = mapped_column(Text, nullable=True) # Ошибки выполнения (stderr)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    user: Mapped["User"] = relationship(back_populates="submissions")
    problem: Mapped["Problem"] = relationship(back_populates="submissions")

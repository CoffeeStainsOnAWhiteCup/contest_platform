"""Populate the demo database. Run with python -m tools.seed_demo --help."""

import argparse
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import SyncSessionLocal
from app.models.models import (
    Contest,
    ContestStatus,
    Language,
    Problem,
    Submission,
    SubmissionStatus,
    SubmissionTestResult,
    Test,
    User,
    UserRole,
    Verdict,
    VerdictStatus,
    utcnow,
)
from app.modules.auth.security import hash_password

ACCOUNTS = (
    ("admin", "Организатор демо", UserRole.ADMIN),
    ("judge", "Судья демо", UserRole.JUDGE),
    ("anna", "Анна Демо", UserRole.PARTICIPANT),
    ("ivan", "Иван Демо", UserRole.PARTICIPANT),
)
SUM_CASES = (("2 3", "5"), ("-4 10", "6"), ("0 0", "0"))
MAX_CASES = (("2 7", "7"), ("-4 -1", "-1"), ("3 3", "3"))
SUM_CODE = "print(sum(map(int, input().split())))"


def demo_id(key: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"contest-platform/demo/v1/{key}")


def problem(title: str, statement: str, cases: tuple[tuple[str, str], ...], ordinal: int = 1) -> Problem:
    return Problem(
        ordinal=ordinal,
        title=title,
        statement=statement,
        time_limit_ms=2000,
        memory_limit_mb=128,
        tests=[
            Test(ordinal=i, input_data=given + "\n", expected_output=answer + "\n", is_sample=i == 1)
            for i, (given, answer) in enumerate(cases, start=1)
        ],
    )


def sum_problem() -> Problem:
    return problem(
        "Сумма двух чисел", "В одной строке даны два целых числа через пробел. Выведите их сумму.", SUM_CASES
    )


def sample_result(user: User, task: Problem, when: datetime, accepted: bool) -> Submission:
    """A historical example, including the verdict and the cases actually reached."""
    status = VerdictStatus.ACCEPTED if accepted else VerdictStatus.WRONG_ANSWER
    finished = when + timedelta(seconds=1)
    reached = task.tests if accepted else task.tests[:1]
    return Submission(
        user=user,
        problem=task,
        created_at=when,
        updated_at=finished,
        judged_at=finished,
        judge_started_at=when,
        judge_attempt=1,
        language=Language.PYTHON,
        code=SUM_CODE if accepted else "print(0)",
        status=SubmissionStatus(status.value),
        total_tests=len(task.tests),
        passed_tests=len(task.tests) if accepted else 0,
        verdict=Verdict(status=status, created_at=finished),
        test_results=[
            SubmissionTestResult(test=t, ordinal=t.ordinal, status=status, exit_code=0, created_at=finished)
            for t in reached
        ],
    )


def populate(db: Session, live: str | None) -> tuple[list[tuple[str, str]], Contest | None]:
    # Two terminals starting the same demo must observe the same committed schedule.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('contest-platform/demo/v1'))"))
    now = utcnow()
    users = {}
    credentials = []
    for login, name, role in ACCOUNTS:
        uid = demo_id("user/" + login)
        user = db.get(User, uid)
        if user is None:
            email = f"demo.{login}@example.com"
            if db.scalar(select(User.id).where(User.email == email)) is not None:
                raise ValueError(f"Адрес {email} уже занят. Создание демоданных отменено.")
            password = "D7-" + secrets.token_urlsafe(16)
            user = User(
                id=uid,
                email=email,
                name=name,
                role=role,
                password_hash=hash_password(password),
                created_at=now - timedelta(days=8),
            )
            db.add(user)
            credentials.append((email, password))
        users[login] = user

    if db.get(Contest, demo_id("training")) is None:
        maximum = problem(
            "Большее из двух", "В одной строке даны два целых числа. Выведите наибольшее.", MAX_CASES, ordinal=2
        )
        db.add(
            Contest(
                id=demo_id("training"),
                title="Демо · Тренировка",
                status=ContestStatus.ACTIVE,
                start_at=now - timedelta(days=1),
                end_at=now + timedelta(days=30),
                problems=[sum_problem(), maximum],
            )
        )

    if db.get(Contest, demo_id("history")) is None:
        start = now - timedelta(days=7)
        task = sum_problem()
        db.add(
            Contest(
                id=demo_id("history"),
                title="Демо · Прошлый тур",
                status=ContestStatus.FINISHED,
                start_at=start,
                end_at=start + timedelta(hours=1),
                created_at=start,
                problems=[task],
            )
        )
        db.add_all(
            [
                sample_result(users["anna"], task, start + timedelta(minutes=5), True),
                sample_result(users["ivan"], task, start + timedelta(minutes=4), False),
                sample_result(users["ivan"], task, start + timedelta(minutes=10), True),
            ]
        )

    contest = None
    if live is not None:
        key = demo_id("telegram/" + live)
        contest = db.get(Contest, key)
        if contest is None:
            start = now + timedelta(minutes=2)
            contest = Contest(
                id=key,
                title=f"Демо · Telegram · {live}",
                status=ContestStatus.ACTIVE,
                start_at=start,
                end_at=start + timedelta(minutes=10),
                problems=[sum_problem()],
            )
            db.add(contest)
    return credentials, contest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Добавить демоданные и при необходимости запланировать короткий конкурс."
    )
    parser.add_argument(
        "--database", default="contest_demo", help="ожидаемое имя базы (по умолчанию contest_demo)"
    )
    parser.add_argument(
        "--live", metavar="RUN", help="метка показа, например check-01; новая метка создаёт новый конкурс"
    )
    args = parser.parse_args()
    if args.live is not None and not re.fullmatch(r"[a-zA-Z0-9_-]{1,32}", args.live):
        parser.error("Используйте от 1 до 32 букв A–Z, цифр, дефисов или подчёркиваний для --live.")

    try:
        with SyncSessionLocal.begin() as db:
            actual = db.scalar(text("SELECT current_database()"))
            if actual != args.database:
                parser.error(f"Подключение ведёт в {actual}, ожидалась база {args.database}.")
            credentials, contest = populate(db, args.live)
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    print(f"Демоданные готовы в {actual}.")
    if credentials:
        print("Сохраните пароли новых демоаккаунтов. Они выводятся только при создании.")
        for email, password in credentials:
            print(f"{email}  {password}")
    if contest is not None:
        print(contest.title)
        print("Начало (UTC):", contest.start_at.astimezone(timezone.utc).isoformat(timespec="seconds"))
        print("Конец  (UTC):", contest.end_at.astimezone(timezone.utc).isoformat(timespec="seconds"))


if __name__ == "__main__":
    main()

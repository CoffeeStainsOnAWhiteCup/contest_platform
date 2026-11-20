# Contests API: правила видимости и миграции

Сводка по ТЗ: FR-CONTEST-06, FR-CONTEST-07, FR-CONTEST-08, §5.4.

## Видимость конкурсов

| Роль | Видимые статусы |
|---|---|
| Гость / Participant | `published`, `active` |
| Judge / Admin | все: `draft`, `published`, `active`, `finished`, `archived` |

- `GET /api/v1/contests` и `GET /api/v1/contests/{id}` доступны без JWT.
- Нет токена — гость; невалидный токен — `401`.
- `finished` и `draft` для гостя и участника дают `404`.
- История решений участника остаётся доступна через `/api/v1/submissions`.

## Отправка решений

- FR-CONTEST-07: решения принимаются только в конкурсах в статусе `active`
  и в пределах интервала `start_at`–`end_at`.
- `published` доступен для просмотра, но отправка в нём запрещена.

## Номера задач

- `Problem.ordinal` уникален в рамках конкурса: `(contest_id, ordinal)`.
- `Test.ordinal` уникален в рамках задачи: `(problem_id, ordinal)`.
- Для новых задач/тестов номер вычисляется как `max + 1` внутри родителя.
- Явный дубликат номера возвращает `409`.

## Порядок запуска миграций

`docker compose up -d` сначала выполняет сервис `migrate`
(`alembic upgrade head`), затем запускает `api` и `worker`.

`Base.metadata.create_all` в приложении больше не вызывается.

### База уже ведётся через Alembic

```bash
alembic upgrade head
```

### База когда-то создана через create_all

Сначала сверить фактическую схему с ревизией:

- схема без `problems.ordinal` — `alembic stamp 6d233f26b0ba`, затем
  `alembic upgrade head`;
- схема уже соответствует `head` — `alembic stamp head`.

Удалять том не требуется.

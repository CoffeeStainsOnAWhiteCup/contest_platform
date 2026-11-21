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

### База не ведётся через Alembic

`alembic stamp` только записывает номер ревизии и схему не меняет. Нельзя
ставить ревизию по признаку отсутствия одной колонки: начальная ревизия
`6d233f26b0ba` включает и другие объекты (`tests.ordinal`, `verdicts`,
`submission_test_results`, дополнительные колонки и индексы `submissions`).
Успешный `alembic upgrade head` тоже не доказывает полноту схемы: например,
отсутствие `submissions.total_tests` он не заметит.

Проверка делается на клоне. Важно направить на копию **оба** URL:
`alembic/env.py` использует `SYNC_DATABASE_URL`, а не `DATABASE_URL`.

```bash
export DATABASE_URL=...          # копия базы, +asyncpg
export SYNC_DATABASE_URL=...     # копия базы, +psycopg
psql "$SYNC_DATABASE_URL" -c "select current_database()"
alembic stamp 6d233f26b0ba
alembic upgrade head
alembic check
```

Убедись, что `alembic_version` и изменения появились именно в копии, а
`alembic check` не находит недостающих объектов. Только после этого повторяй
команды на реальной базе. Если проверки не проходят — схема не соответствует
`6d233`, нужен перенос данных.

### Старая схема с сохранением данных

Для баз вроде `01a24b5` (нет `tests.ordinal`, `verdicts`,
`submission_test_results`, части колонок `submissions`) данные переносятся
отдельно:

1. выгрузить данные: `pg_dump --data-only --column-inserts ... > data.sql`;
2. создать пустую базу и выполнить `alembic upgrade head`;
3. загрузить `data.sql`, при необходимости преобразовав данные
   (`language` в enum, порядковые номера, отсутствующие вердикты);
4. сверить схему (`alembic check`) и количество строк с исходной базой.

Для пустой dev-базы проще пересоздать том, чем переносить данные.

# Contest Platform

FastAPI принимает решения и хранит их в PostgreSQL. Redis обслуживает сессии, кэш рейтинга и очередь Celery. Worker проверяет решения через Docker. Сервис notifications доставляет события в Telegram.

## Запуск демонстрационного стенда

Из корня репозитория в PowerShell, при запущенном Docker Desktop:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
python tools/init_auth_env.py
docker compose up -d --build
Invoke-RestMethod http://localhost:8000/health
docker compose exec api python -m alembic check
```

Для существующей БД сохраните свои параметры подключения. Async и sync URL в локальном .env должны указывать на одну БД. Swagger доступен на http://localhost:8000/docs. Для демонстрации входа через GitHub в Swagger задайте GITHUB_FRONTEND_URL=http://localhost:8000/docs и зарегистрируйте GITHUB_CALLBACK_URL в OAuth-приложении. Для Telegram заполните локальные параметры из .env.example и зарегистрируйте публичный HTTPS-адрес webhook. Подробности приведены в [инструкции по OAuth](docs/AUTH_SESSIONS.md) и [контрактах рейтинга, профиля и Telegram](docs/BACKEND_API.md).

Новые пароли защищены bcrypt с cost 12 в формате bcrypt-sha256 v2. Предварительная обработка пароля сохраняет различия после 72-го байта. Ранее созданные хеши Argon2id продолжают проверяться и обновляются после успешного входа по паролю.

## Фронтенд

Интерфейс на React, TypeScript и Vite лежит в каталоге `frontend`. В Compose он собирается отдельным образом (nginx) и открывается на http://localhost:5173, а запросы к `/api` проксируются на сервис `api`. Для локальной разработки запустите API в Compose, затем:

```powershell
cd frontend
npm ci
npm run dev
```

Dev-сервер слушает порт 5173 и проксирует `/api` на http://localhost:8000, поэтому `GITHUB_FRONTEND_URL` по умолчанию (`http://localhost:5173/auth/callback`) уже подходит. Базовый путь API задаёт `VITE_API_BASE_URL` (по умолчанию `/api/v1`). Типы генерируются из OpenAPI командой `npm run gen:api` (по умолчанию из снимка `frontend/openapi.json`, при необходимости задайте `OPENAPI_URL`). Проверки фронтенда:

```powershell
cd frontend
npm run typecheck
npm run lint
npm run test
npm run build
```

CI-воркфлой `frontend.yml` выполняет эти команды при изменениях в `frontend/`.

## Данные для демонстрации

В работающем Compose-проекте с базой `contest_demo` выполните:

```powershell
docker compose exec api python -m tools.seed_demo
```

Скрипт создаёт администратора, судью и двух участников с адресами
`demo.admin@example.com`, `demo.judge@example.com`, `demo.anna@example.com` и `demo.ivan@example.com`.
Пароли выводятся один раз при создании. Для тренировки доступны две задачи с примерами и скрытыми тестами.
В глобальный рейтинг входят три демонстрационные посылки прошлого тура: Анна решила одну задачу со штрафом 5, Иван — одну со штрафом 30.
Повторный запуск сохраняет пользователей, привязки, пароли и расписание. Для другой демонстрационной БД явно укажите её имя через `--database`.

### Проверка Telegram и Judge

1. Откройте профиль своего участника и убедитесь, что Telegram привязан.
2. Когда готовы начать, выполните `docker compose exec api python -m tools.seed_demo --live check-01`.
   Откройте в разделе «Конкурсы» карточку «Демо · Telegram · check-01». Скрипт печатает время в UTC, сайт показывает время браузера.
   Старт через 2 минуты после создания, продолжительность 10 минут. Для повтора в другое время используйте новую метку, например `check-02`.
3. После сообщения о старте обновите страницу задачи «Сумма двух чисел». Выберите Python.
   Отправьте `print(0)` и дождитесь WRONG_ANSWER. Затем отправьте `print(sum(map(int, input().split())))` и дождитесь ACCEPTED.
   Сверьте каждое сообщение бота с вердиктом в разделе «Решения» и проверьте одну решённую задачу в таблице конкурса.
4. После конца интервала дождитесь сообщения о завершении. Начало и конец получают участники, которые привязали Telegram до соответствующего события. Вердикт получает владелец посылки.
   Фоновый обработчик проверяет очередь примерно каждые 10 секунд.
5. Если вердикт ещё не появился на сайте, смотрите `docker compose logs --since=5m worker`.
   Если вердикт уже есть, проверьте доставку через `docker compose logs --since=5m notifications`.

## Сценарий защиты

1. Подготовить администратора и участника на БД демонстрационного ноутбука. Войти участником, проверить профиль и привязать Telegram до начала контеста.
2. Администратором создать контест и задачу A+B с ограничениями в условии. Загрузить один из [примеров импорта](docs/CONTESTS_API.md). Участнику видны только примеры.
3. Установить статус active в интервале соревнования. Отправить неверное решение, затем правильное. Проверить WRONG_ANSWER и ACCEPTED в истории, число решённых задач 0 → 1 и оба сообщения в Telegram.
4. Выполнить rejudge под судьёй. После повторного ACCEPTED результат остаётся 1. Проверить уведомления о старте и завершении короткого контеста и отказ при попытке отправки после окончания.
5. Открыть /health и /metrics. HTTP-логи без query-параметров и токенов доступны администратору через `docker compose exec api tail /var/log/contest/http.jsonl`. В Compose используется суточная ротация файла API и 30 архивов.

## Проверки

```powershell
docker compose run --rm --build test sh -c 'AUTH_TEST_DATABASE_URL=$DATABASE_URL python -m pytest -q -ra --cov=app.modules.auth --cov=app.modules.rating --cov=app.modules.judge --cov-report=json:coverage.json && python -m tools.check_coverage coverage.json'
docker compose run --rm test python -m pytest -q -s tests/perf_routes.py
```

Используйте локальный тестовый PostgreSQL: фикстуры пересоздают таблицы в отдельной БД contest_test. Бенчмарк запускайте отдельно от основного прогона. Он открывает локальный HTTP-порт, создаёт 100 участников и 500 принятых решений, прогревает лидерборд и измеряет GET при 50 RPS и создание задач при 20 RPS. Для каждого профиля выводятся количество, p95 и максимум. Порог p95 составляет 50 мс для прогретого рейтинга и 500 мс для записи.

Для локальных линтеров установите requirements-dev.txt, затем выполните `ruff check .` и `mypy`. Для включения хуков установите pre-commit и выполните `pre-commit install` в этом окружении. CI проверяет PR, запускает Docker-тесты и разворачивает временный стенд. После слияния main публикует образ с тегом SHA в GHCR при разрешённой записи Packages. Демонстрационный ноутбук обновляется через git и Compose.

## Резервная копия

Сервис backup сохраняет архив фактической базы из DATABASE_URL при старте и затем раз в сутки в том postgres_backup. Архивы старше `BACKUP_RETENTION_DAYS` (по умолчанию 14) удаляются после успешного дампа. Не удаляйте тома при перезапуске. Для проверки можно восстановить копию в **новую пустую** базу. Внутри контейнера backup доступны pg_restore и psql. Перед восстановлением задайте отдельный адрес БД назначения, отличный от адреса работающей платформы.

```powershell
docker compose exec backup sh /opt/backup.sh --once
docker compose exec backup ls -lt /backups
```

После создания отдельной пустой базы в командной строке контейнера backup:

```sh
pg_restore --exit-on-error --dbname="$RESTORE_URL" "/backups/$ARCHIVE"
psql "$RESTORE_URL" -c 'SELECT version_num FROM alembic_version'
```

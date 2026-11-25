# Contest Platform

Платформа для проведения олимпиад по программированию. Участники отправляют решения на Python, C++ и Java, получают результаты проверки на сайте и могут подключить уведомления в Telegram.

## Запуск на Windows

Понадобятся Git, Docker Desktop с Linux-контейнерами и Docker Compose, Python 3 для генерации локальных ключей и PowerShell. Команды ниже выполняются из папки с `docker-compose.yml`. Для первой установки скачайте проект:

```powershell
git clone https://github.com/CoffeeStainsOnAWhiteCup/contest_platform.git
cd contest_platform
```

### 1. Подготовьте файл настроек

Если стенд уже работал на этом компьютере, используйте прежнюю папку проекта и существующий `.env`. Так Compose подключит тот же том PostgreSQL с аккаунтами, решениями и привязками Telegram.

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
python tools/init_auth_env.py
notepad .env
```

Скрипт заполнит пустой `JWT_SECRET_KEY` случайным ключом. При повторном запуске он сохранит имеющийся ключ. Если Python на Windows запускается через `py`, используйте `py -3` вместо `python`.

На **новом** стенде выберите пароль PostgreSQL и укажите его в трёх местах в `.env`. Для демонстрационной базы можно использовать такой набор строк. Замените `YOUR_DB_PASSWORD` во всех трёх строках одним паролем из букв и цифр.

```dotenv
POSTGRES_USER=contest_user
POSTGRES_PASSWORD=YOUR_DB_PASSWORD
POSTGRES_DB=contest_demo
DATABASE_URL=postgresql+asyncpg://contest_user:YOUR_DB_PASSWORD@db:5432/contest_demo
SYNC_DATABASE_URL=postgresql+psycopg://contest_user:YOUR_DB_PASSWORD@db:5432/contest_demo
```

На **существующем** стенде оставьте его имя базы, пользователя, пароль и обе строки подключения. Параметры Redis, Celery и проверки решений для обычного запуска уже заданы в `.env.example`. Храните рабочий `.env` локально.

### 2. Настройте интеграции в том же .env

**Telegram.** Создайте бота командой `/newbot` у `@BotFather` или используйте своего действующего бота. Заполните три поля:

| Параметр | Что вписать |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен бота, выданный BotFather |
| `TELEGRAM_BOT_USERNAME` | Имя этого бота без символа `@` |
| `TELEGRAM_WEBHOOK_SECRET` | Отдельный секрет. Для нового стенда выполните `python -c "import secrets; print(secrets.token_hex(32))"` и вставьте результат |

Для локального webhook понадобится **ngrok authtoken** из вашего аккаунта ngrok. Его запросит скрипт на шаге 4. Если нужны только сайт и проверка решений, поля Telegram можно оставить пустыми и пропустить шаг 4.

**Вход через GitHub.** Для обычной регистрации и входа по паролю достаточно настроек шага 1. Чтобы включить кнопку входа через GitHub, создайте OAuth App в настройках GitHub, в разделе **Developer settings → OAuth Apps**. Укажите Homepage URL `http://localhost:5173` и Authorization callback URL `http://localhost:8000/api/v1/auth/github/callback`. Внесите данные этого приложения в `.env`:

```dotenv
GITHUB_CLIENT_ID=ваш_client_id
GITHUB_CLIENT_SECRET=ваш_client_secret
GITHUB_CALLBACK_URL=http://localhost:8000/api/v1/auth/github/callback
GITHUB_FRONTEND_URL=http://localhost:5173/auth/callback
```

### 3. Запустите платформу

Запустите Docker Desktop, дождитесь готовности движка и выполните:

```powershell
docker compose up -d --build
docker compose ps -a
Invoke-RestMethod http://localhost:8000/health
```

Compose поднимет PostgreSQL, Redis, API, фронтенд, обработчики решений и уведомлений и сервис резервного копирования. Одноразовый контейнер `migrate` применяет миграции и завершается с кодом 0. Если API ещё запускается, повторите запрос к `/health` через несколько секунд.

- Сайт — [localhost:5173](http://localhost:5173).
- Swagger UI — [localhost:8000/docs](http://localhost:8000/docs).

Зарегистрируйтесь на сайте для входа под участником. При первом старте Docker потребуется интернет для загрузки образов. Образы для языков проверки worker скачивает при первом использовании.

### 4. Запустите Telegram и привяжите чат

```powershell
.\tools\start-telegram.ps1
```

Если PowerShell блокирует выполнение локальных скриптов, для этого запуска используйте `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\start-telegram.ps1`.

При первом запросе введите **ngrok authtoken**. Скрипт сохраняет его для текущего пользователя Windows в `%LOCALAPPDATA%\ContestPlatform\ngrok-token.xml`. Если задана переменная окружения `NGROK_AUTHTOKEN`, скрипт использует её. Он запускает контейнеры `contest-tg-receiver` и `contest-tg-ngrok`, получает публичный HTTPS-адрес и регистрирует webhook. Признак успеха — `Webhook registered.`

Откройте свой профиль на сайте, нажмите **«Получить код привязки»**, перейдите в бота и нажмите **Start**. Можно также отправить боту команду `/start КОД` из профиля. Код действует 10 минут. Команда `/profile` в чате покажет привязанный аккаунт. Для проверки доставки отправьте решение в активный конкурс и дождитесь сообщения с вердиктом.

### 5. Добавьте демоданные при необходимости

Для локальной базы `contest_demo` выполните:

```powershell
docker compose exec api python -m tools.seed_demo
```

Появятся тренировочный конкурс, задачи и аккаунты `demo.admin@example.com`, `demo.judge@example.com`, `demo.anna@example.com` и `demo.ivan@example.com`. Сохраните выведенные пароли: скрипт показывает их при создании аккаунтов. Если вы специально используете другую локальную базу для демонстрации, укажите её фактическое имя через `--database ИМЯ_БАЗЫ`.

Примеры для кнопки импорта тестов задачи: [sum-tests.json](docs/examples/sum-tests.json) и [sum-tests.csv](docs/examples/sum-tests.csv).

## Остановка и следующий запуск

Чтобы полностью остановить стенд с Telegram, сначала остановите туннель, затем приёмник. Если запускали только сайт, достаточно последней команды.

```powershell
docker stop contest-tg-ngrok
docker stop contest-tg-receiver
docker compose down
```

Обычный `down` сохраняет данные. Параметр `-v` удаляет тома, в том числе базу и резервные копии. При следующем запуске выполните `docker compose up -d`, затем `.\tools\start-telegram.ps1` для подключения Telegram. После обновления кода используйте `docker compose up -d --build`. После смены токена или секрета Telegram остановите оба Telegram-контейнера, примените настройки командой `docker compose up -d` и снова запустите скрипт.

## Если что-то не запускается

| Симптом | Что проверить |
|---|---|
| Сайт или API недоступен | Выполните `docker compose ps -a` и `docker compose logs --tail=60 migrate api frontend`. Проверьте настройки базы и доступность портов 5173, 8000, 5432 и 6379. |
| Решение долго проверяется | Выполните `docker compose logs --tail=60 worker`. При первой отправке убедитесь, что Docker может скачать образ выбранного языка. |
| Бот не отвечает на /start | Запустите скрипт Telegram, дождитесь `Webhook registered.` и запросите свежий код в профиле. Для проверки туннеля используйте `docker logs --tail=40 contest-tg-ngrok`. |
| Бот подтвердил привязку, но вердикт не пришёл | Проверьте результат отправки на сайте и журнал `docker compose logs --tail=60 notifications`. |

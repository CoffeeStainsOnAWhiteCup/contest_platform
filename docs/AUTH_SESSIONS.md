# Сессии и вход через GitHub

Все пути в таблице начинаются с `/api/v1/auth`.

| Запрос | Что отправляет клиент | Результат |
|---|---|---|
| POST /login | JSON с email и паролем | 200, access_token, refresh_token, token_type и expires_in |
| POST /refresh | JSON с текущим refresh_token | 200, новая пара токенов |
| POST /logout | JSON с текущим refresh_token | 204, сервер отзывает эту сессию |
| GET /github | Переход браузера | 302 на страницу согласия GitHub |
| GET /github/callback | Вызывает GitHub через браузер | 303 на настроенную страницу фронтенда, одноразовая HttpOnly cookie |
| POST /github/exchange | Браузер отправляет cookie, тело пустое | 200, та же пара токенов, что при входе по паролю |

JWT доступа действует 30 минут по умолчанию. Сервер хранит в Redis хеши refresh-токенов. Сессия истекает через 7 дней от входа. Каждое обновление заменяет токен. Повторное предъявление уже обменянного токена отзывает всю эту цепочку. Другие входы пользователя имеют отдельные цепочки. Фронтенду нужен один запрос обновления на сессию одновременно, в том числе при работе нескольких вкладок. После logout клиент удаляет обе локальные копии токенов. Уже выданный JWT действует до своего exp.

## Локальная проверка

Из корня репозитория в PowerShell:

```powershell
docker compose up -d --build api
docker compose run --rm --build test sh -c 'AUTH_TEST_DATABASE_URL=$DATABASE_URL python -m pytest -q -ra'
$LASTEXITCODE
```

Для ручной проверки открой Swagger, выполни login, скопируй refresh_token из ответа в POST /auth/refresh. В logout передай новый refresh_token. Последующая попытка обновиться по нему должна вернуть 401. Ранее выданный access_token подходит для GET /users/me до конца срока действия.

## Настройка GitHub OAuth App

1. В GitHub открой Settings → Developer settings → OAuth Apps → New OAuth App. Для локальной разработки укажи Homepage URL `http://localhost:5173` и Authorization callback URL `http://localhost:8000/api/v1/auth/github/callback`.
2. Перенеси Client ID и Client secret в локальный `.env`. Имена переменных и адреса приведены в `.env.example`. Параметры `GITHUB_CALLBACK_URL` и `GITHUB_FRONTEND_URL` задают соответственно адрес API и конечную страницу фронтенда.
3. После изменения окружения выполни `docker compose up -d --force-recreate api`. Прочие способы входа доступны при пустых настройках GitHub.
4. Кнопка «Войти через GitHub» открывает `http://localhost:8000/api/v1/auth/github` обычной навигацией браузера. После согласия сервер сверяет одноразовый state и cookie этого браузера, обменивает code с PKCE S256 и запрашивает профиль и основной подтверждённый email.
5. На странице фронтенда `/auth/callback` один раз выполни запрос ниже. Сохрани результат тем же способом, что при входе по паролю. До готовности фронтенда этот последний запрос можно выполнить в Swagger на localhost:8000 в том же браузере в течение минуты после callback.

```javascript
const response = await fetch("http://localhost:8000/api/v1/auth/github/exchange", {
  method: "POST",
  credentials: "include",
});
if (!response.ok) throw new Error("Не удалось завершить вход через GitHub");
const tokens = await response.json();
```

Для production используй HTTPS и размещай фронтенд и API в пределах одного сайта (например, app.example.org и api.example.org). Origin фронтенда берётся из GITHUB_FRONTEND_URL. Все адреса задаёт оператор сервиса. Токены платформы выдаются в JSON. В URL редиректа их нет. GitHub-токен используется только для двух запросов к провайдеру.

Аккаунт определяется по постоянному github_id. При первом входе создаётся Participant. При следующих входах обновляются имя и email, роль сохраняется. Совпадение подтверждённого GitHub email с отдельным локальным аккаунтом даёт 409. Связывание такого аккаунта потребует отдельного подтверждения владельца.

## Ограничения из ТЗ

- FR-AUTH-07/08/09/10 — refresh на 7 дней, GitHub OAuth и отзыв refresh при logout.
- NFR-SEC-07 — общее скользящее окно 10 запросов за 60 секунд с IP на маршрутах auth и submissions. Адрес берётся из ASGI-соединения. За обратным прокси настрой доверенные адреса прокси у Uvicorn.
- FR-SUBMIT-05 — дополнительно 10 попыток создания сабмита за 60 секунд для пользователя с учётом всех его IP. Ответ 429 содержит Retry-After в секундах.
- При недоступности Redis эти маршруты возвращают 503. Сессии привязаны к данным Redis. Для развёртывания с восстановлением после сбоя важно сохранять актуальные отзывы и ротации: восстановление старой копии Redis может вернуть прежнее состояние сессий.
- Блокировка, редактирование профиля и журнал изменений описаны в [BACKEND_API.md](BACKEND_API.md).

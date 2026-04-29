# KinNet — семейная социальная сеть и органайзер

[![Stack](https://img.shields.io/badge/stack-Django%205%20%C2%B7%20Postgres%20%C2%B7%20Redis%20%C2%B7%20Celery%20%C2%B7%20aiogram%20v3%20%C2%B7%20PWA-7c3aed)](#)

KinNet превращает базовое семейное CRUD-приложение в полноценную платформу
для совместной жизни: семейное древо, общий календарь, рецепты с авто-списком
покупок, медицинский дашборд, капсулы времени, бюджет/вишлисты, опросы и
геймификацию. Всё это собрано в Docker-окружение с Postgres, Redis, Celery
и Nginx, а Telegram-бот написан на `aiogram` v3 и работает независимо от
веб-приложения через webhooks или polling.

> Этот документ описывает текущее состояние после рефакторинга. Историческое
> описание курсовой работы сохранено в [`description.md`](./description.md).

---

## Оглавление
1. [Архитектура](#архитектура)
2. [Стек](#стек)
3. [Структура репозитория](#структура-репозитория)
4. [Запуск через Docker Compose](#запуск-через-docker-compose)
5. [Локальный запуск без Docker](#локальный-запуск-без-docker)
6. [Telegram-бот](#telegram-бот-aiogram-v3)
7. [REST API](#rest-api)
8. [PWA / фронтенд](#pwa--фронтенд)
9. [Продуктовые модули](#продуктовые-модули)
10. [Celery / расписания](#celery--расписания)
11. [Что изменилось в этом рефакторинге](#что-изменилось-в-этом-рефакторинге)

---

## Архитектура

```
                       ┌────────────┐
                       │   Nginx    │  static + media + reverse proxy
                       └─────┬──────┘
                             │
                  ┌──────────┴──────────┐
                  │   Gunicorn + Django │  ← web (REST + HTML)
                  └─────────┬───────────┘
            ┌───────────────┼─────────────────┬───────────────┐
            ▼               ▼                 ▼               ▼
       ┌────────┐    ┌────────────┐    ┌────────────┐  ┌────────────┐
       │ Postgres│   │   Redis    │    │ Celery     │  │ Celery     │
       │ (data)  │   │ cache+broker│   │ worker     │  │ beat       │
       └────────┘    └────────────┘    └────────────┘  └────────────┘
                                                  ▲
                                                  │
                                            ┌────────────┐
                                            │  aiogram   │
                                            │  bot (v3)  │
                                            └────────────┘
```

* Persistent volumes для БД, медиафайлов и собранной статики обязательны и
  декларированы в `docker-compose.yml`.
* Celery Beat хранит расписания в БД через `django-celery-beat`, что позволяет
  редактировать их прямо из Django Admin.
* Бот общается с Django через ORM (`asgiref.sync_to_async`) и не блокирует
  основной web-процесс.

---

## Стек

| Слой | Технологии |
|------|------------|
| **Backend** | Django 5.2 LTS, Django Ninja, django-environ, gunicorn, whitenoise |
| **БД / cache / queue** | PostgreSQL 16, Redis 7, django-redis |
| **Async tasks** | Celery 5, Celery Beat (`django-celery-beat`), `django-celery-results` |
| **Telegram** | aiogram v3 (webhook + polling), aiohttp |
| **API** | Django Ninja 1.x, pydantic 2 |
| **Frontend** | Tailwind CSS (CDN), HTMX, Alpine.js, Shepherd.js (онбординг), D3.js (древо) |
| **PWA** | Web App Manifest, Service Worker (stale-while-revalidate, offline.html) |
| **Infra** | Docker, docker-compose, Nginx |

---

## Структура репозитория

```
KinNet/
├── apps/
│   ├── api/             # Django Ninja API (`/api/...`)
│   ├── cookbook/        # Рецепты + список покупок
│   ├── timecapsule/     # Капсулы времени
│   ├── health/          # Family Health (карты, лекарства)
│   ├── budget/          # Семейный бюджет + вишлисты
│   ├── polls/           # Опросы и голосования
│   ├── calendar_sync/   # ICS-фид для Google/Apple Calendar
│   └── gamification/    # Бейджи и достижения
├── bot/                 # aiogram v3 бот
│   ├── main.py          # webhook/polling entrypoint
│   ├── handlers/        # /start, /today, /events, /tasks, ...
│   └── keyboards/
├── core/                # Исходный домен: семьи, члены, события, задачи, цели
│   ├── tasks.py         # Celery-задачи (напоминания, дайджест)
│   └── context_processors.py  # elder mode / theme
├── family_circle/       # Django project (settings, urls, celery.py)
├── docker/
│   ├── entrypoint.sh    # web / worker / beat / bot
│   └── nginx/default.conf
├── static/              # Иконки, css/app.css, js/app.js
├── templates/
│   ├── base.html        # Новый shell: Tailwind + bottom nav + elder mode
│   ├── pwa/             # manifest, sw.js, offline.html
│   └── ...              # шаблоны новых модулей
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Запуск через Docker Compose

```bash
cp .env.example .env
# отредактируйте .env — как минимум проставьте TELEGRAM_BOT_TOKEN и DJANGO_SECRET_KEY
docker compose up -d --build
```

Что запустится:

| Сервис | Назначение |
|--------|-----------|
| `db`   | PostgreSQL 16 (volume `pgdata`) |
| `redis`| Redis 7 (volume `redisdata`) |
| `web`  | Gunicorn + Django (миграции/collectstatic запускаются автоматически) |
| `worker` | Celery worker |
| `beat` | Celery Beat (расписание в БД) |
| `bot`  | aiogram v3 (webhook, если выставлен `TELEGRAM_WEBHOOK_URL`, иначе long polling) |
| `nginx`| Reverse-proxy + раздача `media/` и `staticfiles/` |

Сайт будет доступен на `http://localhost:8080` (порт настраивается через `NGINX_PORT`).

Удобные команды:

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py shell
docker compose logs -f bot worker beat
```

---

## Локальный запуск без Docker

Если `DATABASE_URL`/`REDIS_URL` не выставлены, проект автоматически падает в
SQLite + LocMem cache + eager Celery — удобно для быстрых правок.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Запуск Celery вручную:

```bash
celery -A family_circle worker -l info        # воркер
celery -A family_circle beat   -l info        # планировщик
```

Запуск бота локально (long polling):

```bash
TELEGRAM_BOT_TOKEN=... python -m bot.main
```

---

## Telegram-бот (aiogram v3)

* Полный rewrite с `python-telegram-bot` на `aiogram` v3 + `asyncio`.
* Поддерживает оба режима:
  * **Webhook** — если задан `TELEGRAM_WEBHOOK_URL`, бот поднимает aiohttp-сервер
    на `/webhook/<TELEGRAM_WEBHOOK_SECRET>`. Достаточно завести Nginx-route на
    этот сервис.
  * **Long polling** — fallback, удобен для локальной разработки.
* Команды: `/start`, `/today`, `/events [days]`, `/tasks`, `/messages`,
  `/families`, `/help`. Привязка аккаунта по-прежнему через короткую ссылку
  `/telegram/confirm/<token>/`.
* Уведомления (привязка, напоминания, капсулы, лекарства, опросы) шлются из
  Celery-задач напрямую через HTTP `sendMessage`, чтобы не тащить aiogram в
  worker.

---

## REST API

Документация и схема:

* Swagger UI — `/api/docs`
* OpenAPI JSON — `/api/openapi.json`

Поддерживаются эндпоинты для текущего пользователя, семей, членов семьи,
задач (создание/закрытие), событий, целей и сообщений. Аутентификация — по
сессионной cookie (тот же логин, что и в вебе); CSRF-токен для unsafe-запросов.

Расширять API проще всего, добавляя схемы и хендлеры в `apps/api/api.py`.

---

## PWA / фронтенд

* `templates/base.html` — новый shell на Tailwind (CDN) + Alpine.js + HTMX, с
  bottom-навигацией, переключателем тёмной темы и **режимом для старшего
  поколения** (`data-theme="elder"`: крупный шрифт, высокий контраст,
  подчёркнутые ссылки). Состояние хранится в сессии через эндпоинт
  `/profile/ui/`.
* `static/js/app.js`:
  * регистрирует service worker;
  * добавляет swipe-жесты для карточек (`.swipe-card[data-complete-url]/[data-delete-url]`);
  * показывает конфетти-анимацию (без зависимостей) при `?celebrate=1`;
  * запускает онбординг-тур через Shepherd.js при первом входе.
* `templates/pwa/sw.js` — stale-while-revalidate для GET-запросов и
  `offline.html` для падений сети. Список покупок остаётся доступен без
  интернета сразу после первой загрузки.
* `static/icons/icon-{192,512}.svg` — иконки (можно заменить на PNG в
  продакшене).

---

## Продуктовые модули

| URL | Что внутри |
|-----|------------|
| `/family-tree/graph/` | Интерактивное древо на D3 v7 — зум, drag, клики на профили |
| `/cookbook/` | Семейная кулинарная книга + кнопка «→ В список покупок (создать задачу)», который связывается с `core.Task` |
| `/cookbook/shopping/` | Списки покупок, чекбоксы через HTMX, доступны офлайн |
| `/capsule/` | Капсула времени: отложенные сообщения/файлы, доставка через Celery Beat (`apps.timecapsule.tasks.deliver_due_capsules`) |
| `/health/` | Family Health: карта здоровья (группа крови, аллергии, страховка, экстренный контакт) и расписание лекарств с напоминаниями |
| `/budget/` | Семейный бюджет (расходы по категориям) |
| `/budget/wishlists/` | Списки желаний с «бронированием» подарков (анонимно для именинника) |
| `/polls/` | Опросы и голосования с моно/мульти-выбором |
| `/calendar/` | Приватный ICS-фид для Google/Apple Calendar (события + дни рождения, повторяющиеся годами) |
| `/badges/` | Достижения: `Хранитель очага`, `Шеф-повар семьи`, `Главный планировщик`, ... |

---

## Celery / расписания

Beat-schedule по умолчанию (см. `family_circle/celery.py`):

| Задача | Расписание |
|--------|-----------|
| `core.tasks.send_daily_reminders` | каждый день в 08:00 |
| `core.tasks.send_weekly_digest`   | каждый понедельник в 09:00 |
| `apps.timecapsule.tasks.deliver_due_capsules` | каждые 15 минут |
| `apps.health.tasks.send_medication_reminders` | каждые 30 минут (±15 от целевого времени) |

Расписания можно переопределить через Django Admin → `Periodic Tasks`
(scheduler `DatabaseScheduler`).

---

## Что изменилось в этом рефакторинге

> Сводка для PR-ревью.

**База/инфраструктура**
- SQLite → PostgreSQL 16; Redis 7 как cache, session backend и broker.
- Полный `docker-compose.yml` (web/worker/beat/bot/db/redis/nginx) с persistent
  volumes для `pgdata`, `mediadata`, `staticdata`, `redisdata`.
- `Dockerfile` (Python 3.12-slim) + `docker/entrypoint.sh` поддерживает режимы
  `web`, `worker`, `beat`, `bot`, `manage`.
- `family_circle/settings.py` переписан с `django-environ`, conditionальным
  Redis-кэшем, гибкой конфигурацией БД через `DATABASE_URL`.

**Async & бот**
- Celery + Celery Beat (`django-celery-beat`/`django-celery-results`)
  заменили `run_reminder_scheduler` (старый цикл с `time.sleep`).
- `bot/` переписан с `python-telegram-bot` на `aiogram` v3 + `asyncio`,
  поддерживает webhook **и** polling.
- `core/views.telegram_confirm` больше не зависит от старой библиотеки —
  отправка сообщения вынесена в `core/tasks._send_telegram` (HTTP API).

**API**
- Новый слой `apps.api` на Django Ninja: `/api/docs`, аутентификация по
  сессии, CRUD по основным сущностям.

**Продуктовые фичи**
- 7 новых Django-приложений в `apps/`: cookbook, timecapsule, health,
  budget, polls, calendar_sync, gamification.
- Интерактивное древо на D3 (`/family-tree/graph/`).
- ICS-фид с приватным токеном (`apps.calendar_sync`).
- Бейджи за активность с автоматическим выдачей через Django signals.

**UI/UX**
- Новый `base.html` на Tailwind + HTMX + Alpine.
- Bottom navigation + swipe-карточки + confetti + онбординг-тур (Shepherd.js).
- Режим для старшего поколения (`data-theme="elder"`): крупный шрифт,
  высокий контраст, подчёркнутые ссылки.
- PWA: manifest, service worker (offline кеширование), offline.html.

**Безопасность/чистота**
- Зависимость от `python-telegram-bot` удалена (она же приносила
  старый `telegram` пакет).
- `DEFAULT_AUTO_FIELD = BigAutoField`.
- WhiteNoise для production-static; `STATICFILES_DIRS` + `STATIC_ROOT`.

---

## Лицензия

Учебный проект (курсовая работа). Лицензия — на усмотрение автора репозитория.

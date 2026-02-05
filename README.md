# KinNet

KinNet — семейная социальная сеть и органайзер на Django. Объединяет в одном пространстве: семейное древо (D3.js), общий календарь и события, задачи и цели, кулинарную книгу со списком покупок, дашборд здоровья, капсулы времени, бюджет и список желаний, опросы, систему достижений и PWA-фронтенд (Vite + HTMX + Alpine.js).

---

## Содержание

1. [Требования](#требования)
2. [Быстрый старт (локально, без Docker)](#быстрый-старт-локально-без-docker)
3. [Запуск через Docker](#запуск-через-docker)
4. [Переменные окружения](#переменные-окружения)
5. [Уведомления (SSE)](#уведомления-sse)
6. [Демо-данные](#демо-данные)
7. [Демо-сценарий для защиты](#демо-сценарий-для-защиты)
8. [Celery (фоновые задачи)](#celery-фоновые-задачи)
9. [Тесты](#тесты)
10. [Основные разделы приложения](#основные-разделы-приложения)
11. [Архитектура](#архитектура)
12. [Стек](#стек)

---

## Требования

- Python 3.11+ (проверено на 3.14)
- Node.js 18+ и npm
- Git
- Опционально для прод-стека: Docker и Docker Compose

---

## Быстрый старт (локально, без Docker)

В этом режиме приложение использует SQLite, локальный кеш в памяти и eager-режим Celery — отдельный воркер не нужен.

### 1. Клонировать репозиторий

```bash
git clone https://github.com/Aniypon/KinNet.git
cd KinNet
```

### 2. Создать виртуальное окружение Python и установить зависимости

```bash
python -m venv .venv
. .venv/bin/activate           # macOS / Linux
# .venv\Scripts\activate       # Windows PowerShell
pip install -r requirements.txt
```

### 3. Подготовить переменные окружения (опционально)

Для локального запуска `.env` не обязателен — Django подхватит дефолты. Если нужно — скопируйте шаблон:

```bash
cp .env.example .env
```

Минимум, что стоит задать: `DJANGO_SECRET_KEY`.

### 4. Применить миграции

```bash
python manage.py migrate
```

### 5. Создать суперпользователя (для админки)

```bash
python manage.py createsuperuser
```

### 6. Установить фронтенд-зависимости и запустить сборку

В отдельном терминале:

```bash
npm install
npm run dev          # dev-сервер Vite с HMR
# или
npm run build        # production-сборка в static/dist/
```

### 7. Запустить Django

```bash
python manage.py runserver
```

Открыть [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

---

## Запуск через Docker

Полный стек: Django + PostgreSQL + Redis + Celery worker + Celery beat + Nginx.

```bash
cp .env.example .env
# отредактировать .env: задать DJANGO_SECRET_KEY
docker compose up -d --build
```

Сайт будет доступен на [http://localhost:8080](http://localhost:8080).

Первый запуск автоматически применит миграции и соберёт статику. Логи:

```bash
docker compose logs -f web
docker compose logs -f celery
```

Остановить:

```bash
docker compose down            # с сохранением томов
docker compose down -v         # с удалением БД и Redis
```

---

## Переменные окружения

Все переменные читаются через `django-environ`. Файл `.env.example` содержит актуальный список:

| Переменная | Назначение |
| --- | --- |
| `DJANGO_DEBUG` | `1`/`0` — режим отладки |
| `DJANGO_SECRET_KEY` | Секретный ключ Django (обязателен в проде) |
| `DJANGO_ALLOWED_HOSTS` | Через запятую или `*` |
| `SITE_URL` | Базовый URL для писем и ссылок в уведомлениях |
| `DATABASE_URL` | `postgres://...`. Без переменной — fallback на SQLite |
| `REDIS_URL` | URL Redis для кеша |
| `CELERY_BROKER_URL` | Брокер Celery (Redis) |
| `CELERY_RESULT_BACKEND` | Хранилище результатов Celery |
| `NGINX_PORT` | Внешний порт nginx в docker-compose |

---

## Уведомления (SSE)

Уведомления доставляются в реальном времени через **Server-Sent Events** (`/notifications/stream/`). Браузер держит открытое HTTP-соединение и получает события, пока вкладка открыта. Это проще, чем WebSocket (односторонний канал, авто-reconnect через `EventSource`), и не требует VAPID-ключей или регистрации в push-сервисах.

### Как работает

- `apps.notifications.services.notify()` сохраняет запись в БД и публикует payload в Redis pub/sub канал `kinnet:notif:user:<id>`.
- View `apps/notifications/views.py:sse` подписывается на канал текущего пользователя и стримит `event: notification` фреймы.
- Сигналы (`apps/notifications/signals.py`) ловят `post_save` на `Event`, `Task`, `Goal`, `Message`, `UserBadge` и рассылают уведомления участникам семьи.
- Фронтенд (`frontend/src/modules/push.js`) подключает `EventSource`, показывает toast и обновляет badge непрочитанных.

### Требования

- `REDIS_URL` в `.env` — без Redis pub/sub события не доставляются (fallback: polling каждые 60 секунд + запись в БД остаётся).
- В Docker-стеке Redis уже поднят, ничего настраивать не нужно.
- Локально без Docker: запустить Redis (`brew services start redis`) и задать `REDIS_URL=redis://localhost:6379/0`.

### Ограничения

- События приходят только пока вкладка открыта. Для пушей при закрытом браузере нужен Web Push (VAPID) — в текущей версии не используется.

---

## Демо-данные

Заполнить базу демо-семьёй, событиями, задачами и пр.:

```bash
python manage.py seed_demo
```

Очистить демо-данные:

```bash
python manage.py reset_demo
```

Демо-пользователь после заполнения базы:

| Логин | Пароль | Роль |
| --- | --- | --- |
| `anna` | `demo1234` | владелец семьи Ивановых |
| `ivan` | `demo1234` | участник семьи |
| `maria` | `demo1234` | участник семьи |

Если локальный файл `.env` содержит Docker-настройку `DATABASE_URL=postgres://...@db:5432/...`, а запуск выполняется без Docker, используйте явный SQLite URL:

```bash
DATABASE_URL="sqlite:///db.sqlite3" REDIS_URL="" python manage.py migrate
DATABASE_URL="sqlite:///db.sqlite3" REDIS_URL="" python manage.py seed_demo
DATABASE_URL="sqlite:///db.sqlite3" REDIS_URL="" python manage.py runserver
```

---

## Демо-сценарий для защиты

Короткий маршрут, который показывает основную ценность KinNet:

1. Войти под `anna / demo1234`.
2. На главной странице показать активную семью, напоминания и быстрые переходы.
3. Открыть `/members/`: показать родственников, семейный контекст и дерево.
4. Открыть `/events/` и `/tasks/`: показать семейные события, повторяемые дни рождения, задачи и статусы.
5. Открыть `/messages/`: показать семейный чат, ответы и реакции.
6. Открыть `/cookbook/` и `/cookbook/shopping/`: показать рецепты и список покупок.
7. Открыть `/health/`, `/budget/`, `/polls/`: показать дополнительные модули вокруг той же активной семьи.
8. Завершить показом `/api/docs` и команды `python manage.py test`.

---

## Celery (фоновые задачи)

При локальной разработке без Redis Celery работает в eager-режиме — задачи выполняются синхронно, отдельный процесс не нужен.

Если запущен Redis и заданы `CELERY_*` переменные:

```bash
celery -A family_circle worker -l info
celery -A family_circle beat -l info
```

В Docker оба процесса поднимаются автоматически.

Расписания Celery Beat хранятся в БД через `django-celery-beat` — редактируются в админке Django.

---

## Тесты

```bash
python manage.py test                                              # все тесты
python manage.py test core                                         # одно приложение
python manage.py test core.tests.BasicFlowsTests.test_signup_requires_birth_date  # один тест
```

---

## Основные разделы приложения

| URL | Назначение |
| --- | --- |
| `/` | Главная семейная лента |
| `/members/` | Родственники и семейное древо |
| `/events/` | События, дни рождения и комментарии |
| `/tasks/` | Задачи, чек-листы, вклады и обсуждения |
| `/goals/` | Планы и покупки: списки покупок, списки желаний и общие цели |
| `/cookbook/` | Рецепты и автоматическое составление списка покупок |
| `/health/` | Карты здоровья и расписание лекарств |
| `/album/` | Семейный альбом |
| `/capsule/` | Капсулы времени |
| `/budget/` | Семейный бюджет и расходы |
| `/polls/` | Семейные опросы |
| `/badges/` | Достижения |
| `/api/` | REST API (Django Ninja) |
| `/admin/` | Админка Django |

---

## Архитектура

Проект разделён на два слоя:

- **`core/`** — исходный домен: `Family`, `FamilyMember`, `FamilyMembership`, `Event`, `Task`, `Goal`, `Message`, `UserProfile`, `FamilyInvitation`, `FamilyPhoto`, `Tag`, комментарии. Маршруты подключаются в корне (`path("", include("core.urls"))`).
- **`apps/`** — продуктовые модули, каждый смонтирован в `family_circle/urls.py` под своим префиксом:
  - `apps.api` — REST API на Django Ninja (`/api/`)
  - `apps.cookbook` — `/cookbook/`
  - `apps.timecapsule` — `/capsule/`
  - `apps.health` — `/health/`
  - `apps.budget` — `/budget/`
  - `apps.polls` — `/polls/`
  - `apps.calendar_sync` — `/calendar/`
  - `apps.gamification` — `/badges/`, выдача бейджей через Django signals
  - `apps.notifications` — in-app уведомления и SSE-стрим (`/notifications/stream/`)

### Семейный контекст

Активная семья определяется в `core/context_processors.active_family` в порядке:
`?family=` (GET) → `family` (POST) → `session["active_family_id"]` → первая доступная.

Контекст инжектится в каждый шаблон (`active_family`, `all_families`). Переключение происходит через `<select>` в топбаре, который POST-ит в `core.views.set_active_family`.

Декоратор `core.family_context.require_family(roles=...)` навешивает `request.family` и проверяет роль.

### Ключевые паттерны

- Настройки через `django-environ`. Без `DATABASE_URL`/`REDIS_URL` всё фолбэчится на SQLite + locmem + eager Celery.
- API авторизуется сессионной cookie Django + CSRF.
- Доступ к данным ограничен семьями пользователя (`FamilyMembership` или `created_by`). Проверка ролей — `core.permissions.has_role`.
- Язык — русский (`LANGUAGE_CODE = "ru"`, `TIME_ZONE = "Europe/Moscow"`).
- Подтверждения опасных действий — Alpine.js `x-data="{ open: false }"`.

---

## Стек

- **Backend:** Django, Django Ninja, Celery, django-celery-beat
- **БД и кеш:** PostgreSQL + Redis в Docker, SQLite + locmem локально
- **Frontend:** Django-шаблоны, Vite, Tailwind CSS, HTMX, Alpine.js, Lucide icons, Shepherd.js (онбординг)
- **PWA:** manifest, service worker, offline-страница
- **Realtime:** Server-Sent Events + Redis pub/sub
- **Деплой:** Docker Compose с nginx-фронтом

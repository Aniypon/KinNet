import os
import asyncio
import uuid
from datetime import timedelta

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import ReplyKeyboardMarkup
from dotenv import load_dotenv
from asgiref.sync import sync_to_async


def setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "family_circle.settings")
    import django

    django.setup()


load_dotenv()


setup_django()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db.models import Q  # noqa: E402
from django.utils import timezone  # noqa: E402

from core.models import Event, Family, Message, Task, TelegramProfile  # noqa: E402
from core.utils import get_next_event_date  # noqa: E402


KEYBOARD = ReplyKeyboardMarkup(
    [["/events", "/tasks"], ["/messages", "/families"], ["/today", "/help"]],
    resize_keyboard=True,
)


def _get_user_families(user):
    return Family.objects.filter(Q(memberships__user=user) | Q(created_by=user)).distinct()


def _format_date(value):
    if not value:
        return ""
    return value.strftime("%d.%m.%Y")


def _format_event_date(event, value):
    if not value:
        return ""
    if event.kind == "birthday":
        return value.strftime("%d/%m")
    return value.strftime("%d/%m/%Y")


def _parse_days(args, default=30, max_days=180):
    if not args:
        return default
    try:
        days = int(args[0])
    except (TypeError, ValueError):
        return default
    return max(1, min(days, max_days))


def _site_url():
    base = os.getenv("SITE_URL", "http://localhost:8000").strip()
    return base[:-1] if base.endswith("/") else base


def _confirm_link(profile):
    return f"{_site_url()}/telegram/confirm/{profile.confirm_token}/"


def _build_events_lines(user, today, until, days):
    families_qs = _get_user_families(user)
    events_qs = Event.objects.filter(family__in=families_qs).select_related("family", "member")
    upcoming = []
    for item in events_qs:
        occurrence = get_next_event_date(item, today)
        if occurrence and today <= occurrence <= until:
            upcoming.append((occurrence, item))
    upcoming.sort(key=lambda pair: pair[0])
    upcoming = upcoming[:8]
    if not upcoming:
        return []
    lines = [f"Ближайшие события на {days} дн.:"]
    for occurrence, item in upcoming:
        who = f" ({item.member})" if item.member else ""
        lines.append(
            f"• {_format_event_date(item, occurrence)} — {item.title}{who} · {item.family.name}"
        )
    return lines


def _build_tasks_lines(user, until, days):
    families_qs = _get_user_families(user)
    tasks_qs = (
        Task.objects.filter(family__in=families_qs)
        .exclude(status="done")
        .filter(Q(due_date__isnull=True) | Q(due_date__lte=until))
        .order_by("due_date")
        .select_related("family")[:8]
    )
    if not tasks_qs:
        return []
    lines = [f"Активные задачи на {days} дн.:"]
    for item in tasks_qs:
        due = f" до {_format_date(item.due_date)}" if item.due_date else " (без срока)"
        lines.append(f"• {item.title}{due} · {item.family.name}")
    return lines


def _build_messages_lines(user):
    families_qs = _get_user_families(user)
    msgs = (
        Message.objects.filter(family__in=families_qs)
        .select_related("sender", "family")
        .order_by("-created_at")[:5]
    )
    if not msgs:
        return []
    lines = ["Последние сообщения:"]
    for item in msgs:
        name = item.sender.get_full_name() or item.sender.username
        lines.append(f"• {name}: {item.text[:80]} · {item.family.name}")
    return lines


def _build_today_lines(user):
    families_qs = _get_user_families(user)
    today_date = timezone.localdate()
    events_today = []
    events_qs = Event.objects.filter(family__in=families_qs).select_related("family", "member")
    for item in events_qs:
        occurrence = get_next_event_date(item, today_date)
        if occurrence == today_date:
            events_today.append(item)
    lines = [f"Сегодня {_format_date(today_date)}:"]
    if events_today:
        lines.append("События:")
        for item in events_today:
            who = f" ({item.member})" if item.member else ""
            lines.append(f"• {item.title}{who} · {item.family.name}")
    else:
        lines.append("Событий нет.")

    tasks_due = (
        Task.objects.filter(family__in=families_qs, due_date=today_date)
        .exclude(status="done")
        .select_related("family")
    )
    if tasks_due:
        lines.append("Задачи со сроком сегодня:")
        for item in tasks_due:
            lines.append(f"• {item.title} · {item.family.name}")
    return lines


async def _get_profile(update: Update):
    if not update.effective_chat:
        return None
    return await sync_to_async(
        lambda: TelegramProfile.objects.filter(chat_id=update.effective_chat.id)
        .select_related("user")
        .first(),
        thread_sensitive=True,
    )()


async def _require_confirmed(update: Update):
    profile = await _get_profile(update)
    if not profile:
        await update.message.reply_text("Сначала привяжите аккаунт: /link <username>")
        return None
    if not profile.is_confirmed:
        await update.message.reply_text(
            "Подтвердите привязку на главной странице сайта."
        )
        return None
    return profile


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я бот проекта «Семейный круг».\n"
        "Быстрые команды в меню ниже. Для привязки аккаунта: /link <username>.",
        reply_markup=KEYBOARD,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Команды:\n"
        "/link <username> — привязать аккаунт\n"
        "/unlink — отвязать аккаунт\n"
        "/me — информация о привязке\n"
        "/families — список семей\n"
        "/events [дней] — ближайшие события (по умолчанию 30)\n"
        "/tasks [дней] — ближайшие задачи (по умолчанию 30)\n"
        "/messages — последние сообщения\n"
        "/today — что на сегодня",
        reply_markup=KEYBOARD,
    )


async def link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Укажите username: /link <username>")
        return

    if not update.effective_chat:
        return

    username = context.args[0]
    user_model = get_user_model()
    user = await sync_to_async(
        lambda: user_model.objects.filter(username=username).first(),
        thread_sensitive=True,
    )()
    if not user:
        await update.message.reply_text("Пользователь не найден.")
        return

    existing = await sync_to_async(
        lambda: TelegramProfile.objects.filter(chat_id=update.effective_chat.id).first(),
        thread_sensitive=True,
    )()
    if existing and existing.user_id != user.id:
        await update.message.reply_text(
            "Этот чат уже привязан к другому аккаунту. Сначала выполните /unlink."
        )
        return

    new_token = uuid.uuid4()
    profile, created = await sync_to_async(
        lambda: TelegramProfile.objects.update_or_create(
            user=user,
            defaults={
                "chat_id": update.effective_chat.id,
                "username": update.effective_user.username or "",
                "confirm_token": new_token,
                "is_confirmed": False,
                "confirmed_at": None,
                "requested_at": timezone.now(),
            },
        ),
        thread_sensitive=True,
    )()
    if created:
        text = (
            f"Готово! Telegram привязан к пользователю {profile.user}.\n"
            "Подтвердите привязку на главной странице сайта."
        )
    else:
        text = "Привязка обновлена. Подтвердите её на главной странице сайта."
    await update.message.reply_text(text, reply_markup=KEYBOARD)


async def unlink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await _get_profile(update)
    if not profile:
        await update.message.reply_text("Аккаунт не привязан.")
        return
    await sync_to_async(profile.delete, thread_sensitive=True)()
    await update.message.reply_text("Готово! Привязка удалена.", reply_markup=KEYBOARD)


async def me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await _get_profile(update)
    if not profile:
        await update.message.reply_text("Сначала привяжите аккаунт: /link <username>")
        return
    user = profile.user
    name = user.get_full_name() or user.username
    status = "подтверждена" if profile.is_confirmed else "ожидает подтверждения"
    families_text = await sync_to_async(
        lambda: "\n".join(
            f"• {family.name}" for family in _get_user_families(user)
        )
        or "Семьи не найдены.",
        thread_sensitive=True,
    )()
    await update.message.reply_text(
        f"Аккаунт: {name} (@{user.username})\n"
        f"Статус привязки: {status}\n\n"
        f"Семьи:\n{families_text}",
        reply_markup=KEYBOARD,
    )


async def families(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await _require_confirmed(update)
    if not profile:
        return

    text = await sync_to_async(
        lambda: (
            "Ваши семьи:\n" + "\n".join(f"• {family.name}" for family in _get_user_families(profile.user))
        )
        if _get_user_families(profile.user).exists()
        else "Семьи не найдены.",
        thread_sensitive=True,
    )()
    if text == "Семьи не найдены.":
        await update.message.reply_text("Семьи не найдены.")
        return
    await update.message.reply_text(text, reply_markup=KEYBOARD)


async def events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await _require_confirmed(update)
    if not profile:
        return

    days = _parse_days(context.args)
    today = timezone.localdate()
    until = today + timedelta(days=days)

    lines = await sync_to_async(
        lambda: _build_events_lines(profile.user, today, until, days),
        thread_sensitive=True,
    )()
    if not lines:
        await update.message.reply_text("Ближайших событий нет.")
        return

    await update.message.reply_text("\n".join(lines), reply_markup=KEYBOARD)


async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await _require_confirmed(update)
    if not profile:
        return

    days = _parse_days(context.args)
    today = timezone.localdate()
    until = today + timedelta(days=days)

    lines = await sync_to_async(
        lambda: _build_tasks_lines(profile.user, until, days),
        thread_sensitive=True,
    )()
    if not lines:
        await update.message.reply_text("Активных задач нет.")
        return

    await update.message.reply_text("\n".join(lines), reply_markup=KEYBOARD)


async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await _require_confirmed(update)
    if not profile:
        return

    lines = await sync_to_async(
        lambda: _build_messages_lines(profile.user),
        thread_sensitive=True,
    )()
    if not lines:
        await update.message.reply_text("Сообщений пока нет.")
        return

    await update.message.reply_text("\n".join(lines), reply_markup=KEYBOARD)


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await _require_confirmed(update)
    if not profile:
        return

    lines = await sync_to_async(
        lambda: _build_today_lines(profile.user),
        thread_sensitive=True,
    )()
    await update.message.reply_text("\n".join(lines), reply_markup=KEYBOARD)


async def _post_init(application):
    await application.bot.set_my_commands(
        [
            ("start", "Запустить бота"),
            ("help", "Список команд"),
            ("link", "Привязать аккаунт"),
            ("unlink", "Отвязать аккаунт"),
            ("me", "Мой аккаунт"),
            ("families", "Мои семьи"),
            ("events", "Ближайшие события"),
            ("tasks", "Ближайшие задачи"),
            ("messages", "Последние сообщения"),
            ("today", "План на сегодня"),
        ]
    )


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Установите переменную TELEGRAM_BOT_TOKEN")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = ApplicationBuilder().token(token).post_init(_post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("link", link))
    application.add_handler(CommandHandler("unlink", unlink))
    application.add_handler(CommandHandler("me", me))
    application.add_handler(CommandHandler("families", families))
    application.add_handler(CommandHandler("events", events))
    application.add_handler(CommandHandler("tasks", tasks))
    application.add_handler(CommandHandler("messages", messages))
    application.add_handler(CommandHandler("today", today))

    application.run_polling()


if __name__ == "__main__":
    main()

"""Family-data commands (/today, /events, /tasks, /messages, /families)."""

from __future__ import annotations

from datetime import timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from asgiref.sync import sync_to_async

router = Router(name="commands")


@sync_to_async
def _get_user_for_chat(chat_id: int):
    from core.models import TelegramProfile

    profile = (
        TelegramProfile.objects.filter(chat_id=chat_id, is_confirmed=True)
        .select_related("user")
        .first()
    )
    return profile.user if profile else None


@sync_to_async
def _today_lines(user) -> list[str]:
    from django.db.models import Q
    from django.utils import timezone

    from core.models import Event, Task
    from core.utils import get_next_event_date

    today = timezone.localdate()
    family_filter = Q(family__memberships__user=user) | Q(family__created_by=user)
    events = (
        Event.objects.filter(family_filter)
        .select_related("family", "member")
        .distinct()
    )
    today_events = []
    for event in events:
        occurrence = get_next_event_date(event, today)
        if occurrence == today:
            today_events.append(event)
    tasks_due = (
        Task.objects.filter(family_filter, due_date=today)
        .exclude(status="done")
        .distinct()
    )

    lines = [f"<b>Сегодня {today:%d.%m.%Y}</b>"]
    if today_events:
        lines.append("\n<b>События:</b>")
        for ev in today_events:
            lines.append(f"• {ev.title} · {ev.family.name}")
    if tasks_due:
        lines.append("\n<b>Задачи:</b>")
        for task in tasks_due:
            lines.append(f"• {task.title}")
    if len(lines) == 1:
        lines.append("Сегодня всё спокойно ✨")
    return lines


@sync_to_async
def _events_lines(user, days: int) -> list[str]:
    from django.db.models import Q
    from django.utils import timezone

    from core.models import Event
    from core.utils import get_next_event_date

    today = timezone.localdate()
    end = today + timedelta(days=days)
    family_filter = Q(family__memberships__user=user) | Q(family__created_by=user)
    events = (
        Event.objects.filter(family_filter).select_related("family", "member").distinct()
    )
    upcoming = []
    for event in events:
        occurrence = get_next_event_date(event, today)
        if occurrence and today <= occurrence <= end:
            upcoming.append((occurrence, event))
    upcoming.sort(key=lambda pair: pair[0])
    if not upcoming:
        return [f"Ближайших событий на {days} дн. нет."]
    lines = [f"<b>Ближайшие события ({days} дн.)</b>"]
    for occurrence, event in upcoming[:10]:
        lines.append(f"• {occurrence:%d.%m} — {event.title} · {event.family.name}")
    return lines


@sync_to_async
def _tasks_lines(user) -> list[str]:
    from django.db.models import Q

    from core.models import Task

    family_filter = Q(family__memberships__user=user) | Q(family__created_by=user)
    tasks = (
        Task.objects.filter(family_filter)
        .exclude(status="done")
        .order_by("due_date")
        .distinct()[:10]
    )
    if not tasks:
        return ["Нет открытых задач 🎉"]
    lines = ["<b>Активные задачи:</b>"]
    for task in tasks:
        due = f" до {task.due_date:%d.%m}" if task.due_date else ""
        lines.append(f"• {task.title}{due}")
    return lines


@sync_to_async
def _messages_lines(user) -> list[str]:
    from django.db.models import Q

    from core.models import Message as ChatMessage

    family_filter = Q(family__memberships__user=user) | Q(family__created_by=user)
    msgs = (
        ChatMessage.objects.filter(family_filter)
        .select_related("sender", "family")
        .distinct()[:5]
    )
    if not msgs:
        return ["Сообщений пока нет."]
    lines = ["<b>Последние сообщения:</b>"]
    for msg in msgs:
        name = msg.sender.get_full_name() or msg.sender.username
        lines.append(f"• {name}: {msg.text[:80]}")
    return lines


@sync_to_async
def _families_lines(user) -> list[str]:
    from django.db.models import Q

    from core.models import Family

    families = Family.objects.filter(
        Q(memberships__user=user) | Q(created_by=user)
    ).distinct()
    if not families:
        return ["Вы пока не состоите ни в одной семье."]
    lines = ["<b>Мои семьи:</b>"]
    for family in families:
        lines.append(f"• {family.name}")
    return lines


async def _require_user(message: Message):
    if message.chat is None:
        return None
    user = await _get_user_for_chat(message.chat.id)
    if user is None:
        await message.answer(
            "Сначала привяжите аккаунт командой /start и подтвердите ссылку на сайте."
        )
        return None
    return user


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    user = await _require_user(message)
    if not user:
        return
    lines = await _today_lines(user)
    await message.answer("\n".join(lines))


@router.message(Command("events"))
async def cmd_events(message: Message) -> None:
    user = await _require_user(message)
    if not user:
        return
    parts = (message.text or "").split()
    days = 30
    if len(parts) > 1:
        try:
            days = max(1, min(int(parts[1]), 365))
        except ValueError:
            days = 30
    lines = await _events_lines(user, days)
    await message.answer("\n".join(lines))


@router.message(Command("tasks"))
async def cmd_tasks(message: Message) -> None:
    user = await _require_user(message)
    if not user:
        return
    lines = await _tasks_lines(user)
    await message.answer("\n".join(lines))


@router.message(Command("messages"))
async def cmd_messages(message: Message) -> None:
    user = await _require_user(message)
    if not user:
        return
    lines = await _messages_lines(user)
    await message.answer("\n".join(lines))


@router.message(Command("families"))
async def cmd_families(message: Message) -> None:
    user = await _require_user(message)
    if not user:
        return
    lines = await _families_lines(user)
    await message.answer("\n".join(lines))

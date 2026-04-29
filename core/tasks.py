"""Celery tasks for the legacy ``core`` domain.

These tasks replace the old in-process ``run_reminder_scheduler`` management
command. Beat schedules them; the worker container executes them.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def _send_telegram(chat_id: int, text: str) -> None:
    """Best-effort Telegram message via the Bot HTTP API.

    Avoids importing aiogram from the worker process so worker startup stays
    cheap; failures are swallowed because reminders should never crash the
    beat schedule.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or not chat_id:
        return
    try:
        import requests

        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=5,
        )
    except Exception:  # noqa: BLE001 - reminders must never raise
        logger.exception("telegram send failed for chat_id=%s", chat_id)


@shared_task(name="core.tasks.send_daily_reminders")
def send_daily_reminders() -> int:
    """Notify family members about today's events and due tasks."""
    from core.models import Event, Task, TelegramProfile
    from core.utils import get_next_event_date

    today = timezone.localdate()
    sent = 0
    for profile in TelegramProfile.objects.filter(is_confirmed=True).select_related("user"):
        user = profile.user
        family_filter = Q(family__memberships__user=user) | Q(family__created_by=user)

        upcoming_events = []
        events_qs = (
            Event.objects.filter(family_filter)
            .select_related("family", "member")
            .distinct()
        )
        for event in events_qs:
            occurrence = get_next_event_date(event, today)
            if not occurrence:
                continue
            delta_days = (occurrence - today).days
            if 0 <= delta_days <= max(event.remind_days_before, 0):
                upcoming_events.append((occurrence, event))

        due_tasks = (
            Task.objects.filter(family_filter)
            .exclude(status="done")
            .filter(due_date__lte=today + timedelta(days=1))
            .distinct()[:10]
        )

        if not upcoming_events and not due_tasks:
            continue

        lines: list[str] = ["<b>Сегодня в KinNet:</b>"]
        for occ, event in sorted(upcoming_events)[:6]:
            lines.append(f"• {occ:%d.%m} — {event.title} ({event.family.name})")
        for task in due_tasks:
            due = f" до {task.due_date:%d.%m}" if task.due_date else ""
            lines.append(f"• Задача: {task.title}{due}")
        _send_telegram(profile.chat_id, "\n".join(lines))
        sent += 1

    logger.info("daily reminders sent to %s users", sent)
    return sent


@shared_task(name="core.tasks.send_weekly_digest")
def send_weekly_digest() -> int:
    """Compose and deliver a weekly digest per user.

    Uses ``get_next_event_date`` so that birthdays (whose ``Event.date`` stores
    the original birth year) are resolved to their next yearly occurrence and
    not silently dropped by a raw ``date__range`` filter.
    """
    from core.models import Event, Task, TelegramProfile
    from core.utils import get_next_event_date

    today = timezone.localdate()
    end = today + timedelta(days=7)
    sent = 0
    for profile in TelegramProfile.objects.filter(is_confirmed=True).select_related("user"):
        user = profile.user
        family_filter = Q(family__memberships__user=user) | Q(family__created_by=user)

        all_events = (
            Event.objects.filter(family_filter)
            .select_related("family")
            .distinct()
        )
        upcoming_events: list[tuple] = []
        for ev in all_events:
            occurrence = get_next_event_date(ev, today)
            if occurrence and today <= occurrence <= end:
                upcoming_events.append((occurrence, ev))
        upcoming_events.sort(key=lambda pair: pair[0])
        upcoming_events = upcoming_events[:8]

        tasks = (
            Task.objects.filter(family_filter)
            .exclude(status="done")
            .filter(due_date__range=(today, end))
            .distinct()[:8]
        )
        if not upcoming_events and not tasks:
            continue
        lines = [f"<b>Недельный дайджест ({today:%d.%m} – {end:%d.%m})</b>"]
        if upcoming_events:
            lines.append("\n<b>События:</b>")
            for occurrence, ev in upcoming_events:
                lines.append(f"• {occurrence:%d.%m} {ev.title}")
        if tasks:
            lines.append("\n<b>Задачи:</b>")
            for task in tasks:
                lines.append(f"• {task.title} — до {task.due_date:%d.%m}")
        _send_telegram(profile.chat_id, "\n".join(lines))
        sent += 1
    return sent


@shared_task(name="core.tasks.notify_birthday")
def notify_birthday(member_id: int) -> None:
    """One-shot notification fired by Beat for an upcoming birthday."""
    from core.models import FamilyMember

    member = FamilyMember.objects.filter(pk=member_id).select_related("family").first()
    if not member:
        return
    User = get_user_model()
    family_users = User.objects.filter(
        Q(family_memberships__family=member.family) | Q(families_created=member.family)
    ).distinct()
    text = f"🎂 Сегодня день рождения у {member}! Не забудьте поздравить."
    for user in family_users:
        tg = getattr(user, "telegram_profile", None)
        if tg and tg.chat_id and tg.is_confirmed:
            _send_telegram(tg.chat_id, text)

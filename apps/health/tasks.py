"""Celery tasks for medication reminders."""

from __future__ import annotations

import logging
from datetime import time

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.health.tasks.send_medication_reminders")
def send_medication_reminders() -> int:
    """Send a reminder when a medication's scheduled HH:MM matches now (±15 min)."""
    from core.models import FamilyMembership
    from core.tasks import _send_telegram

    from .models import Medication

    now = timezone.localtime()
    sent = 0
    medications = Medication.objects.filter(is_active=True).select_related("member__family")
    for med in medications:
        if not med.times:
            continue
        for raw in med.times.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                hh, mm = raw.split(":")
                target = time(int(hh), int(mm))
            except (ValueError, TypeError):
                continue
            delta_minutes = abs(
                (now.hour * 60 + now.minute) - (target.hour * 60 + target.minute)
            )
            if delta_minutes > 15:
                continue
            text = f"💊 Напоминание: {med.member} — {med.name} ({med.dosage}) в {raw}"
            recipients = FamilyMembership.objects.filter(
                family=med.member.family
            ).select_related("user__telegram_profile")
            for membership in recipients:
                tg = getattr(membership.user, "telegram_profile", None)
                if tg and tg.chat_id and tg.is_confirmed:
                    _send_telegram(tg.chat_id, text)
                    sent += 1
    logger.info("medication reminders sent: %s", sent)
    return sent

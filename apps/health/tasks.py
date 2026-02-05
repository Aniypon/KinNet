"""Celery tasks for medication reminders."""

from __future__ import annotations

import logging
from datetime import time

from celery import shared_task
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

_REMINDER_WINDOW_MINUTES = 15
_DEDUP_TTL_SECONDS = 18 * 60 * 60  # ample buffer past the next scheduled dose


@shared_task(name="apps.health.tasks.send_medication_reminders")
def send_medication_reminders() -> int:
    """Count due medication reminders when scheduled HH:MM matches now (±15 min).

    Beat runs every 30 minutes, so any HH:MM falls within the ±15-minute window
    of *exactly one* run in the common case — but boundary times (e.g. HH:15)
    sit equidistant between two runs. To keep coverage symmetric without
    double-firing, we use an inclusive ``<=`` check and de-duplicate per
    ``(medication, time, day)`` via the cache.
    """
    from .models import Medication

    now = timezone.localtime()
    today = now.date()
    sent = 0
    medications = (
        Medication.objects.filter(is_active=True)
        .filter(Q(starts_on__isnull=True) | Q(starts_on__lte=today))
        .filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
        .select_related("member__family")
    )
    from apps.notifications.services import notify
    from core.models import FamilyMembership

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
            raw_delta = abs(
                (now.hour * 60 + now.minute) - (target.hour * 60 + target.minute)
            )
            # Wrap around midnight: 23:50 vs 00:05 should be 15 min, not 1425.
            delta_minutes = min(raw_delta, 1440 - raw_delta)
            if delta_minutes > _REMINDER_WINDOW_MINUTES:
                continue
            # Once-per-day lock so beat boundary times (e.g. 08:15 with runs at
            # 08:00 and 08:30) still fire exactly once per day.
            dedup_key = f"med-reminder:{med.pk}:{raw}:{today.isoformat()}"
            if not cache.add(dedup_key, "1", _DEDUP_TTL_SECONDS):
                continue
            family = med.member.family
            title = f"Лекарство: {med.name}"
            body = f"{med.member} · {raw}" + (f" · {med.dosage}" if med.dosage else "")
            recipients = {
                m.user for m in FamilyMembership.objects.filter(family=family).select_related("user")
            }
            for user in recipients:
                notify(user, title=title, body=body, url="/health/", kind="medication")
            sent += 1
    logger.info("medication reminders sent: %s", sent)
    return sent

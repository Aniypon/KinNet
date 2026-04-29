"""Celery tasks for the time capsule app."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.timecapsule.tasks.deliver_due_capsules")
def deliver_due_capsules() -> int:
    """Mark scheduled capsules as delivered when their ``reveal_at`` is in the past."""
    from core.tasks import _send_telegram

    from .models import Capsule

    now = timezone.now()
    delivered = 0
    qs = Capsule.objects.filter(status="scheduled", reveal_at__lte=now)
    for capsule in qs:
        capsule.status = "delivered"
        capsule.delivered_at = now
        capsule.save(update_fields=["status", "delivered_at"])
        for user in capsule.recipients_users.all():
            chat = getattr(getattr(user, "telegram_profile", None), "chat_id", None)
            if chat:
                _send_telegram(
                    chat,
                    f"📦 Капсула времени раскрыта: <b>{capsule.title}</b>\n\n{capsule.message[:500]}",
                )
        delivered += 1
    logger.info("delivered %s capsules", delivered)
    return delivered

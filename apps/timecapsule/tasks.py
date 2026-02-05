"""Celery tasks for the time capsule app."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.timecapsule.tasks.deliver_due_capsules")
def deliver_due_capsules() -> int:
    """Mark scheduled capsules as delivered when their ``reveal_at`` is in the past."""
    from .models import Capsule

    now = timezone.now()
    delivered = 0
    qs = Capsule.objects.filter(status="scheduled", reveal_at__lte=now)
    for capsule in qs:
        capsule.status = "delivered"
        capsule.delivered_at = now
        capsule.save(update_fields=["status", "delivered_at"])
        delivered += 1
    logger.info("delivered %s capsules", delivered)
    return delivered


@shared_task(name="apps.timecapsule.tasks.delete_expired_album_photos")
def delete_expired_album_photos() -> int:
    """Delete family album photos one week after upload, including files."""
    from datetime import timedelta

    from core.models import FamilyPhoto

    cutoff = timezone.now() - timedelta(days=7)
    deleted = 0
    for photo in FamilyPhoto.objects.filter(created_at__lte=cutoff):
        if photo.image:
            photo.image.delete(save=False)
        photo.delete()
        deleted += 1
    logger.info("deleted %s expired family album photos", deleted)
    return deleted

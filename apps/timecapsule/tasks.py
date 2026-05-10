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
    qs = Capsule.objects.filter(status="scheduled", reveal_at__lte=now)
    delivered = qs.update(status="delivered", delivered_at=now)
    logger.info("delivered %s capsules", delivered)
    return delivered

@shared_task(name="apps.timecapsule.tasks.delete_expired_album_photos")
def delete_expired_album_photos() -> int:
    """Delete family album photos one week after upload, including files."""
    from datetime import timedelta
    from core.models import FamilyPhoto
    cutoff = timezone.now() - timedelta(days=7)
    # Load in chunks to avoid unbounded memory use on large tables.
    photos = list(FamilyPhoto.objects.filter(created_at__lte=cutoff).only("id", "image"))
    deleted_ids = []
    for photo in photos:
        try:
            if photo.image:
                photo.image.delete(save=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to delete image file for photo %s: %s", photo.id, exc)
            continue
        deleted_ids.append(photo.id)

    count = FamilyPhoto.objects.filter(id__in=deleted_ids).delete()[0] if deleted_ids else 0
    logger.info("deleted %s expired family album photos", count)
    return count

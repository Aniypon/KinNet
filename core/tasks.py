"""Celery tasks for the core family domain."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="core.tasks.refresh_family_digest")
def refresh_family_digest() -> int:
    """Placeholder for internal digest preparation without external messengers."""
    logger.info("family digest refresh completed")
    return 0

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

@shared_task(name="core.tasks.refresh_family_digest")
def refresh_family_digest() -> int:
    logger.info("family digest refresh completed")
    return 0

"""Notification delivery: persists in-app row, sends web push when configured."""

from __future__ import annotations

import json
import logging
from typing import Iterable

from django.conf import settings

from .models import Notification, PushSubscription
from .pubsub import publish as pubsub_publish

logger = logging.getLogger(__name__)


def _push(subscription: PushSubscription, payload: dict) -> bool:
    if not (settings.VAPID_PRIVATE_KEY and settings.VAPID_PUBLIC_KEY):
        return False
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush not installed; skipping push")
        return False
    try:
        webpush(
            subscription_info=subscription.to_subscription_info(),
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
        )
        return True
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):
            subscription.delete()
        logger.warning("webpush failed (%s): %s", status, exc)
        return False


def notify(user, *, title: str, body: str = "", url: str = "", kind: str = "system") -> Notification:
    """Record in-app notification + attempt web push to all user subscriptions."""
    note = Notification.objects.create(
        user=user, kind=kind, title=title, body=body, url=url,
    )
    payload = {"title": title, "body": body, "url": url or "/", "kind": kind, "id": note.id}
    pubsub_publish(user.id, payload)
    for sub in PushSubscription.objects.filter(user=user):
        _push(sub, payload)
    return note


def notify_many(users: Iterable, **kwargs) -> int:
    count = 0
    for user in users:
        notify(user, **kwargs)
        count += 1
    return count

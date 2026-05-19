"""Redis pub/sub helpers for realtime notification delivery.

Falls back to a no-op publisher when Redis is not configured, so local SQLite
dev (no REDIS_URL) keeps working — SSE clients simply receive nothing until
they reconnect and re-poll via the existing /api/notifications endpoint.
"""

from __future__ import annotations

import json
import logging
from typing import Iterator

from django.conf import settings

logger = logging.getLogger(__name__)


def _channel(user_id: int) -> str:
    return f"kinnet:notif:user:{user_id}"


def _client():
    if not settings.REDIS_URL:
        return None
    try:
        import redis  # type: ignore
    except ImportError:
        logger.warning("redis-py not installed; SSE pub/sub disabled")
        return None
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def publish(user_id: int, payload: dict) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.publish(_channel(user_id), json.dumps(payload))
    except Exception as exc:  # noqa: BLE001
        logger.warning("notif publish failed (%s)", exc)


def subscribe(user_id: int, timeout: float = 25.0) -> Iterator[dict]:
    """Yield decoded payloads from the user channel. Generator ends on disconnect."""
    client = _client()
    if client is None:
        return
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(_channel(user_id))
    try:
        while True:
            msg = pubsub.get_message(timeout=timeout)
            if msg is None:
                yield {"_keepalive": True}
                continue
            data = msg.get("data")
            if not data:
                continue
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                continue
    finally:
        try:
            pubsub.close()
        except Exception:  # noqa: BLE001
            pass

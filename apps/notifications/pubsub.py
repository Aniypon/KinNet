from __future__ import annotations

import json
import logging
import threading
from typing import Iterator

from django.conf import settings

logger = logging.getLogger(__name__)

_redis_client = None
_redis_lock = threading.Lock()

def _channel(user_id: int) -> str:
    return f"kinnet:notif:user:{user_id}"

def _client():
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None

    with _redis_lock:
        if _redis_client is not None:
            return _redis_client
        if not getattr(settings, "REDIS_URL", None): return None
        try:
            import redis  # type: ignore
        except ImportError:
            logger.warning("redis-py не установлен; SSE pub/sub отключён")
            return None
            _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client

def publish(user_id: int, payload: dict) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.publish(_channel(user_id), json.dumps(payload))
    except Exception as exc:  # noqa: BLE001
        logger.warning("notif publish failed (%s)", exc)

def subscribe(user_id: int, timeout: float = 25.0) -> Iterator[dict]:
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
            pubsub.unsubscribe()
            pubsub.close()
        except Exception:  # noqa: BLE001
            pass

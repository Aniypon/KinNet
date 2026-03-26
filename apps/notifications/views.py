"""Server-Sent Events stream for realtime notifications.

The endpoint holds an open HTTP response and emits `event: notification` frames
whenever notify() publishes for the authenticated user. Browsers reconnect
automatically via the EventSource API.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, StreamingHttpResponse

from .pubsub import subscribe


def _stream(user_id: int):
    yield "retry: 5000\n\n"
    yield "event: ready\ndata: {}\n\n"
    for payload in subscribe(user_id):
        if payload.get("_keepalive"):
            yield ": keepalive\n\n"
            continue
        yield f"event: notification\ndata: {json.dumps(payload)}\n\n"


@login_required
def sse(request: HttpRequest) -> StreamingHttpResponse:
    # WARNING: each open SSE connection holds one WSGI worker for its lifetime.
    # Keep gunicorn worker count above expected concurrent SSE clients, or
    # migrate to an ASGI server (Daphne/Uvicorn) for production SSE support.
    response = StreamingHttpResponse(
        _stream(request.user.id), content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    response["Connection"] = "keep-alive"
    return response

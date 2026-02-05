"""Per-user secure ICS feed tokens."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models


def _make_token() -> str:
    return secrets.token_urlsafe(24)


class CalendarFeedToken(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calendar_feed_token",
    )
    token = models.CharField(max_length=64, unique=True, default=_make_token)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"feed for {self.user}"

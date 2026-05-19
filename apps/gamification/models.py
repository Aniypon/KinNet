"""Gamification: badges and per-user achievements."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Badge(models.Model):
    code = models.SlugField(unique=True)
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    emoji = models.CharField(max_length=4, default="🏅")

    def __str__(self) -> str:
        return self.title


class UserBadge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="badges",
    )
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="awards")
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "badge")
        ordering = ["-awarded_at"]

    def __str__(self) -> str:
        return f"{self.user} ← {self.badge}"

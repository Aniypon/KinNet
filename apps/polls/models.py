"""Family polls/voting."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Poll(models.Model):
    family = models.ForeignKey(
        "core.Family", on_delete=models.CASCADE, related_name="polls"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="polls_authored",
    )
    question = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    allow_multiple = models.BooleanField(default=False)
    closes_at = models.DateTimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.question

    @property
    def effectively_closed(self) -> bool:
        from django.utils import timezone
        if self.is_closed:
            return True
        return bool(self.closes_at and self.closes_at <= timezone.now())


class PollChoice(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=200)

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return self.text


class PollVote(models.Model):
    choice = models.ForeignKey(PollChoice, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="poll_votes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("choice", "user")

"""Time capsule: scheduled-delivery family messages with optional media."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class Capsule(models.Model):
    STATUS_CHOICES = [
        ("scheduled", "Запланировано"),
        ("delivered", "Доставлено"),
        ("cancelled", "Отменено"),
    ]

    family = models.ForeignKey(
        "core.Family", on_delete=models.CASCADE, related_name="capsules"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="capsules_authored",
    )
    title = models.CharField(max_length=160)
    message = models.TextField(blank=True)
    media = models.FileField(upload_to="capsules/", blank=True, null=True)
    reveal_at = models.DateTimeField()
    recipients_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="capsules_received",
    )
    recipient_member = models.ForeignKey(
        "core.FamilyMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capsules_for_member",
        help_text="Optional: tie reveal to a specific tracked relative (e.g. for an 18th birthday).",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="scheduled")
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["reveal_at"]

    def __str__(self) -> str:
        return f"{self.title} → {self.reveal_at:%d/%m/%Y}"

    @property
    def is_due(self) -> bool:
        return self.status == "scheduled" and self.reveal_at <= timezone.now()

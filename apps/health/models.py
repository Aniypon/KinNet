"""Family health records and medication schedules."""

from __future__ import annotations

from django.db import models


class HealthRecord(models.Model):
    BLOOD_TYPE_CHOICES = [
        ("", "Не указано"),
        ("O-", "O−"),
        ("O+", "O+"),
        ("A-", "A−"),
        ("A+", "A+"),
        ("B-", "B−"),
        ("B+", "B+"),
        ("AB-", "AB−"),
        ("AB+", "AB+"),
    ]

    member = models.OneToOneField(
        "core.FamilyMember",
        on_delete=models.CASCADE,
        related_name="health_record",
    )
    blood_type = models.CharField(max_length=4, choices=BLOOD_TYPE_CHOICES, blank=True)
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    insurance_info = models.CharField(max_length=255, blank=True)
    emergency_contact = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Health: {self.member}"


class Medication(models.Model):
    FREQUENCY_CHOICES = [
        ("daily", "Ежедневно"),
        ("twice_daily", "2 раза в день"),
        ("thrice_daily", "3 раза в день"),
        ("weekly", "Еженедельно"),
        ("as_needed", "По необходимости"),
    ]

    member = models.ForeignKey(
        "core.FamilyMember",
        on_delete=models.CASCADE,
        related_name="medications",
    )
    name = models.CharField(max_length=160)
    dosage = models.CharField(max_length=80, blank=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="daily")
    times = models.CharField(
        max_length=120,
        blank=True,
        help_text="Comma-separated HH:MM, e.g. 08:00,20:00",
    )
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_active", "name"]

    def __str__(self) -> str:
        return f"{self.name} · {self.member}"

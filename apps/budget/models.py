"""Family budget + collaborative wishlists with anonymous reservations."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Expense(models.Model):
    family = models.ForeignKey(
        "core.Family", on_delete=models.CASCADE, related_name="expenses"
    )
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="expenses_paid",
    )
    title = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=80, blank=True)
    spent_on = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-spent_on", "-created_at"]

    def __str__(self) -> str:
        return f"{self.title}: {self.amount}"


class Wishlist(models.Model):
    family = models.ForeignKey(
        "core.Family", on_delete=models.CASCADE, related_name="wishlists"
    )
    owner_member = models.ForeignKey(
        "core.FamilyMember",
        on_delete=models.CASCADE,
        related_name="wishlists",
    )
    title = models.CharField(max_length=160, default="Список желаний")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.title} · {self.owner_member}"


class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name="items")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)
    price_estimate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reserved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reserved_wishes",
    )
    reserved_at = models.DateTimeField(null=True, blank=True)
    is_purchased = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["is_purchased", "-created_at"]

    def __str__(self) -> str:
        return self.title

    @property
    def is_reserved(self) -> bool:
        return self.reserved_by_id is not None

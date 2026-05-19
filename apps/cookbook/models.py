"""Cookbook domain: shared family recipes that can spawn shopping lists."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Recipe(models.Model):
    family = models.ForeignKey(
        "core.Family", on_delete=models.CASCADE, related_name="recipes"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="recipes",
    )
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    cook_time_minutes = models.PositiveIntegerField(default=0)
    servings = models.PositiveIntegerField(default=2)
    photo = models.ImageField(upload_to="recipes/", blank=True, null=True)
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class Ingredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="ingredients")
    name = models.CharField(max_length=120)
    quantity = models.CharField(max_length=60, blank=True)
    unit = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return f"{self.name} ({self.quantity} {self.unit})".strip()


class ShoppingList(models.Model):
    family = models.ForeignKey(
        "core.Family", on_delete=models.CASCADE, related_name="shopping_lists"
    )
    name = models.CharField(max_length=120, default="Список покупок")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="shopping_lists",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    linked_task = models.ForeignKey(
        "core.Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shopping_lists",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} · {self.family.name}"

    @property
    def is_completed(self) -> bool:
        items = list(self.items.all())
        return bool(items) and all(item.is_done for item in items)


class ShoppingItem(models.Model):
    shopping_list = models.ForeignKey(
        ShoppingList, on_delete=models.CASCADE, related_name="items"
    )
    name = models.CharField(max_length=120)
    quantity = models.CharField(max_length=60, blank=True)
    unit = models.CharField(max_length=30, blank=True)
    is_done = models.BooleanField(default=False)

    class Meta:
        ordering = ["is_done", "pk"]

    def __str__(self) -> str:
        return self.name

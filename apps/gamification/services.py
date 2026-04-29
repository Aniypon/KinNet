"""Helpers for awarding badges and shipping seed data."""

from __future__ import annotations

from typing import Iterable

from .models import Badge, UserBadge

DEFAULT_BADGES: tuple[tuple[str, str, str, str], ...] = (
    ("hearth_keeper", "Хранитель очага", "Создал(а) первую семью в KinNet", "🔥"),
    ("family_chef", "Шеф-повар семьи", "Добавил(а) 5 рецептов", "👨\u200d🍳"),
    ("planner", "Главный планировщик", "Закрыл(а) 10 задач", "📋"),
    ("birthday_buddy", "Друг именинников", "Поздравил(а) с днём рождения", "🎂"),
    ("voter", "Голос семьи", "Поучаствовал(а) в опросе", "🗳️"),
)


def ensure_default_badges() -> Iterable[Badge]:
    for code, title, description, emoji in DEFAULT_BADGES:
        Badge.objects.update_or_create(
            code=code,
            defaults={"title": title, "description": description, "emoji": emoji},
        )
    return Badge.objects.all()


def award(user, code: str) -> UserBadge | None:
    if not user or not user.is_authenticated:
        return None
    badge = Badge.objects.filter(code=code).first()
    if not badge:
        return None
    obj, created = UserBadge.objects.get_or_create(user=user, badge=badge)
    return obj if created else None

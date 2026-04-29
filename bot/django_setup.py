"""Bootstraps Django so the aiogram bot can use ORM models off the main thread."""

from __future__ import annotations

import os


def setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "family_circle.settings")
    import django

    django.setup()

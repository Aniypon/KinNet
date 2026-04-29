"""Compatibility shim: ``manage.py run_bot`` now boots the aiogram bot."""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the KinNet Telegram bot (aiogram v3)."

    def handle(self, *args, **options):
        from bot.main import main

        main()

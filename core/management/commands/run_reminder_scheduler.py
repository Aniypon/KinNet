"""Legacy command preserved for backwards compatibility.

The new platform schedules reminders via Celery Beat (see
``family_circle/celery.py``). This command runs the daily-reminder task
synchronously once and exits, which is helpful in cron-only environments
that cannot run Celery.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the daily reminders task once (sync). Prefer Celery Beat in production."

    def handle(self, *args, **options):
        from core.tasks import send_daily_reminders

        sent = send_daily_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent reminders to {sent} users."))

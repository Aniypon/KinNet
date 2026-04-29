import os
import time
from django.core.management import call_command
from django.core.management.base import BaseCommand
from dotenv import load_dotenv


class Command(BaseCommand):
    help = "Run reminders scheduler in a loop."

    def handle(self, *args, **options):
        load_dotenv()
        interval = int(os.getenv("REMINDER_INTERVAL_SECONDS", "86400"))
        self.stdout.write(self.style.SUCCESS(f"Scheduler started, interval={interval}s"))
        while True:
            call_command("send_reminders")
            time.sleep(interval)

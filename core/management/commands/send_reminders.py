import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from telegram import Bot
from dotenv import load_dotenv

from core.models import Event, Family, Task, TelegramProfile
from core.utils import get_next_event_date


class Command(BaseCommand):
    help = "Send Telegram reminders for events and tasks."

    def handle(self, *args, **options):
        load_dotenv()
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            self.stdout.write(self.style.ERROR("TELEGRAM_BOT_TOKEN is not set"))
            return

        bot = Bot(token=token)
        today = timezone.localdate()

        profiles = TelegramProfile.objects.filter(is_confirmed=True).select_related("user")
        if not profiles.exists():
            self.stdout.write(self.style.WARNING("No linked Telegram profiles."))
            return

        for profile in profiles:
            families = Family.objects.filter(
                Q(memberships__user=profile.user) | Q(created_by=profile.user)
            ).values_list("id", flat=True)

            events = Event.objects.filter(family__in=families)
            event_notifications = []
            for event in events:
                if event.remind_days_before is None:
                    continue
                occurrence = get_next_event_date(event, today)
                if occurrence and occurrence - timedelta(days=event.remind_days_before) == today:
                    event_notifications.append((event, occurrence))

            tasks = Task.objects.filter(family__in=families).exclude(status="done")
            task_notifications = []
            for task in tasks:
                if task.due_date and task.due_date - timedelta(days=task.remind_days_before) == today:
                    task_notifications.append(task)

            if not event_notifications and not task_notifications:
                continue

            lines = ["Напоминания от Семейного круга:"]
            for event, occurrence in event_notifications:
                date_text = occurrence.strftime("%d/%m") if event.kind == "birthday" else occurrence.strftime("%d/%m/%Y")
                lines.append(f"• Событие {event.title} — {date_text}")
            for task in task_notifications:
                lines.append(f"• Задача {task.title} — срок {task.due_date}")

            bot.send_message(chat_id=profile.chat_id, text="\n".join(lines))

        self.stdout.write(self.style.SUCCESS("Reminders sent."))

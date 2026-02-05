"""Celery application for KinNet.

Tasks are auto-discovered from any installed Django app exposing a ``tasks``
module. Beat schedule lives in the database via ``django-celery-beat`` so it
can be edited at runtime via the admin.
"""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "family_circle.settings")

app = Celery("kinnet")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Built-in periodic schedule. Database-backed schedules added via Beat take
# precedence; this is the safety net for fresh installs.
app.conf.beat_schedule = {
    "deliver-time-capsules": {
        "task": "apps.timecapsule.tasks.deliver_due_capsules",
        "schedule": crontab(minute="*/15"),
    },
    "delete-expired-album-photos": {
        "task": "apps.timecapsule.tasks.delete_expired_album_photos",
        "schedule": crontab(hour=3, minute=20),
    },
    "medication-reminders": {
        "task": "apps.health.tasks.send_medication_reminders",
        "schedule": crontab(minute="*/30"),
    },
}


@app.task(bind=True)
def debug_task(self):  # pragma: no cover - smoke check
    print(f"Request: {self.request!r}")

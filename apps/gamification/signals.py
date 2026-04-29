"""Signal-driven badge awards."""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Family, Task

from .services import award


@receiver(post_save, sender=Family)
def family_created(sender, instance, created, **kwargs):
    if created and instance.created_by_id:
        award(instance.created_by, "hearth_keeper")


@receiver(post_save, sender=Task)
def task_completed(sender, instance, created, **kwargs):
    if not created and instance.status == "done" and instance.assignee_id:
        award(instance.assignee, "planner")

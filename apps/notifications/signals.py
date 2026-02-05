"""Wire domain create signals to notification dispatch."""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.gamification.models import UserBadge
from core.models import Event, FamilyMembership, Goal, Message, Task

from .services import notify, notify_many


def _family_users(family, exclude_user_id=None):
    qs = FamilyMembership.objects.filter(family=family).select_related("user")
    return [m.user for m in qs if m.user_id and m.user_id != exclude_user_id]


@receiver(post_save, sender=Event)
def on_event_created(sender, instance, created, **kwargs):
    if not created:
        return
    notify_many(
        _family_users(instance.family),
        title="Новое событие",
        body=f"{instance.title} — {instance.date:%d.%m.%Y}",
        url=f"/events/",
        kind="event",
    )


@receiver(post_save, sender=Task)
def on_task_created(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.assignee_id and instance.assignee_id != instance.created_by_id:
        notify(
            instance.assignee,
            title="Назначена задача",
            body=instance.title,
            url="/tasks/",
            kind="task",
        )
    else:
        notify_many(
            _family_users(instance.family, exclude_user_id=instance.created_by_id),
            title="Новая задача",
            body=instance.title,
            url="/tasks/",
            kind="task",
        )


@receiver(post_save, sender=Goal)
def on_goal_created(sender, instance, created, **kwargs):
    if not created:
        return
    notify_many(
        _family_users(instance.family, exclude_user_id=instance.created_by_id),
        title="Новая цель",
        body=instance.title,
        url="/goals/",
        kind="system",
    )


@receiver(post_save, sender=Message)
def on_message_created(sender, instance, created, **kwargs):
    if not created:
        return
    preview = (instance.text or "")[:80]
    notify_many(
        _family_users(instance.family, exclude_user_id=instance.sender_id),
        title=f"Сообщение от {instance.sender.get_username()}",
        body=preview,
        url="/chat/",
        kind="system",
    )


@receiver(post_save, sender=UserBadge)
def on_badge_awarded(sender, instance, created, **kwargs):
    if not created:
        return
    badge = instance.badge
    notify(
        instance.user,
        title="Новое достижение",
        body=f"{badge.emoji} {badge.title}",
        url="/badges/",
        kind="system",
    )

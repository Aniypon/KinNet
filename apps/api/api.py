"""KinNet REST API powered by Django Ninja.

Mounted at ``/api/``. Authentication uses Django's session cookie by default
(set on web login); set ``X-CSRFToken`` for unsafe verbs.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from ninja import ModelSchema, NinjaAPI, Schema
from ninja.security import django_auth

from core.family_context import get_user_families as _user_families
from core.models import Event, FamilyMember, Goal, Message, Task

User = get_user_model()

api = NinjaAPI(
    title="KinNet API",
    version="1.0.0",
    description="Family-network platform API.",
    auth=django_auth,
)


# ---------------------------------------------------------------------------
# Schemas — ModelSchema auto-derives fields from the Django models.
# ---------------------------------------------------------------------------
class FamilyOut(Schema):
    id: int
    name: str
    description: str
    created_by_id: Optional[int]


class MemberOut(ModelSchema):
    class Meta:
        model = FamilyMember
        fields = [
            "id", "family", "first_name", "last_name", "middle_name",
            "relation", "birth_date", "parent1", "parent2", "spouse",
        ]


class TaskOut(ModelSchema):
    class Meta:
        model = Task
        fields = ["id", "family", "title", "status", "due_date", "assignee"]


class TaskIn(Schema):
    family_id: int
    title: str
    description: str = ""
    status: str = "todo"
    due_date: Optional[date] = None


class EventOut(ModelSchema):
    class Meta:
        model = Event
        fields = ["id", "family", "title", "date", "kind", "member"]


class GoalOut(ModelSchema):
    class Meta:
        model = Goal
        fields = ["id", "family", "title", "target_amount"]


class MessageIn(Schema):
    family_id: int
    text: str


class MessageOut(ModelSchema):
    class Meta:
        model = Message
        fields = ["id", "family", "sender", "text"]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@api.get("/me", response=dict)
def me(request):
    user = request.user
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.get_full_name() or user.username,
        "is_staff": user.is_staff,
    }


@api.get("/families", response=List[FamilyOut])
def list_families(request):
    return list(_user_families(request.user).values())


@api.get("/families/{family_id}/members", response=List[MemberOut])
def list_members(request, family_id: int):
    family = get_object_or_404(_user_families(request.user), pk=family_id)
    return list(FamilyMember.objects.filter(family=family))


@api.get("/tasks", response=List[TaskOut])
def list_tasks(request, status: Optional[str] = None):
    qs = Task.objects.filter(family__in=_user_families(request.user))
    if status:
        qs = qs.filter(status=status)
    return list(qs)


@api.post("/tasks", response=TaskOut)
def create_task(request, payload: TaskIn):
    family = get_object_or_404(_user_families(request.user), pk=payload.family_id)
    task = Task.objects.create(
        family=family,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        due_date=payload.due_date,
        created_by=request.user,
    )
    return task


@api.post("/tasks/{task_id}/done", response=TaskOut)
def mark_task_done(request, task_id: int):
    task = get_object_or_404(
        Task.objects.filter(family__in=_user_families(request.user)),
        pk=task_id,
    )
    task.status = "done"
    task.save(update_fields=["status"])
    return task


@api.get("/events", response=List[EventOut])
def list_events(request):
    return list(Event.objects.filter(family__in=_user_families(request.user)))


@api.get("/goals", response=List[GoalOut])
def list_goals(request):
    return list(Goal.objects.filter(family__in=_user_families(request.user)))


@api.post("/messages", response=MessageOut)
def post_message(request, payload: MessageIn):
    family = get_object_or_404(_user_families(request.user), pk=payload.family_id)
    msg = Message.objects.create(family=family, sender=request.user, text=payload.text)
    return msg


# ---------------------------------------------------------------------------
# Web push / notifications
# ---------------------------------------------------------------------------
from django.conf import settings  # noqa: E402

from apps.notifications.models import Notification, PushSubscription  # noqa: E402


class PushKeys(Schema):
    p256dh: str
    auth: str


class PushSubscriptionIn(Schema):
    endpoint: str
    keys: PushKeys
    user_agent: Optional[str] = ""


class NotificationOut(Schema):
    id: int
    kind: str
    title: str
    body: str
    url: str
    is_read: bool
    created_at: str


@api.get("/push/vapid", response=dict, auth=None)
def push_vapid(request):
    return {"public_key": settings.VAPID_PUBLIC_KEY}


@api.post("/push/subscribe", response=dict)
def push_subscribe(request, payload: PushSubscriptionIn):
    sub, _ = PushSubscription.objects.update_or_create(
        endpoint=payload.endpoint,
        defaults={
            "user": request.user,
            "p256dh": payload.keys.p256dh,
            "auth": payload.keys.auth,
            "user_agent": (payload.user_agent or "")[:255],
        },
    )
    return {"id": sub.id}


@api.post("/push/unsubscribe", response=dict)
def push_unsubscribe(request, endpoint: str):
    PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return {"ok": True}


@api.get("/notifications", response=List[NotificationOut])
def list_notifications(request, unread: bool = False, limit: int = 20):
    qs = Notification.objects.filter(user=request.user)
    if unread:
        qs = qs.filter(is_read=False)
    return [
        {
            "id": n.id, "kind": n.kind, "title": n.title, "body": n.body,
            "url": n.url, "is_read": n.is_read, "created_at": n.created_at.isoformat(),
        }
        for n in qs[:limit]
    ]


@api.post("/notifications/{note_id}/read", response=dict)
def mark_notification_read(request, note_id: int):
    Notification.objects.filter(user=request.user, pk=note_id).update(is_read=True)
    return {"ok": True}


@api.post("/notifications/read-all", response=dict)
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return {"ok": True}

"""KinNet REST API powered by Django Ninja.

Mounted at ``/api/``. Authentication uses Django's session cookie by default
(set on web login); set ``X-CSRFToken`` for unsafe verbs.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from ninja import NinjaAPI, Schema
from ninja.security import django_auth

from core.models import Event, Family, FamilyMember, Goal, Message, Task

User = get_user_model()

api = NinjaAPI(
    title="KinNet API",
    version="1.0.0",
    description="Family-network platform API.",
    auth=django_auth,
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class FamilyOut(Schema):
    id: int
    name: str
    description: str
    created_by_id: Optional[int]


class MemberOut(Schema):
    id: int
    family_id: int
    first_name: str
    last_name: str
    middle_name: str
    relation: str
    birth_date: Optional[date]
    parent1_id: Optional[int]
    parent2_id: Optional[int]
    spouse_id: Optional[int]


class TaskOut(Schema):
    id: int
    family_id: int
    title: str
    status: str
    due_date: Optional[date]
    assignee_id: Optional[int]


class TaskIn(Schema):
    family_id: int
    title: str
    description: str = ""
    status: str = "todo"
    due_date: Optional[date] = None


class EventOut(Schema):
    id: int
    family_id: int
    title: str
    date: date
    kind: str
    member_id: Optional[int]


class GoalOut(Schema):
    id: int
    family_id: int
    title: str
    target_amount: float


class MessageIn(Schema):
    family_id: int
    text: str


class MessageOut(Schema):
    id: int
    family_id: int
    sender_id: int
    text: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _user_families(user) -> "list[Family]":
    return Family.objects.filter(
        Q(memberships__user=user) | Q(created_by=user)
    ).distinct()


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
    return list(FamilyMember.objects.filter(family=family).values())


@api.get("/tasks", response=List[TaskOut])
def list_tasks(request, status: Optional[str] = None):
    qs = Task.objects.filter(family__in=_user_families(request.user))
    if status:
        qs = qs.filter(status=status)
    return list(qs.values())


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
    qs = Event.objects.filter(family__in=_user_families(request.user))
    return list(qs.values())


@api.get("/goals", response=List[GoalOut])
def list_goals(request):
    return list(
        Goal.objects.filter(family__in=_user_families(request.user)).values(
            "id", "family_id", "title", "target_amount"
        )
    )


@api.post("/messages", response=MessageOut)
def post_message(request, payload: MessageIn):
    family = get_object_or_404(_user_families(request.user), pk=payload.family_id)
    msg = Message.objects.create(family=family, sender=request.user, text=payload.text)
    return msg

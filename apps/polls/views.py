"""Family poll views."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from datetime import datetime

from django.utils.dateparse import parse_datetime


def _parse_local_datetime(value: str):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return parse_datetime(value)
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.family_context import current_family as _current_family, get_user_families as _user_families
from core.permissions import has_role

from .models import Poll, PollChoice, PollVote


@login_required
def poll_list(request):
    family, families = _current_family(request)
    polls = (
        Poll.objects.filter(family=family)
        .select_related("family", "author")
        .prefetch_related("choices")
    ) if family else Poll.objects.none()
    polls = list(polls)
    active_polls = [p for p in polls if not p.effectively_closed]
    closed_polls = [p for p in polls if p.effectively_closed]
    return render(
        request,
        "polls/poll_list.html",
        {
            "polls": polls,
            "active_polls": active_polls,
            "closed_polls": closed_polls,
            "family": family,
            "families": families,
        },
    )


@login_required
def poll_create(request):
    family, families = _current_family(request)
    if not family:
        return redirect("families")
    if not has_role(request.user, family, ("owner", "admin", "parent")):
        raise PermissionDenied
    if request.method == "POST":
        closes_raw = request.POST.get("closes_at", "").strip()
        closes_at = _parse_local_datetime(closes_raw) if closes_raw else None
        if closes_at and timezone.is_naive(closes_at):
            closes_at = timezone.make_aware(closes_at)
        poll = Poll.objects.create(
            family=family,
            author=request.user,
            question=request.POST.get("question", "Опрос"),
            description=request.POST.get("description", ""),
            allow_multiple=bool(request.POST.get("allow_multiple")),
            closes_at=closes_at,
        )
        for raw in request.POST.get("choices", "").splitlines():
            text = raw.strip()
            if text:
                PollChoice.objects.create(poll=poll, text=text)
        return redirect("polls:poll_detail", poll_id=poll.id)
    return render(request, "polls/poll_form.html", {"families": families, "family": family, "page_title": "Новый опрос"})


@login_required
def poll_update(request, poll_id: int):
    family, families = _current_family(request)
    poll = get_object_or_404(
        Poll.objects.filter(family__in=families),
        pk=poll_id,
    )
    if not has_role(request.user, poll.family, ("owner", "admin", "parent")):
        raise PermissionDenied
    if request.method == "POST":
        poll.family = family or poll.family
        poll.question = request.POST.get("question", "").strip() or "Опрос"
        poll.description = request.POST.get("description", "").strip()
        poll.allow_multiple = bool(request.POST.get("allow_multiple"))
        poll.is_closed = bool(request.POST.get("is_closed"))
        closes_raw = request.POST.get("closes_at", "").strip()
        if closes_raw:
            closes_at = _parse_local_datetime(closes_raw)
            if closes_at and timezone.is_naive(closes_at):
                closes_at = timezone.make_aware(closes_at)
            poll.closes_at = closes_at
        else:
            poll.closes_at = None
        poll.save(update_fields=["family", "question", "description", "allow_multiple", "is_closed", "closes_at"])
        existing = list(poll.choices.order_by("pk"))
        lines = [line.strip() for line in request.POST.get("choices", "").splitlines() if line.strip()]
        for index, text in enumerate(lines):
            if index < len(existing):
                choice = existing[index]
                choice.text = text
                choice.save(update_fields=["text"])
            else:
                PollChoice.objects.create(poll=poll, text=text)
        for choice in existing[len(lines):]:
            choice.delete()
        return redirect("polls:poll_detail", poll_id=poll.id)
    choices_text = "\n".join(poll.choices.values_list("text", flat=True))
    return render(
        request,
        "polls/poll_form.html",
        {"families": families, "family": poll.family, "poll": poll, "choices_text": choices_text, "page_title": "Изменить опрос"},
    )


@login_required
@require_POST
def poll_delete(request, poll_id: int):
    poll = get_object_or_404(
        Poll.objects.filter(family__in=_user_families(request.user)),
        pk=poll_id,
    )
    poll.delete()
    return redirect("polls:poll_list")


@login_required
def poll_detail(request, poll_id: int):
    poll = get_object_or_404(
        Poll.objects.filter(family__in=_user_families(request.user)),
        pk=poll_id,
    )
    choices = (
        poll.choices.annotate(vote_count=Count("votes"))
        .order_by("pk")
    )
    user_voted_ids = set(
        PollVote.objects.filter(user=request.user, choice__poll=poll).values_list(
            "choice_id", flat=True
        )
    )
    return render(
        request,
        "polls/poll_detail.html",
        {"poll": poll, "choices": choices, "user_voted_ids": user_voted_ids},
    )


@login_required
def poll_vote(request, poll_id: int):
    poll = get_object_or_404(
        Poll.objects.filter(family__in=_user_families(request.user)),
        pk=poll_id,
    )
    if poll.effectively_closed or request.method != "POST":
        return redirect("polls:poll_detail", poll_id=poll.id)

    selected = request.POST.getlist("choice")
    if not poll.allow_multiple:
        selected = selected[:1]

    # Always wipe the user's previous votes for this poll so unchecking a
    # previously selected option in a multi-choice poll actually removes it.
    PollVote.objects.filter(user=request.user, choice__poll=poll).delete()

    for choice_id in selected:
        choice = poll.choices.filter(pk=choice_id).first()
        if choice:
            PollVote.objects.get_or_create(choice=choice, user=request.user)
    return redirect("polls:poll_detail", poll_id=poll.id)

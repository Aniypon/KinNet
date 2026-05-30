from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.family_context import current_family as _current_family, get_user_families as _user_families
from core.permissions import has_role
from core.utils import parse_local_datetime as _parse_local_datetime

from .models import Poll, PollChoice, PollVote

@login_required
def poll_list(request):
    family, families = _current_family(request)
    polls = list(Poll.objects.filter(family=family).select_related("family", "author").prefetch_related("choices")) if family else []
    return render(request, "polls/poll_list.html", {
        "polls": polls,
        "active_polls": [p for p in polls if not p.effectively_closed],
        "closed_polls": [p for p in polls if p.effectively_closed],
        "family": family, "families": families,
    })

@login_required
def poll_create(request):
    family, families = _current_family(request)
    if not family: return redirect("families")
    if not has_role(request.user, family, ("owner", "admin")):
        raise PermissionDenied
    if request.method == "POST":
        closes_raw = request.POST.get("closes_at", "").strip()
        closes_at = _parse_local_datetime(closes_raw) if closes_raw else None
        if closes_at and timezone.is_naive(closes_at):
            closes_at = timezone.make_aware(closes_at)
        poll = Poll.objects.create(
            family=family, author=request.user,
            question=request.POST.get("question", "Опрос"),
            description=request.POST.get("description", ""),
            allow_multiple=bool(request.POST.get("allow_multiple")),
            closes_at=closes_at,
        )
        choice_texts = [raw.strip() for raw in request.POST.get("choices", "").splitlines() if raw.strip()]
        if choice_texts:
            PollChoice.objects.bulk_create([PollChoice(poll=poll, text=t) for t in choice_texts])
        return redirect("polls:poll_detail", poll_id=poll.id)
    return render(request, "polls/poll_form.html", {"families": families, "family": family, "page_title": "Новый опрос"})

@login_required
def poll_update(request, poll_id: int):
    family, families = _current_family(request)
    poll = get_object_or_404(Poll.objects.filter(family__in=families), pk=poll_id)
    if not has_role(request.user, poll.family, ("owner", "admin")):
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
            poll.closes_at = timezone.make_aware(closes_at) if closes_at and timezone.is_naive(closes_at) else closes_at
        else:
            poll.closes_at = None
        poll.save(update_fields=["family", "question", "description", "allow_multiple", "is_closed", "closes_at"])
        existing = list(poll.choices.order_by("pk"))
        lines = [line.strip() for line in request.POST.get("choices", "").splitlines() if line.strip()]
        for index, text in enumerate(lines):
            if index < len(existing):
                existing[index].text = text
                existing[index].save(update_fields=["text"])
            else:
                PollChoice.objects.create(poll=poll, text=text)
        for choice in existing[len(lines):]:
            choice.delete()
        return redirect("polls:poll_detail", poll_id=poll.id)
    return render(request, "polls/poll_form.html", {
        "families": families, "family": poll.family, "poll": poll,
        "choices_text": "\n".join(poll.choices.values_list("text", flat=True)), "page_title": "Изменить опрос",
    })

@login_required
@require_POST
def poll_delete(request, poll_id: int):
    poll = get_object_or_404(Poll.objects.filter(family__in=_user_families(request.user)), pk=poll_id)
    poll.delete()
    return redirect("polls:poll_list")

@login_required
def poll_detail(request, poll_id: int):
    poll = get_object_or_404(Poll.objects.filter(family__in=_user_families(request.user)), pk=poll_id)
    choices = poll.choices.annotate(vote_count=Count("votes")).order_by("pk")
    user_voted_ids = set(PollVote.objects.filter(user=request.user, choice__poll=poll).values_list("choice_id", flat=True))
    return render(request, "polls/poll_detail.html", {"poll": poll, "choices": choices, "user_voted_ids": user_voted_ids})

@login_required
def poll_vote(request, poll_id: int):
    poll = get_object_or_404(Poll.objects.filter(family__in=_user_families(request.user)), pk=poll_id)
    if poll.effectively_closed or request.method != "POST":
        return redirect("polls:poll_detail", poll_id=poll.id)
    selected = request.POST.getlist("choice")
    if not poll.allow_multiple:
        selected = selected[:1]
    valid_ids = set(poll.choices.filter(pk__in=selected).values_list("pk", flat=True))
    with transaction.atomic():
        PollVote.objects.filter(user=request.user, choice__poll=poll).delete()
        PollVote.objects.bulk_create([PollVote(choice_id=cid, user=request.user) for cid in valid_ids], ignore_conflicts=True)
    return redirect("polls:poll_detail", poll_id=poll.id)

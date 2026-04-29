"""Family poll views."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Family

from .models import Poll, PollChoice, PollVote


def _user_families(user):
    return Family.objects.filter(
        Q(memberships__user=user) | Q(created_by=user)
    ).distinct()


@login_required
def poll_list(request):
    polls = (
        Poll.objects.filter(family__in=_user_families(request.user))
        .select_related("family", "author")
        .prefetch_related("choices")
    )
    return render(request, "polls/poll_list.html", {"polls": polls})


@login_required
def poll_create(request):
    families = _user_families(request.user)
    if request.method == "POST":
        family = get_object_or_404(families, pk=request.POST.get("family"))
        poll = Poll.objects.create(
            family=family,
            author=request.user,
            question=request.POST.get("question", "Опрос"),
            description=request.POST.get("description", ""),
            allow_multiple=bool(request.POST.get("allow_multiple")),
        )
        for raw in request.POST.get("choices", "").splitlines():
            text = raw.strip()
            if text:
                PollChoice.objects.create(poll=poll, text=text)
        return redirect("polls:poll_detail", poll_id=poll.id)
    return render(request, "polls/poll_form.html", {"families": families})


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
    if poll.is_closed or request.method != "POST":
        return redirect("polls:poll_detail", poll_id=poll.id)

    selected = request.POST.getlist("choice")
    if not poll.allow_multiple:
        selected = selected[:1]
        PollVote.objects.filter(user=request.user, choice__poll=poll).delete()

    for choice_id in selected:
        choice = poll.choices.filter(pk=choice_id).first()
        if choice:
            PollVote.objects.get_or_create(choice=choice, user=request.user)
    return redirect("polls:poll_detail", poll_id=poll.id)

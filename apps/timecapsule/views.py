"""Time-capsule views."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_datetime

from core.models import Family

from .models import Capsule


def _user_families(user):
    return Family.objects.filter(
        Q(memberships__user=user) | Q(created_by=user)
    ).distinct()


@login_required
def capsule_list(request):
    families = _user_families(request.user)
    capsules = (
        Capsule.objects.filter(family__in=families)
        .select_related("family")
        .order_by("status", "reveal_at")
    )
    return render(
        request,
        "timecapsule/capsule_list.html",
        {"capsules": capsules, "families": families},
    )


@login_required
def capsule_create(request):
    families = _user_families(request.user)
    if request.method == "POST":
        family = get_object_or_404(families, pk=request.POST.get("family"))
        reveal_at = parse_datetime(request.POST.get("reveal_at", ""))
        if reveal_at is None:
            return redirect("timecapsule:capsule_create")
        capsule = Capsule.objects.create(
            family=family,
            author=request.user,
            title=request.POST.get("title", "Капсула"),
            message=request.POST.get("message", ""),
            reveal_at=reveal_at,
        )
        recipient_ids = request.POST.getlist("recipients_users")
        if recipient_ids:
            capsule.recipients_users.set(recipient_ids)
        if request.FILES.get("media"):
            capsule.media = request.FILES["media"]
            capsule.save(update_fields=["media"])
        return redirect("timecapsule:capsule_list")
    return render(request, "timecapsule/capsule_form.html", {"families": families})

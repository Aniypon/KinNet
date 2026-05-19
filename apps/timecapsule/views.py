from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from core.family_context import current_family as _current_family
from core.permissions import has_role
from core.utils import parse_local_datetime as _parse_local_datetime

from .models import Capsule

@login_required
def capsule_list(request):
    family, families = _current_family(request)
    if not family: return redirect("families")
    now = timezone.now()
    Capsule.objects.filter(family=family, status="scheduled", reveal_at__lte=now).update(
        status="delivered",
        delivered_at=now,
    )
    capsules = (
        Capsule.objects.filter(family=family)
        .select_related("family")
        .prefetch_related("recipients_users")
        .order_by("status", "reveal_at")
    )
    return render(
        request,
        "timecapsule/capsule_list.html",
        {"capsules": capsules, "family": family, "families": families},
    )

@login_required
def capsule_create(request):
    family, families = _current_family(request)
    if not family: return redirect("families")
    if not has_role(request.user, family, ("owner", "admin", "parent")):
        raise PermissionDenied
    if request.method == "POST":
        reveal_at = _parse_local_datetime(request.POST.get("reveal_at", ""))
        if reveal_at is None:
            return redirect("timecapsule:capsule_create")
        if timezone.is_naive(reveal_at):
            reveal_at = timezone.make_aware(reveal_at, timezone.get_current_timezone())
        capsule = Capsule.objects.create(
            family=family,
            author=request.user,
            title=request.POST.get("title", "Капсула"),
            message=request.POST.get("message", ""),
            reveal_at=reveal_at,
        )
        family_users = get_user_model().objects.filter(family_memberships__family=family).distinct()
        recipient_ids = request.POST.getlist("recipients_users")
        if recipient_ids:
            capsule.recipients_users.set(family_users.filter(id__in=recipient_ids))
        if request.FILES.get("media"):
            capsule.media = request.FILES["media"]
            capsule.save(update_fields=["media"])
        return redirect(f"{reverse('timecapsule:capsule_list')}?family={family.id}")
    users = get_user_model().objects.filter(family_memberships__family=family).distinct()
    return render(request, "timecapsule/capsule_form.html", {"families": families, "family": family, "users": users})

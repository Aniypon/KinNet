from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Badge, UserBadge
from .services import ensure_default_badges

def _progress_for(user, code):
    from core.models import Family, Task
    if code == "hearth_keeper":
        return min(Family.objects.filter(created_by=user).count(), 1), 1
    if code == "family_chef":
        from apps.cookbook.models import Recipe
        return Recipe.objects.filter(author=user).count(), 5
    if code == "planner":
        return Task.objects.filter(assignee=user, status="done").count(), 10
    if code == "voter":
        from apps.polls.models import PollVote
        return min(PollVote.objects.filter(user=user).count(), 1), 1
    return 0, 1

@login_required
def badge_index(request):
    ensure_default_badges()
    earned_map = {ub.badge_id: ub for ub in UserBadge.objects.filter(user=request.user).select_related("badge")}
    items = []
    for badge in Badge.objects.all().order_by("id"):
        ub = earned_map.get(badge.id)
        current, target = (1, 1) if ub else _progress_for(request.user, badge.code)
        current = min(current, target)
        items.append({"badge": badge, "earned": ub is not None, "awarded_at": ub.awarded_at if ub else None, "current": current, "target": target, "percent": int(round(current * 100 / target)) if target else 0})
    earned_count = sum(1 for it in items if it["earned"])
    return render(request, "gamification/badges.html", {"items": items, "earned_count": earned_count, "total_count": len(items)})

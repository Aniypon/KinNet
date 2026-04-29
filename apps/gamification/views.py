"""Gamification views: list of earned badges."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import ensure_default_badges


@login_required
def badge_index(request):
    ensure_default_badges()
    earned = request.user.badges.select_related("badge").all()
    return render(request, "gamification/badges.html", {"earned": earned})

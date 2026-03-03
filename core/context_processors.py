"""Template context processors for KinNet."""

from __future__ import annotations


def active_family(request) -> dict:
    """Expose the currently selected family and all user families to every template."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"active_family": None, "all_families": []}

    from .family_context import current_family

    family, families = current_family(request)
    return {"active_family": family, "all_families": families}


def ui_preferences(request) -> dict:
    """Surface the user's UI prefs (elder mode, theme) for every template.

    Stored in the session so prefs survive across pages without a database
    write. The toggle endpoints under ``/profile/ui/...`` mutate the session.
    """
    session = getattr(request, "session", None)
    elder_mode = bool(session.get("elder_mode")) if session is not None else False
    theme = (session.get("theme") if session is not None else None) or "light"
    if theme not in {"light", "dark"}:
        theme = "light"
    return {
        "ui_elder_mode": elder_mode,
        "ui_theme": theme,
    }


def navigation_badges(request) -> dict:
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"nav_unread_messages": 0}

    from django.db.models import Q

    from .models import Family, Message, MessageReadState

    family_ids = list(
        Family.objects.filter(Q(memberships__user=request.user) | Q(created_by=request.user))
        .distinct()
        .values_list("id", flat=True)
    )
    if not family_ids:
        return {"nav_unread_messages": 0}

    read_states = {
        s.family_id: s.last_read_message_id
        for s in MessageReadState.objects.filter(family_id__in=family_ids, user=request.user)
    }

    # Build a single query instead of one COUNT per family.
    unread_q = Q()
    for fid in family_ids:
        last_read = read_states.get(fid)
        if last_read:
            unread_q |= Q(family_id=fid, id__gt=last_read)
        else:
            unread_q |= Q(family_id=fid)

    unread_total = Message.objects.filter(unread_q).exclude(sender=request.user).count()
    return {"nav_unread_messages": unread_total}

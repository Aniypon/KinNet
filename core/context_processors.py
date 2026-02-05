"""Template context processors for KinNet."""

from __future__ import annotations


def active_family(request) -> dict:
    """Expose the currently selected family and all user families to every template.

    Family selection priority: session > first available.
    The session key is set by the set_active_family view.
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"active_family": None, "all_families": []}

    from django.db.models import Q

    from .models import Family

    families = Family.objects.filter(
        Q(memberships__user=request.user) | Q(created_by=request.user)
    ).distinct()

    session = getattr(request, "session", None)
    family_id = (
        request.GET.get("family")
        or request.POST.get("family")
        or (session.get("active_family_id") if session else None)
    )

    family = None
    if family_id:
        family = families.filter(id=family_id).first()
    if family is None:
        family = families.first()

    if family and session is not None:
        session["active_family_id"] = family.id
        session.modified = True

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

    families = Family.objects.filter(Q(memberships__user=request.user) | Q(created_by=request.user)).distinct()

    # Fetch all read states in one query, keyed by family_id
    read_states = {
        s.family_id: s.last_read_message_id
        for s in MessageReadState.objects.filter(family__in=families, user=request.user)
    }

    unread_total = 0
    for fam in families:
        last_read_id = read_states.get(fam.id)
        qs = Message.objects.filter(family=fam).exclude(sender=request.user)
        if last_read_id:
            qs = qs.filter(id__gt=last_read_id)
        unread_total += qs.count()

    return {"nav_unread_messages": unread_total}

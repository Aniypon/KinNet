"""Shared family resolution helper used by all app views."""

from __future__ import annotations

from functools import wraps

from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import Family


def get_user_families(user):
    return Family.objects.filter(Q(memberships__user=user) | Q(created_by=user)).distinct()


def current_family(request):
    """Resolve and return (family, families) for the current request.

    Priority: GET ?family= → POST family → session active_family_id → first.
    Writes back to session so context stays sticky across navigation.
    """
    families = get_user_families(request.user)
    family_id = (
        request.GET.get("family")
        or request.POST.get("family")
        or request.session.get("active_family_id")
    )
    family = families.filter(id=family_id).first() if family_id else None
    if family is None:
        family = families.first()
    if family:
        request.session["active_family_id"] = family.id
        request.session.modified = True
    return family, families


def require_family(roles=None):
    """Resolve active family, attach to request.family, optionally check role.

    Raises PermissionDenied if no family or role missing.
    Usage:
        @login_required
        @require_family()                       # any membership
        @require_family(roles=("owner","admin"))
    """
    from .permissions import has_role

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            family, families = current_family(request)
            if family is None:
                raise PermissionDenied
            if roles and not has_role(request.user, family, roles):
                raise PermissionDenied
            request.family = family
            request.families = families
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

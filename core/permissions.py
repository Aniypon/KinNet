"""Centralised role/permission helpers for KinNet views."""

from __future__ import annotations

from functools import wraps

from django.core.exceptions import PermissionDenied

from .models import FamilyMembership


def get_membership(user, family):
    return FamilyMembership.objects.filter(user=user, family=family).first()


def has_role(user, family, roles) -> bool:
    """Return True if user's membership role in family is in roles."""
    membership = get_membership(user, family)
    return membership is not None and membership.role in roles


def require_role(*roles):
    """View decorator: resolve active family from session and check role.

    Expects the view to receive ``request`` as first argument and that the
    active family was already written to session (by context processor or
    any prior call to current_family).

    Usage::

        @login_required
        @require_role("owner", "admin")
        def my_write_view(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from .family_context import current_family
            from django.contrib.auth.decorators import login_required

            family, _ = current_family(request)
            if family is None or not has_role(request.user, family, roles):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

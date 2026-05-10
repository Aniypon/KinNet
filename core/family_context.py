from __future__ import annotations

from functools import wraps

from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import Family

def get_user_families(user):
    return Family.objects.filter(Q(memberships__user=user) | Q(created_by=user)).distinct()

def current_family(request):
    families = get_user_families(request.user)
    raw_id = (
        request.GET.get("family")
        or request.POST.get("family")
        or request.session.get("active_family_id")
    )
    try:
        family_id = int(raw_id) if raw_id else None
    except (ValueError, TypeError):
        family_id = None

    family = families.filter(id=family_id).first() if family_id else None
    if family is None:
        family = families.first()
    if family:
        request.session["active_family_id"] = family.id
        request.session.modified = True
    return family, families

def require_family(roles=None):
    from .permissions import has_role

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied
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

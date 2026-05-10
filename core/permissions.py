from __future__ import annotations

from .models import FamilyMembership

def get_membership(user, family):
    return FamilyMembership.objects.filter(user=user, family=family).first()

def has_role(user, family, roles) -> bool:
    membership = get_membership(user, family)
    return membership is not None and membership.role in roles

from __future__ import annotations

from django.db.models import Q

from .models import Family, FamilyMembership

def get_membership(user, family):
    return FamilyMembership.objects.filter(user=user, family=family).first()

def has_role(user, family, roles) -> bool:
    membership = get_membership(user, family)
    return membership is not None and membership.role in roles

def reset_eligible_families(approver):
    """Семьи, в которых approver — создатель или владелец/админ."""
    return Family.objects.filter(
        Q(created_by=approver)
        | Q(memberships__user=approver, memberships__role__in=["owner", "admin"])
    ).distinct()

def can_reset_password_of(approver, target_user) -> bool:
    """Сбросить пароль может админ сайта либо создатель/владелец семьи target_user.
    Свой пароль через эту заявку сбросить нельзя (нужен второй владелец или админ сайта)."""
    if not getattr(approver, "is_authenticated", False) or target_user == approver:
        return False
    if approver.is_staff or approver.is_superuser:
        return True
    return FamilyMembership.objects.filter(
        family__in=reset_eligible_families(approver), user=target_user
    ).exists()

"""Views for family health records."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from core.family_context import get_user_families as _user_families
from core.models import FamilyMember
from core.permissions import has_role

from .models import HealthRecord, Medication


@login_required
def health_index(request):
    families = _user_families(request.user)
    members = FamilyMember.objects.filter(family__in=families).select_related("family")
    return render(
        request,
        "health/index.html",
        {"members": members},
    )


@login_required
def record_edit(request, member_id: int):
    member = get_object_or_404(
        FamilyMember.objects.filter(family__in=_user_families(request.user)),
        pk=member_id,
    )
    record, _ = HealthRecord.objects.get_or_create(member=member)
    if not has_role(request.user, member.family, ("owner", "admin", "parent")) and member.user != request.user:
        raise PermissionDenied
    if request.method == "POST":
        for field in (
            "blood_type",
            "allergies",
            "chronic_conditions",
            "insurance_info",
            "emergency_contact",
            "notes",
        ):
            setattr(record, field, request.POST.get(field, ""))
        record.save()
        return redirect("health:health_index")
    return render(
        request,
        "health/record_form.html",
        {"member": member, "record": record, "page_title": f"Карта здоровья — {member}"},
    )


@login_required
def medication_create(request, member_id: int):
    member = get_object_or_404(
        FamilyMember.objects.filter(family__in=_user_families(request.user)),
        pk=member_id,
    )
    if request.method == "POST":
        Medication.objects.create(
            member=member,
            name=request.POST.get("name", "").strip() or "Препарат",
            dosage=request.POST.get("dosage", "").strip(),
            frequency=request.POST.get("frequency", "daily"),
            times=request.POST.get("times", ""),
            notes=request.POST.get("notes", ""),
        )
        return redirect("health:health_index")
    return render(request, "health/medication_form.html", {"member": member})

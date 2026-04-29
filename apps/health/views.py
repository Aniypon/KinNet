"""Family Health dashboard views."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Family, FamilyMember

from .models import HealthRecord, Medication


def _user_families(user):
    return Family.objects.filter(
        Q(memberships__user=user) | Q(created_by=user)
    ).distinct()


@login_required
def dashboard(request):
    families = _user_families(request.user)
    members = FamilyMember.objects.filter(family__in=families).select_related("family")
    return render(
        request,
        "health/dashboard.html",
        {"members": members},
    )


@login_required
def record_edit(request, member_id: int):
    member = get_object_or_404(
        FamilyMember.objects.filter(family__in=_user_families(request.user)),
        pk=member_id,
    )
    record, _ = HealthRecord.objects.get_or_create(member=member)
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
        return redirect("health:dashboard")
    return render(
        request,
        "health/record_form.html",
        {"member": member, "record": record},
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
        return redirect("health:dashboard")
    return render(request, "health/medication_form.html", {"member": member})

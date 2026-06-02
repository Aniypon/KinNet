from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import PasswordHelpForm
from ..models import FamilyMembership, PasswordResetRequest
from ..permissions import can_reset_password_of, reset_eligible_families

User = get_user_model()

def password_help(request):
    """Публичная форма: юзер без доступа просит сброс пароля.
    Ответ всегда одинаковый — не раскрываем, существует ли аккаунт."""
    submitted = False
    if request.method == "POST":
        form = PasswordHelpForm(request.POST)
        if form.is_valid():
            submitted = True
            username = form.cleaned_data["username"].strip()
            note = form.cleaned_data["note"]
            user = User.objects.filter(username__iexact=username).first()
            if user is not None:
                # Не плодим дубли: создаём pending только если активной заявки нет.
                if not PasswordResetRequest.objects.filter(user=user, status="pending").exists():
                    PasswordResetRequest.objects.create(user=user, note=note)
    else:
        form = PasswordHelpForm()
    return render(request, "registration/password_help.html", {"form": form, "submitted": submitted})

def _visible_pending(approver):
    qs = PasswordResetRequest.objects.filter(status="pending").select_related("user")
    if approver.is_staff or approver.is_superuser:
        return qs
    member_ids = FamilyMembership.objects.filter(
        family__in=reset_eligible_families(approver)
    ).values_list("user_id", flat=True)
    return qs.filter(user_id__in=member_ids).exclude(user=approver)

@login_required
def password_requests(request):
    requests_qs = _visible_pending(request.user)
    history = (
        PasswordResetRequest.objects.exclude(status="pending")
        .select_related("user", "resolved_by")[:20]
        if request.user.is_staff
        else None
    )
    return render(
        request,
        "registration/password_requests.html",
        {"requests": requests_qs, "history": history},
    )

@login_required
def password_request_approve(request, pk):
    obj = get_object_or_404(PasswordResetRequest, pk=pk, status="pending")
    if not can_reset_password_of(request.user, obj.user):
        raise PermissionDenied
    if request.method == "POST":
        form = SetPasswordForm(obj.user, request.POST)
        if form.is_valid():
            form.save()  # валидаторы пароля Django применяются здесь
            obj.status = "approved"
            obj.resolved_by = request.user
            obj.resolved_at = timezone.now()
            obj.save(update_fields=["status", "resolved_by", "resolved_at"])
            return redirect("password_requests")
    else:
        form = SetPasswordForm(obj.user)
    return render(
        request,
        "registration/password_request_approve.html",
        {"form": form, "req": obj},
    )

@login_required
def password_request_reject(request, pk):
    if request.method != "POST":
        return HttpResponse(status=405)
    obj = get_object_or_404(PasswordResetRequest, pk=pk, status="pending")
    if not can_reset_password_of(request.user, obj.user):
        raise PermissionDenied
    obj.status = "rejected"
    obj.resolved_by = request.user
    obj.resolved_at = timezone.now()
    obj.save(update_fields=["status", "resolved_by", "resolved_at"])
    return redirect("password_requests")

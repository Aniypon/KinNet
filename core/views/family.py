"""Family CRUD, memberships, invitations, user lookup."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..family_context import get_user_families
from ..forms import FamilyForm, FamilyInvitationForm, FamilyMembershipRoleForm
from ..models import Family, FamilyInvitation, FamilyMembership, UserProfile
from ..permissions import get_membership, has_role
from ._helpers import has_family_access


@login_required
def families(request):
	if request.method == "POST":
		form = FamilyForm(request.POST)
		if form.is_valid():
			family = form.save(commit=False)
			family.created_by = request.user
			family.save()
			FamilyMembership.objects.create(
				family=family,
				user=request.user,
				role="owner",
				display_order=0,
			)
			return redirect("families")
	else:
		form = FamilyForm()

	families_qs = get_user_families(request.user)
	roles_map = {
		membership.family_id: membership.role
		for membership in FamilyMembership.objects.filter(user=request.user)
	}
	families_data = [
		{"family": family, "role": roles_map.get(family.id)} for family in families_qs
	]
	return render(
		request,
		"families.html",
		{"form": form, "families_data": families_data},
	)


@login_required
def family_edit(request, family_id):
	family = get_object_or_404(Family, id=family_id)
	if not has_role(request.user, family, {"owner", "admin"}):
		return redirect("families")

	if request.method == "POST":
		form = FamilyForm(request.POST, instance=family)
		if form.is_valid():
			form.save()
			return redirect("families")
	else:
		form = FamilyForm(instance=family)

	return render(request, "entity_form.html", {"form": form, "title": "Редактировать семью"})


@login_required
def family_delete(request, family_id):
	family = get_object_or_404(Family, id=family_id)
	if not has_role(request.user, family, {"owner"}):
		return redirect("families")

	if request.method == "POST":
		family.delete()
		return redirect("families")

	return render(
		request,
		"confirm_delete.html",
		{"title": "Удалить семью", "object": family, "action_verb": "Удалить"},
	)


@login_required
def family_leave(request, family_id):
	family = get_object_or_404(Family, id=family_id)
	membership = get_membership(request.user, family)
	if not membership:
		return redirect("members")
	remaining_memberships = family.memberships.exclude(user=request.user)
	next_owner = None
	if membership.role == "owner" and remaining_memberships.exists():
		next_owner = (
			remaining_memberships.filter(role="admin").order_by("joined_at").first()
			or remaining_memberships.order_by("joined_at").first()
		)

	if request.method == "POST":
		if membership.role == "owner" and not family.memberships.exclude(user=request.user).exists():
			family.delete()
		else:
			if next_owner:
				next_owner.role = "owner"
				next_owner.save(update_fields=["role"])
			membership.delete()
		return redirect("families")

	return render(
		request,
		"confirm_delete.html",
		{
			"title": "Покинуть семью",
			"object": family,
			"action_verb": "Покинуть",
			"action_note": (
				"Вы единственный участник, поэтому семья будет удалена."
				if not remaining_memberships.exists()
				else f"Владельцем станет {next_owner.user.get_full_name() or next_owner.user.username}."
				if next_owner
				else "Ваш доступ к семье будет удалён."
			),
		},
	)


@login_required
def family_detail(request, family_id):
	family = get_object_or_404(Family, id=family_id)
	if not has_family_access(request.user, family):
		return redirect("families")

	memberships = family.memberships.select_related("user")
	can_manage_roles = has_role(request.user, family, {"owner"})
	can_invite = has_role(request.user, family, {"owner", "admin"})
	current_membership = get_membership(request.user, family)
	can_leave = bool(current_membership)

	role_form = FamilyMembershipRoleForm()
	invite_form = FamilyInvitationForm()

	if request.method == "POST":
		action = request.POST.get("action")
		if action == "role" and can_manage_roles:
			membership_id = request.POST.get("membership_id")
			membership = get_object_or_404(FamilyMembership, id=membership_id, family=family)
			role_form = FamilyMembershipRoleForm(request.POST, instance=membership)
			if role_form.is_valid():
				new_role = role_form.cleaned_data["role"]
				if membership.role == "owner":
					return redirect("family_detail", family_id=family.id)
				if new_role == "owner":
					owner_membership = get_membership(request.user, family)
					if owner_membership and owner_membership.role == "owner" and membership.user != request.user:
						membership.role = "owner"
						membership.save(update_fields=["role"])
						owner_membership.role = "member"
						owner_membership.save(update_fields=["role"])
						return redirect("family_detail", family_id=family.id)
					return redirect("family_detail", family_id=family.id)
				role_form.save()
				return redirect("family_detail", family_id=family.id)

		if action == "invite" and can_invite:
			invite_form = FamilyInvitationForm(request.POST)
			if invite_form.is_valid():
				username = invite_form.cleaned_data.get("username")
				exists = FamilyInvitation.objects.filter(
					family=family,
					status="pending",
					username=username or "",
				).exists()
				if not exists:
					FamilyInvitation.objects.create(
						family=family,
						invited_by=request.user,
						username=username or "",
					)
				return redirect("family_detail", family_id=family.id)

	return render(
		request,
		"family_detail.html",
		{
			"family": family,
			"memberships": memberships,
			"role_form": role_form,
			"invite_form": invite_form,
			"can_manage_roles": can_manage_roles,
			"can_invite": can_invite,
			"can_leave": can_leave,
			"invitations": family.invitations.exclude(status="revoked").order_by("-created_at"),
			"site_origin": request.build_absolute_uri("/")[:-1],
		},
	)


@login_required
def family_member_remove(request, family_id, membership_id):
	family = get_object_or_404(Family, id=family_id)
	if not has_role(request.user, family, {"owner", "admin"}):
		return redirect("family_detail", family_id=family.id)

	membership = get_object_or_404(FamilyMembership, id=membership_id, family=family)
	if membership.role == "owner":
		return redirect("family_detail", family_id=family.id)

	if request.method == "POST":
		membership.delete()
		return redirect("family_detail", family_id=family.id)

	return render(
		request,
		"confirm_delete.html",
		{"title": "Удалить участника", "object": membership.user, "action_verb": "Удалить"},
	)


@login_required
def invitation_accept(request, token):
	invitation = get_object_or_404(FamilyInvitation, token=token, status="pending")
	user = request.user

	if invitation.username and invitation.username != user.username:
		return redirect("home")
	if request.method == "POST":
		FamilyMembership.objects.get_or_create(
			family=invitation.family,
			user=user,
			defaults={"role": "member", "display_order": invitation.family.memberships.count()},
		)
		invitation.status = "accepted"
		invitation.accepted_at = timezone.now()
		invitation.save(update_fields=["status", "accepted_at"])
		return redirect("families")

	return render(
		request,
		"confirm_invite.html",
		{"family": invitation.family, "invitation": invitation},
	)


@login_required
def user_suggest(request):
	query = request.GET.get("q", "").strip()
	family_id = request.GET.get("family")
	user_model = get_user_model()
	users = user_model.objects.all()
	if query:
		users = users.filter(username__istartswith=query)
	if family_id:
		users = users.exclude(family_memberships__family_id=family_id)
	data = list(users.values_list("username", flat=True)[:10])
	return JsonResponse({"results": data})


@login_required
def invitation_revoke(request, invitation_id):
	invitation = get_object_or_404(FamilyInvitation, id=invitation_id)
	if not has_role(request.user, invitation.family, {"owner", "admin"}):
		return redirect("families")

	if request.method == "POST":
		invitation.status = "revoked"
		invitation.save(update_fields=["status"])
		return redirect("family_detail", family_id=invitation.family.id)

	return render(
		request,
		"confirm_delete.html",
		{"title": "Отозвать приглашение", "object": invitation},
	)


@login_required
def user_detail(request, user_id):
	if not FamilyMembership.objects.filter(user_id=user_id, family__memberships__user=request.user).exists():
		return redirect("members")

	user_model = get_user_model()
	user = get_object_or_404(user_model, id=user_id)
	profile = UserProfile.objects.filter(user=user).first()

	return render(
		request,
		"user_detail.html",
		{"profile_user": user, "profile": profile},
	)

"""Family members listing/CRUD + family tree management."""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..family_context import current_family
from ..forms import FamilyMemberForm
from ..models import Family, FamilyMember, UserProfile
from ..permissions import get_membership, has_role
from ..services.family_tree import (
	FamilyTreeValidationError,
	apply_relation_action,
	validate_family_tree,
)
from ._helpers import (
	audit,
	build_tree_data,
	has_family_access,
	quick_error_response,
	quick_save_response,
)


@login_required
def family_members(request):
	family, families = current_family(request)
	if not family:
		return redirect("families")

	if request.method == "POST":
		form = FamilyMemberForm(request.POST, family=family)
		if form.is_valid():
			member = form.save(commit=False)
			member.family = family
			member.display_order = family.family_members.count()
			member.save()
			quick_response = quick_save_response(request, "Родственник добавлен")
			if quick_response:
				return quick_response
			return redirect(f"{request.path}?family={family.id}")
		quick_response = quick_error_response(request, form)
		if quick_response:
			return quick_response
	else:
		form = FamilyMemberForm(family=family)

	query = request.GET.get("q", "").strip()
	current_view = request.GET.get("view", "people")
	if current_view not in {"people", "tree", "add"}:
		current_view = "people"
	tree_mode = request.GET.get("mode", "view")
	can_manage = has_role(request.user, family, {"owner", "admin"})
	current_membership = get_membership(request.user, family)
	can_leave = bool(current_membership)
	if tree_mode == "edit" and not can_manage:
		tree_mode = "view"
	if current_view == "tree" and tree_mode != "edit":
		current_view = "people"
	selected_person_id = request.GET.get("person", "")
	members = family.family_members.filter(user__isnull=True)
	memberships = family.memberships.select_related("user")
	if query:
		members = members.filter(
			Q(first_name__icontains=query)
			| Q(last_name__icontains=query)
			| Q(middle_name__icontains=query)
			| Q(relation__icontains=query)
		)
		memberships = memberships.filter(
			Q(user__username__icontains=query)
			| Q(user__first_name__icontains=query)
			| Q(user__last_name__icontains=query)
		)
	profiles_by_user = {
		profile.user_id: profile
		for profile in UserProfile.objects.filter(user__in=[m.user for m in memberships])
	}
	tree_data = build_tree_data(family, include_all=True)
	tree_issues = [issue.__dict__ for issue in validate_family_tree(family)]
	return render(
		request,
		"members.html",
		{
			"form": form,
			"members": members,
			"memberships": memberships,
			"query": query,
			"profiles_by_user": profiles_by_user,
			"family": family,
			"families": families,
			"can_manage": can_manage,
			"can_leave": can_leave,
			"current_view": current_view,
			"tree_mode": tree_mode,
			"selected_person_id": selected_person_id,
			"tree_data": tree_data,
			"tree_issues": tree_issues,
		},
	)


@login_required
def member_detail(request, member_id):
	member = get_object_or_404(FamilyMember, id=member_id)
	if not has_family_access(request.user, member.family):
		return redirect("members")

	return render(
		request,
		"member_detail.html",
		{"member": member},
	)


@login_required
def member_edit(request, member_id):
	member = get_object_or_404(FamilyMember, id=member_id)
	if not has_family_access(request.user, member.family):
		return redirect("members")

	if request.method == "POST":
		form = FamilyMemberForm(request.POST, instance=member, family=member.family)
		if form.is_valid():
			form.save()
			return redirect(f"/members/?family={member.family.id}")
	else:
		form = FamilyMemberForm(instance=member, family=member.family)

	return render(
		request,
		"entity_form.html",
		{"form": form, "title": "Редактировать родственника"},
	)


@login_required
def member_delete(request, member_id):
	member = get_object_or_404(FamilyMember, id=member_id)
	if not has_family_access(request.user, member.family):
		return redirect("members")

	if request.method == "POST":
		family_id = member.family.id
		member.delete()
		return redirect(f"/members/?family={family_id}")

	return render(
		request,
		"confirm_delete.html",
		{"title": "Удалить родственника", "object": member},
	)


@login_required
def family_tree(request):
	family, families = current_family(request)
	if not family:
		return redirect("families")
	return redirect(f"/members/?family={family.id}&view=tree&mode=view")


@login_required
def family_tree_edit(request):
	family, families = current_family(request)
	if not family:
		return redirect("families")
	if not has_role(request.user, family, {"owner", "admin"}):
		return redirect(f"/members/?family={family.id}&view=tree&mode=view")
	return redirect(f"/members/?family={family.id}&view=tree&mode=edit")


@login_required
def family_tree_edit_legacy(request):
	family, families = current_family(request)
	if not family:
		return redirect("families")
	if not has_role(request.user, family, {"owner", "admin"}):
		return redirect("family_tree_graph")

	members = family.family_members.all()
	available_members = family.family_members.filter(in_tree=False)

	if request.method == "POST":
		member_id = request.POST.get("member_id")
		if not member_id:
			return redirect("family_tree_edit")
		parent1_id = request.POST.get("parent1") or None
		parent2_id = request.POST.get("parent2") or None
		children_ids = request.POST.getlist("children")

		member = get_object_or_404(FamilyMember, id=member_id, family=family)
		member.parent1_id = int(parent1_id) if parent1_id else None
		member.parent2_id = int(parent2_id) if parent2_id else None
		member.save(update_fields=["parent1", "parent2"])

		for child in members:
			is_selected = str(child.id) in children_ids
			if is_selected:
				if child.parent1_id in (None, member.id):
					child.parent1 = member
				elif child.parent2_id in (None, member.id):
					child.parent2 = member
				child.save(update_fields=["parent1", "parent2"])
			else:
				if child.parent1_id == member.id:
					child.parent1 = None
				if child.parent2_id == member.id:
					child.parent2 = None
				child.save(update_fields=["parent1", "parent2"])

		return redirect("family_tree_edit")

	tree_data = build_tree_data(family, include_all=True)
	tree_issues = [issue.__dict__ for issue in validate_family_tree(family)]

	return render(
		request,
		"family_tree_edit.html",
		{
			"family": family,
			"families": families,
			"members": members,
			"available_members": available_members,
			"tree_data": tree_data,
			"tree_issues": tree_issues,
		},
	)


@login_required
def family_tree_order_update(request):
	if request.method != "POST":
		return JsonResponse({"error": "Method not allowed"}, status=405)

	payload = json.loads(request.body.decode("utf-8"))
	family_id = payload.get("family")
	people = payload.get("people", [])

	family = get_object_or_404(Family, id=family_id)
	if not has_role(request.user, family, {"owner", "admin"}):
		return JsonResponse({"error": "Forbidden"}, status=403)

	people_qs = family.family_members.filter(id__in=people)
	for index, item_id in enumerate(people):
		people_qs.filter(id=item_id).update(display_order=index)

	return JsonResponse({"status": "ok"})


@login_required
def family_tree_relations_update(request):
	if request.method != "POST":
		return JsonResponse({"error": "Method not allowed"}, status=405)

	payload = json.loads(request.body.decode("utf-8"))
	family_id = payload.get("family")
	action = payload.get("action")

	family = get_object_or_404(Family, id=family_id)
	if not has_role(request.user, family, {"owner", "admin"}):
		return JsonResponse({"error": "Forbidden"}, status=403)

	try:
		apply_relation_action(family, action, payload)
	except FamilyTreeValidationError as exc:
		return JsonResponse({"error": exc.message, "code": exc.code}, status=400)
	audit(family, request.user, "tree", "FamilyMember", f"Изменены связи древа: {action}", payload={"action": action})

	return JsonResponse(
		{
			"status": "ok",
			"tree_data": build_tree_data(family, include_all=True),
			"issues": [issue.__dict__ for issue in validate_family_tree(family)],
		}
	)


@login_required
def family_tree_graph(request):
	"""Interactive D3-driven family-tree graph with zoom + drag."""
	user = request.user
	family_id = request.GET.get("family")
	families_qs = Family.objects.filter(
		Q(memberships__user=user) | Q(created_by=user)
	).distinct()

	family = None
	if family_id:
		family = families_qs.filter(pk=family_id).first()
	family = family or families_qs.first()
	if family:
		return redirect(f"/members/?family={family.id}&view=tree&mode=view")
	members = []
	if family:
		members = list(
			FamilyMember.objects.filter(family=family).values(
				"id",
				"first_name",
				"last_name",
				"middle_name",
				"relation",
				"birth_date",
				"parent1_id",
				"parent2_id",
				"spouse_id",
				"display_order",
			)
		)
	can_manage = bool(family and has_role(request.user, family, {"owner", "admin"}))
	for member in members:
		if member.get("birth_date") is not None:
			member["birth_date"] = str(member["birth_date"])
	return render(
		request,
		"family_tree_graph.html",
		{
			"families": families_qs,
			"current_family": family,
			"members_data": members,
			"can_manage": can_manage,
		},
	)

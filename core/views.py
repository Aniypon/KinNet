import json
import os

from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
	EventForm,
	FamilyForm,
	FamilyInvitationForm,
	FamilyMemberForm,
	FamilyMembershipRoleForm,
	MessageForm,
	SignupForm,
	UserProfileForm,
	TaskChecklistItemForm,
	TaskContributionForm,
	TaskForm,
	TaskCommentForm,
	EventCommentForm,
	GoalForm,
	GoalContributionForm,
	FamilyPhotoForm,
)
from .models import (
	Event,
	Family,
	FamilyInvitation,
	FamilyMember,
	FamilyMembership,
	Message,
	Goal,
	GoalContribution,
	TaskComment,
	EventComment,
	FamilyPhoto,
	Task,
	TaskChecklistItem,
	TelegramProfile,
	UserProfile,
)
from .utils import get_next_event_date


def _get_user_families(user):
	return Family.objects.filter(Q(memberships__user=user) | Q(created_by=user)).distinct()


def _has_family_access(user, family):
	return _get_user_families(user).filter(id=family.id).exists()


def _get_membership(user, family):
	return FamilyMembership.objects.filter(user=user, family=family).first()


def _has_role(user, family, roles):
	membership = _get_membership(user, family)
	return membership is not None and membership.role in roles


def _get_current_family(request):
	families = _get_user_families(request.user)
	family_id = request.GET.get("family")
	if family_id:
		return families.filter(id=family_id).first(), families
	return families.first(), families


def _sync_birthday_events(user, birth_date):
	families = _get_user_families(user)
	if birth_date:
		for family in families:
			membership = _get_membership(user, family)
			member, _ = FamilyMember.objects.get_or_create(
				family=family,
				user=user,
				defaults={
					"first_name": user.first_name or user.username,
					"last_name": user.last_name,
					"relation": "Участник",
					"display_order": membership.display_order if membership else 0,
				},
			)
			title = f"День рождения {member}"
			event, created = Event.objects.get_or_create(
				family=family,
				member=member,
				kind="birthday",
				defaults={"title": title, "date": birth_date},
			)
			if not created:
				updates = {}
				if event.date != birth_date:
					updates["date"] = birth_date
				if event.title != title:
					updates["title"] = title
				if updates:
					Event.objects.filter(id=event.id).update(**updates)
	else:
		Event.objects.filter(
			family__in=families,
			kind="birthday",
			member__user=user,
		).delete()


def _build_tree_data(family, include_all=False):
	members = family.family_members.all()
	if not include_all:
		members = members.filter(in_tree=True)
	return [
		{
			"id": member.id,
			"label": str(member),
			"relation": member.relation,
			"parent1": member.parent1_id,
			"parent2": member.parent2_id,
			"spouse": member.spouse_id,
			"is_user": bool(member.user_id),
			"in_tree": member.in_tree,
		}
		for member in members
	]


def home(request):
	family = None
	families = []
	pending_invitations = []
	pending_telegram = None
	upcoming_events = []
	upcoming_tasks = []
	latest_message = None
	if request.user.is_authenticated:
		family, families = _get_current_family(request)
		pending_invitations = FamilyInvitation.objects.filter(
			status="pending",
			username=request.user.username,
		)
		pending_telegram = TelegramProfile.objects.filter(
			user=request.user,
			is_confirmed=False,
		).first()
		if family:
			today = timezone.localdate()
			events = list(family.events.select_related("member"))
			for event in events:
				event.next_date = get_next_event_date(event, today)
			upcoming_events = [
				event for event in events if event.next_date and event.next_date >= today
			]
			upcoming_events.sort(key=lambda item: item.next_date)
			upcoming_events = upcoming_events[:3]
			upcoming_tasks = list(
				family.tasks.filter(status__in=["todo", "in_progress"], due_date__isnull=False)
				.order_by("due_date")[:3]
			)
			latest_message = family.messages.order_by("-created_at").select_related("sender").first()
	return render(
		request,
		"home.html",
		{
			"family": family,
			"families": families,
			"pending_invitations": pending_invitations,
			"pending_telegram": pending_telegram,
			"upcoming_events": upcoming_events,
			"upcoming_tasks": upcoming_tasks,
			"latest_message": latest_message,
		},
	)


@login_required
def telegram_confirm(request, token):
	profile = get_object_or_404(TelegramProfile, confirm_token=token)
	if profile.user_id != request.user.id:
		return render(
			request,
			"telegram_confirm.html",
			{
				"success": False,
				"message": "Эта привязка принадлежит другому аккаунту.",
			},
		)

	if not profile.is_confirmed:
		profile.is_confirmed = True
		profile.confirmed_at = timezone.now()
		profile.save(update_fields=["is_confirmed", "confirmed_at"])
		try:
			from core.tasks import _send_telegram

			_send_telegram(
				profile.chat_id,
				"Привязка Telegram успешно подтверждена. Теперь команды доступны.",
			)
		except Exception:
			pass

	return render(
		request,
		"telegram_confirm.html",
		{
			"success": True,
			"message": "Telegram успешно подтверждён.",
		},
	)


def signup(request):
	if request.method == "POST":
		form = SignupForm(request.POST)
		if form.is_valid():
			user = form.save()
			login(request, user)
			return redirect("home")
	else:
		form = SignupForm()
	return render(request, "registration/signup.html", {"form": form})


@login_required
def profile_edit(request):
	profile, _ = UserProfile.objects.get_or_create(
		user=request.user,
		defaults={"birth_date": timezone.localdate()},
	)
	if request.method == "POST":
		form = UserProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
		if form.is_valid():
			profile = form.save()
			_sync_birthday_events(request.user, profile.birth_date)
			return redirect("profile_edit")
	else:
		form = UserProfileForm(instance=profile, user=request.user)

	return render(
		request,
		"entity_form.html",
		{"form": form, "title": "Мои данные"},
	)


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

	families_qs = _get_user_families(request.user)
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
	if not _has_role(request.user, family, {"owner", "admin"}):
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
	if not _has_role(request.user, family, {"owner"}):
		return redirect("families")

	if request.method == "POST":
		family.delete()
		return redirect("families")

	return render(
		request,
		"confirm_delete.html",
		{"title": "Удалить семью", "object": family},
	)


@login_required
def family_detail(request, family_id):
	family = get_object_or_404(Family, id=family_id)
	if not _has_family_access(request.user, family):
		return redirect("families")

	memberships = family.memberships.select_related("user")
	can_manage_roles = _has_role(request.user, family, {"owner"})
	can_invite = _has_role(request.user, family, {"owner", "admin"})

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
					owner_membership = _get_membership(request.user, family)
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
			"invitations": family.invitations.exclude(status="revoked").order_by("-created_at"),
		},
	)


@login_required
def family_member_remove(request, family_id, membership_id):
	family = get_object_or_404(Family, id=family_id)
	if not _has_role(request.user, family, {"owner", "admin"}):
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
		{"title": "Удалить участника", "object": membership.user},
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
	if not _has_role(request.user, invitation.family, {"owner", "admin"}):
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
def family_members(request):
	family, families = _get_current_family(request)
	if not family:
		return redirect("families")

	if request.method == "POST":
		form = FamilyMemberForm(request.POST, family=family)
		if form.is_valid():
			member = form.save(commit=False)
			member.family = family
			member.display_order = family.family_members.count()
			member.save()
			return redirect(f"{request.path}?family={family.id}")
	else:
		form = FamilyMemberForm(family=family)

	query = request.GET.get("q", "").strip()
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
	can_manage = _has_role(request.user, family, {"owner", "admin"})
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
		},
	)


@login_required
def member_detail(request, member_id):
	member = get_object_or_404(FamilyMember, id=member_id)
	if not _has_family_access(request.user, member.family):
		return redirect("members")

	return render(
		request,
		"member_detail.html",
		{"member": member},
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


@login_required
def family_tree(request):
	family, families = _get_current_family(request)
	if not family:
		return redirect("families")

	memberships = family.memberships.select_related("user")
	for membership in memberships:
		FamilyMember.objects.get_or_create(
			family=family,
			user=membership.user,
			defaults={
				"first_name": membership.user.first_name or membership.user.username,
				"last_name": membership.user.last_name,
				"relation": "Участник",
				"display_order": membership.display_order,
			},
		)

	members = family.family_members.all()
	tree_data = _build_tree_data(family)
	can_manage = _has_role(request.user, family, {"owner", "admin"})
	return render(
		request,
		"family_tree.html",
		{
			"family": family,
			"families": families,
			"members": members,
			"memberships": memberships,
			"tree_data": tree_data,
			"can_manage": can_manage,
		},
	)


@login_required
def family_tree_edit(request):
	family, families = _get_current_family(request)
	if not family:
		return redirect("families")
	if not _has_role(request.user, family, {"owner", "admin"}):
		return redirect("family_tree")

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

	tree_data = _build_tree_data(family, include_all=True)

	return render(
		request,
		"family_tree_edit.html",
		{
			"family": family,
			"families": families,
			"members": members,
			"available_members": available_members,
			"tree_data": tree_data,
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
	if not _has_role(request.user, family, {"owner", "admin"}):
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
	if not _has_role(request.user, family, {"owner", "admin"}):
		return JsonResponse({"error": "Forbidden"}, status=403)

	if action == "pair":
		member_a = get_object_or_404(FamilyMember, id=payload.get("memberA"), family=family)
		member_b = get_object_or_404(FamilyMember, id=payload.get("memberB"), family=family)
		if member_a.id == member_b.id:
			return JsonResponse({"error": "Same member"}, status=400)
		if member_a.spouse_id and member_a.spouse_id != member_b.id:
			return JsonResponse({"error": "Member already has spouse"}, status=400)
		if member_b.spouse_id and member_b.spouse_id != member_a.id:
			return JsonResponse({"error": "Member already has spouse"}, status=400)
		member_a.spouse = member_b
		member_b.spouse = member_a
		member_a.in_tree = True
		member_b.in_tree = True
		member_a.save(update_fields=["spouse", "in_tree"])
		member_b.save(update_fields=["spouse", "in_tree"])
		return JsonResponse({"status": "ok", "tree_data": _build_tree_data(family, include_all=True)})

	if action == "add_child":
		child = get_object_or_404(FamilyMember, id=payload.get("child"), family=family)
		parent1 = get_object_or_404(FamilyMember, id=payload.get("parent1"), family=family)
		parent2 = get_object_or_404(FamilyMember, id=payload.get("parent2"), family=family)
		if child.id in (parent1.id, parent2.id):
			return JsonResponse({"error": "Invalid parent"}, status=400)
		child.parent1 = parent1
		child.parent2 = parent2
		child.in_tree = True
		parent1.in_tree = True
		parent2.in_tree = True
		child.save(update_fields=["parent1", "parent2", "in_tree"])
		parent1.save(update_fields=["in_tree"])
		parent2.save(update_fields=["in_tree"])
		return JsonResponse({"status": "ok", "tree_data": _build_tree_data(family, include_all=True)})

	if action == "set_parent":
		child = get_object_or_404(FamilyMember, id=payload.get("child"), family=family)
		parent = get_object_or_404(FamilyMember, id=payload.get("parent"), family=family)
		if child.id == parent.id:
			return JsonResponse({"error": "Invalid parent"}, status=400)
		if child.parent1_id in (None, parent.id):
			child.parent1 = parent
		else:
			child.parent2 = parent
		child.in_tree = True
		parent.in_tree = True
		child.save(update_fields=["parent1", "parent2", "in_tree"])
		parent.save(update_fields=["in_tree"])
		return JsonResponse({"status": "ok", "tree_data": _build_tree_data(family, include_all=True)})

	if action == "clear_parents":
		member = get_object_or_404(FamilyMember, id=payload.get("member"), family=family)
		member.parent1 = None
		member.parent2 = None
		member.in_tree = True
		member.save(update_fields=["parent1", "parent2", "in_tree"])
		return JsonResponse({"status": "ok", "tree_data": _build_tree_data(family, include_all=True)})

	if action == "remove_from_tree":
		member = get_object_or_404(FamilyMember, id=payload.get("member"), family=family)
		member.parent1 = None
		member.parent2 = None
		if member.spouse_id:
			spouse = member.spouse
			member.spouse = None
			member.save(update_fields=["parent1", "parent2", "spouse"])
			if spouse and spouse.family_id == family.id:
				spouse.spouse = None
				spouse.save(update_fields=["spouse"])
		member.in_tree = False
		member.save(update_fields=["in_tree"])
		return JsonResponse({"status": "ok", "tree_data": _build_tree_data(family, include_all=True)})

	if action == "unpair":
		member = get_object_or_404(FamilyMember, id=payload.get("member"), family=family)
		if member.spouse_id:
			spouse = member.spouse
			member.spouse = None
			member.save(update_fields=["spouse"])
			if spouse and spouse.family_id == family.id:
				spouse.spouse = None
				spouse.save(update_fields=["spouse"])
		return JsonResponse({"status": "ok", "tree_data": _build_tree_data(family, include_all=True)})

	if action == "clear_tree":
		family.family_members.update(parent1=None, parent2=None, spouse=None, in_tree=False)
		return JsonResponse({"status": "ok", "tree_data": _build_tree_data(family, include_all=True)})

	if action == "show_all":
		family.family_members.update(in_tree=True)
		return JsonResponse({"status": "ok", "tree_data": _build_tree_data(family, include_all=True)})

	return JsonResponse({"error": "Unknown action"}, status=400)


@login_required
def events(request):
	family, families = _get_current_family(request)
	if not family:
		return redirect("families")

	if request.method == "POST":
		form = EventForm(request.POST, family=family)
		if form.is_valid():
			event = form.save(commit=False)
			event.family = family
			event.save()
			return redirect(f"{request.path}?family={family.id}")
	else:
		form = EventForm(family=family)

	items = family.events.select_related("member")
	query = request.GET.get("q", "").strip()
	kind = request.GET.get("kind", "").strip()
	if query:
		items = items.filter(title__icontains=query)
	if kind:
		items = items.filter(kind=kind)
	can_manage = _has_role(request.user, family, {"owner", "admin"})
	return render(
		request,
		"events.html",
		{
			"form": form,
			"events": items,
			"family": family,
			"families": families,
			"can_manage": can_manage,
			"query": query,
			"kind": kind,
		},
	)


@login_required
def event_detail(request, event_id):
	event = get_object_or_404(Event, id=event_id)
	if not _has_family_access(request.user, event.family):
		return redirect("events")

	comments = event.comments.select_related("author")
	comment_form = EventCommentForm()
	if request.method == "POST" and "comment-text" in request.POST:
		comment_form = EventCommentForm(request.POST)
		if comment_form.is_valid():
			comment = comment_form.save(commit=False)
			comment.event = event
			comment.author = request.user
			comment.save()
			return redirect("event_detail", event_id=event.id)

	return render(
		request,
		"event_detail.html",
		{
			"event": event,
			"comments": comments,
			"comment_form": comment_form,
		},
	)


@login_required
def tasks(request):
	family, families = _get_current_family(request)
	if not family:
		return redirect("families")

	if request.method == "POST":
		action = request.POST.get("action")
		if action == "status":
			task = get_object_or_404(Task, id=request.POST.get("task_id"), family=family)
			new_status = request.POST.get("status")
			if new_status in dict(Task.STATUS_CHOICES):
				task.status = new_status
				task.save(update_fields=["status"])
			return redirect(f"{request.path}?family={family.id}")

		form = TaskForm(request.POST, family=family)
		if form.is_valid():
			task = form.save(commit=False)
			task.family = family
			task.created_by = request.user
			task.save()
			return redirect(f"{request.path}?family={family.id}")
	else:
		form = TaskForm(family=family)

	items = family.tasks.select_related("assignee")
	query = request.GET.get("q", "").strip()
	status = request.GET.get("status", "").strip()
	if query:
		items = items.filter(title__icontains=query)
	if status:
		items = items.filter(status=status)
	can_manage = _has_role(request.user, family, {"owner", "admin"})
	return render(
		request,
		"tasks.html",
		{
			"form": form,
			"tasks": items,
			"family": family,
			"families": families,
			"can_manage": can_manage,
			"query": query,
			"status": status,
		},
	)


@login_required
def task_detail(request, task_id):
	task = get_object_or_404(Task, id=task_id)
	family = task.family
	families = _get_user_families(request.user)
	if not families.filter(id=family.id).exists():
		return redirect("tasks")
	can_manage = _has_role(request.user, family, {"owner", "admin"})

	checklist_form = TaskChecklistItemForm(prefix="check")
	contribution_form = TaskContributionForm(prefix="contrib", family=family)
	comment_form = TaskCommentForm(prefix="comment")
	total_cost = task.contributions.aggregate(total=Sum("amount")).get("total") or 0
	comments = task.comments.select_related("author")

	if request.method == "POST":
		if "toggle-id" in request.POST:
			item = get_object_or_404(TaskChecklistItem, id=request.POST.get("toggle-id"), task=task)
			item.is_done = "toggle-done" in request.POST
			item.save(update_fields=["is_done"])
			return redirect("task_detail", task_id=task.id)

		if "check-title" in request.POST:
			checklist_form = TaskChecklistItemForm(request.POST, prefix="check")
			if checklist_form.is_valid():
				item = checklist_form.save(commit=False)
				item.task = task
				item.save()
				return redirect("task_detail", task_id=task.id)

		if "contrib-user" in request.POST:
			contribution_form = TaskContributionForm(request.POST, prefix="contrib", family=family)
			if contribution_form.is_valid():
				contribution = contribution_form.save(commit=False)
				contribution.task = task
				contribution.save()
				return redirect("task_detail", task_id=task.id)

		if "comment-text" in request.POST:
			comment_form = TaskCommentForm(request.POST, prefix="comment")
			if comment_form.is_valid():
				comment = comment_form.save(commit=False)
				comment.task = task
				comment.author = request.user
				comment.save()
				return redirect("task_detail", task_id=task.id)

	return render(
		request,
		"task_detail.html",
		{
			"task": task,
			"checklist_form": checklist_form,
			"contribution_form": contribution_form,
			"comment_form": comment_form,
			"comments": comments,
			"total_cost": total_cost,
			"family": family,
			"families": families,
			"can_manage": can_manage,
		},
	)


@login_required
def goals(request):
	family, families = _get_current_family(request)
	if not family:
		return redirect("families")

	if request.method == "POST":
		form = GoalForm(request.POST)
		if form.is_valid():
			goal = form.save(commit=False)
			goal.family = family
			goal.created_by = request.user
			goal.save()
			return redirect(f"{request.path}?family={family.id}")
	else:
		form = GoalForm()

	items = family.goals.all()
	return render(
		request,
		"goals.html",
		{"form": form, "goals": items, "family": family, "families": families},
	)


@login_required
def goal_detail(request, goal_id):
	goal = get_object_or_404(Goal, id=goal_id)
	if not _has_family_access(request.user, goal.family):
		return redirect("goals")

	contribution_form = GoalContributionForm(prefix="contrib", family=goal.family)
	total = goal.contributions.aggregate(total=Sum("amount")).get("total") or 0

	if request.method == "POST" and "contrib-user" in request.POST:
		contribution_form = GoalContributionForm(request.POST, prefix="contrib", family=goal.family)
		if contribution_form.is_valid():
			contribution = contribution_form.save(commit=False)
			contribution.goal = goal
			contribution.save()
			return redirect("goal_detail", goal_id=goal.id)

	return render(
		request,
		"goal_detail.html",
		{
			"goal": goal,
			"contribution_form": contribution_form,
			"total": total,
		},
	)


@login_required
def family_album(request):
	family, families = _get_current_family(request)
	if not family:
		return redirect("families")

	if request.method == "POST":
		form = FamilyPhotoForm(request.POST, request.FILES)
		if form.is_valid():
			photo = form.save(commit=False)
			photo.family = family
			photo.uploaded_by = request.user
			photo.save()
			return redirect(f"{request.path}?family={family.id}")
	else:
		form = FamilyPhotoForm()

	photos = family.photos.select_related("uploaded_by")
	return render(
		request,
		"family_album.html",
		{"form": form, "photos": photos, "family": family, "families": families},
	)


@login_required
def messages(request):
	family, families = _get_current_family(request)
	if not family:
		return redirect("families")

	if request.method == "POST":
		form = MessageForm(request.POST)
		if form.is_valid():
			message = form.save(commit=False)
			message.family = family
			message.sender = request.user
			message.save()
			return redirect(f"{request.path}?family={family.id}")
	else:
		form = MessageForm()

	items = family.messages.select_related("sender")
	can_manage = _has_role(request.user, family, {"owner", "admin"})
	return render(
		request,
		"messages.html",
		{"form": form, "messages": items, "family": family, "families": families, "can_manage": can_manage},
	)


@login_required
def member_edit(request, member_id):
	member = get_object_or_404(FamilyMember, id=member_id)
	if not _has_family_access(request.user, member.family):
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
	if not _has_family_access(request.user, member.family):
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
def event_edit(request, event_id):
	event = get_object_or_404(Event, id=event_id)
	if not _has_family_access(request.user, event.family):
		return redirect("events")

	if request.method == "POST":
		form = EventForm(request.POST, instance=event, family=event.family)
		if form.is_valid():
			form.save()
			return redirect(f"/events/?family={event.family.id}")
	else:
		form = EventForm(instance=event, family=event.family)

	return render(
		request,
		"entity_form.html",
		{"form": form, "title": "Редактировать событие"},
	)


@login_required
def event_delete(request, event_id):
	event = get_object_or_404(Event, id=event_id)
	if not _has_family_access(request.user, event.family):
		return redirect("events")

	if request.method == "POST":
		family_id = event.family.id
		event.delete()
		return redirect(f"/events/?family={family_id}")

	return render(
		request,
		"confirm_delete.html",
		{"title": "Удалить событие", "object": event},
	)


@login_required
def task_edit(request, task_id):
	task = get_object_or_404(Task, id=task_id)
	if not _has_family_access(request.user, task.family):
		return redirect("tasks")

	if request.method == "POST":
		form = TaskForm(request.POST, instance=task, family=task.family)
		if form.is_valid():
			form.save()
			return redirect(f"/tasks/?family={task.family.id}")
	else:
		form = TaskForm(instance=task, family=task.family)

	return render(
		request,
		"entity_form.html",
		{"form": form, "title": "Редактировать задачу"},
	)


@login_required
def task_delete(request, task_id):
	task = get_object_or_404(Task, id=task_id)
	if not _has_family_access(request.user, task.family):
		return redirect("tasks")

	if request.method == "POST":
		family_id = task.family.id
		task.delete()
		return redirect(f"/tasks/?family={family_id}")

	return render(
		request,
		"confirm_delete.html",
		{"title": "Удалить задачу", "object": task},
	)


@login_required
def message_delete(request, message_id):
	message = get_object_or_404(Message, id=message_id)
	if not _has_family_access(request.user, message.family):
		return redirect("messages")

	if message.sender != request.user:
		membership = FamilyMembership.objects.filter(family=message.family, user=request.user).first()
		if not membership or membership.role not in {"owner", "admin"}:
			return redirect(f"/messages/?family={message.family.id}")

	if request.method == "POST":
		family_id = message.family.id
		message.delete()
		return redirect(f"/messages/?family={family_id}")

	return render(
		request,
		"confirm_delete.html",
		{"title": "Удалить сообщение", "object": message},
	)


# ---------------------------------------------------------------------------
# UI preferences (elder mode / theme)
# ---------------------------------------------------------------------------
def ui_set_pref(request):
	"""Toggle elder mode / theme stored in the session.

	Plain ``<form>`` submissions need to navigate back so the page re-renders
	with the new preferences applied; HTMX callers can still swap fragments by
	following the same redirect.
	Accepts POST with ``elder`` (1/0) and/or ``theme`` (light/dark/elder).
	"""
	if request.method != "POST":
		return HttpResponse(status=405)
	if "elder" in request.POST:
		request.session["elder_mode"] = request.POST.get("elder") in {"1", "true", "on"}
	if "theme" in request.POST:
		theme = request.POST.get("theme") or "light"
		if theme not in {"light", "dark", "elder"}:
			theme = "light"
		request.session["theme"] = theme
	request.session.modified = True
	return redirect(request.META.get("HTTP_REFERER", "/"))


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
			)
		)
	# Birth dates need to be JSON-serializable; ``json_script`` (used in the
	# template) handles HTML escaping for us — including stray ``</script>``
	# fragments embedded in user-controlled names.
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
		},
	)

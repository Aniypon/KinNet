"""Internal helpers shared across core view modules."""

from __future__ import annotations

import os
import re

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ..family_context import get_user_families
from ..models import AuditLog, Event, FamilyMember, FamilyPhoto
from ..permissions import get_membership
from ..services.family_tree import validate_family_tree  # noqa: F401 – re-exported


def has_family_access(user, family):
	return get_user_families(user).filter(id=family.id).exists()


def is_hx_request(request):
	return request.headers.get("HX-Request") == "true"


def quick_save_response(request, message="Сохранено"):
	if is_hx_request(request):
		return JsonResponse({"status": "ok", "message": message})
	return None


def quick_error_response(request, form):
	if is_hx_request(request):
		return JsonResponse({"status": "error", "errors": form.errors}, status=422)
	return None


def message_payload(message, request_user=None, can_manage=False):
	reactions = {}
	for reaction in message.reactions.all():
		bucket = reactions.setdefault(reaction.emoji, {"emoji": reaction.emoji, "count": 0, "mine": False})
		bucket["count"] += 1
		if request_user and reaction.user_id == request_user.id:
			bucket["mine"] = True

	reply = None
	if message.reply_to_id and message.reply_to:
		reply = {
			"id": message.reply_to_id,
			"sender": message.reply_to.sender.get_full_name() or message.reply_to.sender.username,
			"text": message.reply_to.text[:140],
		}

	return {
		"id": message.id,
		"sender_id": message.sender_id,
		"sender": message.sender.get_full_name() or message.sender.username,
		"sender_initial": (message.sender.get_full_name() or message.sender.username or "?")[:1].upper(),
		"text": message.text,
		"created_at": timezone.localtime(message.created_at).strftime("%d/%m/%Y %H:%M"),
		"is_pinned": message.is_pinned,
		"thread_type": message.thread_type,
		"thread_label": message.get_thread_type_display(),
		"attachment": message.attachment.url if message.attachment else "",
		"attachment_name": message.attachment_name or (message.attachment.name.rsplit("/", 1)[-1] if message.attachment else ""),
		"reply_to": reply,
		"reactions": list(reactions.values()),
		"can_delete": bool(request_user and (message.sender_id == request_user.id or can_manage)),
	}


def chat_typing_key(family_id):
	return f"family-chat-typing:{family_id}"


def active_typers(family, request_user):
	now = timezone.now().timestamp()
	typing = cache.get(chat_typing_key(family.id), {})
	active = {}
	for user_id, item in typing.items():
		if int(user_id) == request_user.id:
			continue
		if now - item.get("timestamp", 0) <= 6:
			active[user_id] = item
	cache.set(chat_typing_key(family.id), active, timeout=12)
	return [item["name"] for item in active.values()]


def audit(family, actor, action, entity_type, summary, entity_id="", payload=None):
	AuditLog.objects.create(
		family=family,
		actor=actor if actor and actor.is_authenticated else None,
		action=action,
		entity_type=entity_type,
		entity_id=str(entity_id or ""),
		summary=summary,
		payload=payload or {},
	)


def sync_birthday_events(user, birth_date):
	families = get_user_families(user)
	if birth_date:
		for family in families:
			membership = get_membership(user, family)
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
				defaults={"title": title, "date": birth_date, "recurrence": "yearly"},
			)
			if not created:
				updates = {}
				if event.date != birth_date:
					updates["date"] = birth_date
				if event.title != title:
					updates["title"] = title
				if event.recurrence != "yearly":
					updates["recurrence"] = "yearly"
				if updates:
					Event.objects.filter(id=event.id).update(**updates)
	else:
		Event.objects.filter(
			family__in=families,
			kind="birthday",
			member__user=user,
		).delete()


def build_tree_data(family, include_all=False):
	members = family.family_members.select_related("parent1", "parent2", "spouse", "user")
	if not include_all:
		members = members.filter(in_tree=True)
	return [
		{
			"id": member.id,
			"label": str(member),
			"first_name": member.first_name,
			"last_name": member.last_name,
			"middle_name": member.middle_name,
			"relation": member.relation,
			"birth_date": str(member.birth_date) if member.birth_date else "",
			"phone": member.phone,
			"email": member.email,
			"address_home": member.address_home,
			"address_country_house": member.address_country_house,
			"socials": member.socials,
			"workplace": member.workplace,
			"notes": member.notes,
			"parent1": member.parent1_id,
			"parent2": member.parent2_id,
			"spouse": member.spouse_id,
			"is_user": bool(member.user_id),
			"in_tree": member.in_tree,
			"display_order": member.display_order,
			"detail_url": f"/members/{member.id}/",
			"edit_url": f"/members/{member.id}/edit/",
			"delete_url": f"/members/{member.id}/delete/",
		}
		for member in members
	]


def get_family_photo_for_user(user, photo_id):
	photo = get_object_or_404(FamilyPhoto.objects.select_related("family"), id=photo_id)
	if not has_family_access(user, photo.family):
		return None
	return photo


def album_archive_path(photo, used_paths):
	folder = photo.event.title if photo.event_id else "Без привязки к событию"
	folder = re.sub(r'[\\/:*?"<>|]+', "_", folder).strip() or "Альбом"
	filename = os.path.basename(photo.image.name) or f"photo-{photo.id}"
	name, ext = os.path.splitext(filename)
	filename = re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or f"photo-{photo.id}"
	ext = re.sub(r'[\\/:*?"<>|]+', "", ext) or ".jpg"
	archive_path = f"{folder}/{filename}{ext}"
	index = 2
	while archive_path in used_paths:
		archive_path = f"{folder}/{filename}-{index}{ext}"
		index += 1
	used_paths.add(archive_path)
	return archive_path

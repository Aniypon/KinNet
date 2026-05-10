from __future__ import annotations

import os
import re

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from ..family_context import get_user_families
from ..models import AuditLog, Event, FamilyMember, FamilyPhoto
from ..permissions import get_membership
from ..services.family_tree import validate_family_tree  # noqa: F401

def has_family_access(user, family):
    return get_user_families(user).filter(id=family.id).exists()

def is_hx_request(request):
    return request.headers.get("HX-Request") == "true"

def quick_save_response(request, message="Сохранено"):
    return JsonResponse({"status": "ok", "message": message}) if is_hx_request(request) else None

def quick_error_response(request, form):
    return JsonResponse({"status": "error", "errors": form.errors}, status=422) if is_hx_request(request) else None

def message_payload(message, request_user=None, can_manage=False):
    reactions = {}
    for reaction in message.reactions.all():
        bucket = reactions.setdefault(reaction.emoji, {"emoji": reaction.emoji, "count": 0, "mine": False})
        bucket["count"] += 1
        if request_user and reaction.user_id == request_user.id:
            bucket["mine"] = True
    reply = None
    if message.reply_to_id and message.reply_to:
        reply = {"id": message.reply_to_id, "sender": message.reply_to.sender.get_full_name() or message.reply_to.sender.username, "text": message.reply_to.text[:140]}
    return {
        "id": message.id, "sender_id": message.sender_id,
        "sender": message.sender.get_full_name() or message.sender.username,
        "sender_initial": (message.sender.get_full_name() or message.sender.username or "?")[:1].upper(),
        "text": message.text, "created_at": timezone.localtime(message.created_at).strftime("%d/%m/%Y %H:%M"),
        "is_pinned": message.is_pinned, "thread_type": message.thread_type, "thread_label": message.get_thread_type_display(),
        "attachment": message.attachment.url if message.attachment else "",
        "attachment_name": message.attachment_name or (message.attachment.name.rsplit("/", 1)[-1] if message.attachment else ""),
        "reply_to": reply, "reactions": list(reactions.values()),
        "can_delete": bool(request_user and (message.sender_id == request_user.id or can_manage)),
    }

def chat_typing_key(family_id, user_id):
    return f"family-chat-typing:{family_id}:{user_id}"

def active_typers(family, request_user):
    now = timezone.now().timestamp()
    other_ids = [uid for uid in family.memberships.values_list("user_id", flat=True) if uid != request_user.id]
    if not other_ids: return []
    keys = {uid: chat_typing_key(family.id, uid) for uid in other_ids}
    cached = cache.get_many(list(keys.values()))
    return [item["name"] for uid, key in keys.items() if (item := cached.get(key)) and now - item.get("timestamp", 0) <= 6]

def audit(family, actor, action, entity_type, summary, entity_id="", payload=None):
    AuditLog.objects.create(family=family, actor=actor if actor and actor.is_authenticated else None, action=action, entity_type=entity_type, entity_id=str(entity_id or ""), summary=summary, payload=payload or {})

def sync_birthday_events(user, birth_date):
    from django.db import transaction
    families = list(get_user_families(user).select_related())
    if not birth_date:
        Event.objects.filter(family__in=families, kind="birthday", member__user=user).delete()
        return
    memberships = {m.family_id: m for m in user.family_memberships.filter(family__in=families)}
    for family in families:
        with transaction.atomic():
            membership = memberships.get(family.id)
            member, _ = FamilyMember.objects.select_for_update().get_or_create(
                family=family, user=user,
                defaults={"first_name": user.first_name or user.username, "last_name": user.last_name, "relation": "Участник", "display_order": membership.display_order if membership else 0},
            )
            title = f"День рождения {member}"
            event, created = Event.objects.select_for_update().get_or_create(family=family, member=member, kind="birthday", defaults={"title": title, "date": birth_date, "recurrence": "yearly"})
            if not created:
                updates = {k: v for k, v in [("date", birth_date), ("title", title), ("recurrence", "yearly")] if getattr(event, k) != v}
                if updates:
                    Event.objects.filter(id=event.id).update(**updates)

def build_tree_data(family, include_all=False):
    members = family.family_members.select_related("parent1", "parent2", "spouse", "user")
    if not include_all:
        members = members.filter(in_tree=True)
    return [
        {
            "id": m.id, "label": str(m), "first_name": m.first_name, "last_name": m.last_name,
            "middle_name": m.middle_name, "relation": m.relation,
            "birth_date": str(m.birth_date) if m.birth_date else "", "phone": m.phone,
            "email": m.email, "address_home": m.address_home, "address_country_house": m.address_country_house,
            "socials": m.socials, "workplace": m.workplace, "notes": m.notes,
            "parent1": m.parent1_id, "parent2": m.parent2_id, "spouse": m.spouse_id,
            "is_user": bool(m.user_id), "in_tree": m.in_tree, "display_order": m.display_order,
            "detail_url": reverse("member_detail", args=[m.id]),
            "edit_url": reverse("member_edit", args=[m.id]),
            "delete_url": reverse("member_delete", args=[m.id]),
        }
        for m in members
    ]

def get_family_photo_for_user(user, photo_id):
    photo = get_object_or_404(FamilyPhoto.objects.select_related("family"), id=photo_id)
    return photo if has_family_access(user, photo.family) else None

def album_archive_path(photo, used_paths):
    folder = re.sub(r'[\\/:*?"<>|]+', "_", photo.event.title if photo.event_id else "Без привязки к событию").strip() or "Альбом"
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

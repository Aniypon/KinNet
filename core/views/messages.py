"""Family chat: page view, JSON API endpoints, message delete."""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..family_context import current_family
from ..forms import MessageForm
from ..models import FamilyMembership, Message, MessageReaction, MessageReadState
from ..permissions import has_role
from ._helpers import (
	active_typers,
	audit,
	chat_typing_key,
	has_family_access,
	message_payload,
	quick_error_response,
	quick_save_response,
)


@login_required
def messages(request):
	family, families = current_family(request)
	if not family:
		return redirect("families")

	if request.method == "POST":
		form = MessageForm(request.POST)
		if form.is_valid():
			message = form.save(commit=False)
			message.family = family
			message.sender = request.user
			reply_to_id = request.POST.get("reply_to")
			if reply_to_id:
				message.reply_to = family.messages.filter(id=reply_to_id).first()
			message.save()
			quick_response = quick_save_response(request, "Сообщение отправлено")
			if quick_response:
				return quick_response
			return redirect(f"{request.path}?family={family.id}")
		quick_response = quick_error_response(request, form)
		if quick_response:
			return quick_response
	else:
		form = MessageForm()

	items = family.messages.select_related("sender", "reply_to", "reply_to__sender", "event", "task").prefetch_related("reactions").order_by("created_at")
	thread = request.GET.get("thread", "all")
	if thread != "all":
		if thread in {"general", "event", "task"}:
			items = items.filter(thread_type=thread)
		elif thread.startswith("event:"):
			items = items.filter(thread_type="event", event_id=thread.split(":", 1)[1])
		elif thread.startswith("task:"):
			items = items.filter(thread_type="task", task_id=thread.split(":", 1)[1])
	last_message = items.last()
	if last_message:
		MessageReadState.objects.update_or_create(
			family=family,
			user=request.user,
			defaults={"last_read_message": last_message},
		)
	pinned_messages = family.messages.filter(is_pinned=True).select_related("sender").order_by("-created_at")[:4]
	thread_events = family.events.order_by("date")[:12]
	thread_tasks = family.tasks.exclude(status="done").order_by("due_date", "created_at")[:12]
	can_manage = has_role(request.user, family, {"owner", "admin"})
	return render(
		request,
		"messages.html",
		{
			"form": form,
			"messages": items,
			"family": family,
			"families": families,
			"can_manage": can_manage,
			"pinned_messages": pinned_messages,
			"thread": thread,
			"thread_events": thread_events,
			"thread_tasks": thread_tasks,
		},
	)


@login_required
def messages_api(request):
	family, _families = current_family(request)
	if not family:
		return JsonResponse({"error": "Семья не найдена."}, status=404)
	if not has_family_access(request.user, family):
		return JsonResponse({"error": "Forbidden"}, status=403)
	can_manage = has_role(request.user, family, {"owner", "admin"})

	items = family.messages.select_related("sender", "reply_to", "reply_to__sender", "event", "task").prefetch_related("reactions").order_by("created_at")
	thread = request.GET.get("thread", "all")
	if thread != "all":
		if thread in {"general", "event", "task"}:
			items = items.filter(thread_type=thread)
		elif thread.startswith("event:"):
			items = items.filter(thread_type="event", event_id=thread.split(":", 1)[1])
		elif thread.startswith("task:"):
			items = items.filter(thread_type="task", task_id=thread.split(":", 1)[1])
	after_id = request.GET.get("after")
	if after_id and str(after_id).isdigit():
		items = items.filter(id__gt=int(after_id))
	items = list(items.order_by("-created_at")[:50])
	items.sort(key=lambda item: item.created_at)

	return JsonResponse(
		{
			"messages": [message_payload(message, request.user, can_manage) for message in items],
			"typing": active_typers(family, request.user),
		}
	)


@login_required
def message_send_api(request):
	if request.method != "POST":
		return JsonResponse({"error": "Method not allowed"}, status=405)
	family, _families = current_family(request)
	if not family:
		return JsonResponse({"error": "Семья не найдена."}, status=404)
	if not has_family_access(request.user, family):
		return JsonResponse({"error": "Forbidden"}, status=403)
	can_manage = has_role(request.user, family, {"owner", "admin"})

	if request.content_type and request.content_type.startswith("multipart/form-data"):
		payload = request.POST
	else:
		try:
			payload = json.loads(request.body.decode("utf-8"))
		except json.JSONDecodeError:
			payload = request.POST
	text = (payload.get("text") or "").strip()
	attachment = request.FILES.get("attachment")
	if not text and not attachment:
		return JsonResponse({"error": "Напишите сообщение или прикрепите файл."}, status=400)
	reply_to = None
	reply_to_id = payload.get("reply_to")
	if reply_to_id:
		reply_to = family.messages.filter(id=reply_to_id).first()
	thread_type = payload.get("thread_type") if payload.get("thread_type") in {"general", "event", "task"} else "general"
	event = family.events.filter(id=payload.get("event")).first() if thread_type == "event" and payload.get("event") else None
	task = family.tasks.filter(id=payload.get("task")).first() if thread_type == "task" and payload.get("task") else None
	message = Message.objects.create(
		family=family,
		sender=request.user,
		text=text,
		reply_to=reply_to,
		thread_type=thread_type,
		event=event,
		task=task,
		attachment=attachment or None,
		attachment_name=attachment.name if attachment else "",
	)
	audit(family, request.user, "chat", "Message", "Новое сообщение в семейном чате", message.id)
	return JsonResponse({"status": "ok", "message": message_payload(message, request.user, can_manage)})


@login_required
def message_pin_api(request):
	if request.method != "POST":
		return JsonResponse({"error": "Method not allowed"}, status=405)
	family, _families = current_family(request)
	if not family:
		return JsonResponse({"error": "Семья не найдена."}, status=404)
	if not has_family_access(request.user, family):
		return JsonResponse({"error": "Forbidden"}, status=403)

	payload = json.loads(request.body.decode("utf-8"))
	message = get_object_or_404(Message, id=payload.get("message"), family=family)
	message.is_pinned = not message.is_pinned
	message.save(update_fields=["is_pinned"])
	audit(family, request.user, "chat", "Message", "Закреп изменён", message.id, {"is_pinned": message.is_pinned})
	can_manage = has_role(request.user, family, {"owner", "admin"})
	return JsonResponse({"status": "ok", "message": message_payload(message, request.user, can_manage)})


@login_required
def message_reaction_api(request):
	if request.method != "POST":
		return JsonResponse({"error": "Method not allowed"}, status=405)
	family, _families = current_family(request)
	if not family:
		return JsonResponse({"error": "Семья не найдена."}, status=404)
	if not has_family_access(request.user, family):
		return JsonResponse({"error": "Forbidden"}, status=403)
	can_manage = has_role(request.user, family, {"owner", "admin"})

	payload = json.loads(request.body.decode("utf-8"))
	message = get_object_or_404(Message, id=payload.get("message"), family=family)
	emoji = (payload.get("emoji") or "").strip()[:12]
	if emoji not in {"❤️", "👍", "😂", "🙏"}:
		return JsonResponse({"error": "Неизвестная реакция."}, status=400)
	reaction = MessageReaction.objects.filter(message=message, user=request.user, emoji=emoji).first()
	if reaction:
		reaction.delete()
	else:
		MessageReaction.objects.create(message=message, user=request.user, emoji=emoji)
	message = family.messages.select_related("sender", "reply_to", "reply_to__sender").prefetch_related("reactions").get(id=message.id)
	return JsonResponse({"status": "ok", "message": message_payload(message, request.user, can_manage)})


@login_required
def message_typing_api(request):
	if request.method != "POST":
		return JsonResponse({"error": "Method not allowed"}, status=405)
	family, _families = current_family(request)
	if not family:
		return JsonResponse({"error": "Семья не найдена."}, status=404)
	if not has_family_access(request.user, family):
		return JsonResponse({"error": "Forbidden"}, status=403)

	from django.utils import timezone

	payload = json.loads(request.body.decode("utf-8"))
	typing = cache.get(chat_typing_key(family.id), {})
	user_key = str(request.user.id)
	if payload.get("typing"):
		typing[user_key] = {
			"name": request.user.get_full_name() or request.user.username,
			"timestamp": timezone.now().timestamp(),
		}
	else:
		typing.pop(user_key, None)
	cache.set(chat_typing_key(family.id), typing, timeout=12)
	return JsonResponse({"status": "ok", "typing": active_typers(family, request.user)})


@login_required
def message_delete(request, message_id):
	message = get_object_or_404(Message, id=message_id)
	if not has_family_access(request.user, message.family):
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

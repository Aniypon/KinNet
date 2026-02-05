"""Event listing/CRUD."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..family_context import current_family
from ..forms import EventCommentForm, EventForm
from ..models import Event
from ..permissions import has_role
from ..utils import get_next_event_date
from ._helpers import has_family_access, quick_error_response, quick_save_response


@login_required
def events(request):
	family, families = current_family(request)
	if not family:
		return redirect("families")

	if request.method == "POST":
		form = EventForm(request.POST, family=family)
		if form.is_valid():
			event = form.save(commit=False)
			event.family = family
			event.save()
			quick_response = quick_save_response(request, "Событие добавлено")
			if quick_response:
				return quick_response
			return redirect(f"{request.path}?family={family.id}")
		quick_response = quick_error_response(request, form)
		if quick_response:
			return quick_response
	else:
		form = EventForm(family=family)

	items = family.events.select_related("member")
	query = request.GET.get("q", "").strip()
	kind = request.GET.get("kind", "").strip()
	if query:
		items = items.filter(title__icontains=query)
	if kind:
		items = items.filter(kind=kind)
	today = timezone.localdate()
	items = list(items)
	for item in items:
		item.next_date = get_next_event_date(item, today)
	items.sort(key=lambda item: (item.next_date or item.date, item.title))
	can_manage = has_role(request.user, family, {"owner", "admin"})
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
	if not has_family_access(request.user, event.family):
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
def event_edit(request, event_id):
	event = get_object_or_404(Event, id=event_id)
	if not has_family_access(request.user, event.family):
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
	if not has_family_access(request.user, event.family):
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

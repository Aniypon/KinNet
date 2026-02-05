"""Task listing/CRUD + detail (checklist, contributions, comments)."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from ..family_context import current_family, get_user_families
from ..forms import TaskChecklistItemForm, TaskCommentForm, TaskContributionForm, TaskForm
from ..models import Task, TaskChecklistItem
from ..permissions import has_role
from ._helpers import has_family_access, quick_error_response, quick_save_response


@login_required
def tasks(request):
	family, families = current_family(request)
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
			quick_response = quick_save_response(request, "Задача добавлена")
			if quick_response:
				return quick_response
			return redirect(f"{request.path}?family={family.id}")
		quick_response = quick_error_response(request, form)
		if quick_response:
			return quick_response
	else:
		form = TaskForm(family=family)

	items = family.tasks.select_related("assignee")
	query = request.GET.get("q", "").strip()
	status = request.GET.get("status", "").strip()
	if query:
		items = items.filter(title__icontains=query)
	if status:
		items = items.filter(status=status)
	can_manage = has_role(request.user, family, {"owner", "admin"})
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
	families = get_user_families(request.user)
	if not families.filter(id=family.id).exists():
		return redirect("tasks")
	can_manage = has_role(request.user, family, {"owner", "admin"})

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
def task_edit(request, task_id):
	task = get_object_or_404(Task, id=task_id)
	if not has_family_access(request.user, task.family):
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
		{"form": form, "title": "Редактировать задачу", "delete_url": f"/tasks/{task.id}/delete/", "delete_label": "Удалить задачу"},
	)


@login_required
def task_delete(request, task_id):
	task = get_object_or_404(Task, id=task_id)
	if not has_family_access(request.user, task.family):
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

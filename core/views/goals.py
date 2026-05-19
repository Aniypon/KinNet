"""Financial goals listing/detail."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..family_context import current_family
from ..forms import GoalContributionForm, GoalForm
from ..models import Goal, GoalContribution
from ..permissions import has_role
from ._helpers import has_family_access, quick_error_response, quick_save_response


@login_required
def goals(request):
	family, families = current_family(request)
	if not family:
		return redirect("families")

	if request.method == "POST":
		form = GoalForm(request.POST)
		if form.is_valid():
			goal = form.save(commit=False)
			goal.family = family
			goal.created_by = request.user
			goal.save()
			quick_response = quick_save_response(request, "Цель добавлена")
			if quick_response:
				return quick_response
			return redirect(f"{request.path}?family={family.id}")
		quick_response = quick_error_response(request, form)
		if quick_response:
			return quick_response
	else:
		form = GoalForm()

	today = timezone.localdate()
	all_goals = list(family.goals.prefetch_related("contributions").all())
	active_goals = []
	done_goals = []
	total_target = Decimal("0")
	total_collected = Decimal("0")
	for goal in all_goals:
		target = goal.target_amount or Decimal("0")
		collected = sum((c.amount for c in goal.contributions.all()), Decimal("0"))
		goal.collected = collected
		goal.remaining = max(target - collected, Decimal("0"))
		goal.pct = int(min(collected / target * 100, 100)) if target > 0 else 0
		goal.is_done = target > 0 and collected >= target
		goal.contributors_count = len({c.user_id for c in goal.contributions.all()})
		if goal.due_date:
			delta = (goal.due_date - today).days
			goal.days_left = delta
			goal.is_overdue = delta < 0 and not goal.is_done
		else:
			goal.days_left = None
			goal.is_overdue = False
		total_target += target
		total_collected += collected
		(done_goals if goal.is_done else active_goals).append(goal)

	active_goals.sort(key=lambda g: (g.due_date is None, g.due_date or today, -g.pct))

	overall_pct = int(min(total_collected / total_target * 100, 100)) if total_target > 0 else 0

	return render(
		request,
		"goals.html",
		{
			"form": form,
			"active_goals": active_goals,
			"done_goals": done_goals,
			"family": family,
			"families": families,
			"total_target": total_target,
			"total_collected": total_collected,
			"overall_pct": overall_pct,
			"active_count": len(active_goals),
			"done_count": len(done_goals),
		},
	)


@login_required
def goal_detail(request, goal_id):
	goal = get_object_or_404(Goal, id=goal_id)
	if not has_family_access(request.user, goal.family):
		return redirect("goals")

	contribution_form = GoalContributionForm(prefix="contrib", family=goal.family)
	can_manage_family = has_role(request.user, goal.family, {"owner", "admin"})

	if request.method == "POST":
		if "contrib-delete" in request.POST:
			contribution = get_object_or_404(GoalContribution, id=request.POST["contrib-delete"], goal=goal)
			if contribution.user_id == request.user.id or can_manage_family:
				contribution.delete()
			return redirect("goal_detail", goal_id=goal.id)
		if "contrib-edit" in request.POST:
			contribution = get_object_or_404(GoalContribution, id=request.POST["contrib-edit"], goal=goal)
			if contribution.user_id == request.user.id or can_manage_family:
				try:
					amount = Decimal(request.POST.get("amount", "").replace(",", "."))
				except (InvalidOperation, ArithmeticError):
					amount = None
				if amount is not None and amount > 0:
					contribution.amount = amount
					contribution.comment = request.POST.get("comment", "").strip()[:255]
					contribution.save()
			return redirect("goal_detail", goal_id=goal.id)
		if "contrib-user" in request.POST:
			contribution_form = GoalContributionForm(request.POST, prefix="contrib", family=goal.family)
			if contribution_form.is_valid():
				contribution = contribution_form.save(commit=False)
				contribution.goal = goal
				contribution.save()
				return redirect("goal_detail", goal_id=goal.id)

	total = goal.contributions.aggregate(total=Sum("amount")).get("total") or 0

	return render(
		request,
		"goal_detail.html",
		{
			"goal": goal,
			"contribution_form": contribution_form,
			"total": total,
			"can_manage_family": can_manage_family,
		},
	)

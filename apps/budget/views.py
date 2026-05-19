from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.family_context import current_family as _current_family, get_user_families as _user_families
from core.models import FamilyMember
from .models import Expense, ExpenseContribution, Wishlist, WishlistItem

User = get_user_model()

def _family_user_choices(family):
    if not family: return []
    return list(User.objects.filter(family_memberships__family=family).distinct().order_by("first_name", "username"))

def _apply_contributions(expense, mode, rows):
    ExpenseContribution.objects.filter(expense=expense).delete()
    if mode != "multi" or not rows:
        return
    valid_ids = set(User.objects.filter(id__in=[r[0] for r in rows], family_memberships__family=expense.family).distinct().values_list("id", flat=True))
    objs = [ExpenseContribution(expense=expense, contributor_id=uid, amount=amount) for uid, amount in rows if uid in valid_ids and amount > 0]
    if objs:
        ExpenseContribution.objects.bulk_create(objs)

def _parse_contribution_rows(request):
    rows = []
    for raw_id, raw_amount in zip(request.POST.getlist("contributor"), request.POST.getlist("contribution_amount")):
        if not raw_id or not raw_id.isdigit():
            continue
        try:
            amount = Decimal(raw_amount or "0")
        except InvalidOperation:
            continue
        rows.append((int(raw_id), amount))
    return rows

def _family_url(name, family):
    url = reverse(name)
    return f"{url}?family={family.id}" if family else url

def _parse_user_date(value):
    value = (value or "").strip()
    if not value: return timezone.localdate()
    if d := parse_date(value): return d
    for fmt in ("%d/%m/%Y", "%d.%m.%Y"):
        try: return datetime.strptime(value, fmt).date()
        except ValueError: pass
    return timezone.localdate()

def _can_manage_wishlist(user, wishlist):
    return wishlist.owner_member.user_id == user.id or (wishlist.owner_member.user_id is None and wishlist.created_by_id == user.id)

def _current_user_member(family, user):
    with transaction.atomic():
        membership = family.memberships.select_for_update().filter(user=user).first()
        member, _ = FamilyMember.objects.get_or_create(family=family, user=user, defaults={"first_name": user.first_name or user.username, "last_name": user.last_name, "relation": "Участник", "display_order": membership.display_order if membership else family.family_members.count()})
    return member

PERIOD_CHOICES = (("month", "Этот месяц"), ("prev", "Прошлый месяц"), ("3m", "3 месяца"), ("year", "Год"), ("all", "Всё время"))

def _period_range(period):
    today = timezone.localdate()
    first = today.replace(day=1)
    if period == "prev":
        prev_last = first - timezone.timedelta(days=1)
        return prev_last.replace(day=1), first, "Прошлый месяц"
    if period == "3m":
        m = first
        for _ in range(2):
            m = (m - timezone.timedelta(days=1)).replace(day=1)
        return m, None, "Последние 3 месяца"
    if period == "year": return first.replace(month=1), None, "С начала года"
    if period == "all": return None, None, "Всё время"
    return first, None, "Этот месяц"

def _prev_period_range(period):
    if period not in ("month", "prev"):
        return None
    start_cur, _, _ = _period_range(period)
    if start_cur is None:
        return None
    prev_end = start_cur
    return (prev_end - timezone.timedelta(days=1)).replace(day=1), prev_end

@login_required
def expense_list(request):
    family, families = _current_family(request)
    period = request.GET.get("period", "month")
    if period not in {k for k, _ in PERIOD_CHOICES}:
        period = "month"
    start, end, period_label = _period_range(period)
    base_qs = Expense.objects.filter(family=family).select_related("family", "payer") if family else Expense.objects.none()
    period_qs = base_qs
    if start is not None:
        period_qs = period_qs.filter(spent_on__gte=start)
    if end is not None:
        period_qs = period_qs.filter(spent_on__lt=end)

    agg = period_qs.aggregate(t=Sum("amount"), n=Count("id"))
    period_total = agg["t"] or Decimal("0")
    period_count = agg["n"] or 0
    period_avg = (period_total / period_count) if period_count else Decimal("0")
    prev_range = _prev_period_range(period)
    delta_pct = prev_total = None
    if prev_range:
        prev_total = base_qs.filter(spent_on__gte=prev_range[0], spent_on__lt=prev_range[1]).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        if prev_total and prev_total > 0:
            delta_pct = float((period_total - prev_total) / prev_total * 100)
    delta_arrow = "▼" if (delta_pct is not None and delta_pct < 0) else "▲"
    by_category = [
        {"label": row["category"] or "Без категории", "total": row["total"], "pct": round(float(row["total"] / period_total * 100), 1) if period_total else 0}
        for row in period_qs.values("category").annotate(total=Sum("amount")).order_by("-total")
    ]
    top_category = by_category[0]["label"] if by_category else None
    with_contribs_subq = ExpenseContribution.objects.filter(expense__in=period_qs).values("expense_id")
    payers_map: dict = {}
    for row in period_qs.exclude(id__in=with_contribs_subq).filter(payer__isnull=False).values("payer_id", "payer__first_name", "payer__last_name", "payer__username").annotate(total=Sum("amount"), n=Count("id")):
        payers_map[row["payer_id"]] = {"fn": row["payer__first_name"], "ln": row["payer__last_name"], "un": row["payer__username"], "total": row["total"] or Decimal("0"), "n": row["n"]}
    for row in ExpenseContribution.objects.filter(expense__in=period_qs, contributor__isnull=False).values("contributor_id", "contributor__first_name", "contributor__last_name", "contributor__username").annotate(total=Sum("amount"), n=Count("expense_id", distinct=True)):
        uid = row["contributor_id"]
        if uid in payers_map:
            payers_map[uid]["total"] += row["total"] or Decimal("0")
            payers_map[uid]["n"] += row["n"]
        else:
            payers_map[uid] = {"fn": row["contributor__first_name"], "ln": row["contributor__last_name"], "un": row["contributor__username"], "total": row["total"] or Decimal("0"), "n": row["n"]}
    by_payer = sorted(
        [{"payer__first_name": v["fn"], "payer__last_name": v["ln"], "payer__username": v["un"], "total": v["total"], "n": v["n"]} for v in payers_map.values()],
        key=lambda r: r["total"], reverse=True,
    )
    return render(request, "budget/expense_list.html", {
        "expenses": list(period_qs.order_by("-spent_on", "-created_at")[:30]),
        "families": families, "family": family, "period": period, "period_label": period_label,
        "period_choices": PERIOD_CHOICES, "period_total": period_total, "period_count": period_count,
        "period_avg": period_avg, "prev_total": prev_total, "delta_pct": delta_pct, "delta_arrow": delta_arrow,
        "by_category": by_category, "by_payer": by_payer, "top_category": top_category,
    })

def _resolve_payer(request, family):
    payer_id = request.POST.get("payer")
    if payer_id and payer_id.isdigit():
        payer = User.objects.filter(id=int(payer_id), family_memberships__family=family).first()
        if payer:
            return payer
    return request.user

@login_required
def expense_create(request):
    family, families = _current_family(request)
    if not family: return redirect("families")
    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except InvalidOperation:
            amount = Decimal("0")
        if amount <= 0:
            amount = Decimal("0")
        with transaction.atomic():
            expense = Expense.objects.create(
                family=family, payer=_resolve_payer(request, family),
                title=request.POST.get("title", "Расход"), amount=amount,
                category=request.POST.get("category", ""),
                spent_on=_parse_user_date(request.POST.get("spent_on", "")),
                notes=request.POST.get("notes", ""),
            )
            mode = request.POST.get("payer_mode", "single")
            _apply_contributions(expense, mode, _parse_contribution_rows(request) if mode == "multi" else [])
        if request.headers.get("HX-Request"):
            return render(request, "budget/_expense_row.html", {"expense": expense})
        return redirect(_family_url("budget:expense_list", family))
    return render(request, "budget/expense_form.html", {"families": families, "family": family, "page_title": "Новый расход", "payer_choices": _family_user_choices(family)})

@login_required
def expense_update(request, expense_id: int):
    expense = get_object_or_404(Expense.objects.filter(family__in=_user_families(request.user)), pk=expense_id)
    family = expense.family
    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except InvalidOperation:
            amount = expense.amount
        with transaction.atomic():
            expense.title = request.POST.get("title", expense.title).strip() or expense.title
            expense.amount = amount
            expense.category = request.POST.get("category", expense.category)
            expense.spent_on = _parse_user_date(request.POST.get("spent_on", "")) or expense.spent_on
            expense.notes = request.POST.get("notes", "")
            expense.payer = _resolve_payer(request, family)
            expense.save()
            mode = request.POST.get("payer_mode", "single")
            _apply_contributions(expense, mode, _parse_contribution_rows(request) if mode == "multi" else [])
        return redirect(_family_url("budget:expense_list", family))
    contribs = list(expense.contributions.values("contributor_id", "amount").order_by("created_at"))
    current_rows = [{"id": c["contributor_id"], "amount": str(c["amount"])} for c in contribs if c["contributor_id"]]
    return render(request, "budget/expense_form.html", {
        "families": list(_user_families(request.user)), "family": family, "page_title": "Изменить расход",
        "expense": expense, "payer_choices": _family_user_choices(family),
        "current_rows": current_rows, "current_mode": "multi" if current_rows else "single",
    })

@login_required
def expense_delete(request, expense_id: int):
    expense = get_object_or_404(Expense.objects.filter(family__in=_user_families(request.user)), pk=expense_id)
    if request.method != "POST":
        return render(request, "budget/confirm_delete.html", {"object": expense, "family": expense.family})
    expense.delete()
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect(_family_url("budget:expense_list", expense.family))

@login_required
def expense_contribution_add(request, expense_id: int):
    expense = get_object_or_404(Expense.objects.filter(family__in=_user_families(request.user)), pk=expense_id)
    if request.method == "POST":
        if not _user_families(request.user).filter(id=expense.family_id).exists():
            return HttpResponseForbidden("Недостаточно прав.")
        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except InvalidOperation:
            amount = Decimal("0")
        if amount > 0:
            ExpenseContribution.objects.create(expense=expense, contributor=request.user, amount=amount, note=request.POST.get("note", "").strip())
    return redirect(_family_url("budget:expense_list", expense.family))

@login_required
def wishlist_index(request):
    family, families = _current_family(request)
    if not family: return redirect("families")
    wishlists = Wishlist.objects.filter(family=family).select_related("owner_member", "created_by").prefetch_related("items")
    members = family.family_members.filter(wishlists__isnull=False).distinct()
    my_member = FamilyMember.objects.filter(family=family, user=request.user).first()
    wish_member = request.GET.get("wish_member", "")
    wish_query = request.GET.get("wish_q", "").strip()
    if wish_member and str(wish_member).isdigit():
        wishlists = wishlists.filter(owner_member_id=int(wish_member))
    if wish_query:
        wishlists = wishlists.filter(Q(owner_member__first_name__icontains=wish_query) | Q(owner_member__last_name__icontains=wish_query) | Q(title__icontains=wish_query))
    wishlists = list(wishlists)
    my_member_id = my_member.id if my_member else None
    for wl in wishlists:
        wl.can_manage = _can_manage_wishlist(request.user, wl)
        wl.is_mine = my_member_id is not None and wl.owner_member_id == my_member_id
    return render(request, "budget/wishlist_index.html", {
        "family": family, "families": families, "members": members, "my_member": my_member,
        "wishlists": wishlists, "wish_member": wish_member, "wish_query": wish_query,
    })

@login_required
def wishlist_create(request):
    family, families = _current_family(request)
    if not family: return redirect("families")
    member = _current_user_member(family, request.user)
    if request.method == "POST":
        wishlist = Wishlist.objects.create(family=member.family, owner_member=member, created_by=request.user, title=request.POST.get("title", "").strip() or "Мой список желаний")
        return redirect(_family_url("budget:wishlist_index", wishlist.family))
    return render(request, "budget/wishlist_form.html", {"family": family, "families": families, "page_title": "Новый список желаний"})

@login_required
def wishlist_update(request, wishlist_id: int):
    wishlist = get_object_or_404(Wishlist.objects.select_related("family", "owner_member").filter(family__in=_user_families(request.user)), pk=wishlist_id)
    if not _can_manage_wishlist(request.user, wishlist):
        return HttpResponseForbidden("Недостаточно прав.")
    if request.method == "POST":
        wishlist.title = request.POST.get("title", "").strip() or "Список желаний"
        wishlist.save(update_fields=["title"])
        return redirect(_family_url("budget:wishlist_index", wishlist.family))
    return render(request, "budget/wishlist_form.html", {"wishlist": wishlist, "family": wishlist.family, "page_title": "Изменить список желаний"})

@login_required
def wishlist_delete(request, wishlist_id: int):
    wishlist = get_object_or_404(Wishlist.objects.select_related("family", "owner_member").filter(family__in=_user_families(request.user)), pk=wishlist_id)
    if not _can_manage_wishlist(request.user, wishlist):
        return HttpResponseForbidden("Недостаточно прав.")
    if request.method == "POST":
        wishlist.delete()
    return redirect(f"{reverse('budget:wishlist_index')}?family={wishlist.family_id}")

@login_required
def wishlist_item_add(request, wishlist_id: int):
    wishlist = get_object_or_404(Wishlist.objects.filter(family__in=_user_families(request.user)), pk=wishlist_id)
    if request.method == "POST":
        if not _can_manage_wishlist(request.user, wishlist):
            return HttpResponseForbidden("Добавлять желания можно только в свой список.")
        price = None
        try:
            if request.POST.get("price_estimate"):
                price = Decimal(request.POST["price_estimate"])
        except InvalidOperation:
            pass
        raw_url = request.POST.get("url", "").strip()
        WishlistItem.objects.create(
            wishlist=wishlist, title=request.POST.get("title", "Желание"),
            description=request.POST.get("description", ""),
            url=raw_url if raw_url.startswith("https://") else "",
            price_estimate=price, share_with_family=True,
        )
    return redirect(_family_url("budget:wishlist_index", wishlist.family))

@login_required
def wishlist_item_reserve(request, item_id: int):
    if request.method != "POST":
        item = get_object_or_404(WishlistItem.objects.select_related("wishlist__family"), pk=item_id, wishlist__family__in=_user_families(request.user))
        return redirect(_family_url("budget:wishlist_index", item.wishlist.family))
    with transaction.atomic():
        item = get_object_or_404(WishlistItem.objects.select_related("wishlist__owner_member").select_for_update().filter(wishlist__family__in=_user_families(request.user)), pk=item_id)
        if _can_manage_wishlist(request.user, item.wishlist):
            return HttpResponseForbidden("Нельзя бронировать собственные желания.")
        if item.reserved_by_id and item.reserved_by_id != request.user.id:
            return redirect(_family_url("budget:wishlist_index", item.wishlist.family))
        if item.reserved_by_id == request.user.id:
            item.reserved_by = None
            item.reserved_at = None
        else:
            item.reserved_by = request.user
            item.reserved_at = timezone.now()
        item.save(update_fields=["reserved_by", "reserved_at"])
    return redirect(_family_url("budget:wishlist_index", item.wishlist.family))

@login_required
def wishlist_item_update(request, item_id: int):
    item = get_object_or_404(WishlistItem.objects.select_related("wishlist", "wishlist__family", "wishlist__owner_member").filter(wishlist__family__in=_user_families(request.user)), pk=item_id)
    if not _can_manage_wishlist(request.user, item.wishlist):
        return HttpResponseForbidden("Недостаточно прав.")
    if request.method == "POST":
        item.title = request.POST.get("title", "").strip() or item.title
        item.description = request.POST.get("description", "").strip()
        raw_url = request.POST.get("url", "").strip()
        item.url = raw_url if raw_url.startswith("https://") else ""
        try:
            item.price_estimate = Decimal(request.POST["price_estimate"]) if request.POST.get("price_estimate") else None
        except InvalidOperation:
            item.price_estimate = None
        item.save(update_fields=["title", "description", "url", "price_estimate"])
    return redirect(_family_url("budget:wishlist_index", item.wishlist.family))

@login_required
def wishlist_item_delete(request, item_id: int):
    item = get_object_or_404(WishlistItem.objects.select_related("wishlist", "wishlist__family", "wishlist__owner_member").filter(wishlist__family__in=_user_families(request.user)), pk=item_id)
    if not _can_manage_wishlist(request.user, item.wishlist):
        return HttpResponseForbidden("Недостаточно прав.")
    if request.method == "POST":
        item.delete()
    return redirect(_family_url("budget:wishlist_index", item.wishlist.family))

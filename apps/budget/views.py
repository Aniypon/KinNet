"""Budget + wishlist views."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from django.contrib.auth import get_user_model

from core.family_context import current_family as _current_family, get_user_families as _user_families
from core.models import Family, FamilyMember

User = get_user_model()


def _family_user_choices(family):
    if not family:
        return []
    return list(
        User.objects.filter(family_memberships__family=family).distinct().order_by("first_name", "username")
    )


def _apply_contributions(expense, mode: str, rows: list[tuple[int, Decimal]]):
    """Replace contributions on expense. rows = [(user_id, amount), ...]."""
    ExpenseContribution.objects.filter(expense=expense).delete()
    if mode != "multi" or not rows:
        return
    valid_ids = set(
        User.objects.filter(
            id__in=[r[0] for r in rows],
            family_memberships__family=expense.family,
        )
        .distinct()
        .values_list("id", flat=True)
    )
    for uid, amount in rows:
        if uid not in valid_ids or amount <= 0:
            continue
        ExpenseContribution.objects.create(
            expense=expense,
            contributor_id=uid,
            amount=amount,
        )


def _parse_contribution_rows(request) -> list[tuple[int, Decimal]]:
    ids = request.POST.getlist("contributor")
    amounts = request.POST.getlist("contribution_amount")
    rows: list[tuple[int, Decimal]] = []
    for raw_id, raw_amount in zip(ids, amounts):
        if not raw_id or not raw_id.isdigit():
            continue
        try:
            amount = Decimal(raw_amount or "0")
        except InvalidOperation:
            continue
        rows.append((int(raw_id), amount))
    return rows

from .models import Expense, ExpenseContribution, Wishlist, WishlistItem


def _family_url(name, family):
    url = reverse(name)
    if family:
        return f"{url}?family={family.id}"
    return url


def _parse_user_date(value):
    value = (value or "").strip()
    if not value:
        return timezone.localdate()
    parsed = parse_date(value)
    if parsed:
        return parsed
    for fmt in ("%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return timezone.localdate()


def _can_manage_wishlist(user, wishlist):
    if wishlist.owner_member.user_id == user.id:
        return True
    return wishlist.owner_member.user_id is None and wishlist.created_by_id == user.id


def _current_user_member(family, user):
    membership = family.memberships.filter(user=user).first()
    member = FamilyMember.objects.filter(family=family, user=user).first()
    if member is None:
        member = FamilyMember.objects.create(
            family=family,
            user=user,
            first_name=user.first_name or user.username,
            last_name=user.last_name,
            relation="Участник",
            display_order=membership.display_order if membership else family.family_members.count(),
        )
    return member


PERIOD_CHOICES = (
    ("month", "Этот месяц"),
    ("prev", "Прошлый месяц"),
    ("3m", "3 месяца"),
    ("year", "Год"),
    ("all", "Всё время"),
)


def _period_range(period: str):
    """Return (start_date, end_date_exclusive, label) for period key. None bounds = open."""
    today = timezone.localdate()
    first_of_month = today.replace(day=1)
    if period == "prev":
        end = first_of_month
        # first of previous month
        prev_last = first_of_month - timezone.timedelta(days=1)
        start = prev_last.replace(day=1)
        return start, end, "Прошлый месяц"
    if period == "3m":
        # last 3 full months including current
        month = first_of_month
        for _ in range(2):
            month = (month - timezone.timedelta(days=1)).replace(day=1)
        return month, None, "Последние 3 месяца"
    if period == "year":
        return first_of_month.replace(month=1), None, "С начала года"
    if period == "all":
        return None, None, "Всё время"
    return first_of_month, None, "Этот месяц"


def _prev_period_range(period: str):
    """Range immediately before current `period`, for delta comparison. Returns (start, end) or None."""
    today = timezone.localdate()
    first_of_month = today.replace(day=1)
    if period in ("month", "prev"):
        # compare to month before the current/prev month
        target_end = first_of_month if period == "month" else first_of_month.replace(day=1)
        # naive: previous full month before start of current period
        start_cur, _end, _ = _period_range(period)
        if start_cur is None:
            return None
        prev_end = start_cur
        prev_last = prev_end - timezone.timedelta(days=1)
        prev_start = prev_last.replace(day=1)
        return prev_start, prev_end
    return None


@login_required
def expense_list(request):
    family, families = _current_family(request)
    period = request.GET.get("period", "month")
    if period not in {k for k, _ in PERIOD_CHOICES}:
        period = "month"
    start, end, period_label = _period_range(period)

    base_qs = (
        Expense.objects.filter(family=family)
        .select_related("family", "payer")
        if family
        else Expense.objects.none()
    )
    period_qs = base_qs
    if start is not None:
        period_qs = period_qs.filter(spent_on__gte=start)
    if end is not None:
        period_qs = period_qs.filter(spent_on__lt=end)

    period_total = period_qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")
    period_count = period_qs.count()
    period_avg = (period_total / period_count) if period_count else Decimal("0")

    # delta vs previous comparable period
    prev_range = _prev_period_range(period)
    delta_pct = None
    prev_total = None
    if prev_range:
        prev_total = (
            base_qs.filter(spent_on__gte=prev_range[0], spent_on__lt=prev_range[1])
            .aggregate(t=Sum("amount"))["t"]
            or Decimal("0")
        )
        if prev_total and prev_total > 0:
            delta_pct = float((period_total - prev_total) / prev_total * 100)
    delta_arrow = "▼" if (delta_pct is not None and delta_pct < 0) else "▲"

    # category breakdown with percentages
    by_category_raw = (
        period_qs.values("category")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    by_category = []
    for row in by_category_raw:
        share = float(row["total"] / period_total * 100) if period_total else 0
        by_category.append(
            {
                "label": row["category"] or "Без категории",
                "total": row["total"],
                "pct": round(share, 1),
            }
        )
    top_category = by_category[0]["label"] if by_category else None

    # "Кто платил": combine single-payer expenses (no contributions) with per-contributor amounts.
    period_ids = list(period_qs.values_list("id", flat=True))
    expenses_with_contribs = set(
        ExpenseContribution.objects.filter(expense_id__in=period_ids)
        .values_list("expense_id", flat=True)
        .distinct()
    )
    single_qs = period_qs.exclude(id__in=expenses_with_contribs).filter(payer__isnull=False)
    payers_map: dict[int, dict] = {}
    for row in single_qs.values(
        "payer_id", "payer__first_name", "payer__last_name", "payer__username"
    ).annotate(total=Sum("amount"), n=Count("id")):
        payers_map[row["payer_id"]] = {
            "first_name": row["payer__first_name"],
            "last_name": row["payer__last_name"],
            "username": row["payer__username"],
            "total": row["total"] or Decimal("0"),
            "n": row["n"],
        }
    contrib_rows = (
        ExpenseContribution.objects.filter(
            expense_id__in=period_ids, contributor__isnull=False
        )
        .values(
            "contributor_id",
            "contributor__first_name",
            "contributor__last_name",
            "contributor__username",
        )
        .annotate(total=Sum("amount"), n=Count("expense_id", distinct=True))
    )
    for row in contrib_rows:
        uid = row["contributor_id"]
        existing = payers_map.get(uid)
        if existing:
            existing["total"] += row["total"] or Decimal("0")
            existing["n"] += row["n"]
        else:
            payers_map[uid] = {
                "first_name": row["contributor__first_name"],
                "last_name": row["contributor__last_name"],
                "username": row["contributor__username"],
                "total": row["total"] or Decimal("0"),
                "n": row["n"],
            }
    by_payer = sorted(
        (
            {
                "payer__first_name": v["first_name"],
                "payer__last_name": v["last_name"],
                "payer__username": v["username"],
                "total": v["total"],
                "n": v["n"],
            }
            for v in payers_map.values()
        ),
        key=lambda r: r["total"],
        reverse=True,
    )

    recent_expenses = list(period_qs.order_by("-spent_on", "-created_at")[:30])

    return render(
        request,
        "budget/expense_list.html",
        {
            "expenses": recent_expenses,
            "families": families,
            "family": family,
            "period": period,
            "period_label": period_label,
            "period_choices": PERIOD_CHOICES,
            "period_total": period_total,
            "period_count": period_count,
            "period_avg": period_avg,
            "prev_total": prev_total,
            "delta_pct": delta_pct,
            "delta_arrow": delta_arrow,
            "by_category": by_category,
            "by_payer": by_payer,
            "top_category": top_category,
        },
    )


def _resolve_payer(request, family):
    """Pick payer from POST (validated against family) or default to current user."""
    payer_id = request.POST.get("payer")
    if payer_id and payer_id.isdigit():
        payer = User.objects.filter(
            id=int(payer_id),
            family_memberships__family=family,
        ).first()
        if payer:
            return payer
    return request.user


@login_required
def expense_create(request):
    family, families = _current_family(request)
    if not family:
        return redirect("families")
    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except InvalidOperation:
            amount = Decimal("0")
        expense = Expense.objects.create(
            family=family,
            payer=_resolve_payer(request, family),
            title=request.POST.get("title", "Расход"),
            amount=amount,
            category=request.POST.get("category", ""),
            spent_on=_parse_user_date(request.POST.get("spent_on", "")),
            notes=request.POST.get("notes", ""),
        )
        mode = request.POST.get("payer_mode", "single")
        rows = _parse_contribution_rows(request) if mode == "multi" else []
        _apply_contributions(expense, mode, rows)
        if request.headers.get("HX-Request"):
            return render(request, "budget/_expense_row.html", {"expense": expense})
        return redirect(_family_url("budget:expense_list", family))
    return render(
        request,
        "budget/expense_form.html",
        {
            "families": families,
            "family": family,
            "page_title": "Новый расход",
            "payer_choices": _family_user_choices(family),
        },
    )


@login_required
def expense_update(request, expense_id: int):
    expense = get_object_or_404(
        Expense.objects.filter(family__in=_user_families(request.user)),
        pk=expense_id,
    )
    family = expense.family
    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except InvalidOperation:
            amount = expense.amount
        expense.title = request.POST.get("title", expense.title).strip() or expense.title
        expense.amount = amount
        expense.category = request.POST.get("category", expense.category)
        expense.spent_on = _parse_user_date(request.POST.get("spent_on", "")) or expense.spent_on
        expense.notes = request.POST.get("notes", "")
        expense.payer = _resolve_payer(request, family)
        expense.save()
        mode = request.POST.get("payer_mode", "single")
        rows = _parse_contribution_rows(request) if mode == "multi" else []
        _apply_contributions(expense, mode, rows)
        return redirect(_family_url("budget:expense_list", family))
    contribs = list(
        expense.contributions.values("contributor_id", "amount").order_by("created_at")
    )
    current_rows = [
        {"id": c["contributor_id"], "amount": str(c["amount"])}
        for c in contribs
        if c["contributor_id"]
    ]
    return render(
        request,
        "budget/expense_form.html",
        {
            "families": list(_user_families(request.user)),
            "family": family,
            "page_title": "Изменить расход",
            "expense": expense,
            "payer_choices": _family_user_choices(family),
            "current_rows": current_rows,
            "current_mode": "multi" if current_rows else "single",
        },
    )


@login_required
def expense_delete(request, expense_id: int):
    expense = get_object_or_404(
        Expense.objects.filter(family__in=_user_families(request.user)),
        pk=expense_id,
    )
    if request.method == "POST":
        expense.delete()
        if request.headers.get("HX-Request"):
            return HttpResponse("")
    return redirect(_family_url("budget:expense_list", expense.family))


@login_required
def expense_contribution_add(request, expense_id: int):
    expense = get_object_or_404(
        Expense.objects.filter(family__in=_user_families(request.user)),
        pk=expense_id,
    )
    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except InvalidOperation:
            amount = Decimal("0")
        if amount > 0:
            ExpenseContribution.objects.create(
                expense=expense,
                contributor=request.user,
                amount=amount,
                note=request.POST.get("note", "").strip(),
            )
    return redirect(_family_url("budget:expense_list", expense.family))


@login_required
def wishlist_index(request):
    family, families = _current_family(request)
    if not family:
        return redirect("families")
    wishlists = (
        Wishlist.objects.filter(family=family)
        .select_related("owner_member", "created_by")
        .prefetch_related("items")
    )
    members = family.family_members.filter(wishlists__isnull=False).distinct()
    my_member = _current_user_member(family, request.user)
    wish_member = request.GET.get("wish_member", "")
    wish_query = request.GET.get("wish_q", "").strip()
    if wish_member and str(wish_member).isdigit():
        wishlists = wishlists.filter(owner_member_id=int(wish_member))
    if wish_query:
        wishlists = wishlists.filter(
            Q(owner_member__first_name__icontains=wish_query)
            | Q(owner_member__last_name__icontains=wish_query)
            | Q(title__icontains=wish_query)
        )
    wishlists = list(wishlists)
    for wishlist in wishlists:
        wishlist.can_manage = _can_manage_wishlist(request.user, wishlist)
        wishlist.is_mine = wishlist.owner_member_id == my_member.id
    return render(
        request,
        "budget/wishlist_index.html",
        {
            "family": family,
            "families": families,
            "members": members,
            "my_member": my_member,
            "wishlists": wishlists,
            "wish_member": wish_member,
            "wish_query": wish_query,
        },
    )


@login_required
def wishlist_create(request):
    family, families = _current_family(request)
    if not family:
        return redirect("families")
    member = _current_user_member(family, request.user)
    if request.method == "POST":
        wishlist = Wishlist.objects.create(
            family=member.family,
            owner_member=member,
            created_by=request.user,
            title=request.POST.get("title", "").strip() or "Мой список желаний",
        )
        return redirect(_family_url("budget:wishlist_index", wishlist.family))
    return render(request, "budget/wishlist_form.html", {"family": family, "families": families, "page_title": "Новый список желаний"})


@login_required
def wishlist_update(request, wishlist_id: int):
    wishlist = get_object_or_404(
        Wishlist.objects.select_related("family", "owner_member").filter(family__in=_user_families(request.user)),
        pk=wishlist_id,
    )
    if not _can_manage_wishlist(request.user, wishlist):
        return HttpResponseForbidden("Недостаточно прав.")
    if request.method == "POST":
        wishlist.title = request.POST.get("title", "").strip() or "Список желаний"
        wishlist.save(update_fields=["title"])
        return redirect(_family_url("budget:wishlist_index", wishlist.family))
    return render(request, "budget/wishlist_form.html", {"wishlist": wishlist, "family": wishlist.family, "page_title": "Изменить список желаний"})


@login_required
def wishlist_delete(request, wishlist_id: int):
    wishlist = get_object_or_404(
        Wishlist.objects.select_related("family", "owner_member").filter(family__in=_user_families(request.user)),
        pk=wishlist_id,
    )
    family_id = wishlist.family_id
    if not _can_manage_wishlist(request.user, wishlist):
        return HttpResponseForbidden("Недостаточно прав.")
    if request.method == "POST":
        wishlist.delete()
    return redirect(f"{reverse('budget:wishlist_index')}?family={family_id}")


@login_required
def wishlist_item_add(request, wishlist_id: int):
    wishlist = get_object_or_404(
        Wishlist.objects.filter(family__in=_user_families(request.user)),
        pk=wishlist_id,
    )
    if request.method == "POST":
        if not _can_manage_wishlist(request.user, wishlist):
            return HttpResponseForbidden("Добавлять желания можно только в свой список.")
        price = None
        try:
            if request.POST.get("price_estimate"):
                price = Decimal(request.POST["price_estimate"])
        except InvalidOperation:
            price = None
        item = WishlistItem.objects.create(
            wishlist=wishlist,
            title=request.POST.get("title", "Желание"),
            description=request.POST.get("description", ""),
            url=request.POST.get("url", ""),
            price_estimate=price,
            share_with_family=True,
        )
    return redirect(_family_url("budget:wishlist_index", wishlist.family))


@login_required
def wishlist_item_reserve(request, item_id: int):
    item = get_object_or_404(
        WishlistItem.objects.filter(
            wishlist__family__in=_user_families(request.user)
        ),
        pk=item_id,
    )
    if request.method != "POST":
        return redirect(_family_url("budget:wishlist_index", item.wishlist.family))
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
    item = get_object_or_404(
        WishlistItem.objects.select_related("wishlist", "wishlist__family", "wishlist__owner_member").filter(
            wishlist__family__in=_user_families(request.user)
        ),
        pk=item_id,
    )
    if not _can_manage_wishlist(request.user, item.wishlist):
        return HttpResponseForbidden("Недостаточно прав.")
    if request.method == "POST":
        item.title = request.POST.get("title", "").strip() or item.title
        item.description = request.POST.get("description", "").strip()
        item.url = request.POST.get("url", "").strip()
        try:
            item.price_estimate = Decimal(request.POST["price_estimate"]) if request.POST.get("price_estimate") else None
        except InvalidOperation:
            item.price_estimate = None
        item.save(update_fields=["title", "description", "url", "price_estimate"])
    return redirect(_family_url("budget:wishlist_index", item.wishlist.family))


@login_required
def wishlist_item_delete(request, item_id: int):
    item = get_object_or_404(
        WishlistItem.objects.select_related("wishlist", "wishlist__family", "wishlist__owner_member").filter(
            wishlist__family__in=_user_families(request.user)
        ),
        pk=item_id,
    )
    wishlist = item.wishlist
    if not _can_manage_wishlist(request.user, wishlist):
        return HttpResponseForbidden("Недостаточно прав.")
    if request.method == "POST":
        item.delete()
    return redirect(_family_url("budget:wishlist_index", wishlist.family))

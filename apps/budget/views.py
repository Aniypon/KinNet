"""Budget + wishlist views."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.models import Family, FamilyMember

from .models import Expense, Wishlist, WishlistItem


def _user_families(user):
    return Family.objects.filter(
        Q(memberships__user=user) | Q(created_by=user)
    ).distinct()


@login_required
def expense_list(request):
    families = _user_families(request.user)
    expenses = (
        Expense.objects.filter(family__in=families)
        .select_related("family", "payer")
        .order_by("-spent_on", "-created_at")
    )
    totals = expenses.values("family__name").annotate(total=Sum("amount"))
    return render(
        request,
        "budget/expense_list.html",
        {"expenses": expenses, "families": families, "totals": list(totals)},
    )


@login_required
def expense_create(request):
    families = _user_families(request.user)
    if request.method == "POST":
        family = get_object_or_404(families, pk=request.POST.get("family"))
        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except InvalidOperation:
            amount = Decimal("0")
        spent_on = parse_date(request.POST.get("spent_on", "")) or timezone.localdate()
        Expense.objects.create(
            family=family,
            payer=request.user,
            title=request.POST.get("title", "Расход"),
            amount=amount,
            category=request.POST.get("category", ""),
            spent_on=spent_on,
            notes=request.POST.get("notes", ""),
        )
        return redirect("budget:expense_list")
    return render(request, "budget/expense_form.html", {"families": families})


@login_required
def wishlist_index(request):
    families = _user_families(request.user)
    wishlists = (
        Wishlist.objects.filter(family__in=families)
        .select_related("owner_member", "family")
        .prefetch_related("items")
    )
    return render(
        request,
        "budget/wishlist_index.html",
        {"wishlists": wishlists},
    )


@login_required
def wishlist_create(request):
    families = _user_families(request.user)
    members = FamilyMember.objects.filter(family__in=families)
    if request.method == "POST":
        member = get_object_or_404(members, pk=request.POST.get("owner_member"))
        wishlist = Wishlist.objects.create(
            family=member.family,
            owner_member=member,
            title=request.POST.get("title", "Список желаний"),
        )
        return redirect("budget:wishlist_index")
    return render(
        request,
        "budget/wishlist_form.html",
        {"members": members},
    )


@login_required
def wishlist_item_add(request, wishlist_id: int):
    wishlist = get_object_or_404(
        Wishlist.objects.filter(family__in=_user_families(request.user)),
        pk=wishlist_id,
    )
    if request.method == "POST":
        price = None
        try:
            if request.POST.get("price_estimate"):
                price = Decimal(request.POST["price_estimate"])
        except InvalidOperation:
            price = None
        WishlistItem.objects.create(
            wishlist=wishlist,
            title=request.POST.get("title", "Желание"),
            description=request.POST.get("description", ""),
            url=request.POST.get("url", ""),
            price_estimate=price,
        )
    return redirect("budget:wishlist_index")


@login_required
def wishlist_item_reserve(request, item_id: int):
    item = get_object_or_404(
        WishlistItem.objects.filter(
            wishlist__family__in=_user_families(request.user)
        ),
        pk=item_id,
    )
    if item.reserved_by_id and item.reserved_by_id != request.user.id:
        return redirect("budget:wishlist_index")
    if item.reserved_by_id == request.user.id:
        item.reserved_by = None
        item.reserved_at = None
    else:
        item.reserved_by = request.user
        item.reserved_at = timezone.now()
    item.save(update_fields=["reserved_by", "reserved_at"])
    return redirect("budget:wishlist_index")

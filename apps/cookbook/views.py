"""Cookbook views (recipes + shopping list)."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import escape
from django.views.decorators.http import require_POST

from core.models import Family, Task

from .models import Ingredient, Recipe, ShoppingItem, ShoppingList


def _user_families(user):
    return Family.objects.filter(
        Q(memberships__user=user) | Q(created_by=user)
    ).distinct()


@login_required
def recipe_list(request):
    families = _user_families(request.user)
    recipes = Recipe.objects.filter(family__in=families).select_related("family", "author")
    return render(
        request,
        "cookbook/recipe_list.html",
        {"recipes": recipes, "families": families},
    )


@login_required
def recipe_create(request):
    families = _user_families(request.user)
    if request.method == "POST":
        family = get_object_or_404(families, pk=request.POST.get("family"))
        recipe = Recipe.objects.create(
            family=family,
            author=request.user,
            title=request.POST.get("title", "").strip() or "Новый рецепт",
            description=request.POST.get("description", "").strip(),
            instructions=request.POST.get("instructions", "").strip(),
            cook_time_minutes=int(request.POST.get("cook_time_minutes") or 0),
            servings=int(request.POST.get("servings") or 2),
            tags=request.POST.get("tags", "").strip(),
        )
        ingredients_raw = request.POST.get("ingredients", "").strip()
        for line in ingredients_raw.splitlines():
            if not line.strip():
                continue
            parts = line.strip().split("|")
            Ingredient.objects.create(
                recipe=recipe,
                name=parts[0].strip(),
                quantity=parts[1].strip() if len(parts) > 1 else "",
                unit=parts[2].strip() if len(parts) > 2 else "",
            )
        return redirect("cookbook:recipe_detail", recipe_id=recipe.id)
    return render(request, "cookbook/recipe_form.html", {"families": families})


@login_required
def recipe_detail(request, recipe_id: int):
    recipe = get_object_or_404(
        Recipe.objects.filter(family__in=_user_families(request.user)), pk=recipe_id
    )
    return render(request, "cookbook/recipe_detail.html", {"recipe": recipe})


@login_required
@require_POST
def recipe_to_shopping_list(request, recipe_id: int):
    recipe = get_object_or_404(
        Recipe.objects.filter(family__in=_user_families(request.user)), pk=recipe_id
    )
    shopping_list = ShoppingList.objects.create(
        family=recipe.family,
        name=f"Покупки: {recipe.title}",
        created_by=request.user,
    )
    for ing in recipe.ingredients.all():
        ShoppingItem.objects.create(
            shopping_list=shopping_list,
            name=ing.name,
            quantity=f"{ing.quantity} {ing.unit}".strip(),
        )
    task = Task.objects.create(
        family=recipe.family,
        title=f"Купить продукты: {recipe.title}",
        description="Авто-сгенерировано из рецепта",
        created_by=request.user,
    )
    shopping_list.linked_task = task
    shopping_list.save(update_fields=["linked_task"])
    return redirect("cookbook:shopping_list_detail", list_id=shopping_list.id)


@login_required
def shopping_list_index(request):
    families = _user_families(request.user)
    lists = ShoppingList.objects.filter(family__in=families).select_related("family")
    return render(request, "cookbook/shopping_list_index.html", {"lists": lists})


@login_required
def shopping_list_detail(request, list_id: int):
    shopping_list = get_object_or_404(
        ShoppingList.objects.filter(family__in=_user_families(request.user)),
        pk=list_id,
    )
    return render(
        request,
        "cookbook/shopping_list_detail.html",
        {"shopping_list": shopping_list},
    )


@login_required
def shopping_item_toggle(request, item_id: int):
    item = get_object_or_404(
        ShoppingItem.objects.filter(
            shopping_list__family__in=_user_families(request.user)
        ),
        pk=item_id,
    )
    item.is_done = not item.is_done
    item.save(update_fields=["is_done"])
    if request.headers.get("HX-Request"):
        toggle_url = reverse("cookbook:shopping_item_toggle", args=[item.id])
        return HttpResponse(
            f'<li data-id="{item.id}" class="{"done" if item.is_done else ""}">'
            f'<input type="checkbox" hx-post="{toggle_url}" '
            f'hx-target="closest li" hx-swap="outerHTML" '
            f'{"checked" if item.is_done else ""}> {escape(item.name)} '
            f'<span class="meta">{escape(item.quantity)}</span></li>'
        )
    return HttpResponseRedirect(
        reverse("cookbook:shopping_list_detail", args=[item.shopping_list_id])
    )

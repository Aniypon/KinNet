"""Cookbook views (recipes + shopping list)."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.middleware.csrf import get_token
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import escape
from django.views.decorators.http import require_POST

from core.family_context import current_family as _current_family, get_user_families as _user_families
from core.models import Family, Task
from core.permissions import has_role

from .models import Ingredient, Recipe, ShoppingItem, ShoppingList


def _back_to_shopping(request, family_id):
    return redirect(request.META.get("HTTP_REFERER") or f"{reverse('cookbook:shopping_list_index')}?family={family_id}")


@login_required
def recipe_list(request):
    family, families = _current_family(request)
    recipes = Recipe.objects.filter(family=family).select_related("family", "author") if family else Recipe.objects.none()
    return render(
        request,
        "cookbook/recipe_list.html",
        {"recipes": recipes, "families": families, "family": family},
    )


@login_required
def recipe_create(request):
    family, families = _current_family(request)
    if not family:
        return redirect("families")
    if not has_role(request.user, family, ("owner", "admin", "parent")):
        raise PermissionDenied
    if request.method == "POST":
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
        _save_ingredients(recipe, request.POST.get("ingredients", ""))
        if request.headers.get("HX-Request"):
            return render(request, "cookbook/_recipe_card.html", {"recipe": recipe})
        return redirect("cookbook:recipe_detail", recipe_id=recipe.id)
    return render(request, "cookbook/recipe_form.html", {"families": families, "family": family, "page_title": "Новый рецепт"})


def _save_ingredients(recipe, ingredients_raw):
    recipe.ingredients.all().delete()
    for name, quantity, unit in _parse_product_lines(ingredients_raw):
        Ingredient.objects.create(
            recipe=recipe,
            name=name,
            quantity=quantity,
            unit=unit,
        )


def _parse_product_lines(raw):
    for line in raw.strip().splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.strip().split("|")]
        yield parts[0], parts[1] if len(parts) > 1 else "", parts[2] if len(parts) > 2 else ""


def _shopping_items_text(shopping_list):
    return "\n".join(
        " | ".join(part for part in [item.name, item.quantity, item.unit] if part)
        for item in shopping_list.items.all()
    )


def _replace_shopping_items(shopping_list, raw):
    shopping_list.items.all().delete()
    for name, quantity, unit in _parse_product_lines(raw):
        ShoppingItem.objects.create(
            shopping_list=shopping_list,
            name=name,
            quantity=quantity,
            unit=unit,
        )


@login_required
def recipe_detail(request, recipe_id: int):
    recipe = get_object_or_404(
        Recipe.objects.filter(family__in=_user_families(request.user)), pk=recipe_id
    )
    return render(request, "cookbook/recipe_detail.html", {"recipe": recipe})


@login_required
def recipe_update(request, recipe_id: int):
    recipe = get_object_or_404(
        Recipe.objects.filter(family__in=_user_families(request.user)), pk=recipe_id
    )
    family, families = _current_family(request)
    if not has_role(request.user, recipe.family, ("owner", "admin", "parent")):
        raise PermissionDenied
    if request.method == "POST":
        recipe.family = family or recipe.family
        recipe.title = request.POST.get("title", "").strip() or "Новый рецепт"
        recipe.description = request.POST.get("description", "").strip()
        recipe.instructions = request.POST.get("instructions", "").strip()
        recipe.cook_time_minutes = int(request.POST.get("cook_time_minutes") or 0)
        recipe.servings = int(request.POST.get("servings") or 2)
        recipe.tags = request.POST.get("tags", "").strip()
        recipe.save(update_fields=["family", "title", "description", "instructions", "cook_time_minutes", "servings", "tags"])
        _save_ingredients(recipe, request.POST.get("ingredients", ""))
        return redirect("cookbook:recipe_detail", recipe_id=recipe.id)
    ingredients_text = "\n".join(
        " | ".join(part for part in [ing.name, ing.quantity, ing.unit] if part)
        for ing in recipe.ingredients.all()
    )
    return render(
        request,
        "cookbook/recipe_form.html",
        {"families": families, "family": recipe.family, "recipe": recipe, "ingredients_text": ingredients_text, "page_title": "Изменить рецепт"},
    )


@login_required
@require_POST
def recipe_delete(request, recipe_id: int):
    recipe = get_object_or_404(
        Recipe.objects.filter(family__in=_user_families(request.user)), pk=recipe_id
    )
    if not has_role(request.user, recipe.family, ("owner", "admin", "parent")):
        raise PermissionDenied
    recipe.delete()
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("cookbook:recipe_list")


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
            quantity=ing.quantity,
            unit=ing.unit,
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
    family, families = _current_family(request)
    if not family:
        return redirect("families")
    if request.method == "POST":
        name = request.POST.get("name", "").strip() or "Список покупок"
        sl = ShoppingList.objects.create(family=family, name=name, created_by=request.user)
        return redirect("cookbook:shopping_list_detail", list_id=sl.id)
    lists = list(ShoppingList.objects.filter(family=family).prefetch_related("items"))
    active_lists = [sl for sl in lists if not sl.is_completed]
    done_lists = [sl for sl in lists if sl.is_completed]
    return render(
        request,
        "cookbook/shopping_list_index.html",
        {
            "lists": lists,
            "active_lists": active_lists,
            "done_lists": done_lists,
            "family": family,
            "families": families,
        },
    )


@login_required
def shopping_list_detail(request, list_id: int):
    shopping_list = get_object_or_404(
        ShoppingList.objects.filter(family__in=_user_families(request.user)),
        pk=list_id,
    )
    return render(
        request,
        "cookbook/shopping_list_detail.html",
        {"shopping_list": shopping_list, "items_text": _shopping_items_text(shopping_list)},
    )


@login_required
@require_POST
def shopping_list_update(request, list_id: int):
    shopping_list = get_object_or_404(
        ShoppingList.objects.filter(family__in=_user_families(request.user)),
        pk=list_id,
    )
    shopping_list.name = request.POST.get("name", "").strip() or shopping_list.name
    shopping_list.save(update_fields=["name"])
    if "items_bulk" in request.POST:
        _replace_shopping_items(shopping_list, request.POST.get("items_bulk", ""))
    return _back_to_shopping(request, shopping_list.family_id)


@login_required
@require_POST
def shopping_list_delete(request, list_id: int):
    shopping_list = get_object_or_404(
        ShoppingList.objects.filter(family__in=_user_families(request.user)),
        pk=list_id,
    )
    family_id = shopping_list.family_id
    shopping_list.delete()
    return redirect(f"{reverse('cookbook:shopping_list_index')}?family={family_id}")


@login_required
@require_POST
def shopping_item_add(request, list_id: int):
    shopping_list = get_object_or_404(
        ShoppingList.objects.filter(family__in=_user_families(request.user)),
        pk=list_id,
    )
    name = request.POST.get("name", "").strip()
    if name:
        ShoppingItem.objects.create(
            shopping_list=shopping_list,
            name=name,
            quantity=request.POST.get("quantity", "").strip(),
            unit=request.POST.get("unit", "").strip(),
        )
    return _back_to_shopping(request, shopping_list.family_id)


@login_required
def shopping_item_update(request, item_id: int):
    item = get_object_or_404(
        ShoppingItem.objects.filter(shopping_list__family__in=_user_families(request.user)),
        pk=item_id,
    )
    if request.method == "POST":
        item.name = request.POST.get("name", "").strip() or item.name
        item.quantity = request.POST.get("quantity", "").strip()
        item.unit = request.POST.get("unit", "").strip()
        item.save(update_fields=["name", "quantity", "unit"])
        return redirect("cookbook:shopping_list_detail", list_id=item.shopping_list_id)
    return render(
        request,
        "cookbook/shopping_item_form.html",
        {"item": item, "shopping_list": item.shopping_list},
    )


@login_required
@require_POST
def shopping_item_delete(request, item_id: int):
    item = get_object_or_404(
        ShoppingItem.objects.filter(shopping_list__family__in=_user_families(request.user)),
        pk=item_id,
    )
    family_id = item.shopping_list.family_id
    item.delete()
    return _back_to_shopping(request, family_id)


@login_required
@require_POST
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
        update_url = reverse("cookbook:shopping_item_update", args=[item.id])
        delete_url = reverse("cookbook:shopping_item_delete", args=[item.id])
        csrf_token = get_token(request)
        return HttpResponse(
            f'<li data-id="{item.id}" class="shopping-item-row {"done" if item.is_done else ""}">'
            f'<label class="shopping-check">'
            f'<input type="checkbox" hx-post="{toggle_url}" '
            f'hx-target="closest li" hx-swap="outerHTML" '
            f'{"checked" if item.is_done else ""}>'
            f'<span class="shopping-item-name">{escape(item.name)}</span>'
            f'<span class="meta">{escape(" ".join(p for p in [item.quantity, item.unit] if p))}</span>'
            f'</label>'
            f'<div class="card-actions shopping-item-actions">'
            f'<a class="btn small secondary" href="{update_url}">Изменить</a>'
            f'<form method="post" action="{delete_url}" onsubmit="return confirm(\'Удалить пункт?\');" style="display:inline;">'
            f'<input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">'
            f'<button class="btn small secondary danger-soft" type="submit">Удалить</button></form></div></li>'
        )
    return _back_to_shopping(request, item.shopping_list.family_id)

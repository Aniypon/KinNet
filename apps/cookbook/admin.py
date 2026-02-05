from django.contrib import admin

from .models import Ingredient, Recipe, ShoppingItem, ShoppingList


class IngredientInline(admin.TabularInline):
    model = Ingredient
    extra = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("title", "family", "author", "cook_time_minutes", "servings")
    search_fields = ("title", "tags")
    inlines = [IngredientInline]


class ShoppingItemInline(admin.TabularInline):
    model = ShoppingItem
    extra = 1


@admin.register(ShoppingList)
class ShoppingListAdmin(admin.ModelAdmin):
    list_display = ("name", "family", "created_by", "created_at")
    inlines = [ShoppingItemInline]

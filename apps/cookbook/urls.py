from django.urls import path

from . import views

app_name = "cookbook"

urlpatterns = [
    path("", views.recipe_list, name="recipe_list"),
    path("new/", views.recipe_create, name="recipe_create"),
    path("<int:recipe_id>/", views.recipe_detail, name="recipe_detail"),
    path(
        "<int:recipe_id>/shopping-list/",
        views.recipe_to_shopping_list,
        name="recipe_to_shopping_list",
    ),
    path("shopping/", views.shopping_list_index, name="shopping_list_index"),
    path(
        "shopping/<int:list_id>/",
        views.shopping_list_detail,
        name="shopping_list_detail",
    ),
    path(
        "shopping/items/<int:item_id>/toggle/",
        views.shopping_item_toggle,
        name="shopping_item_toggle",
    ),
]

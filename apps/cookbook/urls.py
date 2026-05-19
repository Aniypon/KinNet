from django.urls import path

from . import views

app_name = "cookbook"

urlpatterns = [
    path("", views.recipe_list, name="recipe_list"),
    path("new/", views.recipe_create, name="recipe_create"),
    path("<int:recipe_id>/", views.recipe_detail, name="recipe_detail"),
    path("<int:recipe_id>/edit/", views.recipe_update, name="recipe_update"),
    path("<int:recipe_id>/delete/", views.recipe_delete, name="recipe_delete"),
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
    path("shopping/<int:list_id>/edit/", views.shopping_list_update, name="shopping_list_update"),
    path("shopping/<int:list_id>/delete/", views.shopping_list_delete, name="shopping_list_delete"),
    path("shopping/<int:list_id>/items/new/", views.shopping_item_add, name="shopping_item_add"),
    path(
        "shopping/items/<int:item_id>/toggle/",
        views.shopping_item_toggle,
        name="shopping_item_toggle",
    ),
    path("shopping/items/<int:item_id>/edit/", views.shopping_item_update, name="shopping_item_update"),
    path("shopping/items/<int:item_id>/delete/", views.shopping_item_delete, name="shopping_item_delete"),
]

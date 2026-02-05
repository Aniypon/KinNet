from django.urls import path

from . import views

app_name = "budget"

urlpatterns = [
    path("", views.expense_list, name="expense_list"),
    path("new/", views.expense_create, name="expense_create"),
    path("<int:expense_id>/edit/", views.expense_update, name="expense_update"),
    path("<int:expense_id>/delete/", views.expense_delete, name="expense_delete"),
    path("<int:expense_id>/contributions/new/", views.expense_contribution_add, name="expense_contribution_add"),
    path("wishlists/", views.wishlist_index, name="wishlist_index"),
    path("wishlists/new/", views.wishlist_create, name="wishlist_create"),
    path("wishlists/<int:wishlist_id>/edit/", views.wishlist_update, name="wishlist_update"),
    path("wishlists/<int:wishlist_id>/delete/", views.wishlist_delete, name="wishlist_delete"),
    path(
        "wishlists/<int:wishlist_id>/items/new/",
        views.wishlist_item_add,
        name="wishlist_item_add",
    ),
    path(
        "wishlists/items/<int:item_id>/reserve/",
        views.wishlist_item_reserve,
        name="wishlist_item_reserve",
    ),
    path("wishlists/items/<int:item_id>/edit/", views.wishlist_item_update, name="wishlist_item_update"),
    path("wishlists/items/<int:item_id>/delete/", views.wishlist_item_delete, name="wishlist_item_delete"),
]

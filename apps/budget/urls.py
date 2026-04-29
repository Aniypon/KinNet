from django.urls import path

from . import views

app_name = "budget"

urlpatterns = [
    path("", views.expense_list, name="expense_list"),
    path("new/", views.expense_create, name="expense_create"),
    path("wishlists/", views.wishlist_index, name="wishlist_index"),
    path("wishlists/new/", views.wishlist_create, name="wishlist_create"),
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
]

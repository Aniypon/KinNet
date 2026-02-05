from django.contrib import admin

from .models import Expense, Wishlist, WishlistItem


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("title", "family", "payer", "amount", "spent_on")
    list_filter = ("family", "spent_on")
    search_fields = ("title", "category")


class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 1


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("title", "owner_member", "family", "created_at")
    inlines = [WishlistItemInline]

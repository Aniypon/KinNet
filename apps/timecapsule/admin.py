from django.contrib import admin

from .models import Capsule


@admin.register(Capsule)
class CapsuleAdmin(admin.ModelAdmin):
    list_display = ("title", "family", "reveal_at", "status", "delivered_at")
    list_filter = ("status", "family")
    search_fields = ("title",)
    filter_horizontal = ("recipients_users",)

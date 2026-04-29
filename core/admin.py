from django.contrib import admin

from .models import (
	Event,
	Family,
	FamilyInvitation,
	FamilyMember,
	FamilyMembership,
	Message,
	Task,
	TaskChecklistItem,
	TaskContribution,
	TelegramProfile,
)


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
	list_display = ("name", "created_by", "created_at")
	search_fields = ("name",)


@admin.register(FamilyMembership)
class FamilyMembershipAdmin(admin.ModelAdmin):
	list_display = ("family", "user", "role", "joined_at")
	list_filter = ("role",)
	search_fields = ("family__name", "user__username", "user__email")


@admin.register(FamilyInvitation)
class FamilyInvitationAdmin(admin.ModelAdmin):
	list_display = ("family", "email", "username", "status", "created_at")
	list_filter = ("status",)
	search_fields = ("family__name", "email", "username")


@admin.register(FamilyMember)
class FamilyMemberAdmin(admin.ModelAdmin):
	list_display = ("family", "first_name", "last_name", "relation", "phone", "birth_date")
	list_filter = ("family",)
	search_fields = ("first_name", "last_name", "middle_name", "phone", "email")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
	list_display = ("title", "family", "date", "kind", "member")
	list_filter = ("kind", "family")
	search_fields = ("title",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
	list_display = ("title", "family", "status", "assignee", "due_date")
	list_filter = ("status", "family")
	search_fields = ("title",)


@admin.register(TaskChecklistItem)
class TaskChecklistItemAdmin(admin.ModelAdmin):
	list_display = ("task", "title", "is_done")
	list_filter = ("is_done",)


@admin.register(TaskContribution)
class TaskContributionAdmin(admin.ModelAdmin):
	list_display = ("task", "user", "amount", "created_at")
	search_fields = ("task__title", "user__username", "user__email")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
	list_display = ("family", "sender", "created_at")
	search_fields = ("sender__username", "text")


@admin.register(TelegramProfile)
class TelegramProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "chat_id", "username", "linked_at")
	search_fields = ("user__username", "chat_id", "username")

from django.contrib import admin

from .models import Poll, PollChoice, PollVote


class PollChoiceInline(admin.TabularInline):
    model = PollChoice
    extra = 2


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("question", "family", "author", "is_closed", "created_at")
    list_filter = ("is_closed", "family")
    inlines = [PollChoiceInline]


admin.site.register(PollVote)

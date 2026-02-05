from django.contrib import admin

from .models import HealthRecord, Medication


@admin.register(HealthRecord)
class HealthRecordAdmin(admin.ModelAdmin):
    list_display = ("member", "blood_type", "updated_at")
    search_fields = ("member__first_name", "member__last_name")


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ("name", "member", "frequency", "is_active")
    list_filter = ("frequency", "is_active")
    search_fields = ("name", "member__first_name", "member__last_name")

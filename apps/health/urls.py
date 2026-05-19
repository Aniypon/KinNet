from django.urls import path

from . import views

app_name = "health"

urlpatterns = [
    path("", views.health_index, name="health_index"),
    path("members/<int:member_id>/record/", views.record_edit, name="record_edit"),
    path(
        "members/<int:member_id>/medication/new/",
        views.medication_create,
        name="medication_create",
    ),
]

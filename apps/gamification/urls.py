from django.urls import path

from . import views

app_name = "gamification"

urlpatterns = [
    path("", views.badge_index, name="badge_index"),
]

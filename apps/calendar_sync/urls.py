from django.urls import path

from . import views

app_name = "calendar_sync"

urlpatterns = [
    path("", views.feed_settings, name="feed_settings"),
    path("feed/<str:token>.ics", views.ics_feed, name="ics_feed"),
]

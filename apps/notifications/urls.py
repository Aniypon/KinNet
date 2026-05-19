from django.urls import path

from .views import sse

app_name = "notifications"

urlpatterns = [
    path("stream/", sse, name="sse"),
]

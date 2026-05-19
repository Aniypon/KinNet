from django.urls import path

from . import views

app_name = "polls"

urlpatterns = [
    path("", views.poll_list, name="poll_list"),
    path("new/", views.poll_create, name="poll_create"),
    path("<int:poll_id>/", views.poll_detail, name="poll_detail"),
    path("<int:poll_id>/edit/", views.poll_update, name="poll_update"),
    path("<int:poll_id>/delete/", views.poll_delete, name="poll_delete"),
    path("<int:poll_id>/vote/", views.poll_vote, name="poll_vote"),
]

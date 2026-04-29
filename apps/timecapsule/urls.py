from django.urls import path

from . import views

app_name = "timecapsule"

urlpatterns = [
    path("", views.capsule_list, name="capsule_list"),
    path("new/", views.capsule_create, name="capsule_create"),
]

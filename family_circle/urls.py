"""Top-level URL configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from apps.api.api import api as ninja_api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("api/", ninja_api.urls),
    # PWA
    path(
        "manifest.webmanifest",
        TemplateView.as_view(
            template_name="pwa/manifest.webmanifest",
            content_type="application/manifest+json",
        ),
        name="pwa_manifest",
    ),
    path(
        "sw.js",
        TemplateView.as_view(
            template_name="pwa/sw.js",
            content_type="application/javascript",
        ),
        name="pwa_service_worker",
    ),
    path(
        "offline/",
        TemplateView.as_view(template_name="pwa/offline.html"),
        name="pwa_offline",
    ),
    # New product apps
    path("cookbook/", include("apps.cookbook.urls")),
    path("capsule/", include("apps.timecapsule.urls")),
    path("health/", include("apps.health.urls")),
    path("budget/", include("apps.budget.urls")),
    path("polls/", include("apps.polls.urls")),
    path("calendar/", include("apps.calendar_sync.urls")),
    path("badges/", include("apps.gamification.urls")),
    path("notifications/", include("apps.notifications.urls")),
    # Legacy domain (members/families/events/tasks/goals/...)
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

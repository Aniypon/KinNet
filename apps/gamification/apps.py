from django.apps import AppConfig


class GamificationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.gamification"
    label = "kinnet_gamification"
    verbose_name = "Микроинтеракции и достижения"

    def ready(self):  # pragma: no cover - signal wiring
        from . import signals  # noqa: F401

from django.apps import AppConfig


class PollsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.polls"
    label = "kinnet_polls"
    verbose_name = "Опросы и голосования"

from django.apps import AppConfig


class CookbookConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cookbook"
    label = "cookbook"
    verbose_name = "Семейная кулинарная книга"

from django.apps import AppConfig


class RischiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rischi"
    verbose_name = "Libreria"

    def ready(self):
        from . import registro  # noqa: F401  collega i segnali

from django.apps import AppConfig


class CaisseConfig(AppConfig):
    """Business app. Its label must also be in `BUSINESS_APPS` (Pitfall 12)."""

    name = "domaine.caisse"
    label = "caisse"
    verbose_name = "caisse"

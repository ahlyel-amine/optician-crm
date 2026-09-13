from django.apps import AppConfig


class StockConfig(AppConfig):
    """Business app. Its label must also be in `BUSINESS_APPS` (Pitfall 12)."""

    name = "domaine.stock"
    label = "stock"
    verbose_name = "stock"

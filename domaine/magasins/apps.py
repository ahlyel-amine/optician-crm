from django.apps import AppConfig


class MagasinsConfig(AppConfig):
    """A business app. Its tables exist only in client databases, never in `default`.

    `TenantRouter.allow_migrate` returns `False` for business apps on `default`, which
    is what makes the bypass-proof backstop true: a stray `.using("default")` gets
    `relation does not exist` rather than reading or writing the control plane.
    """

    name = "domaine.magasins"
    label = "magasins"
    verbose_name = "Magasins"

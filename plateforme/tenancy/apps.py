from django.apps import AppConfig


class TenancyConfig(AppConfig):
    """The tenancy infrastructure app. It owns no models and no tables.

    Django derives the label `tenancy` from the dotted name, and that label must appear
    in `CONTROL_PLANE_APPS` — the system check registered below only exempts apps whose
    name starts with `django.`, so an unlisted `tenancy` would make the check fail on
    itself.
    """

    name = "plateforme.tenancy"
    label = "tenancy"
    verbose_name = "Tenancy"

    def ready(self):
        """Register the system check and the Celery leak guard. **Nothing else.**

        `ready()` must not register a tenant alias and must not touch the database
        (Pitfall 4, threat T-02-22). `makemigrations` iterates every alias present in
        `connections` whenever `DATABASE_ROUTERS` is set and calls
        `check_consistent_history` against each, opening a real connection — so a
        `ready()` that pre-registered all clients would silently make
        `manage.py makemigrations` connect to every production database.
        """
        from plateforme.tenancy import checks  # noqa: F401 — import registers the check
        from plateforme.tenancy import tasks  # noqa: F401 — import connects task_prerun

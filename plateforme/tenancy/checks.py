"""The startup system check that protects every future phase.

Pitfall 12, stated concretely: Phase 7 adds a `caisse` app, nobody updates
`BUSINESS_APPS`, `allow_migrate` returns `None`, `ConnectionRouter.allow_migrate` defaults
to `True` when every router declines, and the caisse tables are created in the
**control-plane database** — where every client's rows would then share one table.

`allow_migrate` cannot raise (it is a build-time path), so the loud failure has to happen
somewhere else. `manage.py check` runs on every `runserver`, every `migrate` and in CI,
which makes it the right place: cheap, permanent, and it covers apps that do not exist yet.
"""

from __future__ import annotations

from django.apps import apps
from django.core.checks import Error, register


@register()
def check_every_app_is_classified(app_configs, **kwargs):
    """Every installed non-Django app must be classified control-plane or business.

    Only apps whose `AppConfig.name` starts with `django.` are exempt — which is why
    `rest_framework` and `tenancy` must be listed in `CONTROL_PLANE_APPS` explicitly.
    """
    from plateforme.tenancy.router import BUSINESS_APPS, CONTROL_PLANE_APPS

    errors = []
    for cfg in apps.get_app_configs():
        if cfg.name.startswith("django."):
            continue
        if cfg.label not in CONTROL_PLANE_APPS and cfg.label not in BUSINESS_APPS:
            errors.append(
                Error(
                    f"App '{cfg.label}' is classified as neither control-plane nor "
                    "business.",
                    hint=(
                        "Add it to CONTROL_PLANE_APPS or BUSINESS_APPS in "
                        "plateforme/tenancy/router.py. An unclassified app defaults to "
                        "the control-plane database, which is a cross-client leak."
                    ),
                    id="tenancy.E001",
                )
            )
    return errors

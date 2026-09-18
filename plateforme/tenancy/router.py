"""The fail-closed database router. TENANT-04, and the security core of the product.

What Django does with a falsy return, quoted from `django/db/utils.py`
(`ConnectionRouter._router_func`)::

    for router in self.routers:
        try:
            method = getattr(router, action)
        except AttributeError:
            pass                       # only a MISSING METHOD is swallowed
        else:
            chosen_db = method(model, **hints)
            if chosen_db:
                return chosen_db       # note: truthiness, so "" falls through too
    instance = hints.get("instance")
    if instance is not None and instance._state.db:
        return instance._state.db
    return DEFAULT_DB_ALIAS            # <-- the cross-client leak

So declining *is* the leak, and raising is safe: an exception raised inside
`db_for_read` / `db_for_write` propagates untouched, because only `AttributeError` from a
missing method is caught.

**The router is defence #1, not a guarantee.** `.using(alias)` sets `QuerySet._db` and
skips the router entirely. The absolute defence is `allow_migrate` below: because
business apps never migrate to `default`, their tables do not exist there, and a bypass
gets `relation does not exist` (threat T-02-19).
"""

from __future__ import annotations

from plateforme.tenancy.context import CrossTenantAccess, current_alias

#: Apps whose tables live in the control-plane database, on `default`, and nowhere else.
#:
#: `rest_framework` and `tenancy` are **load-bearing entries, not padding.** The system
#: check in `checks.py` skips only apps whose `AppConfig.name` starts with `"django."`.
#: `rest_framework` is in `INSTALLED_APPS`, and `tenancy` is the label Django derives for
#: `plateforme.tenancy` itself. Omit either and `tenancy.E001` fires the moment the check
#: registers.
#: `comptes` carries `AUTH_USER_MODEL` (CLAUDE.md #11): identity, business membership and
#: permission grants belong to the fleet, not to one optician's database. `projection` and
#: `drf_spectacular` own no models at all, but the check exempts only `django.*` names, so
#: an app with nothing to migrate still has to be classified or `manage.py check` fails.
CONTROL_PLANE_APPS = frozenset(
    {
        "control_plane",
        "admin",
        "auth",
        "contenttypes",
        "sessions",
        "messages",
        "django_celery_beat",
        "rest_framework",
        "drf_spectacular",
        "tenancy",
        "comptes",
        "projection",
        # `django.contrib.postgres`, dont Django dérive le label `postgres`. Elle ne
        # possède aucun modèle — elle est installée pour ses lookups ORM, voir
        # `config/settings/base.py` — mais le check n'exempte que les `AppConfig.name`
        # commençant par `"django."`, et son *label* n'en est pas un. Non classée, elle
        # ferait échouer `manage.py check` avec `tenancy.E001`, exactement comme
        # `projection` et `drf_spectacular` au-dessus.
        "postgres",
    }
)

#: Apps whose tables live in each client's own database. Phases 5 through 8 extend this,
#: and the `tenancy.E001` system check makes forgetting impossible rather than merely
#: unlikely — add the label here in the **same commit** that adds the app to
#: `INSTALLED_APPS`, or `manage.py check` fails on the next run (Pitfall 12).
BUSINESS_APPS = frozenset(
    {
        "magasins",
        "stock",
        "caisse",
        # La fiche client et, plus tard, ses ordonnances. **Pas** `control_plane.Client`,
        # qui est l'affaire de l'opticien et reste sur `default` (CLAUDE.md #11) : ce qui
        # est isolé ici, ce sont les données de santé et de commerce, pas la ligne de
        # connexion.
        "clients",
    }
)

TENANT_ALIAS_PREFIX = "tenant_"


class ImproperlyClassifiedApp(RuntimeError):
    """An app is in neither `CONTROL_PLANE_APPS` nor `BUSINESS_APPS`."""


def is_tenant_alias(alias: str) -> bool:
    """True for a client-database alias. Mirrors `registry.alias_for`'s prefix."""
    return alias.startswith(TENANT_ALIAS_PREFIX)


class TenantRouter:
    """Routes control-plane models to `default` and business models to the bound client."""

    def _route(self, model, hints):
        app_label = model._meta.app_label

        if app_label in CONTROL_PLANE_APPS:
            return "default"

        if app_label not in BUSINESS_APPS:
            # An app nobody classified. Failing loudly here is the whole point: an
            # unclassified app silently defaulting to `default` is the leak. The system
            # check in checks.py is what makes this branch unreachable in practice.
            raise ImproperlyClassifiedApp(
                f"App '{app_label}' is in neither CONTROL_PLANE_APPS nor BUSINESS_APPS. "
                "Classify it in plateforme/tenancy/router.py."
            )

        alias = current_alias()  # raises NoTenantBound when unset

        instance = hints.get("instance")
        if instance is not None and instance._state.db:
            # Django's documented default is that hinted fetches follow the instance's
            # database. If the instance came from a *different* client, honouring the
            # hint is a cross-tenant read (threat T-02-16).
            if instance._state.db != alias:
                raise CrossTenantAccess(
                    f"Instance loaded on {instance._state.db!r} was used while "
                    f"{alias!r} is bound. Reload it inside the current tenant scope."
                )
            return instance._state.db

        return alias

    # db_for_read and db_for_write are deliberately identical: there are no read replicas
    # in this design, and adding one later must be an explicit change rather than an
    # accident. Written as ordinary methods, not lambdas, so tracebacks name them.
    def db_for_read(self, model, **hints):
        return self._route(model, hints)

    def db_for_write(self, model, **hints):
        return self._route(model, hints)

    def allow_relation(self, obj1, obj2, **hints):
        """Same database only. Never cross the control-plane / tenant boundary."""
        return obj1._state.db == obj2._state.db

    def allow_migrate(self, db, app_label, **hints):
        """**MUST NOT RAISE.** `makemigrations` calls this for every alias x app x model.

        The asymmetry with `_route` is deliberate, not an inconsistency: `_route` is a
        runtime data path where silence is a leak, so it raises on an unclassified app.
        `allow_migrate` is a build-time path where raising crashes `makemigrations` from
        deep inside Django (Pitfall 7), so it returns `None` — no opinion — and the
        `tenancy.E001` system check is what catches the unclassified app instead.
        """
        if app_label in CONTROL_PLANE_APPS:
            return db == "default"
        if app_label in BUSINESS_APPS:
            return is_tenant_alias(db)
        return None

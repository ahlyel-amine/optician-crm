"""TENANT-04 — the fail-closed router, and the backstop a router bypass cannot defeat.

`CLAUDE.md`: *"a leak across clients is a security failure, not a bug."* Four layered
defences, so that no single mistake is a breach:

1. The router **raises** when no client is bound. Returning `None` falls through to
   `default`, which is a silent cross-client read.
2. The context is cleared with `set(_UNSET)`, never a token-based undo — see
   `tests/test_tenancy_context.py`.
3. `allow_migrate` keeps business tables **out of the control-plane database entirely**,
   so a `.using("default")` that bypasses the router hits `relation does not exist`.
   This is the only defence a router bypass cannot defeat.
4. A system check fails at startup if any installed app is unclassified, so defence 3
   cannot silently stop covering an app added in a later phase.
"""

from unittest import mock

import pytest
from django.apps import apps
from django.core import checks
from django.db import connections

from domaine.magasins.models import Magasin
from plateforme.tenancy.context import (
    CrossTenantAccess,
    NoTenantBound,
    clear,
    tenant_context,
)
from plateforme.tenancy.router import BUSINESS_APPS, CONTROL_PLANE_APPS, TenantRouter


def test_tenant04_router_raises_when_no_client_bound():
    """With no client bound, a business query raises `NoTenantBound` — it does not fall back.

    `Magasin.objects.count()` with an empty context must raise. Not return an empty
    queryset, not query `default`. Django's `ConnectionRouter._router_func` returns
    `DEFAULT_DB_ALIAS` when every router declines, so "declining" *is* the leak; raising
    is the only fail-closed answer, and an exception raised inside `db_for_read`
    propagates untouched — `_router_func` swallows only `AttributeError`, and only for a
    missing method (threat T-02-14).
    """
    clear()
    with pytest.raises(NoTenantBound):
        Magasin.objects.count()


def test_tenant04_router_never_returns_none():
    """`db_for_read` / `db_for_write` never return a falsy alias.

    Assert against **falsiness**, not against `is None`. Django's `_router_func` tests
    `if chosen_db:` — so an empty string falls through to `default` exactly as `None`
    does, and a test written as `is not None` would pass against that bug.

    Unbound, the methods raise rather than returning anything at all, which is stronger
    than returning a truthy value and is asserted as such.
    """
    router = TenantRouter()

    clear()
    for method in (router.db_for_read, router.db_for_write):
        with pytest.raises(NoTenantBound):
            method(Magasin)

    with tenant_context("tenant_a"):
        for method in (router.db_for_read, router.db_for_write):
            chosen = method(Magasin)
            assert chosen, (
                f"{method.__name__} returned {chosen!r}, which is falsy. Django's "
                "_router_func tests `if chosen_db:` and falls through to DEFAULT_DB_ALIAS, "
                "so an empty string leaks exactly as None does."
            )
            assert chosen == "tenant_a"


@pytest.mark.django_db
def test_tenant04_business_models_never_migrate_to_default():
    """**The backstop.** Zero business tables exist in the control-plane database.

    Queries `information_schema.tables` on the `default` connection and asserts that no
    table belongs to a model of a `BUSINESS_APPS` app. The expected table names are
    derived from `apps.get_app_config(label).get_models()` rather than hardcoded, so a
    model added in Phase 5 is covered automatically.

    This assertion holds **even if the router is circumvented**, which no router-level
    assertion can claim: `.using("default")` sets `QuerySet._db` and skips the router
    entirely (threat T-02-19). If the tables are not there, the bypass gets
    `relation does not exist`.

    The test also proves it is not vacuous: the same tables **must** exist on the tenant
    aliases. A run where nothing was migrated anywhere would otherwise pass trivially.
    """
    business_tables = {
        model._meta.db_table
        for label in BUSINESS_APPS
        if apps.is_installed(apps.get_app_config(label).name)
        for model in apps.get_app_config(label).get_models()
    }
    assert business_tables, (
        "No business tables were derived at all — BUSINESS_APPS is empty or misspelled, "
        "which would make this test pass while proving nothing."
    )

    with connections["default"].cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = ANY(%s)",
            [sorted(business_tables)],
        )
        found = {row[0] for row in cur.fetchall()}

    assert found == set(), (
        f"Business tables {sorted(found)} exist in the control-plane database. "
        "allow_migrate must return False for business apps on 'default'. Their absence "
        "is the only defence that survives a .using('default') bypass (T-02-19)."
    )


@pytest.mark.tenancy
def test_tenant04_business_tables_do_exist_on_a_tenant_alias(db_all):
    """The other half of the backstop: the tables are somewhere, just not in `default`.

    Without this, `test_tenant04_business_models_never_migrate_to_default` would pass on
    a run where the migrations never applied anywhere.
    """
    business_tables = {
        model._meta.db_table
        for label in BUSINESS_APPS
        for model in apps.get_app_config(label).get_models()
    }
    with connections["tenant_a"].cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = ANY(%s)",
            [sorted(business_tables)],
        )
        found = {row[0] for row in cur.fetchall()}

    assert found == business_tables, (
        f"Missing {sorted(business_tables - found)} on tenant_a. Business apps must "
        "migrate to tenant aliases."
    )


@pytest.mark.tenancy
def test_tenant04_tenant_a_cannot_read_tenant_b_data(tenant_a, tenant_b):
    """The isolation test itself: two clients, and neither can see the other's rows.

    Both tenant fixtures are requested because the second client is the **control** —
    with a single tenant, a router bug that always returns the same alias passes every
    isolation test (`.planning/TESTING.md` §3). The scopes below are explicit so the
    sequence of bindings is visible in the test rather than hidden in fixture nesting.
    """
    with tenant_context("tenant_a"):
        Magasin.objects.create(code="A-ONLY", nom="Chez A")
        assert Magasin.objects.filter(code="A-ONLY").exists()

    with tenant_context("tenant_b"):
        assert not Magasin.objects.filter(code="A-ONLY").exists(), (
            "tenant_b can see tenant_a's magasin. The router is returning the same alias "
            "for both clients, or falling through to default."
        )
        Magasin.objects.create(code="B-ONLY", nom="Chez B")

    with tenant_context("tenant_a"):
        codes = set(Magasin.objects.values_list("code", flat=True))
        assert codes == {"A-ONLY"}, (
            f"tenant_a sees {sorted(codes)}; it must see only its own magasin."
        )


def test_tenant04_every_installed_app_is_classified():
    """`manage.py check` fails for an app that is neither control-plane nor business.

    Asserted in **both** directions: `run_checks()` produces no `tenancy.E001` for the
    real app list, and — with a fabricated unclassified app config patched in — it does.
    A check that can never fire is not a check.

    This is what protects Phases 5, 6 and 7 (threat T-02-20). `allow_migrate` returning
    `None` for an unknown app means Django defaults to `True`, and the new app's tables
    would be created in the control-plane database.
    """
    from plateforme.tenancy import checks as tenancy_checks

    ids = {error.id for error in checks.run_checks()}
    assert "tenancy.E001" not in ids, (
        "An installed app is unclassified today. Add it to CONTROL_PLANE_APPS or "
        "BUSINESS_APPS in plateforme/tenancy/router.py."
    )

    fake = mock.Mock()
    fake.label = "comptabilite"
    fake.name = "domaine.comptabilite"
    with mock.patch.object(
        tenancy_checks.apps,
        "get_app_configs",
        return_value=[*apps.get_app_configs(), fake],
    ):
        errors = tenancy_checks.check_every_app_is_classified(app_configs=None)

    assert [e.id for e in errors] == ["tenancy.E001"], (
        "The check did not fire for an unclassified app. A check that cannot fail is "
        "decoration, and Phase 7's caisse tables would land in the control plane."
    )
    assert "comptabilite" in errors[0].msg


def test_tenant04_every_django_contrib_app_is_skipped_by_the_check():
    """The check skips `django.*` apps, and that exemption must not be wider than that.

    `rest_framework` and `tenancy` do **not** start with `django.`, so both are
    load-bearing members of `CONTROL_PLANE_APPS` rather than padding — omit either and
    `tenancy.E001` fires the moment the check registers.
    """
    unclassified = [
        cfg.label
        for cfg in apps.get_app_configs()
        if not cfg.name.startswith("django.")
        and cfg.label not in CONTROL_PLANE_APPS
        and cfg.label not in BUSINESS_APPS
    ]
    assert unclassified == [], f"unclassified non-django apps: {unclassified}"
    assert "rest_framework" in CONTROL_PLANE_APPS
    assert "tenancy" in CONTROL_PLANE_APPS


def test_tenant04_allow_migrate_never_raises():
    """`allow_migrate` is a build-time path: it returns True/False/None, and never raises.

    Called across the cartesian product of every registered alias and every installed app
    label, plus a fabricated unclassified label. `makemigrations` calls it for every
    alias x app x model, so raising there crashes `makemigrations` from deep inside
    Django, for an alias nobody was thinking about (Pitfall 7).

    The deliberate asymmetry with `_route`, which *does* raise on an unclassified app, is
    that `_route` is a runtime data path where silence is a leak.
    """
    router = TenantRouter()
    labels = [cfg.label for cfg in apps.get_app_configs()] + ["une_app_inconnue"]

    clear()  # unbound on purpose: allow_migrate must not depend on the context either
    for alias in list(connections.settings):
        for label in labels:
            result = router.allow_migrate(alias, label)
            assert result in (True, False, None), (
                f"allow_migrate({alias!r}, {label!r}) returned {result!r}"
            )

    assert router.allow_migrate("default", "control_plane") is True
    assert router.allow_migrate("tenant_a", "control_plane") is False
    assert router.allow_migrate("default", "magasins") is False
    assert router.allow_migrate("tenant_a", "magasins") is True
    assert router.allow_migrate("default", "une_app_inconnue") is None


@pytest.mark.tenancy
def test_tenant04_related_fetch_from_another_tenant_is_refused(db_all):
    """A stale `instance._state.db` must not be allowed to pull rows across tenants.

    Django's documented default is that fetches hinted with an instance follow that
    instance's database. Honouring the hint blindly is a cross-tenant read whenever an
    object outlives the scope it was loaded in (threat T-02-16), so the router compares
    the hint against the bound alias and refuses on disagreement.

    Exercised through a real ORM path, not only through the router's API:
    `Model.refresh_from_db()` builds `hints={"instance": self}` and goes through
    `db_for_read` — the same call a related descriptor makes.
    """
    with tenant_context("tenant_a"):
        magasin = Magasin.objects.create(code="A-REL", nom="Chez A")
    assert magasin._state.db == "tenant_a"

    with tenant_context("tenant_b"):
        with pytest.raises(CrossTenantAccess):
            magasin.refresh_from_db()

        with pytest.raises(CrossTenantAccess):
            TenantRouter().db_for_read(Magasin, instance=magasin)

    # Back on its own tenant the same hint is honoured, not merely tolerated.
    with tenant_context("tenant_a"):
        assert TenantRouter().db_for_read(Magasin, instance=magasin) == "tenant_a"
        magasin.refresh_from_db()

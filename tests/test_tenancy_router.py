"""TENANT-04 — the fail-closed router, and the backstop a router bypass cannot defeat.

`CLAUDE.md`: *"a leak across clients is a security failure, not a bug."* Four layered
defences, so that no single mistake is a breach:

1. The router **raises** when no client is bound. Returning `None` falls through to
   `default`, which is a silent cross-client read.
2. The context is cleared with `set(_UNSET)`, never `reset(token)` — see
   `tests/test_tenancy_context.py`.
3. `allow_migrate` keeps business tables **out of the control-plane database entirely**,
   so a `.using("default")` that bypasses the router hits `relation does not exist`.
   This is the only defence a router bypass cannot defeat.
4. A system check fails at startup if any installed app is unclassified, so defence 3
   cannot silently stop covering an app added in a later phase.

Every import of `plateforme.tenancy.*` here is **function-local**, on purpose. A
module-scope import of a module that does not exist yet turns a pending test into a
*collection error*, which `-m "not pending"` cannot deselect, because deselection happens
after import.
"""

import pytest


@pytest.mark.pending
def test_tenant04_router_raises_when_no_client_bound():
    """With no client bound, a business query raises `NoTenantBound` — it does not fall back.

    `Magasin.objects.count()` with an empty context must raise. Not return an empty
    queryset, not query `default`. Django's `ConnectionRouter._router_func` returns
    `DEFAULT_DB_ALIAS` when every router declines, so "declining" is the leak; raising
    is the only fail-closed answer.

    Pending: needs `plateforme.tenancy.router` and `plateforme.tenancy.context`.
    """
    pytest.fail("pending: implemented by plan 02-03")


@pytest.mark.pending
def test_tenant04_router_never_returns_none():
    """`db_for_read` / `db_for_write` never return a falsy alias, bound or unbound.

    Assert against **falsiness**, not against `is None`. Django's `_router_func` tests
    `if chosen_db:` — so an empty string falls through to `default` exactly as `None`
    does, and a test written as `is not None` would pass against that bug.

    Pending: needs `plateforme.tenancy.router`.
    """
    pytest.fail("pending: implemented by plan 02-03")


@pytest.mark.pending
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

    Pending: needs `TenantRouter.allow_migrate`, so that the test databases are built
    with business tables on the tenants only.
    """
    pytest.fail("pending: implemented by plan 02-03")


@pytest.mark.pending
@pytest.mark.tenancy
def test_tenant04_tenant_a_cannot_read_tenant_b_data():
    """The isolation test itself: two clients, and neither can see the other's rows.

    Under `tenant_context("tenant_a")` create a `Magasin` with a distinguishing code;
    under `tenant_context("tenant_b")` assert it is absent and create a different one;
    back in `tenant_a`, assert only the first is visible.

    Uses both tenant fixtures. The second client is the **control** — with a single
    tenant, a router bug that always returns the same alias passes
    (`.planning/TESTING.md` §3).

    Pending: needs the router and the context.
    """
    pytest.fail("pending: implemented by plan 02-03")


@pytest.mark.pending
def test_tenant04_every_installed_app_is_classified():
    """`manage.py check` fails for an app that is neither control-plane nor business.

    Asserted in **both** directions: `django.core.checks.run_checks()` produces no
    `tenancy.E001` for the real app list, and — with a fabricated unclassified app
    label patched in — it *does*. A check that can never fire is not a check.

    This is what protects Phases 5, 6 and 7 (threat T-02-20): `allow_migrate` returning
    `None` for an unknown app means Django defaults to `True`, and the new app's tables
    are created in the control-plane database.

    Pending: needs `plateforme.tenancy.checks`.
    """
    pytest.fail("pending: implemented by plan 02-03")


@pytest.mark.pending
def test_tenant04_allow_migrate_never_raises():
    """`allow_migrate` is a build-time path: it must return True/False/None, never raise.

    Called across the cartesian product of every registered alias and every installed
    app label, plus a fabricated unclassified label. `makemigrations` calls it for every
    alias x app x model, so raising there crashes `makemigrations` from deep inside
    Django, for an alias nobody was thinking about (Pitfall 7).

    The deliberate asymmetry with `_route`, which *does* raise on an unclassified app, is
    that `_route` is a runtime data path where silence is a leak.

    Pending: needs `plateforme.tenancy.router`.
    """
    pytest.fail("pending: implemented by plan 02-03")


@pytest.mark.pending
@pytest.mark.tenancy
def test_tenant04_related_fetch_from_another_tenant_is_refused():
    """A stale `instance._state.db` must not be allowed to pull rows across tenants.

    Load an instance under `tenant_a`, then inside `tenant_context("tenant_b")` touch a
    related descriptor on it, and assert `CrossTenantAccess`.

    Django's documented default is that related fetches follow the instance's database
    hint. Honouring that hint blindly is a cross-tenant read whenever an object outlives
    the scope it was loaded in (threat T-02-16), so the router compares the hint against
    the bound alias and refuses on disagreement.

    Pending: needs the router's hint handling.
    """
    pytest.fail("pending: implemented by plan 02-03")

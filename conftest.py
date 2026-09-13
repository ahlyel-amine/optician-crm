"""Session-wide test configuration.

Lives at the repository root rather than inside `tests/` so that `pytest_sessionstart`
applies to the whole session regardless of which paths are selected.

**Nothing here overrides pytest-django's database-setup or db-settings-modification
fixtures, and nothing ever should.** They look like the obvious hook for registering
tenant aliases and they silently break pytest-xdist:
`django_db_modify_db_settings_xdist_suffix` runs *first*, so aliases introduced inside an
override never receive the `_gw0` worker suffix and parallel workers then collide on the
same test databases. The static `tenant_a` / `tenant_b`
aliases declared in `config/settings/test.py` already give creation, migration, teardown,
per-test rollback and xdist suffixing for free. See `.planning/TESTING.md` §3 and
`02-RESEARCH.md` Pitfall 8.

Runtime alias registration is exercised deliberately by a small number of `slow` tests
that do real `CREATE DATABASE`, not by making the whole suite imitate production.
"""

from __future__ import annotations

import warnings

import pytest

#: Every alias the tenancy suite may touch. `default` is the control plane; `tenant_a`
#: and `tenant_b` are two *different* clients, because isolation cannot be proved against
#: a single tenant.
TENANT_DBS = ["default", "tenant_a", "tenant_b"]

#: SQL LIKE patterns for databases the reaper below is allowed to drop. Anchored to the
#: test prefixes and nothing else (threat T-02-09): a pattern such as `%` or `optique_%`
#: would destroy developer data on the same PostgreSQL instance.
STALE_TEST_DB_PATTERNS = [
    "test_optique_test_%",  # test_optique_test_a / _b, plus any `_gw0` xdist suffix
    "test_client_%",  # databases created by the provisioning tests
]

#: The same prefixes, as a belt-and-braces guard applied per name immediately before the
#: DROP is issued. The LIKE pattern and this check must both agree.
STALE_TEST_DB_PREFIXES = ("test_optique_test_", "test_client_")


def pytest_sessionstart(session):
    """Drop test databases left behind by a crashed previous run, before anything starts.

    Cleaning at session **start** rather than at the end is deliberate: a `SIGKILL` never
    gets to run your teardown, and a crashed run that left `test_client_*` databases
    behind makes the next run's provisioning test fail for the wrong reason — which is
    the most expensive kind of red, because it points at the wrong file.

    Defensive on two axes:

    * **Scope.** Only names matching `STALE_TEST_DB_PREFIXES` are ever dropped, checked
      twice — once as a bound `LIKE` pattern in the query, once per name here.
    * **Availability.** If PostgreSQL is unreachable (someone is running the unit tests
      without Compose up), warn and continue. Refusing to start the session would make a
      pure-settings test run depend on Docker.

    Skipped inside pytest-xdist workers: each worker would otherwise drop the databases
    of the workers that started before it. `workerinput` exists only on workers, so the
    reaper runs once, in the controlling process, before any worker starts.
    """
    if hasattr(session.config, "workerinput"):
        return

    try:
        from plateforme.tenancy.maintenance import (
            databases_matching,
            drop_database_force,
            maintenance_connection,
        )

        with maintenance_connection() as cur:
            stale = databases_matching(cur, STALE_TEST_DB_PATTERNS)
            for name in stale:
                if not name.startswith(STALE_TEST_DB_PREFIXES):
                    # Unreachable given the LIKE patterns above, and that is the point:
                    # if someone widens them, this refuses rather than obeys.
                    warnings.warn(
                        f"Refusing to drop {name!r}: it does not match a test-database "
                        f"prefix. Check STALE_TEST_DB_PATTERNS in conftest.py.",
                        stacklevel=1,
                    )
                    continue
                drop_database_force(cur, name)
            if stale:
                print(f"\nreaped {len(stale)} stale test database(s): {', '.join(stale)}")
    except Exception as exc:  # noqa: BLE001 — availability must not fail the session
        warnings.warn(
            f"Stale-test-database reaper skipped: {exc!r}. This is only a problem if a "
            "previous run crashed; bring Compose up if the provisioning tests fail.",
            stacklevel=1,
        )


#: Fixtures whose users need all three aliases created, not just `default`.
TENANCY_FIXTURES = frozenset({"db_all", "tenant_a", "tenant_b"})


def pytest_collection_modifyitems(items):
    """Mark every tenancy test with `django_db(databases=TENANT_DBS)` **at collection time**.

    This is a timing fix, not a preference. pytest-django decides which test databases to
    *create* in its session-scoped setup fixture, from
    `_get_databases_for_setup(request.session.items)`, which reads each item's
    `django_db` marker. A marker applied from inside a fixture body arrives after that
    decision for every item except the one that happens to trigger the setup first — so a
    run whose first database test asks only for `default` (as
    `tests/test_tenancy_router.py` does) creates only `default`, and the tenancy tests
    that follow connect to the *production* `optique_test_a` instead of
    `test_optique_test_a`. Observed, not theorised.

    Applying the marker during collection puts it where pytest-django looks. This is
    still not an override of the database-setup fixture — the aliases remain static in
    `config/settings/test.py`, so creation, migration, teardown, per-test rollback and
    xdist `_gw0` suffixing all keep working.
    """
    for item in items:
        if TENANCY_FIXTURES & set(getattr(item, "fixturenames", ())):
            # append=False so this is the closest marker, beating a narrower
            # `django_db()` the test may also carry.
            item.add_marker(pytest.mark.django_db(databases=TENANT_DBS), append=False)


@pytest.fixture
def db_all(request):
    """Grant the test access to every alias in `TENANT_DBS`, each rolled back per test.

    `pytest.mark.django_db(databases=TENANT_DBS)` builds a `TestCase` subclass whose
    `databases` covers all three, so each one is wrapped in a transaction and rolled
    back — including the two tenants. The marker is normally already present from
    `pytest_collection_modifyitems` above; applying it here too is idempotent and keeps
    the fixture correct when used through an unusual collection path.
    """
    request.applymarker(pytest.mark.django_db(databases=TENANT_DBS))
    return request.getfixturevalue("_django_db_helper")


@pytest.fixture
def tenant_a(db_all):
    """Bind client A's connection for the duration of the test."""
    from plateforme.tenancy.context import tenant_context

    with tenant_context("tenant_a"):
        yield "tenant_a"


@pytest.fixture
def tenant_b(db_all):
    """Client B — **the control**, and the reason there are two tenant fixtures.

    A single test tenant cannot prove isolation: with one tenant, a router bug that
    always returns the same alias passes every test in the suite. Every isolation test
    needs a second client whose data must **not** appear (`.planning/TESTING.md` §3).
    """
    from plateforme.tenancy.context import tenant_context

    with tenant_context("tenant_b"):
        yield "tenant_b"

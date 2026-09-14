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

#: Roles the provisioning tests create. They are **cluster-wide**, so dropping the
#: databases does not remove them, and a role left behind by a killed run is a landmine:
#: a later run that reaches the same primary key stores a fresh password, finds the role
#: already present, and produces a client that cannot authenticate — failing in a step
#: nowhere near the cause. `create_role_if_absent` now converges the password, so this is
#: the second of two defences rather than the only one.
STALE_TEST_ROLE_PREFIX = "test_client_u"


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

            # Roles, after the databases that depend on them. `starts_with`, never a
            # LIKE pattern: `_` is a single-character wildcard in LIKE, so
            # `test_client_u%` would also match names this has no business touching.
            from psycopg import sql

            cur.execute(
                "SELECT rolname FROM pg_roles WHERE starts_with(rolname, %s) ORDER BY 1",
                (STALE_TEST_ROLE_PREFIX,),
            )
            roles = [row[0] for row in cur.fetchall()]
            for role in roles:
                if not role.startswith(STALE_TEST_ROLE_PREFIX):
                    continue  # unreachable; refuses rather than obeys if widened
                cur.execute(
                    sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role))
                )
            if roles:
                print(f"reaped {len(roles)} stale test role(s): {', '.join(roles)}")
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


class _RuntimeTenantAliasesAllowed(frozenset):
    """A `databases` set that also answers "yes" for any runtime `tenant_<pk>` alias.

    Iteration is unchanged — it still yields only the statically declared aliases, so
    fixture setup, flushing and teardown behave exactly as before. Only ``in`` is widened.
    """

    def __contains__(self, item) -> bool:
        return super().__contains__(item) or str(item).startswith("tenant_")


def _active_test_case_class():
    """The `PytestDjangoTestCase` guarding the current test, or None.

    `SimpleTestCase._add_databases_failures` installs
    `ensure_connection_patch_method()` — a closure over the test case class — onto
    `BaseDatabaseWrapper.ensure_connection`. The class is defined inside a pytest-django
    fixture and is not otherwise reachable, so it is read back out of that closure.
    """
    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.test import SimpleTestCase

    guard = BaseDatabaseWrapper.ensure_connection
    for cell in getattr(guard, "__closure__", None) or ():
        try:
            value = cell.cell_contents
        except ValueError:  # pragma: no cover — an empty cell
            continue
        if isinstance(value, type) and issubclass(value, SimpleTestCase):
            return value
    return None


@pytest.fixture
def allow_runtime_tenant_aliases(request):
    """Let *this* test open connections to `tenant_<pk>` aliases it creates at runtime.

    Why it is needed. Django's `SimpleTestCase.ensure_connection_patch_method` refuses any
    alias that is present in `connections` but absent from the test case's `databases`::

        if (self.connection is None and self.alias not in cls.databases
                and self.alias != NO_DB_ALIAS
                and self.alias in connections):        # <- the escape hatch
            ... DatabaseOperationForbidden

    The escape hatch — *"dynamically created connections are always allowed"* — tests
    `alias in connections`, which is `alias in connections.settings`. A runtime alias
    registered by `register_client_database` **is** in `connections.settings`, so it does
    not qualify, and `cls.databases` was frozen at class setup, before the client this
    test provisions existed. Observed, not theorised: without this fixture the
    provisioning tests fail with *"Database threaded connections to 'tenant_7' are not
    allowed in this test"*.

    Why it is opt-in rather than global. The guard is load-bearing for every other test:
    plan 02-03's `bound_to_test_aliases` fixture exists precisely because a test that
    quietly connects to an alias nobody tears down is a leak. Only the handful of tests
    that do real `CREATE DATABASE` — the ones `.planning/TESTING.md` §3 says should "pay
    that cost explicitly" — ask for this, and each of them drops what it created in a
    `finally`.

    What it does **not** do: it does not touch `default`, `tenant_a` or `tenant_b`, it
    does not override pytest-django's database-setup fixture, and it restores the original
    `databases` value on teardown.
    """
    request.getfixturevalue("_django_db_helper")

    cls = _active_test_case_class()
    if cls is None:  # pragma: no cover — pytest-django changed shape
        raise RuntimeError(
            "Could not find the active PytestDjangoTestCase behind "
            "BaseDatabaseWrapper.ensure_connection. pytest-django's internals have "
            "changed; allow_runtime_tenant_aliases in conftest.py needs updating. "
            "Failing loudly rather than silently leaving the guard in place, because a "
            "silent failure here looks like a provisioning bug."
        )

    original = cls.databases
    cls.databases = _RuntimeTenantAliasesAllowed(original)
    try:
        yield
    finally:
        cls.databases = original


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


#: Les deux magasins que `deux_magasins` crée, dans l'ordre. Deux **codes distincts et
#: reconnaissables** plutôt que `MAG001` / `MAG002` : une assertion qui échoue en disant
#: « attendu ANFA, obtenu MAARIF » se lit, là où deux codes séquentiels demandent de
#: remonter à la fixture pour savoir lequel était lequel.
MAGASINS_PAR_DEFAUT = (
    ("ANFA", "Optique Anfa"),
    ("MAARIF", "Optique Maârif"),
)


def _creer_magasins(codes=MAGASINS_PAR_DEFAUT):
    """Crée les magasins nommés dans le locataire **actuellement lié**, et les renvoie.

    Aucun alias n'est nommé : `MagasinFactory` laisse le routeur résoudre la connexion
    depuis le contexte, ce qui est exactement le mécanisme que la suite de tenancy existe
    pour vérifier. Un `using=` ici serait un contournement déguisé.
    """
    from tests.factories import MagasinFactory

    return [MagasinFactory(code=code, nom=nom, actif=True) for code, nom in codes]


@pytest.fixture
def deux_magasins(tenant_a):
    """**Deux** magasins actifs chez le client A — jamais un seul.

    Même argument que `tenant_b`, un cran plus bas dans la hiérarchie. Un test de portée
    magasin qui ne dispose que d'un magasin ne prouve rien : une vue qui ignore
    complètement la portée, ou qui renvoie toujours le même magasin, passe chaque
    assertion, parce que la bonne réponse et la mauvaise sont le même objet. Il faut un
    second magasin dont les lignes doivent **ne pas** apparaître, exactement comme il faut
    un second locataire (`03-RESEARCH.md` P16, `.planning/TESTING.md` §3).

    C'est aussi la forme que PERM-04 exige : un gérant a accès à `ANFA` et pas à `MAARIF`,
    et le droit accordé sur l'un ne fuit pas vers l'autre (CLAUDE.md #13).

    Renvoie `[anfa, maarif]`, dans cet ordre.
    """
    return _creer_magasins()


@pytest.fixture
def magasins_du_client_b(tenant_b):
    """Les mêmes deux magasins, chez le client B — le contrôle d'isolation croisée.

    Les codes sont **identiques** à ceux du client A, délibérément. Deux opticiens
    marocains peuvent parfaitement avoir tous les deux un magasin « ANFA », et un bug qui
    résout un magasin par son code sans passer par la connexion du locataire rendrait
    alors les données de l'autre affaire. Des codes distincts par locataire cacheraient ce
    bug derrière une collision qui n'arrive jamais en test.
    """
    return _creer_magasins()

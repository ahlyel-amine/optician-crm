"""TENANT-01 / TENANT-05 / TENANT-06 — provisioning a client's database.

`CREATE DATABASE` cannot be executed inside a transaction block, so "completes or rolls
back cleanly" (TENANT-05) **cannot** be one atomic transaction. It is a status state
machine with compensating cleanup, where the control-plane `Client` row is the durable
record of intent and the only transactional part of it.

The invariant that makes TENANT-05 true: **only ACTIVE clients are ever routed to or
migrated.** A half-provisioned client is simply not visible to the rest of the system.
FAILED rows are visible to the operator, not to the router.

These tests do real `CREATE DATABASE` against Compose, so they are `slow` and need
`transaction=True` — the transaction that `TestCase` opens would make the DDL impossible.

**Safety.** Every database these tests create is named from `settings.TENANT_DB_NAME_PREFIX`,
which `config/settings/test.py` overrides to `test_client_c`. That is deliberate and it is
not cosmetic: production derives `optique_c000001` from a primary key, and a test control
plane starts its primary keys at 1 too, so sharing the prefix would make a test run *adopt
and then drop* a developer's real `optique_c000001`. The test prefix also matches the
`test_client_%` pattern the session-start reaper in `conftest.py` already collects, so a
run killed with SIGKILL is cleaned up by the next one. Cleanup here drops databases **by
exact name only**, never by pattern.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.db import connections
from psycopg import sql

from plateforme.control_plane.models import Client
from plateforme.tenancy.maintenance import (
    database_exists,
    drop_database_force,
    maintenance_connection,
)
from plateforme.tenancy.registry import alias_for


# --------------------------------------------------------------------------------------
# Cleanup — exact names only
# --------------------------------------------------------------------------------------
def _destroy(code: str) -> None:
    """Drop everything the named client owns, by exact name, and forget its alias.

    Refuses to touch anything whose name does not carry the configured test prefixes.
    A cleanup path that drops by pattern is one bad predicate away from destroying a
    live client (the same reasoning as `reap_orphan_databases`), so this one never
    composes a pattern at all.
    """
    client = Client.objects.using("default").filter(code=code).first()
    if client is None:
        return

    alias = alias_for(client.pk)
    if alias in connections.settings:
        try:
            connections[alias].close()
            del connections[alias]
        except (AttributeError, KeyError):
            pass

    with maintenance_connection() as cur:
        if client.db_name:
            assert client.db_name.startswith(settings.TENANT_DB_NAME_PREFIX), (
                f"refusing to drop {client.db_name!r}: it does not carry the configured "
                f"prefix {settings.TENANT_DB_NAME_PREFIX!r}"
            )
            drop_database_force(cur, client.db_name)
        if client.db_user:
            assert client.db_user.startswith(settings.TENANT_DB_USER_PREFIX), (
                f"refusing to drop role {client.db_user!r}"
            )
            # Roles are cluster-wide and survive DROP DATABASE. Leaving one behind makes
            # the next run's CREATE ROLE a no-op, which is harmless, but it also leaks a
            # login account on a shared instance.
            cur.execute(
                sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(client.db_user))
            )

    Client.objects.using("default").filter(pk=client.pk).delete()


def _count_client_databases() -> int:
    """How many databases carry a name `derive_db_name` could have produced.

    `starts_with`, never `LIKE '<prefix>%'` — `_` is a single-character wildcard in SQL
    LIKE, so `optique_c%` also matches `optique_control`.
    """
    from plateforme.control_plane.provisioning import is_client_database_name

    with maintenance_connection() as cur:
        cur.execute(
            "SELECT datname FROM pg_database WHERE starts_with(datname, %s)",
            (settings.TENANT_DB_NAME_PREFIX,),
        )
        return sum(1 for (name,) in cur.fetchall() if is_client_database_name(name))


# --------------------------------------------------------------------------------------
# TENANT-01
# --------------------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant01_provision_client_creates_database_at_migration_head(
    allow_runtime_tenant_aliases,
):
    """TENANT-01: after `provision_client`, a real database exists, migrated to head.

    Assert more than "no exception was raised". The database appears in `pg_database`;
    `pending_plan(alias)` is empty, so it is at head rather than merely created; and the
    `Client` row is ACTIVE with `applied_heads` recorded and `provisioned_at` set.

    Asserting on `applied_heads` rather than on a version integer is the point of
    TENANT-02's shape: several business apps have independent migration chains, so a
    single number cannot express "stock is at 0004 but facturation is at 0011".
    """
    from plateforme.control_plane.provisioning import provision_client
    from plateforme.control_plane.schema_version import pending_plan, read_applied_heads

    code = "test-a"
    try:
        client = provision_client(
            code=code, raison_sociale="Optique Test A SARL", magasins=["Centre"]
        )

        assert client.status == Client.ACTIVE
        assert client.provisioned_at is not None
        assert client.db_name.startswith(settings.TENANT_DB_NAME_PREFIX)

        with maintenance_connection() as cur:
            assert database_exists(cur, client.db_name), (
                f"{client.db_name} is not in pg_database — the row says ACTIVE but no "
                "database was created."
            )

        alias = alias_for(client.pk)
        assert pending_plan(alias) == [], (
            "the database is not at the current migration head; it was created but not "
            "fully migrated, which is what TENANT-01 forbids."
        )

        assert client.applied_heads, "applied_heads was never recorded"
        assert client.applied_heads == read_applied_heads(alias)
        assert "magasins" in client.applied_heads, (
            f"no business app in applied_heads: {client.applied_heads!r}"
        )
        assert client.schema_digest, "schema_digest was never computed"
        assert client.schema_checked_at is not None

        # Negative control. `pending_plan(alias) == []` above is only evidence if
        # `pending_plan` can also say "behind" — with one business migration in the tree,
        # an assertion that a plan is empty would otherwise pass against a function that
        # always returns []. Roll the client back and watch it report the gap.
        from django.core.management import call_command

        call_command("migrate", "magasins", "zero", database=alias, verbosity=0)
        assert pending_plan(alias), (
            "pending_plan reported nothing to do on a database rolled back to zero, so "
            "the 'at migration head' assertion above proves nothing."
        )
    finally:
        _destroy(code)


# --------------------------------------------------------------------------------------
# TENANT-05
# --------------------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant05_failed_provisioning_leaves_no_active_client(
    allow_runtime_tenant_aliases,
):
    """A provisioning run that fails leaves the row FAILED, never ACTIVE — and invisible.

    Force a failure at the migrate step and assert the `Client` ends FAILED with
    `last_error` populated. Then assert the part that actually matters: **the client is
    invisible to the router**, because the router and `migrate_all` both select on
    `Client.ROUTABLE_STATUSES`. An ACTIVE row is a promise that a working database exists
    behind it; the `active_client_has_db_name` CHECK constraint is the same promise
    stated at the database level (threat T-02-08, T-02-24).

    The exception must also propagate: swallowing it here would make a failed provision
    look like a success to the operator and to the Phase 12 self-serve flow.
    """
    from plateforme.control_plane.provisioning import provision_client

    code = "test-fail"
    boom = RuntimeError("migrate exploded on purpose")
    try:
        with patch(
            "plateforme.control_plane.provisioning.call_command", side_effect=boom
        ):
            with pytest.raises(RuntimeError, match="migrate exploded on purpose"):
                provision_client(
                    code=code, raison_sociale="Optique Fail SARL", magasins=["Centre"]
                )

        client = Client.objects.using("default").get(code=code)
        assert client.status == Client.FAILED
        assert "migrate exploded on purpose" in client.last_error

        # Invisibility, not merely status. This is the query the middleware and the
        # fan-out both make.
        routable = Client.objects.using("default").filter(
            code=code, status__in=Client.ROUTABLE_STATUSES
        )
        assert not routable.exists(), (
            "a half-provisioned client is reachable by the router's own query — "
            "TENANT-05's invariant is broken."
        )
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant05_rerun_after_kill_converges_to_active(allow_runtime_tenant_aliases):
    """A run killed after `CREATE DATABASE` converges to ACTIVE when rerun.

    That is what idempotent means here, and each step earns it separately: identity via
    `get_or_create(code=...)` with `db_name` derived from the pk and never regenerated;
    `CREATE ROLE` and `CREATE DATABASE` guarded by existence checks; `migrate` idempotent
    for free through `django_migrations`; seeding `get_or_create` only; activation a
    single transactional UPDATE.
    """
    from plateforme.control_plane.provisioning import provision_client
    from plateforme.control_plane.schema_version import pending_plan

    code = "test-rerun"
    try:
        # Kill: the database and role are created, then migrate raises.
        with patch(
            "plateforme.control_plane.provisioning.call_command",
            side_effect=RuntimeError("killed"),
        ):
            with pytest.raises(RuntimeError):
                provision_client(
                    code=code, raison_sociale="Optique Rerun SARL", magasins=["Centre"]
                )

        killed = Client.objects.using("default").get(code=code)
        assert killed.status == Client.FAILED
        with maintenance_connection() as cur:
            assert database_exists(cur, killed.db_name), (
                "the kill was staged in the wrong place: no database exists, so the "
                "rerun is not exercising adoption of a half-created client."
            )

        # Rerun, unpatched, with the same code.
        client = provision_client(
            code=code, raison_sociale="Optique Rerun SARL", magasins=["Centre"]
        )

        assert client.pk == killed.pk, "the rerun created a second Client row"
        assert client.db_name == killed.db_name, "the rerun regenerated db_name"
        assert client.status == Client.ACTIVE
        assert Client.objects.using("default").filter(code=code).count() == 1
        assert pending_plan(alias_for(client.pk)) == []
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant05_rerun_creates_no_second_database(allow_runtime_tenant_aliases):
    """Rerunning provisioning must not orphan a database.

    Count `pg_database` entries carrying the client prefix before and after the rerun and
    assert the count is unchanged and that `Client.db_name` still names the original.

    This is why `db_name` is derived from the primary key rather than generated fresh: a
    regenerated name on rerun would leave the first database behind with no `Client` row
    pointing at it, and a true orphan is only reapable by hand.
    """
    from plateforme.control_plane.provisioning import provision_client

    code = "test-noorph"
    try:
        first = provision_client(
            code=code, raison_sociale="Optique NoOrphan SARL", magasins=["Centre"]
        )
        before = _count_client_databases()

        second = provision_client(
            code=code, raison_sociale="Optique NoOrphan SARL", magasins=["Centre"]
        )
        after = _count_client_databases()

        assert after == before, (
            f"the rerun created {after - before} extra database(s) carrying the "
            f"{settings.TENANT_DB_NAME_PREFIX!r} prefix."
        )
        assert second.pk == first.pk
        assert second.db_name == first.db_name
        assert Client.objects.using("default").filter(code=code).count() == 1
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant05_provisioning_is_idempotent_for_an_already_active_client(
    allow_runtime_tenant_aliases,
):
    """Calling `provision_client` on an ACTIVE client touches no DDL at all.

    Not in the validation map, and cheap: it pins the early return that makes the
    operator's "did that work? let me run it again" harmless. Asserted against the
    provisioner rather than against the result, because the result looks identical either
    way.
    """
    from plateforme.control_plane.provisioning import provision_client

    code = "test-noop"
    try:
        client = provision_client(
            code=code, raison_sociale="Optique NoOp SARL", magasins=["Centre"]
        )
        assert client.status == Client.ACTIVE

        with patch(
            "plateforme.control_plane.provisioning.get_provisioner"
        ) as get_provisioner:
            get_provisioner.return_value = MagicMock()
            again = provision_client(
                code=code, raison_sociale="Optique NoOp SARL", magasins=["Centre"]
            )

        assert again.pk == client.pk
        get_provisioner.assert_not_called()
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant05_deprovision_drops_the_database_but_keeps_the_row(
    allow_runtime_tenant_aliases,
):
    """Deprovisioning drops the database and marks the row DELETED. The row survives.

    Art. 211 CGI requires ten years of record retention, and the audit trail wants to
    know a client existed. `Client` rows are therefore never deleted — the status is the
    tombstone.
    """
    from plateforme.control_plane.provisioning import deprovision_client, provision_client

    code = "test-deprov"
    try:
        client = provision_client(
            code=code, raison_sociale="Optique Deprov SARL", magasins=["Centre"]
        )
        db_name = client.db_name

        deprovision_client(client)

        assert client.status == Client.DELETED
        with maintenance_connection() as cur:
            assert not database_exists(cur, db_name)
        assert Client.objects.using("default").filter(code=code).exists(), (
            "the Client row was deleted; deprovisioning must leave a tombstone."
        )
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.tenancy
@pytest.mark.django_db(transaction=True)
def test_tenant04_a_client_role_cannot_connect_to_another_clients_database(
    allow_runtime_tenant_aliases,
):
    """Isolation below the application: client A's role is refused by client B's database.

    PostgreSQL grants `CONNECT` on a new database to `PUBLIC`, so without an explicit
    revoke every client's login role can open every other client's database. The router
    would never do it — but "the application would never" is not an isolation boundary,
    and database-per-client exists precisely so the boundary sits below the application.

    Two clients, because one cannot prove isolation (`.planning/TESTING.md` §3). The
    positive half matters as much as the negative one: A must still be able to open its
    *own* database, or the revoke has simply broken everything.
    """
    import psycopg

    from plateforme.control_plane.provisioning import provision_client

    code_a, code_b = "test-iso-a", "test-iso-b"
    try:
        a = provision_client(
            code=code_a, raison_sociale="Optique Iso A", magasins=["Centre"]
        )
        b = provision_client(
            code=code_b, raison_sociale="Optique Iso B", magasins=["Centre"]
        )

        def _connect(as_client, to_db):
            return psycopg.connect(
                host=settings.PG_ADMIN_HOST,
                port=settings.PG_ADMIN_PORT,
                user=as_client.db_user,
                password=as_client.db_password,
                dbname=to_db,
                connect_timeout=5,
            )

        with _connect(a, a.db_name) as own:
            with own.cursor() as c:
                c.execute("SELECT current_database()")
                assert c.fetchone()[0] == a.db_name

        with pytest.raises(psycopg.OperationalError) as excinfo:
            _connect(a, b.db_name).close()
        assert "permission denied" in str(excinfo.value).lower(), (
            f"client A reached client B's database. PostgreSQL said: {excinfo.value}"
        )
    finally:
        _destroy(code_a)
        _destroy(code_b)


# --------------------------------------------------------------------------------------
# TENANT-06 — the operator entry point
# --------------------------------------------------------------------------------------
def test_tenant06_management_command_delegates_to_provision_client():
    """The command parses arguments and calls `provision_client`. Nothing more.

    Repeated `--magasin` arrives as a list, which is the whole of TENANT-07's provisioning
    half reaching the state machine unmodified.

    No database, no DDL — the point of the test is the delegation, and patching the
    function is what makes it fast enough to live in the quick loop.
    """
    from django.core.management import call_command

    target = (
        "plateforme.control_plane.management.commands.provision_client.provision_client"
    )
    with patch(target) as provision:
        provision.return_value = MagicMock(
            code="OPT001", db_name="optique_c000001", db_host="h", schema_digest="d"
        )
        call_command(
            "provision_client",
            "--code",
            "OPT001",
            "--raison-sociale",
            "Optique Centre SARL",
            "--magasin",
            "Centre",
            "--magasin",
            "Maarif",
        )

    provision.assert_called_once_with(
        code="OPT001",
        raison_sociale="Optique Centre SARL",
        magasins=["Centre", "Maarif"],
        db_host=None,
    )


def test_tenant06_command_module_contains_no_provisioning_logic():
    """A source-level assertion, because the failure mode is drift rather than a wrong answer.

    Phase 12's self-serve signup calls `provision_client` from a Celery task, not this
    command. Any logic that migrates here is logic self-serve will not have, and that
    divergence would be discovered by a customer rather than by a test. Reading the source
    is the only thing that catches a line added later.
    """
    import inspect

    from plateforme.control_plane.management.commands import provision_client as module

    source = inspect.getsource(module)
    forbidden = (
        "CREATE DATABASE",
        'call_command("migrate"',
        "sql.Identifier",
        "maintenance_connection",
        "Client.objects",
    )
    for needle in forbidden:
        assert needle not in source, (
            f"{needle!r} appears in the provision_client command. Provisioning logic "
            "belongs in plateforme/control_plane/provisioning.py, which is what the "
            "Phase 12 self-serve flow will call."
        )


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant06_reap_orphan_databases_never_drops_a_known_client_database():
    """Threat T-02-25: a database belonging to a FAILED client is not an orphan.

    A database created before a kill has a `Client` row in CREATING_DB or FAILED, and a
    rerun adopts it. Only a `pg_database` entry with no matching `Client.db_name` in
    **any** status is an orphan, and that only arises from manual meddling.

    Also asserts the command is dry-run by default: a command that drops databases based
    on a diff is one bad predicate away from destroying a live client.
    """
    import io

    from django.core.management import call_command

    from plateforme.control_plane.provisioning import derive_db_name, derive_db_user

    code = "test-reap"
    client = Client.objects.using("default").create(
        code=code,
        raison_sociale="Optique Reap SARL",
        status=Client.FAILED,
        db_host=settings.PG_ADMIN_HOST,
        db_port=settings.PG_ADMIN_PORT,
    )
    client.db_name = derive_db_name(client.pk)
    client.db_user = derive_db_user(client.pk)
    client.save(using="default")

    orphan_name = f"{settings.TENANT_DB_NAME_PREFIX}999999"
    # The bait that caught the real bug. With the prefix `optique_c`, the obvious
    # predicate `datname LIKE 'optique_c%'` matches `optique_control`, because `_` is a
    # single-character wildcard in SQL LIKE — and so does `str.startswith`. The first run
    # of this command against the development stack reported the control-plane database
    # itself as an orphan. Under the test prefix the same shape is `test_client_control`.
    lookalike = f"{settings.TENANT_DB_NAME_PREFIX}ontrol"
    try:
        with maintenance_connection() as cur:
            cur.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(client.db_name))
            )
            cur.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(orphan_name))
            )
            cur.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(lookalike))
            )

        out = io.StringIO()
        call_command("reap_orphan_databases", stdout=out)
        report = out.getvalue()

        assert lookalike not in report, (
            f"{lookalike} was reported as an orphan. It is not a name derive_db_name "
            "could produce — the predicate is matching on a prefix rather than on the "
            f"full shape, which is how `optique_control` becomes a reap target.\n{report}"
        )
        assert client.db_name not in report, (
            f"{client.db_name} was reported as an orphan, but its Client row exists in "
            f"{client.status}. A rerun adopts that database; dropping it would destroy "
            "a half-provisioned client's work (threat T-02-25)."
        )
        assert orphan_name in report, (
            "the reaper reported no orphan at all, so the assertion above proves "
            f"nothing. Expected {orphan_name} in:\n{report}"
        )

        # Dry-run is the default: both databases must still exist afterwards.
        with maintenance_connection() as cur:
            assert database_exists(cur, client.db_name)
            assert database_exists(cur, orphan_name), (
                "the reaper dropped a database without --yes-i-am-sure."
            )
    finally:
        with maintenance_connection() as cur:
            for name in (orphan_name, lookalike):
                assert name.startswith(settings.TENANT_DB_NAME_PREFIX)
                drop_database_force(cur, name)
        _destroy(code)

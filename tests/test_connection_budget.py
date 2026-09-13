"""TENANT-08 — the connection budget is a set of configuration invariants.

TENANT-08 is not a feature. It is four one-line settings, and those four lines are the
entire difference between "server connections scale with concurrency" and "server
connections scale with client count". At 300 clients the second one pages someone.

These tests read `django.conf.settings` and a parsed ini file. They touch no database,
so they run in milliseconds and belong in the quick loop. They exist so that
configuration drift turns the suite red rather than surfacing as a production incident.

Every settings test iterates `settings.DATABASES` rather than naming aliases, so it
automatically covers `tenant_a`, `tenant_b` and any alias a future phase adds.
"""

import configparser
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from django.conf import settings
from django.db import close_old_connections, connections
from psycopg import sql

PGBOUNCER_INI = Path(__file__).resolve().parent.parent / "docker" / "pgbouncer" / "pgbouncer.ini"


def test_tenant08_conn_max_age_is_zero_on_every_alias():
    for alias, cfg in settings.DATABASES.items():
        assert cfg.get("CONN_MAX_AGE") == 0, (
            f"DATABASES[{alias!r}]['CONN_MAX_AGE'] is {cfg.get('CONN_MAX_AGE')!r}, must be 0. "
            "CONN_MAX_AGE > 0 makes each worker thread hold a *client* connection per alias it "
            "has ever touched, so client connections become C_web x N_touched and blow through "
            "PgBouncer's max_client_conn. PgBouncer owns pooling, not Django (TENANT-08)."
        )


def test_tenant08_no_alias_has_atomic_requests():
    for alias, cfg in settings.DATABASES.items():
        assert bool(cfg.get("ATOMIC_REQUESTS", False)) is False, (
            f"DATABASES[{alias!r}]['ATOMIC_REQUESTS'] is truthy. CLAUDE.md non-negotiable #12: "
            "BaseHandler.make_view_atomic() iterates *every* alias in connections.settings and "
            "wraps the view in transaction.atomic(using=alias) for each one. With 300 clients "
            "registered that is 300 transactions per request. Use explicit atomic() blocks."
        )


def test_tenant08_server_side_cursors_are_disabled():
    for alias, cfg in settings.DATABASES.items():
        assert cfg.get("DISABLE_SERVER_SIDE_CURSORS") is True, (
            f"DATABASES[{alias!r}]['DISABLE_SERVER_SIDE_CURSORS'] is "
            f"{cfg.get('DISABLE_SERVER_SIDE_CURSORS')!r}, must be True. Server-side cursors are "
            "local to a connection and remain open at the end of a transaction under AUTOCOMMIT "
            "— which is exactly the moment transaction-mode pooling hands that server connection "
            "to somebody else (TENANT-08)."
        )


def test_tenant08_pgbouncer_holds_no_idle_connections_per_idle_client():
    """The PgBouncer half of TENANT-08. Parses the ini; needs no running container."""
    config = configparser.ConfigParser()
    read = config.read(PGBOUNCER_INI)
    assert read, f"{PGBOUNCER_INI} not found — the pooling topology is not configured."

    pgb = config["pgbouncer"]

    assert pgb.get("pool_mode") == "transaction", (
        f"pool_mode is {pgb.get('pool_mode')!r}, must be 'transaction'. Session pooling "
        "holds one server connection per client connection for the whole session, which "
        "is the connection budget we are specifically trying not to have."
    )

    assert int(pgb.get("min_pool_size")) == 0, (
        f"min_pool_size is {pgb.get('min_pool_size')!r}, must be 0. Pools are keyed by "
        "(user, database), so N client databases means N pools. Any value above zero "
        "makes every *idle* client hold that many server connections, turning the budget "
        "from O(concurrency) into O(client_count): 300 clients x 5 = 1500 server "
        "connections against a max_connections of 200 (TENANT-08, threat T-02-01)."
    )

    assert int(pgb.get("max_client_conn")) >= 1000, (
        f"max_client_conn is {pgb.get('max_client_conn')!r}, must be >= 1000. It has to "
        "exceed peak app concurrency (gunicorn workers x threads, plus Celery "
        "concurrency) with generous margin, or requests queue at the pooler."
    )

    databases = config["databases"]

    assert "*" in databases, (
        "The [databases] section has no bare '*' fallback entry. Without it every newly "
        "provisioned client database needs a PgBouncer config change and a reload before "
        "it can be reached."
    )

    # The official documentation defines only the bare `*` fallback. Prefix wildcards
    # such as `tenant_* = ...` appear in blog posts only; one that silently fails to match
    # would fall through to a different entry and route a tenant to the wrong database
    # (threat T-02-06).
    starred = [key for key in databases if "*" in key and key != "*"]
    assert not starred, (
        f"[databases] contains undocumented wildcard key(s): {starred}. PgBouncer "
        "documents only the bare '*' fallback. A prefix wildcard is not guaranteed to "
        "match and would route a client database to the wrong entry (threat T-02-06)."
    )


ALIAS_COUNT = 300
CONCURRENCY = 4


@pytest.mark.slow
def test_tenant08_connection_count_does_not_scale_with_alias_count(django_db_blocker):
    """The observable form of TENANT-08: 300 registered aliases do not move `pg_stat_activity`.

    The other four tests in this file assert the *configuration*. This one asserts the
    *consequence*, against the running Compose stack, and it is the only test in the
    repository that proves the connection budget is `O(concurrency)` rather than
    `O(client_count)`. At 300 clients the difference is the one that pages someone.

    Three claims, in increasing strength:

    1. **Registering 300 aliases opens nothing.** `DatabaseWrapper` construction is lazy,
       so a process that knows about every client still holds no connections.
    2. **Serving all 300 at concurrency 4 costs about 4 connections, not 300.** A monitor
       thread samples the server-side backend count throughout, so the assertion is on
       the observed *peak* rather than on a quiet reading taken afterwards.
    3. **Nothing is left behind.** `CONN_MAX_AGE = 0` means the per-request close is a
       real close, and the count returns to its baseline.

    All 300 aliases point at one physical database on purpose: the claim under test is
    about *alias* count, and creating 300 databases would be testing `CREATE DATABASE`.

    The test creates and drops that database itself rather than borrowing a pytest-django
    one, because `TransactionTestCase` refuses connections to any alias outside its
    declared `databases` list — and every alias here is created at runtime, which is the
    whole point. `django_db_blocker.unblock()` is the documented way to opt out of the
    access guard for a test that manages its own connections. The probe database is named
    with the `test_client_` prefix so that `conftest.py`'s session-start reaper collects
    it if this run is killed.
    """
    from plateforme.tenancy.maintenance import (
        database_exists,
        drop_database_force,
        maintenance_connection,
    )
    from plateforme.tenancy.registry import evict_alias, register_client_database

    default_cfg = settings.DATABASES["default"]
    dbname = f"test_client_budget_{os.getpid()}"
    aliases = [f"tenant_{i}" for i in range(1, ALIAS_COUNT + 1)]

    def backend_count(cur) -> int:
        cur.execute(
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (dbname,),
        )
        return cur.fetchone()[0]

    with maintenance_connection() as cur:
        drop_database_force(cur, dbname)
        cur.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(dbname), sql.Identifier(default_cfg["USER"])
            )
        )
        assert database_exists(cur, dbname)

        try:
            baseline = backend_count(cur)

            for alias in aliases:
                register_client_database(
                    alias=alias,
                    name=dbname,
                    host=default_cfg["HOST"],
                    port=default_cfg["PORT"],
                    user=default_cfg["USER"],
                    password=default_cfg["PASSWORD"],
                )

            after_registration = backend_count(cur)
            assert after_registration == baseline, (
                f"Registering {ALIAS_COUNT} aliases moved the server connection count "
                f"from {baseline} to {after_registration}. Registration must be lazy — "
                "it happens on every request, for whichever client that request is for."
            )

            peak = baseline
            stop = threading.Event()

            def monitor():
                nonlocal peak
                with maintenance_connection() as watch:
                    while not stop.is_set():
                        peak = max(peak, backend_count(watch))
                        time.sleep(0.005)

            def serve(alias):
                # One "request" for one client. The teardown calls the *real*
                # `close_old_connections` — the function Django wires to
                # `request_started` and `request_finished` — rather than closing this
                # alias by hand. That is deliberate: `close_old_connections` honours
                # `CONN_MAX_AGE`, so this test fails if that setting ever drifts above
                # zero, whereas an explicit `.close()` would pass regardless and prove
                # nothing. Verified by mutation.
                try:
                    with connections[alias].cursor() as c:
                        c.execute("SELECT 1")
                        c.fetchone()
                finally:
                    close_old_connections()

            watcher = threading.Thread(target=monitor, daemon=True)
            watcher.start()
            try:
                with django_db_blocker.unblock():
                    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
                        list(pool.map(serve, aliases))
            finally:
                stop.set()
                watcher.join(timeout=5)

            settled = backend_count(cur)

            ceiling = CONCURRENCY + 2
            assert peak - baseline <= ceiling, (
                f"Peak server connections to {dbname} rose by {peak - baseline} above a "
                f"baseline of {baseline} while serving {ALIAS_COUNT} aliases at "
                f"concurrency {CONCURRENCY}. The budget is C_web + C_celery + slack = "
                f"{ceiling}. A number near {ALIAS_COUNT} means connections scale with "
                "client count, which is the TENANT-08 failure mode: PgBouncer's pools "
                "saturate and PostgreSQL answers FATAL: too many connections."
            )
            assert peak - baseline < ALIAS_COUNT / 10, (
                f"Peak rose by {peak - baseline} for {ALIAS_COUNT} aliases — the count is "
                "tracking alias count rather than concurrency."
            )
            assert settled == baseline, (
                f"{settled - baseline} connection(s) outlived the work. CONN_MAX_AGE = 0 "
                "means every per-request close is a real close; anything left behind is "
                "the orphaned socket of Pitfall 5."
            )
            print(
                f"\nTENANT-08: {ALIAS_COUNT} aliases, concurrency {CONCURRENCY} -> "
                f"baseline {baseline}, after registration {after_registration}, "
                f"peak {peak}, settled {settled}"
            )
        finally:
            for alias in aliases:
                if alias in connections.settings:
                    try:
                        evict_alias(alias)
                    except Exception:  # noqa: BLE001 — cleanup must not mask a failure
                        pass
                    connections.settings.pop(alias, None)
            drop_database_force(cur, dbname)

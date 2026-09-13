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
from pathlib import Path

import pytest
from django.conf import settings

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


@pytest.mark.slow
@pytest.mark.pending
def test_tenant08_connection_count_does_not_scale_with_alias_count():
    """Load check: pg_stat_activity must not grow with the number of registered aliases.

    Pending: this needs `register_client_database`, which plan 02-03 builds. That plan
    removes the `pending` marker and implements this test — register N client aliases,
    issue one query against each, and assert the server-connection count tracks
    concurrency rather than N.
    """
    pytest.fail("pending: implemented in 02-03")

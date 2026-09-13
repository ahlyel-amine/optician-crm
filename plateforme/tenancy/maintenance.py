"""The direct-to-PostgreSQL maintenance connection, and the DDL helpers that use it.

This is the one place in the system where a Python string becomes DDL (threat T-02-12),
so every identifier goes through `psycopg.sql.Identifier` and every value through
parameter binding. There are no f-strings in the SQL here, and there must never be.

Why a bespoke connection rather than Django's `connections[...]`:

* `CREATE DATABASE` and `DROP DATABASE` **cannot be executed inside a transaction
  block** (PostgreSQL 18 docs), so the connection must be `autocommit=True`.
* `DROP DATABASE ... WITH (FORCE)` terminates sessions attached to the target. It cannot
  terminate the *server* connections PgBouncer holds on our behalf, because those belong
  to the pooler, not to us. So this goes **direct to PostgreSQL**, never through the
  pooler.
* Django's private "no database" cursor helper on the PostgreSQL backend does something
  similar, and is private. Reusing it would couple provisioning to an undocumented
  internal whose fallback behaviour — connecting to the *first other database it can
  find* when `postgres` is unavailable — is wrong for us.
"""

from __future__ import annotations

import contextlib

import psycopg
from django.conf import settings
from psycopg import sql


@contextlib.contextmanager
def maintenance_connection():
    """Yield an autocommit cursor on the `postgres` maintenance database.

    Direct to PostgreSQL on PG_ADMIN_HOST/PG_ADMIN_PORT — deliberately not
    PGBOUNCER_HOST/PGBOUNCER_PORT. Closed in a `finally` on every path.
    """
    conn = psycopg.connect(
        host=settings.PG_ADMIN_HOST,
        port=settings.PG_ADMIN_PORT,
        user=settings.PG_ADMIN_USER,
        password=settings.PG_ADMIN_PASSWORD,
        dbname="postgres",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def database_exists(cur, name: str) -> bool:
    """True when a database of that name exists. The value is bound, never interpolated."""
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
    return cur.fetchone() is not None


def drop_database_force(cur, name: str) -> None:
    """`DROP DATABASE IF EXISTS <name> WITH (FORCE)`, with the name safely quoted.

    `WITH (FORCE)` (PostgreSQL 13+) terminates sessions still attached to the target,
    which a plain `DROP DATABASE` refuses to do. It still fails if prepared transactions
    or logical replication slots exist on the database.
    """
    cur.execute(
        sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
    )


def databases_matching(cur, patterns: list[str]) -> list[str]:
    """Database names matching any SQL `LIKE` pattern. Patterns are bound as values.

    Used by the test session's stale-database reaper, which must never be handed an
    open-ended pattern — see `conftest.py`.
    """
    cur.execute(
        "SELECT datname FROM pg_database WHERE datname LIKE ANY(%s) ORDER BY datname",
        (patterns,),
    )
    return [row[0] for row in cur.fetchall()]

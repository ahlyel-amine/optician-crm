"""Proving that two databases hold identical data. The part TENANT-09 actually turns on.

**Row counts are not verification.** They pass while every column value is wrong, which is
the failure a restore drill exists to catch. So: an ordered per-table `md5` digest folded
into one `sha256`, plus sequence positions.

Three details, each of which the digest is wrong without:

1. **The row *hashes* are ordered, not the rows.** `pg_restore` does not preserve physical
   row order, so a digest that depended on it would report every restore as a failure —
   and a verification step that always fails stops being run.
2. **`SET TIME ZONE 'UTC'` first.** `timestamptz` renders per session timezone and every
   ledger row carries a `created_at`, so without pinning it the digest computed by an
   operator in Casablanca differs from the one computed by a worker in UTC.
3. **Sequences are included.** A restored database with reset sequences is not identical
   even when every row matches, and in this product that is not academic: Phase 6's
   facture numbering depends on counters, and a reset sequence re-issues keys that already
   exist in the retained audit trail.

Two known caveats, recorded because they will matter later:

* **`t::text` renders `float` and `numeric` differently**, and floats differ across
  platforms. This project is `Decimal`/`numeric` everywhere (CLAUDE.md non-negotiable #7),
  so it is fine today — but a `FloatField` added in a later phase would make digests
  non-comparable between machines, silently.
  `test_tenant07_ledger_amounts_are_decimal_not_float` is the guard.
* **A column added by a later migration changes every table's digest.** Digests are
  therefore only comparable **within one schema version**. Always record `schema_digest`
  alongside — which is why `BackupRun` carries one and `restore_client` refuses a
  mismatch.
"""

from __future__ import annotations

import hashlib

from django.db import connections
from psycopg import sql

#: The key the sequence positions are filed under in the per-table breakdown. Not a real
#: table name, and chosen so it cannot collide with one.
SEQUENCES_KEY = "__sequences__"


def _base_tables(cur) -> list[str]:
    """Every base table in `public`, ordered by name. Views and Django's own are included.

    `django_migrations` is deliberately **not** excluded: a restored database that is at a
    different migration state is not identical, and that is exactly what we want to hear
    about.
    """
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
        "ORDER BY table_name"
    )
    return [row[0] for row in cur.fetchall()]


def tenant_checksum_detail(alias: str) -> dict[str, str]:
    """`{table_name: md5}` plus `__sequences__`, for localising a mismatch.

    Reporting "the databases differ" against a restore of ten years of a client's records
    is not an answer anybody can act on at 3am. This says which table.
    """
    detail: dict[str, str] = {}
    with connections[alias].cursor() as cur:
        # Reproducibility, see the module docstring. Restored afterwards rather than left
        # on the session: leaking session state onto a connection that goes back to a pool
        # is the transaction-pooling hazard the whole project is careful about
        # (threat T-02-02).
        cur.execute("SHOW TimeZone")
        previous_tz = cur.fetchone()[0]
        cur.execute("SET TIME ZONE 'UTC'")
        try:
            for table in _base_tables(cur):
                # The table name is composed as an identifier, never interpolated. It
                # comes from information_schema rather than from input, and it is composed
                # properly anyway — this is the same rule as the provisioner's.
                cur.execute(
                    sql.SQL(
                        "SELECT md5(coalesce(string_agg(row_md5, '' ORDER BY row_md5), ''))"
                        " FROM (SELECT md5(t::text) AS row_md5 FROM {} t) s"
                    ).format(sql.Identifier(table))
                )
                detail[table] = cur.fetchone()[0]

            cur.execute(
                "SELECT schemaname, sequencename, last_value "
                "FROM pg_sequences ORDER BY 1, 2"
            )
            rendered = "|".join(
                f"{schema}.{name}={value}" for schema, name, value in cur.fetchall()
            )
            detail[SEQUENCES_KEY] = hashlib.md5(
                rendered.encode("utf-8"), usedforsecurity=False
            ).hexdigest()
        finally:
            cur.execute(sql.SQL("SET TIME ZONE {}").format(sql.Literal(previous_tz)))
    return detail


def tenant_checksum(alias: str) -> str:
    """One 64-character hex digest over every base table and every sequence position.

    Equal digests mean the two databases hold the same data, at the same schema version,
    with their sequences in the same place.
    """
    detail = tenant_checksum_detail(alias)
    payload = "\n".join(f"{name}={digest}" for name, digest in sorted(detail.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

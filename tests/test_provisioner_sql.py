"""TENANT-01 / TENANT-05 — the one place in Phase 2 where a Python string becomes DDL.

These tests assert on the *composed SQL*, against a mock cursor, so they need no database
and stay in the quick loop. That is deliberate: the injection surface is worth a direct,
fast test that runs on every commit rather than a slow one that only runs against Compose.

`db_name` and `db_user` are derived from the `Client` primary key, never from operator
input, so the hostile name below cannot occur in practice. The test uses one anyway,
because "it cannot happen" is exactly the assumption that stops being true when Phase 12's
self-serve signup starts calling the same function (threat T-02-23).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.conf import settings
from psycopg import sql

from plateforme.tenancy.provisioner import (
    DatabaseProvisioner,
    SqlProvisioner,
    get_provisioner,
)

#: A name that, interpolated with an f-string, would close the identifier and append a
#: second statement. Composed through `sql.Identifier` it is a single quoted identifier.
HOSTILE_NAME = 'evil"; DROP DATABASE optique; --'


def _cursor(*, database_exists: bool = False, role_exists: bool = False) -> MagicMock:
    """A mock cursor whose `fetchone` answers the guard queries."""
    cur = MagicMock()
    cur.fetchone.return_value = (1,) if (database_exists or role_exists) else None
    return cur


def _rendered(cur: MagicMock) -> list[str]:
    """Every statement the provisioner executed, rendered to its final SQL text."""
    out = []
    for call in cur.execute.call_args_list:
        stmt = call.args[0]
        out.append(stmt.as_string() if hasattr(stmt, "as_string") else str(stmt))
    return out


def test_tenant01_database_name_reaches_ddl_only_as_a_quoted_identifier():
    """A hostile database name is one quoted identifier, never a second statement.

    This is the single injection surface in the phase. `psycopg.sql.Identifier` doubles
    the embedded quote, so the injected statement stays *inside* the identifier and the
    composed SQL remains one `CREATE DATABASE`.
    """
    cur = _cursor(database_exists=False)

    SqlProvisioner().create_database(cur, name=HOSTILE_NAME, owner="optique_u000001")

    statements = _rendered(cur)
    ddl = [s for s in statements if "CREATE DATABASE" in s]
    assert len(ddl) == 1, f"expected exactly one CREATE DATABASE, got {statements!r}"
    stmt = ddl[0]

    quoted = sql.Identifier(HOSTILE_NAME).as_string()
    assert quoted == '"evil""; DROP DATABASE optique; --"', (
        f"psycopg quoted the hostile name as {quoted!r}; the doubled quote is what "
        "keeps the payload inside the identifier."
    )
    assert quoted in stmt, f"the name was not composed as an identifier: {stmt!r}"

    # Remove the quoted identifier and nothing destructive may remain anywhere — i.e.
    # the injected statement never escaped into the SQL text.
    outside = stmt.replace(quoted, "<NAME>")
    assert "DROP" not in outside.upper(), (
        f"the injected statement escaped the identifier: {outside!r}"
    )
    assert ";" not in outside, (
        f"the composed statement contains a statement separator: {outside!r}"
    )

    # And the executed object is a composed SQL value, not a str — a str would mean
    # someone built it with an f-string somewhere upstream.
    executed = [c.args[0] for c in cur.execute.call_args_list]
    assert any(isinstance(e, (sql.Composed, sql.SQL)) for e in executed)


def test_tenant01_create_database_is_skipped_when_the_database_exists():
    """Guarded idempotency: the existence check is what lets a killed run be rerun.

    Step 2 of the provisioning state machine is a check-then-act. The check is what makes
    the rerun converge on the *same* database instead of failing or orphaning one.
    """
    cur = _cursor(database_exists=True)

    SqlProvisioner().create_database(cur, name="optique_c000042", owner="optique_u000042")

    statements = _rendered(cur)
    assert not any("CREATE DATABASE" in s for s in statements), (
        f"create_database issued DDL against an existing database: {statements!r}"
    )
    assert any("pg_database" in s for s in statements), (
        "create_database did not probe pg_database at all — it is not guarded."
    )


def test_tenant01_create_database_uses_template0_and_the_project_collation():
    """`TEMPLATE template0` plus the configured locale, both in the composed statement.

    `TEMPLATE template0` is *required* when specifying ENCODING or a locale; `template1`
    is the default and may carry user objects created by whoever touched it last.

    The locale is the ICU provider rather than an OS locale (`fr_FR.UTF-8`): the stock
    `postgres` image generates only `en_US.utf8`, so an OS locale fails with "invalid
    locale name", while ICU carries its own locale data. Verified against the live stack
    in plan 02-01 and again here.
    """
    cur = _cursor(database_exists=False)

    SqlProvisioner().create_database(cur, name="optique_c000042", owner="optique_u000042")

    stmt = next(s for s in _rendered(cur) if "CREATE DATABASE" in s)
    assert "TEMPLATE template0" in stmt, stmt
    assert "ENCODING 'UTF8'" in stmt, stmt
    assert f"LOCALE_PROVIDER {settings.TENANT_DB_LOCALE_PROVIDER}" in stmt, stmt
    assert f"'{settings.TENANT_DB_ICU_LOCALE}'" in stmt, stmt
    assert '"optique_u000042"' in stmt, "the owner must be a quoted identifier too"


def test_tenant05_drop_database_uses_force():
    """`DROP DATABASE IF EXISTS {} WITH (FORCE)`.

    `WITH (FORCE)` (PostgreSQL 13+) terminates sessions still attached to the target. A
    plain drop refuses while anything is connected, which makes deprovisioning and test
    teardown flaky rather than reliable.
    """
    cur = _cursor()

    SqlProvisioner().drop_database(cur, name="optique_c000042")

    statements = _rendered(cur)
    assert len(statements) == 1, statements
    stmt = statements[0]
    assert stmt.startswith("DROP DATABASE IF EXISTS "), stmt
    assert stmt.endswith("WITH (FORCE)"), stmt
    assert '"optique_c000042"' in stmt, stmt


def test_tenant01_provisioner_is_an_interface_with_two_methods():
    """`DatabaseProvisioner` is abstract and declares exactly two abstract methods.

    This test is what preserves the provider-API escape hatch. `02-RESEARCH.md` Open
    Question 2 — *does the managed provider's application role have `CREATEDB`, or must
    logical databases be created through the provider's API?* — is a Phase 1 procurement
    fact that is still open. If the answer is "API only", a second implementation of this
    interface costs a day. If someone inlines raw DDL into `provisioning.py` instead, it
    costs a redesign, and this test is what fails first.
    """
    import abc

    assert issubclass(DatabaseProvisioner, abc.ABC)
    assert DatabaseProvisioner.__abstractmethods__ == frozenset(
        {"create_database", "drop_database"}
    ), (
        "The interface must stay at exactly two methods. Anything more and a provider-API "
        f"implementation is no longer cheap. Got: {DatabaseProvisioner.__abstractmethods__}"
    )

    with pytest.raises(TypeError):
        DatabaseProvisioner()  # abstract — cannot be instantiated

    assert issubclass(SqlProvisioner, DatabaseProvisioner)
    assert not SqlProvisioner.__abstractmethods__
    assert isinstance(get_provisioner(), DatabaseProvisioner)

"""The `DatabaseProvisioner` interface, and the SQL implementation of it.

**Why an interface for two methods.** `02-RESEARCH.md` Open Question 2 — flagged there as
*the highest-value unknown in this phase* — is whether the managed hosting provider's
application role will have `CREATEDB` at all, or whether logical databases must be created
through the provider's own API. That is a Phase 1 procurement fact, not a coding decision,
and it is still open. Putting `create_database` and `drop_database` behind an interface
from day one means the answer "API only" costs a second implementation of two methods
rather than a redesign of the provisioning state machine.

`create_role_if_absent` is deliberately **not** on the abstract interface. It is a
`SqlProvisioner` concern: a provider that creates databases through an API creates their
owning roles the same way, so forcing it into the contract would make the interface
describe SQL rather than the operation. `test_tenant01_provisioner_is_an_interface_with_
two_methods` pins the interface at exactly two abstract methods for that reason.

**Every identifier goes through `psycopg.sql.Identifier` and every value through either a
bound parameter or `psycopg.sql.Literal`. There are no f-strings in the SQL here, and
there must never be** (threat T-02-23).

A note on why the locale is composed with `sql.Literal` rather than bound as `%s`:
`CREATE DATABASE` is a utility statement and PostgreSQL will not accept parameters in it.
Verified against the live PostgreSQL 18.6 stack — binding the locale produces
`SyntaxError: syntax error at or near "$1"`. `sql.Literal` does the quoting client-side
and is equally injection-safe; the value is a setting, not user input, either way.
"""

from __future__ import annotations

import abc
import contextlib
from collections.abc import Iterator

import psycopg
from django.conf import settings
from django.utils.module_loading import import_string
from psycopg import sql

from plateforme.tenancy.maintenance import (
    database_exists,
    drop_database_force,
    maintenance_connection,
)


class DatabaseProvisioner(abc.ABC):
    """Create and drop one client's logical database.

    Exactly two methods, because the provider may withhold `CREATEDB` and force both
    operations through an HTTP API — see this module's docstring and `02-RESEARCH.md`
    Open Question 2. Keep it at two.

    `cur` is an optional already-open maintenance cursor. SQL implementations use it (and
    open their own when it is `None`); an API implementation ignores it entirely, which is
    why it is positional-optional rather than required.
    """

    @abc.abstractmethod
    def create_database(self, cur=None, *, name: str, owner: str) -> None:
        """Create the database if it does not already exist. Must be idempotent."""

    @abc.abstractmethod
    def drop_database(self, cur=None, *, name: str) -> None:
        """Drop the database if it exists. Must be idempotent."""


@contextlib.contextmanager
def _cursor(cur) -> Iterator:
    """Yield `cur` when one was supplied, otherwise open a maintenance connection.

    Provisioning passes its own cursor so that role creation and database creation share
    one autocommit connection; the unit tests pass a mock; an ad-hoc caller passes
    nothing and gets a connection opened and closed around the single statement.
    """
    if cur is not None:
        yield cur
        return
    with maintenance_connection() as owned:
        yield owned


class SqlProvisioner(DatabaseProvisioner):
    """`CREATE DATABASE` / `DROP DATABASE` over SQL, on the direct maintenance connection.

    Requires a role with `CREATEDB` (and `CREATEROLE` for `create_role_if_absent`). That
    grant is the widest privilege in the system and is accepted rather than mitigated
    (threat T-02-27): it is unavoidable for database-per-client over SQL, and it is
    bounded by the connection being autocommit, direct, short-lived and used only here.
    """

    def create_role_if_absent(self, cur=None, *, user: str, password: str) -> None:
        """`CREATE ROLE <user> LOGIN PASSWORD <password>`, guarded on `pg_roles`.

        The name is an identifier (`sql.Identifier`); the password is a **value** and is
        quoted as a string literal (`sql.Literal`). It is deliberately *not* an
        identifier — quoting a password as an identifier would both change it and leave
        it unescaped for single quotes.

        Why `sql.Literal` rather than a bound `%s` parameter, which would be the normal
        answer: `CREATE ROLE` is a utility statement and PostgreSQL does not accept
        parameters in one. Verified against the live 18.6 stack — binding the password
        gives `SyntaxError: syntax error at or near "$1"`. `sql.Literal` does the quoting
        client-side and is equally injection-safe.

        One consequence to be honest about: the password therefore appears in the
        statement text, so a server with `log_statement = all` logs it. Compose sets that
        for development. It is not a new exposure — PostgreSQL logs bind parameters too,
        and a password reaching the server at all means the server's log is already as
        privileged as the credential. Production must not run `log_statement = all`.

        Also called by the restore path: `pg_dump` dumps a single database and roles are
        cluster-wide, so a restore onto a fresh instance produces a database nobody can
        connect to unless the role is recreated (Pitfall 10, threat T-02-47).
        """
        with _cursor(cur) as c:
            c.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,))
            if c.fetchone():
                # The role exists — but its password may not be the one the control plane
                # holds, and a role whose password does not match the control-plane record
                # is simply unusable. The control plane is the source of truth for the
                # credential, so converge on it rather than assuming.
                #
                # Found the hard way: a run killed after CREATE ROLE leaves the role
                # behind, and a later provision of the same primary key generates a fresh
                # password, stores it, skips the CREATE, and produces a client that
                # authenticates with nothing —
                #     FATAL: password authentication failed for user "optique_u000013"
                # from a step nowhere near the cause. Making this ALTER is what turns
                # "idempotent unless the role predates the row" into idempotent.
                c.execute(
                    sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                        sql.Identifier(user), sql.Literal(password)
                    )
                )
                return
            try:
                c.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(user), sql.Literal(password)
                    )
                )
            except psycopg.errors.DuplicateObject:
                # The guard above is a check-then-act and two concurrent provisions of
                # the same client can race between the SELECT and the CREATE.
                return

    def create_database(self, cur=None, *, name: str, owner: str) -> None:
        """`CREATE DATABASE <name> OWNER <owner>`, guarded on `pg_database`.

        `TEMPLATE template0` is required once ENCODING or a locale is specified;
        `template1` is the default and may carry whatever objects someone created in it.

        The collation is the project's one collation decision, and it is taken here, once,
        at creation time, because retrofitting per-column collations across a live fleet
        is expensive (`02-RESEARCH.md` assumption A7). It matters for a French/Moroccan
        product: Phase 4's `test_client10_search_finds_mohamed_mohammed_and_mhamed`
        depends on it. The provider is **ICU** rather than an OS locale — the stock
        `postgres` image generates only `en_US.utf8`, so `LC_COLLATE 'fr_FR.UTF-8'` fails
        with "invalid locale name", while ICU ships its own locale data and needs no
        custom image.
        """
        with _cursor(cur) as c:
            if database_exists(c, name):
                # Still (re-)apply the CONNECT restriction below: it is idempotent, and a
                # database created by an earlier build that lacked it must be fixed on
                # the next provisioning run rather than staying open forever.
                self._restrict_connect(c, name=name, owner=owner)
                return
            statement = sql.SQL(
                "CREATE DATABASE {name} OWNER {owner} TEMPLATE template0 "
                "ENCODING 'UTF8' LOCALE_PROVIDER {provider} ICU_LOCALE {locale}"
            ).format(
                name=sql.Identifier(name),
                owner=sql.Identifier(owner),
                # A bare SQL keyword, validated against the two values PostgreSQL accepts
                # so a settings typo cannot become a SQL fragment.
                provider=sql.SQL(_locale_provider()),
                locale=sql.Literal(settings.TENANT_DB_ICU_LOCALE),
            )
            try:
                c.execute(statement)
            except psycopg.errors.DuplicateDatabase:
                # Same check-then-act race as the role above (threat T-02-28). Two
                # concurrent provisions of one client converge here because `db_name` is
                # derived from the primary key, so both racers wanted the same name.
                pass
            self._restrict_connect(c, name=name, owner=owner)

    def _restrict_connect(self, cur, *, name: str, owner: str) -> None:
        """`REVOKE CONNECT ... FROM PUBLIC`, then `GRANT CONNECT` to the owning role only.

        **PostgreSQL grants `CONNECT` on a new database to `PUBLIC` by default.** Without
        this, every client's login role can open every *other* client's database — one
        `psql` away from reading another optician's ordonnances. The application would
        never do it, because the router binds one alias; but "the application would never"
        is not an isolation boundary, and the whole point of database-per-client is that
        the boundary is enforced below the application.

        Found while running this plan's own smoke drill: `deprovision_client` left
        `optique_u000001` behind, and that role could still connect to anything. The
        leftover role is now harmless, which is why deprovisioning deliberately keeps it —
        a restore from backup needs the credential the control-plane row still holds.

        Idempotent, so it is re-applied on every provisioning run including reruns.
        """
        cur.execute(
            sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(
                sql.Identifier(name)
            )
        )
        cur.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(name), sql.Identifier(owner)
            )
        )

    def drop_database(self, cur=None, *, name: str) -> None:
        """`DROP DATABASE IF EXISTS <name> WITH (FORCE)`, via `maintenance.drop_database_force`."""
        with _cursor(cur) as c:
            drop_database_force(c, name)


def _locale_provider() -> str:
    """The configured locale provider, restricted to the values PostgreSQL 18 accepts.

    `LOCALE_PROVIDER` takes a bare keyword, not a quotable literal, so this is the one
    fragment that is concatenated rather than composed — and it is therefore validated
    against an allow-list instead.
    """
    provider = settings.TENANT_DB_LOCALE_PROVIDER
    if provider not in {"icu", "libc", "builtin"}:
        raise ValueError(
            f"TENANT_DB_LOCALE_PROVIDER={provider!r} is not one of 'icu', 'libc', "
            "'builtin'. It is composed into DDL as a bare keyword, so it is "
            "allow-listed rather than quoted."
        )
    return provider


def get_provisioner() -> DatabaseProvisioner:
    """The configured provisioner, `SqlProvisioner` unless `DATABASE_PROVISIONER` says otherwise."""
    return import_string(settings.DATABASE_PROVISIONER)()

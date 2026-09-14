"""TENANT-08 / TENANT-04 — the pooled traffic path, exercised against real PgBouncer.

Every other test in this suite connects **directly** to PostgreSQL: `config/settings/test.py`
overrides HOST/PORT to `PG_ADMIN_HOST`/`PG_ADMIN_PORT` for `default`, `tenant_a` and
`tenant_b`, because the suite creates and drops databases and DDL cannot run through
transaction pooling. That is correct, and it left a hole: **nothing proved that a client
could authenticate through PgBouncer at all.**

It could not. PgBouncer shipped with `auth_type = scram-sha-256` and a static `auth_file`
holding exactly one hand-written development credential, while real traffic
(`Client.connection_params(direct=False)`) points at PgBouncer and authenticates as that
client's own `optique_u######` role — a role created minutes ago by the provisioner and
therefore absent from the file. Phase 3's first authenticated request would have failed to
connect. The fix is `auth_query` (docker/postgres/init/01-pgbouncer-auth.sql); these tests
are what makes its absence red.

The load-bearing assertion is in `test_tenant08_newly_provisioned_client_...`: the client's
role is asserted **absent from `userlist.txt`** before the connection is opened. Without
that, the test could pass because somebody pasted the credential into the file — which is
exactly the operational cost (a file edit and a pooler reload per new client) that
`auth_query` exists to remove.

These tests need the Compose stack up: PostgreSQL on `PG_ADMIN_PORT` and PgBouncer on
`PGBOUNCER_PORT`. They do real `CREATE DATABASE`, so they are `slow` and need
`transaction=True`.
"""

from __future__ import annotations

import configparser
from pathlib import Path

import psycopg
import pytest
from django.conf import settings

from plateforme.control_plane.models import Client

# Cleanup lives in exactly one place. `_destroy` drops a client's database and role **by
# exact name**, refusing anything that does not carry the configured test prefixes; a
# second copy of that logic here would be a second chance to get it wrong.
from tests.test_provisioning import _destroy

DOCKER = Path(__file__).resolve().parent.parent / "docker"
PGBOUNCER_INI = DOCKER / "pgbouncer" / "pgbouncer.ini"
PGBOUNCER_USERLIST = DOCKER / "pgbouncer" / "userlist.txt"


def _pooled_connect(*, user: str, password: str, dbname: str):
    """Open a connection **through PgBouncer**, never directly to PostgreSQL.

    `settings.PGBOUNCER_PORT`, not `DATABASES["default"]["PORT"]` — under the test
    settings the latter is PostgreSQL's own port, and that substitution is exactly how
    this gap survived the phase.
    """
    return psycopg.connect(
        host=settings.PGBOUNCER_HOST,
        port=settings.PGBOUNCER_PORT,
        user=user,
        password=password,
        dbname=dbname,
        connect_timeout=5,
    )


def _pgbouncer_ini() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    assert config.read(PGBOUNCER_INI), f"{PGBOUNCER_INI} not found."
    return config


# --------------------------------------------------------------------------------------
# Configuration — cheap, no container needed
# --------------------------------------------------------------------------------------
def test_tenant08_pgbouncer_resolves_credentials_by_query_not_by_file():
    """`auth_query` is configured, so a role created after startup can authenticate.

    A static `auth_file` is a snapshot of the roles that existed when somebody last edited
    it. Provisioning creates a role per client, continuously, and TENANT-01's promise — "a
    new client is a provisioning operation, not a deployment" — dies if each one also
    needs a config edit and a `RELOAD` on the pooler.
    """
    pgb = _pgbouncer_ini()["pgbouncer"]

    assert pgb.get("auth_query"), (
        "No auth_query in pgbouncer.ini. Without it PgBouncer can only authenticate the "
        "roles literally present in auth_file, so every client the provisioner creates is "
        "refused at the pooler and Phase 3's first real request fails to connect."
    )
    assert pgb.get("auth_user"), (
        "auth_query is set but auth_user is not. PgBouncer runs the query as auth_user; "
        "with no auth_user there is nobody to run it as."
    )
    assert pgb.get("auth_dbname"), (
        "auth_query is set but auth_dbname is not. PgBouncer runs auth_query inside the "
        "database the client asked for, so without auth_dbname the lookup function would "
        "have to exist in every client database — and one created tomorrow would not "
        "have it."
    )

    # The lookup must not read pg_shadow directly: that needs superuser, and an auth_user
    # holding superuser would make the pooler's own credential the keys to the cluster.
    assert "pg_shadow" not in pgb["auth_query"].lower(), (
        f"auth_query reads pg_shadow directly: {pgb['auth_query']!r}. pg_shadow is "
        "superuser-only, so this forces auth_user to be a superuser. Call a SECURITY "
        "DEFINER function instead, with EXECUTE granted to auth_user alone."
    )


def test_tenant08_no_client_role_is_written_into_the_static_auth_file():
    """`userlist.txt` holds development credentials only — never a provisioned client.

    The file remains as a documented fallback for PgBouncer's own admin console, which
    does not go through auth_query. The moment an `optique_u######` line appears in it,
    the operational cost auth_query removed is back, and this test says so.
    """
    text = PGBOUNCER_USERLIST.read_text()
    for prefix in ("optique_u", "test_client_u"):
        assert prefix not in text, (
            f"{PGBOUNCER_USERLIST} contains a per-client role ({prefix}...). Client "
            "credentials are resolved by auth_query against PostgreSQL; writing one into "
            "the static file reintroduces the per-client file edit and reload that "
            "auth_query exists to remove."
        )


# --------------------------------------------------------------------------------------
# The pooled path, end to end
# --------------------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant08_newly_provisioned_client_authenticates_through_pgbouncer(
    allow_runtime_tenant_aliases,
):
    """Provision a client, then query its database **through PgBouncer** as its own role.

    This is the assertion the suite was missing. The client's role did not exist when
    PgBouncer started, is not in `userlist.txt` (asserted below, before the connection is
    opened), and no reload happened between the `CREATE ROLE` and this connection. If it
    authenticates, `auth_query` is genuinely resolving the credential from PostgreSQL.
    """
    from plateforme.control_plane.provisioning import provision_client

    code = "test-pgb-auth"
    try:
        client = provision_client(
            code=code, raison_sociale="Optique PgBouncer SARL", magasins=["Centre"]
        )
        assert client.status == Client.ACTIVE

        # Before connecting: prove the credential is not in the file. A green test against
        # a hand-edited userlist would prove nothing at all.
        assert client.db_user not in PGBOUNCER_USERLIST.read_text(), (
            f"{client.db_user} was written into userlist.txt. Remove it: this test is "
            "meant to prove auth_query resolves the credential, not that somebody pasted "
            "it in."
        )
        assert settings.PGBOUNCER_PORT != settings.PG_ADMIN_PORT, (
            "PGBOUNCER_PORT and PG_ADMIN_PORT are the same, so this test cannot "
            "distinguish the pooled path from the direct one."
        )

        with _pooled_connect(
            user=client.db_user, password=client.db_password, dbname=client.db_name
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user")
                database, role = cur.fetchone()
                # A real query, not merely a successful handshake: the pooler has to hand
                # this client a server connection and route the result back.
                cur.execute("SELECT count(*) FROM magasins_magasin")
                magasins = cur.fetchone()[0]

        assert database == client.db_name
        assert role == client.db_user, (
            f"connected through PgBouncer as {role!r}, expected {client.db_user!r}. The "
            "pooler substituted a different server-side role, which would mean every "
            "client shares one identity below the pooler."
        )
        assert magasins == 1, (
            "the query ran but returned some other database's contents; provisioning "
            "seeded exactly one magasin for this client."
        )
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.tenancy
@pytest.mark.django_db(transaction=True)
def test_tenant04_client_role_cannot_reach_another_clients_database_through_pgbouncer(
    allow_runtime_tenant_aliases,
):
    """`_restrict_connect` must hold on the pooled path too, or auth_query opened a hole.

    `test_tenant04_a_client_role_cannot_connect_to_another_clients_database` proves this
    against PostgreSQL directly. It has to be proved again here, because PgBouncer is a
    second front door: it authenticates the client itself and then opens its *own* server
    connection, so a misconfigured pooler could authenticate A and hand it a server
    connection to B's database. Two clients, because one cannot prove isolation.

    The positive half matters as much as the negative one — A must still reach its own
    database through the pooler, or "refused" would only mean "nothing works".
    """
    from plateforme.control_plane.provisioning import provision_client

    code_a, code_b = "test-pgb-iso-a", "test-pgb-iso-b"
    try:
        a = provision_client(
            code=code_a, raison_sociale="Optique PgB Iso A", magasins=["Centre"]
        )
        b = provision_client(
            code=code_b, raison_sociale="Optique PgB Iso B", magasins=["Centre"]
        )

        with _pooled_connect(
            user=a.db_user, password=a.db_password, dbname=a.db_name
        ) as own:
            with own.cursor() as cur:
                cur.execute("SELECT current_database()")
                assert cur.fetchone()[0] == a.db_name

        with pytest.raises(psycopg.OperationalError) as excinfo:
            _pooled_connect(
                user=a.db_user, password=a.db_password, dbname=b.db_name
            ).close()
        assert "permission denied" in str(excinfo.value).lower(), (
            "client A reached client B's database through PgBouncer. The pooler said: "
            f"{excinfo.value}"
        )

        # B's own credential still works against B, so the refusal above is about *who*
        # asked, not about B's database being unreachable through the pooler at all.
        with _pooled_connect(
            user=b.db_user, password=b.db_password, dbname=b.db_name
        ) as owns_b:
            with owns_b.cursor() as cur:
                cur.execute("SELECT current_database()")
                assert cur.fetchone()[0] == b.db_name
    finally:
        _destroy(code_a)
        _destroy(code_b)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant08_wrong_password_is_still_refused_through_pgbouncer(
    allow_runtime_tenant_aliases,
):
    """The negative control for auth_query: it must resolve credentials, not wave clients through.

    Without this, `auth_query` could be verifying nothing — `auth_type = trust`, or a
    lookup function returning a NULL verifier — and the test above would still be green.
    """
    from plateforme.control_plane.provisioning import provision_client

    code = "test-pgb-badpw"
    try:
        client = provision_client(
            code=code, raison_sociale="Optique PgBouncer BadPw", magasins=["Centre"]
        )

        with pytest.raises(psycopg.OperationalError) as excinfo:
            _pooled_connect(
                user=client.db_user,
                password=client.db_password + "-wrong",
                dbname=client.db_name,
            ).close()
        assert "password authentication failed" in str(excinfo.value).lower(), (
            f"a wrong password was not refused by PgBouncer: {excinfo.value}"
        )
    finally:
        _destroy(code)

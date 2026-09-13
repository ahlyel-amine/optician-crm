"""TENANT-02 — the control plane's durable record of every client business.

The `Client` row is the single source of truth that everything else in the tenancy
layer reads from: provisioning writes it, the middleware reads it to build a
connection, `migrate_all` iterates it, backup schedules off it. These tests pin the
shape of that record and the two properties that are security rather than convenience —
credentials are never readable in plaintext from the control-plane database alone, and
an ACTIVE client without a database is refused by PostgreSQL, not by a `clean()` method.

These tests need only the `default` alias. No tenant database is involved.
"""

import pytest
from django.conf import settings
from django.db import IntegrityError, connections, transaction

pytestmark = pytest.mark.django_db


def test_tenant02_control_plane_records_db_name_host_and_schema_version():
    """TENANT-02: name, host, port and applied migration heads round-trip from `default`.

    `db_host` is present from day one so that moving a client to another PostgreSQL
    instance is a data change, not a migration. `applied_heads` is a JSON mapping of
    app label to migration name, not a single integer, because several business apps
    have independent migration chains — one integer cannot express "stock is at 0004
    but facturation is at 0011".
    """
    from plateforme.control_plane.models import Client

    Client.objects.create(
        code="opt-001",
        raison_sociale="Optique Centre SARL",
        db_name="optique_c000001",
        db_host="pgbouncer.internal",
        db_port=6432,
        db_user="optique_u000001",
        applied_heads={"magasins": "0001_initial"},
    )

    reread = Client.objects.using("default").get(code="opt-001")
    assert reread.raison_sociale == "Optique Centre SARL"
    assert reread.db_name == "optique_c000001"
    assert reread.db_host == "pgbouncer.internal"
    assert reread.db_port == 6432
    assert reread.db_user == "optique_u000001"
    assert reread.status == Client.PENDING
    assert isinstance(reread.applied_heads, dict), (
        f"applied_heads came back as {type(reread.applied_heads).__name__}, not dict. "
        "A JSONField that round-trips as a string means it was declared as a TextField "
        "somewhere, and every caller would then need to remember to json.loads it."
    )
    assert reread.applied_heads == {"magasins": "0001_initial"}


def test_tenant02_db_password_is_never_stored_in_plaintext():
    """Threat T-02-07: reading the control-plane database must not hand over every client.

    One table holds the connection credentials for every client database, and those
    databases hold ordonnances — health data under law 09-08. So the assertion is made
    against the **raw column bytes**, read through a cursor rather than through the
    model, because the model is exactly the layer that would make a plaintext column
    look encrypted.
    """
    from plateforme.control_plane.models import Client

    secret = "hunter2-hunter2"
    client = Client.objects.create(
        code="opt-002",
        raison_sociale="Optique Maarif SARL",
        db_host="pgbouncer.internal",
    )
    client.set_db_password(secret)
    client.save(using="default")

    with connections["default"].cursor() as cur:
        cur.execute(
            "SELECT db_password_encrypted FROM control_plane_client WHERE code = %s",
            ["opt-002"],
        )
        (raw,) = cur.fetchone()

    assert raw, "db_password_encrypted is empty — the credential was never stored at all."
    raw_bytes = bytes(raw)
    assert secret.encode() not in raw_bytes, (
        "The plaintext database password is readable straight out of the control-plane "
        "column. An operator or attacker with read access to one table would hold the "
        "credentials of every client database (threat T-02-07)."
    )

    assert Client.objects.using("default").get(code="opt-002").db_password == secret


def test_tenant02_active_client_cannot_exist_without_a_db_name():
    """TENANT-05's invariant, stated at the database level rather than in application code.

    A `clean()` method is bypassed by `bulk_update`, by `queryset.update()` and by a
    `manage.py shell` session. A CHECK constraint is not. An ACTIVE client with no
    database is a row the router would happily try to route to.
    """
    from plateforme.control_plane.models import Client

    with pytest.raises(IntegrityError):
        with transaction.atomic(using="default"):
            Client.objects.create(
                code="opt-003",
                raison_sociale="Optique Gueliz SARL",
                db_host="pgbouncer.internal",
                db_name=None,
                status=Client.ACTIVE,
            )


def test_tenant02_connection_params_use_pgbouncer_by_default_and_direct_when_asked():
    """Two connection paths, made explicit on the model instead of remembered per call site.

    Web and Celery traffic goes through PgBouncer in transaction mode. Migrations,
    provisioning, `pg_dump` and `pg_restore` must not: `CREATE DATABASE` cannot run
    inside a transaction block, and long DDL transactions are the opposite of what a
    transaction pooler is for.
    """
    from plateforme.control_plane.models import Client

    client = Client.objects.create(
        code="opt-004",
        raison_sociale="Optique Agdal SARL",
        db_name="optique_c000004",
        db_host="pgbouncer.internal",
        db_port=6432,
        db_user="optique_u000004",
    )
    client.set_db_password("s3cret-s3cret")

    pooled = client.connection_params()
    assert pooled["host"] == "pgbouncer.internal"
    assert pooled["port"] == 6432
    assert pooled["name"] == "optique_c000004"
    assert pooled["user"] == "optique_u000004"
    assert pooled["password"] == "s3cret-s3cret"
    assert pooled["alias"] == f"tenant_{client.pk}"

    direct = client.connection_params(direct=True)
    assert direct["host"] == settings.PG_ADMIN_HOST
    assert direct["port"] == settings.PG_ADMIN_PORT
    assert direct["name"] == "optique_c000004"
    assert direct["alias"] == pooled["alias"]

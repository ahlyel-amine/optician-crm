"""TENANT-01 / TENANT-05 / TENANT-06 — the provisioning state machine.

One function, two entry points. `manage.py provision_client` calls it today; Phase 12's
self-serve signup calls the same function from a Celery task. Anything that lives in the
command instead of here is logic self-serve will not have, which is why
`test_tenant06_command_module_contains_no_provisioning_logic` reads the command's source.

**Why this is a state machine and not a transaction.** PostgreSQL: *"CREATE DATABASE
cannot be executed inside a transaction block."* So TENANT-05's "completes or rolls back
cleanly" cannot be `atomic()`. The `Client` row is the durable record of intent and the
only transactional part; every other step is made individually idempotent so that a run
killed at any point **converges on rerun** instead of rolling back.

The invariant that makes TENANT-05 true is not cleanup — it is visibility. Only ACTIVE
clients are routed to (`middleware.resolve_client`) or migrated (`migrate_all`), so a
half-provisioned client is simply not part of the system. A FAILED row is visible to the
operator and to nobody else.
"""

from __future__ import annotations

import secrets

from django.conf import settings
from django.core.management import call_command
from django.db import connections, transaction
from django.utils import timezone
from django.utils.connection import ConnectionDoesNotExist

from plateforme.control_plane.models import Client
from plateforme.control_plane.schema_version import (
    read_applied_heads,
    schema_digest,
)
from plateforme.control_plane.seeding import seed_new_client
from plateforme.tenancy.context import tenant_context
from plateforme.tenancy.maintenance import maintenance_connection
from plateforme.tenancy.provisioner import get_provisioner
from plateforme.tenancy.registry import alias_for, evict_alias, register_client_database


def derive_db_name(pk: int) -> str:
    """`optique_c000047` — the client's database name, derived from its primary key.

    **Never from operator input** (threat T-02-23). Two consequences, both load-bearing:
    a rerun of a killed provision computes the same name and adopts the database it
    already created rather than orphaning it, and two concurrent provisions of one code
    converge on one name rather than racing to create two databases (T-02-28).

    The prefix is `settings.TENANT_DB_NAME_PREFIX`, `optique_c` in production. It is a
    setting only so the test suite can create its databases under `test_client_c` — see
    the comment on that setting; sharing the prefix would let a test run adopt and drop a
    developer's real client database.
    """
    return f"{settings.TENANT_DB_NAME_PREFIX}{pk:06d}"


def derive_db_user(pk: int) -> str:
    """`optique_u000047` — the owning role, derived from the primary key. See above."""
    return f"{settings.TENANT_DB_USER_PREFIX}{pk:06d}"


def is_client_database_name(name: str) -> bool:
    """True only for a name `derive_db_name` could have produced: prefix + six digits.

    **Not `startswith(prefix)`, and not a SQL `LIKE 'optique_c%'`.** Both are wrong, and
    the second is dangerous: in SQL `LIKE`, `_` is a single-character wildcard, so
    `optique_c%` matches **`optique_control`** — the control-plane database itself. That
    was not hypothetical; `reap_orphan_databases` listed the development control plane as
    an orphan the first time it was run. A plain `startswith` has the same blind spot,
    because `"optique_control".startswith("optique_c")` is also true.

    A restore target (`<db_name>_restore_<ts>`, plan 02-07) deliberately does **not**
    match. The reaper must never drop a restore that is in flight or awaiting acceptance;
    the runbook tells the operator to drop those by name once the restore is accepted.
    """
    prefix = settings.TENANT_DB_NAME_PREFIX
    suffix = name[len(prefix) :]
    return name.startswith(prefix) and len(suffix) == 6 and suffix.isdigit()


def provision_client(*, code, raison_sociale, magasins, db_host=None) -> Client:
    """Provision one client business end to end. Idempotent; safe to rerun after a kill.

    Status sequence::

        PENDING -> CREATING_DB -> MIGRATING -> SEEDING -> ACTIVE
                                 (any step) -> FAILED -> (rerun) -> ...

    Per-step idempotency, which is the reason a killed run converges rather than needing
    a rollback:

    ======================  ==========================================================
    Step                    Idempotency mechanism
    ======================  ==========================================================
    1. Identity             ``get_or_create(code=...)``; ``db_name`` derived from the
                            pk and never regenerated
    2. ``CREATE ROLE``      guarded by ``SELECT 1 FROM pg_roles WHERE rolname = %s``
    2. ``CREATE DATABASE``  guarded by ``SELECT 1 FROM pg_database WHERE datname = %s``,
                            plus ``DuplicateDatabase`` caught for the check-then-act race
    3. ``migrate``          Django's own ``django_migrations`` table, for free
    4. Seed                 ``get_or_create`` only; no blind ``create()``
    5. Activate             one transactional ``UPDATE`` on ``default``
    ======================  ==========================================================

    On failure the row is marked FAILED with `last_error` and the exception is
    **re-raised**. Swallowing it would make a failure look like a success to the operator
    and to the Phase 12 self-serve flow (threat T-02-29).

    **Deliberately not implemented: template databases.**
    ``CREATE DATABASE x TEMPLATE optique_template`` turns a ~20 s migrate into a ~1 s file
    copy, and it is the obvious optimisation to reach for. It is not taken here for two
    reasons: no other session may be connected to a template while it is copied, so
    provisioning would serialise and fail under concurrency; and a template that drifts
    behind the migration head silently provisions out-of-date clients. If it is ever
    added it must be guarded by ``read_applied_heads(template) == code_heads()`` and only
    once provisioning latency has been *measured* to be a problem. At manual-onboarding
    volumes it never will be.
    """
    default_db = settings.DATABASES["default"]

    # -- 1. Reserve identity, transactionally, on `default` ----------------------------
    # The only atomic step, and the one that makes a killed run converge.
    with transaction.atomic(using="default"):
        client, _created = Client.objects.using("default").get_or_create(
            code=code,
            defaults={
                "raison_sociale": raison_sociale,
                "status": Client.PENDING,
                # Where this client's *traffic* goes: PgBouncer in local and production,
                # PostgreSQL directly under the test settings. `db_host` is on the row
                # from day one so moving a client to another instance — or sharding when
                # one hits its logical-database cap — is a data change, not a migration.
                "db_host": db_host or default_db["HOST"],
                "db_port": int(default_db["PORT"]),
            },
        )
        if client.status == Client.ACTIVE:
            # Idempotent no-op. The operator ran it twice, or self-serve retried.
            return client

        if db_host:
            client.db_host = db_host
        client.db_name = derive_db_name(client.pk)
        client.db_user = derive_db_user(client.pk)
        if not client.db_password_encrypted:
            # Generated server-side, never chosen, never logged, never printed by the
            # command (threat T-02-26). Only generated when absent, so a rerun keeps the
            # password the existing role already has.
            client.set_db_password(secrets.token_urlsafe(32))
        client.status = Client.CREATING_DB
        client.last_error = ""
        client.save(using="default")

    alias = alias_for(client.pk)

    try:
        # -- 2. CREATE ROLE + CREATE DATABASE ------------------------------------------
        # On the autocommit maintenance connection, direct to PostgreSQL: CREATE DATABASE
        # needs autocommit, and transaction-mode pooling is the wrong place for DDL.
        provisioner = get_provisioner()
        with maintenance_connection() as cur:
            create_role = getattr(provisioner, "create_role_if_absent", None)
            if create_role is not None:
                create_role(cur, user=client.db_user, password=client.db_password)
            provisioner.create_database(cur, name=client.db_name, owner=client.db_user)

        # -- 3. MIGRATE ----------------------------------------------------------------
        client.advance(Client.MIGRATING)
        # direct=True: migrations hold long DDL transactions, which is the opposite of
        # what a transaction pool is for, and the freshly created role is not in
        # PgBouncer's userlist anyway.
        register_client_database(**client.connection_params(direct=True))
        call_command("migrate", database=alias, interactive=False, verbosity=0)

        # -- 4. SEED -------------------------------------------------------------------
        client.advance(Client.SEEDING)
        with tenant_context(alias):
            seed_new_client(client, magasins)

        # -- 5. RECORD THE SCHEMA VERSION AND ACTIVATE ---------------------------------
        heads = read_applied_heads(alias)
        now = timezone.now()
        with transaction.atomic(using="default"):
            Client.objects.using("default").filter(pk=client.pk).update(
                applied_heads=heads,
                schema_digest=schema_digest(heads),
                schema_checked_at=now,
                status=Client.ACTIVE,
                provisioned_at=client.provisioned_at or now,
                last_error="",
            )
        client.refresh_from_db(using="default")
        return client

    except Exception as exc:
        Client.objects.using("default").filter(pk=client.pk).update(
            status=Client.FAILED, last_error=repr(exc)[:2000]
        )
        client.status = Client.FAILED
        client.last_error = repr(exc)[:2000]
        raise


def deprovision_client(client: Client) -> Client:
    """Drop a client's database and mark the row DELETED. The row itself survives.

    Art. 211 CGI requires ten years of record retention and the audit trail wants to know
    the client existed, so the `Client` row is never deleted — the status is the
    tombstone, and `db_name` stays on it so a restore from backup has somewhere to go.
    """
    client.advance(Client.DROPPING)
    try:
        if client.db_name:
            get_provisioner().drop_database(name=client.db_name)
        alias = alias_for(client.pk)
        if alias in connections.settings:
            try:
                evict_alias(alias)
            except ConnectionDoesNotExist:
                # Registered in `connections.settings` but never opened on this thread,
                # so there is no wrapper to close. Found by the SMOKE01 drill: the
                # command dropped the database and then crashed here, leaving the row in
                # DROPPING — a database gone with a row that says it is still going.
                pass
        client.advance(Client.DELETED)
        return client
    except Exception as exc:
        client.advance(Client.FAILED, last_error=repr(exc)[:2000])
        raise

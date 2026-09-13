"""TENANT-02 — the control plane's durable record of every client business.

One row per optician business. It records where that business's database lives, how to
open it, and which migrations have been applied to it. Provisioning writes the row, the
middleware reads it to build a connection, `migrate_all` iterates it, backup schedules
off it.

Two rules are enforced here rather than by convention:

1. The database password is Fernet-encrypted (`crypto.py`). Reading the control-plane
   database must not be equivalent to holding every client's credentials (T-02-07).
2. An ACTIVE client must have a `db_name`, stated as a CHECK constraint. A `clean()`
   method is bypassed by `bulk_update`, by `queryset.update()` and by a shell session;
   a CHECK constraint is not (T-02-08).

The control plane holds **no** health data. Ordonnances live in the client's own
database. What lives here is identity, connection metadata and schema bookkeeping.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models, transaction

from plateforme.control_plane import crypto


class ClientStatus(models.TextChoices):
    """The provisioning state machine.

    ``PENDING -> CREATING_DB -> MIGRATING -> SEEDING -> ACTIVE``, with ``FAILED``
    reachable from any step and rerunnable, and ``DROPPING -> DELETED`` for
    deprovisioning. Declared at module level rather than nested inside ``Client``
    because ``Meta.constraints`` is evaluated in its own namespace and cannot see the
    enclosing class body.
    """

    PENDING = "pending", "En attente"
    CREATING_DB = "creating_db", "Création de la base"
    MIGRATING = "migrating", "Migration"
    SEEDING = "seeding", "Initialisation"
    ACTIVE = "active", "Actif"
    FAILED = "failed", "Échec"
    SUSPENDED = "suspended", "Suspendu"
    DROPPING = "dropping", "Suppression"
    DELETED = "deleted", "Supprimé"


class Client(models.Model):
    """One optician business, and the coordinates of its database.

    `db_name` is derived from the primary key at provisioning time
    (`optique_c{pk:06d}`), never from user input — that is what makes a run killed
    halfway converge on rerun instead of creating an orphan database.
    """

    Status = ClientStatus

    # Shorthands, so call sites read `Client.ACTIVE` rather than `Client.Status.ACTIVE`.
    PENDING = ClientStatus.PENDING
    CREATING_DB = ClientStatus.CREATING_DB
    MIGRATING = ClientStatus.MIGRATING
    SEEDING = ClientStatus.SEEDING
    ACTIVE = ClientStatus.ACTIVE
    FAILED = ClientStatus.FAILED
    SUSPENDED = ClientStatus.SUSPENDED
    DROPPING = ClientStatus.DROPPING
    DELETED = ClientStatus.DELETED

    #: Statuses the router and `migrate_all` will act on. Everything else is invisible
    #: to the rest of the system — which is precisely what makes TENANT-05 true: a
    #: half-provisioned client cannot be routed to.
    ROUTABLE_STATUSES = frozenset({ClientStatus.ACTIVE})

    code = models.SlugField(max_length=20, unique=True)
    raison_sociale = models.CharField(max_length=200)
    status = models.CharField(
        max_length=16, choices=ClientStatus.choices, default=ClientStatus.PENDING, db_index=True
    )

    # 63 is PostgreSQL's identifier length limit (NAMEDATALEN - 1), not a round number.
    db_name = models.CharField(max_length=63, unique=True, null=True, blank=True)
    # Present from day one so that moving a client to another instance — or sharding
    # across instances when one hits its logical-database cap — is a data change rather
    # than a migration.
    db_host = models.CharField(max_length=255)
    db_port = models.PositiveIntegerField(default=6432)
    db_user = models.CharField(max_length=63, null=True, blank=True)
    db_password_encrypted = models.BinaryField(null=True, blank=True)

    # {app_label: latest applied migration name}. Several business apps have independent
    # migration chains, so a single integer cannot express "stock is at 0004 but
    # facturation is at 0011".
    applied_heads = models.JSONField(default=dict, blank=True)
    # sha256 of the sorted applied_heads items: one short value for list views and for
    # equality comparison.
    schema_digest = models.CharField(max_length=64, blank=True)
    # When the recorded value was last confirmed against the live database. Recorded and
    # probed truth can diverge (someone ran `migrate` by hand); the control plane shows
    # both and keeps them distinguishable.
    schema_checked_at = models.DateTimeField(null=True, blank=True)

    provisioned_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            # `condition=` — not `check=`. Verified against the installed Django 6.1.1:
            # `CheckConstraint.__init__(self, *, condition, name, ...)`; the `check`
            # keyword was deprecated in 5.1 and is gone in 6.1.
            models.CheckConstraint(
                condition=~models.Q(status=ClientStatus.ACTIVE)
                | models.Q(db_name__isnull=False),
                name="active_client_has_db_name",
                violation_error_message=(
                    "An ACTIVE client must have a db_name. A client with no database is "
                    "not routable, and the router must never see one."
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.raison_sociale}"

    # -- credentials ------------------------------------------------------------------

    def set_db_password(self, plaintext: str) -> None:
        """Encrypt and store the client database password. Does not save."""
        self.db_password_encrypted = crypto.encrypt(plaintext)

    @property
    def db_password(self) -> str | None:
        """Decrypt the stored password, or None when none has been set yet."""
        if not self.db_password_encrypted:
            return None
        return crypto.decrypt(self.db_password_encrypted)

    # -- connection -------------------------------------------------------------------

    @property
    def alias(self) -> str:
        """The Django connection alias for this client. Mirrors `registry.alias_for`."""
        return f"tenant_{self.pk}"

    def connection_params(self, direct: bool = False) -> dict:
        """Connection parameters, ready to splat into `register_client_database(**...)`.

        The rule, stated once here so no call site has to remember it:

        * **Web and Celery traffic goes through PgBouncer** — `direct=False`, the
          default, uses the row's own `db_host`/`db_port`, which point at the pooler.
        * **DDL, migrations, `pg_dump` and `pg_restore` go direct to PostgreSQL** —
          `direct=True` swaps in `settings.PG_ADMIN_HOST`/`PG_ADMIN_PORT`. `CREATE
          DATABASE` cannot run inside a transaction block, migrations hold long DDL
          transactions, and `DROP DATABASE ... WITH (FORCE)` cannot terminate the server
          connections PgBouncer is holding on our behalf.
        """
        return {
            "alias": self.alias,
            "name": self.db_name,
            "host": settings.PG_ADMIN_HOST if direct else self.db_host,
            "port": settings.PG_ADMIN_PORT if direct else self.db_port,
            "user": self.db_user,
            "password": self.db_password,
        }

    # -- state machine ----------------------------------------------------------------

    def advance(self, new_status: str, *, last_error: str = "") -> None:
        """Move the row to `new_status` in one transactional UPDATE on `default`.

        Provisioning is a status state machine rather than one atomic transaction,
        because `CREATE DATABASE` cannot run inside a transaction block. The control
        plane row is the only transactional part of it, and it is the durable record of
        intent that makes a killed run resumable.
        """
        with transaction.atomic(using="default"):
            Client.objects.using("default").filter(pk=self.pk).update(
                status=new_status, last_error=last_error
            )
        self.status = new_status
        self.last_error = last_error

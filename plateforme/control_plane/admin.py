"""The operator admin. **Control-plane models only.**

`django.contrib.admin.options` calls `db_for_write(self.model)` in three places
(`save_model`, `delete_model`, `delete_queryset`), and the changelist goes through
`db_for_read`. Registering a *business* model here would therefore make the operator admin
raise `NoTenantBound` the moment anyone opened it, because the admin is not inside a
tenant-bound request. That is arguably the correct behaviour — it is exactly the fail-closed
router doing its job — but it must be a deliberate decision rather than a surprise
discovered in production. So: nothing from `domaine.` is imported in this file.

Business data gets its own magasin- and permission-scoped UI in Phases 3 through 7. The
operator admin is for the fleet, not for one optician's stock.
"""

from django.contrib import admin

from plateforme.control_plane.models import (
    BackupRun,
    Client,
    MigrationRun,
    MigrationRunResult,
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Every client database, its host, and how far behind its schema is.

    `schema_digest` / `schema_checked_at` show the **recorded** truth — what was true
    after the last successful `migrate`. It drifts from reality the moment someone runs
    `migrate` by hand, which is why `migrate_all --check` exists and is authoritative.
    `schema_checked_at` is how stale the recorded value is allowed to look.
    """

    list_display = (
        "code",
        "raison_sociale",
        "status",
        "db_name",
        "db_host",
        "db_port",
        "schema_digest",
        "schema_checked_at",
        "provisioned_at",
    )
    list_filter = ("status",)
    search_fields = ("code", "raison_sociale")
    ordering = ("code",)
    date_hierarchy = "created_at"

    readonly_fields = (
        "db_name",
        "db_user",
        "applied_heads",
        "schema_digest",
        "schema_checked_at",
        "provisioned_at",
        "last_error",
        "created_at",
        "updated_at",
    )
    # The Fernet token never reaches a form or a readonly view. Reading the control-plane
    # database must not be equivalent to holding every client's credentials (threat
    # T-02-07), and an admin page that renders the ciphertext puts it in a browser cache,
    # a screenshot and a support ticket.
    exclude = ("db_password_encrypted",)

    def has_delete_permission(self, request, obj=None):
        """Never. Deprovisioning is `manage.py deprovision_client`, which keeps the row.

        Art. 211 CGI requires ten years of record retention and the audit trail wants to
        know a client existed. A delete button here would also leave the client's
        database behind with nothing pointing at it — a true orphan, reapable only by hand.
        """
        return False


class MigrationRunResultInline(admin.TabularInline):
    """Who failed and why, on the same page as the run. One page, not a log grep."""

    model = MigrationRunResult
    extra = 0
    can_delete = False
    fields = ("client", "status", "heads_before", "heads_after", "duration_seconds", "error")
    readonly_fields = fields
    ordering = ("status", "client__code")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(MigrationRun)
class MigrationRunAdmin(admin.ModelAdmin):
    """Read-only history of every fan-out, with its per-client results inline.

    Note the two truths this page has to keep apart. `Client.schema_digest` is the
    **recorded** version — what was true after the last successful `migrate`. A `check`
    run here is the **probed** version, and it is authoritative. "Recorded: behind" and
    "probed: behind" are different facts, and a control plane that showed only one of
    them would be lying whenever somebody had run `migrate` by hand (threat T-02-36).
    """

    list_display = (
        "pk",
        "mode",
        "status",
        "started_at",
        "finished_at",
        "succeeded",
        "failed",
        "behind",
        "triggered_by",
    )
    list_filter = ("mode", "status", "triggered_by")
    date_hierarchy = "started_at"
    inlines = [MigrationRunResultInline]
    readonly_fields = (
        "started_at",
        "finished_at",
        "triggered_by",
        "target_heads",
        "mode",
        "status",
        "succeeded",
        "failed",
        "behind",
    )

    def has_add_permission(self, request):
        """Runs are created by `migrate_all`, never by hand — an empty one means nothing."""
        return False


@admin.register(BackupRun)
class BackupRunAdmin(admin.ModelAdmin):
    """Read-only evidence that each client really was backed up, and how large the dump was.

    A backup system that silently skips a client is worse than none, because it is
    trusted. This page is what turns "we take backups" into something an operator can
    check (threat T-02-50). Filtering on `failed` is the one view that matters.
    """

    list_display = (
        "client",
        "started_at",
        "finished_at",
        "status",
        "bytes",
        "schema_digest",
        "object_key",
    )
    list_filter = ("status",)
    search_fields = ("client__code", "object_key", "sha256")
    date_hierarchy = "started_at"
    readonly_fields = (
        "client",
        "started_at",
        "finished_at",
        "status",
        "bytes",
        "sha256",
        "object_key",
        "schema_digest",
        "error",
    )

    def has_add_permission(self, request):
        """Rows are created by the dump itself; an empty one would be a false record."""
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MigrationRunResult)
class MigrationRunResultAdmin(admin.ModelAdmin):
    """Also registered standalone, so "show me every failure across every run" is one filter."""

    list_display = ("run", "client", "status", "duration_seconds")
    list_filter = ("status",)
    search_fields = ("client__code", "error")
    readonly_fields = (
        "run",
        "client",
        "status",
        "heads_before",
        "heads_after",
        "duration_seconds",
        "error",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

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

from plateforme.control_plane.models import Client


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

"""The guard every `RunPython` and `RunSQL` callable must start with.

Django's multi-database documentation, on `allow_migrate`'s `model_name` hint:

    "is None for the RunPython and RunSQL operations unless they provide it using hints"

So the router has no model to classify. Schema operations gate themselves on
`allow_migrate_model`, which is why `magasins_magasin` never appears in the control-plane
database — but a `RunPython` callable is opaque Python and Django runs it against every
alias `migrate` is pointed at. A data migration written to backfill a tenant table will
happily run against `default` too, writing into the control plane or raising
`relation does not exist` halfway through a fan-out across the fleet (threat T-02-31).

Usage, and it must be the **first statement**::

    from plateforme.tenancy.migration_guard import migration_allowed

    def forwards(apps, schema_editor):
        if not migration_allowed(schema_editor, "stock"):
            return
        ...

Enforced by `tests/test_migration_conventions.py`, which walks every
`*/*/migrations/*.py` with `ast`. That check is itself proven to fire against synthetic
modules — including one that *calls* the guard without acting on its answer, which reads
as compliant to a grep and is not.
"""

from __future__ import annotations


def migration_allowed(schema_editor, app_label: str) -> bool:
    """True when this app's data may be written on the connection `migrate` is using.

    Imported inside the function because migration modules are loaded by the migration
    loader in contexts where importing the router at module scope is needlessly early.
    """
    from django.db import router

    return router.allow_migrate(schema_editor.connection.alias, app_label)

"""Reading a client database's schema version — the honest way and the fast way.

`02-RESEARCH.md` section 5 draws a distinction this module exists to preserve, because
collapsing it produces a control plane that lies:

* **Recorded** truth is `Client.applied_heads`, written after the last successful
  `migrate`. It is one row read, and it is what a list view shows.
* **Probed** truth is what these functions return. They open the client's database and
  ask it. That is authoritative, and it is what `migrate_all --check` gates a deploy on.

The two diverge the moment somebody runs `migrate` by hand. `Client.schema_checked_at`
records when the recorded value was last confirmed against reality.

Nothing here maintains a parallel version counter. Django already maintains
`django_migrations`, and a second source of truth would drift from it.
"""

from __future__ import annotations

import hashlib
import json

from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader

from plateforme.tenancy.router import BUSINESS_APPS


def read_applied_heads(alias: str) -> dict[str, str]:
    """`{app_label: latest applied migration name}` for the database behind `alias`.

    A dict rather than an integer because several business apps have independent
    migration chains: "stock is at 0004 but facturation is at 0011" is not expressible as
    one number, and a number would have to be maintained by hand.
    """
    loader = MigrationExecutor(connections[alias]).loader
    heads: dict[str, str] = {}
    for app_label, name in loader.applied_migrations:
        if heads.get(app_label, "") < name:
            heads[app_label] = name
    return heads


def pending_plan(alias: str) -> list:
    """The migrations this database still needs, as Django's own migration plan.

    Empty means "at head". This is the only honest way to say so — an empty plan is
    computed from the code's leaf nodes against the database's `django_migrations` table,
    so it cannot be fooled by a stale recorded value.
    """
    executor = MigrationExecutor(connections[alias])
    return executor.migration_plan(executor.loader.graph.leaf_nodes())


def is_behind(alias: str) -> bool:
    """True when the database behind `alias` has migrations still to apply."""
    return bool(pending_plan(alias))


def code_heads() -> dict[str, str]:
    """`{app_label: leaf migration name}` as the *code* currently defines it.

    The target a fan-out is aiming at, recorded on `MigrationRun.target_heads` so a run
    stays interpretable after the code has moved on. Read from the migration graph with
    no database connection — `MigrationLoader(None)` loads from disk only.
    """
    graph = MigrationLoader(None, ignore_no_migrations=True).graph
    heads: dict[str, str] = {}
    for app_label, name in graph.leaf_nodes():
        if heads.get(app_label, "") < name:
            heads[app_label] = name
    return heads


def schema_digest(applied_heads: dict[str, str]) -> str:
    """One short sha256 over the **business** apps' heads, for equality comparison.

    Filtered to `BUSINESS_APPS` deliberately. When `migrate` runs against a tenant alias,
    every control-plane operation becomes a no-op (each one gates on
    `allow_migrate_model`) but the migration is still **recorded** in that tenant's
    `django_migrations` table. That is normal Django behaviour, not a bug — and it means
    an unfiltered digest would churn on control-plane-only changes, so two clients at the
    identical business schema would compare unequal.
    """
    filtered = {k: v for k, v in sorted(applied_heads.items()) if k in BUSINESS_APPS}
    payload = json.dumps(filtered, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

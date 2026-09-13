# Migration conventions

Written for whoever executes Phases 4 through 10. Two rules. Both are cheap now and
expensive to retrofit once a client is live, which is the only reason they are written
down in Phase 2 rather than when they first bite.

Context: there is **one database per client business**, and a deploy runs
`manage.py migrate_all`, which fans the same migration out across every ACTIVE client.
Neither rule matters in a single-database project. Both matter here.

---

## 1. Every `RunPython` and `RunSQL` guards on the router

Django's multi-database documentation, on `allow_migrate`'s `model_name` hint:

> is `None` for the `RunPython` and `RunSQL` operations unless they provide it using hints

Schema operations gate themselves on `allow_migrate_model`, which is why
`magasins_magasin` does not exist in the control-plane database even though
`magasins.0001_initial` is recorded as applied there. A `RunPython` callable is opaque
Python, so Django cannot gate it and runs it against whatever connection `migrate` was
pointed at.

A data migration written to backfill a tenant table will therefore **also run against
`default`**, either writing into the control plane or raising `relation does not exist`
partway through a fan-out across the fleet.

```python
from django.db import migrations

from plateforme.tenancy.migration_guard import migration_allowed


def forwards(apps, schema_editor):
    if not migration_allowed(schema_editor, "stock"):
        return
    Mouvement = apps.get_model("stock", "MouvementStock")
    ...


class Migration(migrations.Migration):
    dependencies = [("stock", "0003_...")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
```

The guard must be the **first statement** (a docstring is allowed before it), and it must
`return` or `raise`. Calling `migration_allowed` and ignoring the answer reads as
compliant to a grep and is not; the check knows the difference.

**Enforced by** `tests/test_migration_conventions.py::test_tenant03_every_runpython_callable_guards_on_allow_migrate`,
which walks every `*/*/migrations/*.py` with `ast`. There are no `RunPython` migrations in
the tree yet, so that test passes vacuously today — which is why it is accompanied by
synthetic cases proving it rejects an unguarded module, accepts a guarded one, and rejects
one that consults the guard without acting on it.

`RunSQL` must also supply `reverse_sql`, or carry an `# irreversible: <reason>` comment
beside it. A fan-out across hundreds of databases should not be a one-way door, and if it
has to be, that should be visible in review rather than discovered during a rollback.

---

## 2. Expand / contract

A fan-out across hundreds of databases is not instantaneous. During a deploy the fleet is
**partially migrated**, so old and new application code must both work against both
schemas. This is not a theoretical window — `migrate_all --parallel 4` over 300 clients is
minutes, and one client failing leaves it partially migrated indefinitely until someone
fixes that client.

So never add a non-null column and backfill it in one migration. Split it across releases:

| Release | Migration | Application code |
|---|---|---|
| 1 (expand) | add the column **nullable**, no default requiring a table rewrite | writes both old and new; reads old |
| 2 (backfill) | `RunPython`, guarded, in batches | reads new when present, falls back to old |
| 3 (contract) | make it non-null, drop the old column | reads new only |

Each release must be deployable and revertible on its own, and `migrate_all --check` must
exit 0 between them.

The same shape applies to renames (add, dual-write, backfill, drop — never
`AlterField(name=...)`), and to dropping a column (stop writing it, deploy, then drop).

**Not enforced by a test**, deliberately: no static check can tell a safe non-null column
from an unsafe one. It is a review rule, and this document is where it is written down.

---

## Related

- `plateforme/tenancy/migration_guard.py` — the helper, with the citation.
- `plateforme/tenancy/router.py` — `CONTROL_PLANE_APPS` / `BUSINESS_APPS`. A new app must
  be added to one of them in the same commit that adds it to `INSTALLED_APPS`, or
  `manage.py check` fails with `tenancy.E001`.
- `manage.py migrate_all --check` — the deploy gate. Exits 1 if any ACTIVE client is
  behind.

---
phase: 02-tenancy-foundation-control-plane
plan: 05
subsystem: migration-fanout
tags: [tenancy, TENANT-03, migrate_all, process-pool, deploy-gate, migration-conventions]
requires:
  - 02-03 (router, registry, BUSINESS_APPS)
  - 02-04 (schema_version, provision_client, ACTIVE-only rule)
provides:
  - plateforme/control_plane/fanout.py — migrate_one (child process) / migrate_fleet
  - plateforme/control_plane/models.py — MigrationRun, MigrationRunResult
  - manage.py migrate_all [--check] [--parallel N] [--client CODE] [--fail-fast]
  - plateforme/tenancy/migration_guard.py — migration_allowed
  - docs/migration-conventions.md
affects:
  - 02-07 (phase gate — `migrate_all --check` exits 0)
  - Phases 4-10 (every migration they write obeys the two conventions)
tech-stack:
  added: []
  patterns:
    - failure isolation by process boundary, asserted by worker pid rather than assumed
    - exit code as the deploy contract, not a printed warning
    - recorded vs probed schema version kept distinguishable
    - a convention check proven to fire against synthetic modules before it is trusted
key-files:
  created:
    - plateforme/control_plane/fanout.py
    - plateforme/control_plane/migrations/0002_migrationrun.py
    - plateforme/control_plane/management/commands/migrate_all.py
    - plateforme/tenancy/migration_guard.py
    - docs/migration-conventions.md
    - tests/test_migration_conventions.py
  modified:
    - plateforme/control_plane/models.py
    - plateforme/control_plane/admin.py
    - tests/test_migrate_all.py
    - README.md
decisions:
  - "spawn start method explicitly, on every platform — fork would copy open psycopg sockets"
  - "the child process never touches the control plane; the parent composes the job and writes the rows"
  - "--check never updates applied_heads: probed truth is authoritative but is not recorded truth"
  - "CommandError(returncode=1) rather than sys.exit, so call_command and the shell agree"
metrics:
  tasks: 3
  commits: 3
  tests-added: 14
  completed: 2026-09-13
---

# Phase 2 Plan 05: Migration Fan-out Summary

`manage.py migrate_all` applies a migration across every ACTIVE client database, reports
per-client succeeded / failed / behind with durations and error text, and `--check` is a
deploy gate that is correct **by exit code**. One client failing does not stop the others,
and that is asserted by result-row count and by worker pid rather than inferred.

## The argument surface and the exit-code contract

```
manage.py migrate_all [--check] [--parallel N] [--client CODE ...] [--fail-fast]
                      [--triggered-by NAME]
```

| Argument | Default | Meaning |
|---|---|---|
| `--check` | off | Probe every ACTIVE client, apply nothing |
| `--parallel` | **4** | Clients migrated concurrently, each in its own process |
| `--client` | all ACTIVE | Repeatable; restricts the set |
| `--fail-fast` | **off** | Stop submitting new work after the first failure |
| `--triggered-by` | `command` | Recorded on `MigrationRun`: command / celery / deploy |

**Exit codes are the contract:**

| Mode | 0 | 1 |
|---|---|---|
| `--check` | every ACTIVE client at head | any ACTIVE client behind |
| apply | every client succeeded | any client failed |

Signalled with `CommandError(..., returncode=1)`, which
`execute_from_command_line` turns into `sys.exit(1)` and which `call_command` propagates —
so the shell and the test suite read the same number. Verified from a real shell, not only
through `call_command`; see Verification.

`--fail-fast` is off by default because the requirement is the opposite. When on, no *new*
work is submitted after the first failure, but results already in flight are still
collected: a half-reported run would be worse than either extreme.

## The `migrate_one` result dict — it crosses a pickle boundary

Later work must keep this picklable. Primitives only: no model instances, no exceptions,
no connections.

```python
{
    "pk": int,
    "code": str,
    "db_name": str,
    "host": str,
    "pid": int,                  # the child process that did the work
    "status": "ok" | "failed" | "behind",
    "heads_before": dict[str, str],
    "heads_after": dict[str, str],
    "duration_seconds": float,
    "error": str,                # repr(exc)[:2000], empty on success
}
```

The input side is `build_job(client, *, check_only) -> dict`, built in the **parent**, and
it carries `client.connection_params(direct=True)`.

### Why `pid` is in there

"Failure isolation is structural" is a claim about process boundaries. A test that only
checks the failed client was reported would pass just as happily against a thread pool, or
against a `for` loop with a `try`. `test_tenant03_one_client_failing_does_not_stop_the_others`
runs at `--parallel 3` and asserts that no result carries the parent's pid and that at
least two distinct pids appear. Without that, the process pool was decorative.

### Two design points the plan left open

**The child never touches the control plane.** The plan says *"Load the `Client` from
`default`"* in the child. It must not: a child that calls `django.setup()` reads the
settings module, whose `default` `NAME` is the **development** control plane —
pytest-django rewrites that in the parent's memory only. Under test, the fan-out would
have quietly read and migrated real clients. The parent therefore reads `Client`, composes
a picklable job carrying the client's own connection parameters, and writes every
`MigrationRunResult` itself.

**Nothing at module level in `fanout.py` imports a Django model.** A spawned child imports
the module to resolve the function it is asked to run, and that happens before
`django.setup()`. A model import there fails with `AppRegistryNotReady` inside a child
process, which is a miserable thing to debug.

**Start method: `spawn`, explicitly, on every platform.** `fork` would hand the child a
copy of every open psycopg socket and every lock held at the moment of the fork.

**`--parallel 1` is a real code path**, not a degenerate one — it runs `migrate_one`
in-process. It is the documented escape hatch if cross-database DDL lock contention
(assumption A4) ever turns out to be real.

## Recorded versus probed, kept distinguishable

Only a **successful apply** updates `Client.applied_heads`, `schema_digest` and
`schema_checked_at`. `--check` deliberately does not, even though its answer is
authoritative: recording it would erase the distinction between "recorded: behind" and
"probed: behind", which is the one thing that makes drift after a manual `migrate`
detectable (threat T-02-36). The operator admin shows both.

The per-client table has a fixed column order so two deploys can be diffed:

```
code            db_name               host              before                after                 status  duration error
GATE01          optique_c000002       127.0.0.1         -                     magasins=0001_initial ok      0.063s
1 ok, 0 failed, 0 behind (1 ACTIVE client(s), run #4)
```

`before` / `after` are filtered to `BUSINESS_APPS`, the same filter `schema_digest` uses
and for the same reason: `migrate` records control-plane migrations in a tenant's
`django_migrations` too, and printing them would bury the one column that changes.

## Assumption A4: no cross-database lock contention observed

`--parallel 3` against three client databases, each doing a real `migrate` from zero to
head, completed with no contention, no deadlock and no retry. That is a small sample — 3
clients, not 300 — so it is **consistent with** A4 rather than a proof of it. DDL locks are
per-database, so the theory says two `migrate` runs against two different databases cannot
contend; if that is ever wrong the failure mode is slowness rather than corruption, and
the fix is `--parallel 1`, which is a supported path. The real measurement belongs to the
first deploy against a fleet of meaningful size.

## The two migration-authoring conventions

`docs/migration-conventions.md`, linked from `README.md`.

1. **Every `RunPython` and `RunSQL` guards on the router**, as its first statement, using
   `migration_allowed(schema_editor, app_label)`. Django passes `model_name=None` for
   these operations, so the router cannot classify them and an unguarded data migration
   written for the tenant schema **also executes against `default`** (threat T-02-31).
2. **Expand / contract.** A fan-out across the fleet leaves it partially migrated for
   minutes — indefinitely if one client fails — so old and new code must both work
   against both schemas. Add nullable, deploy, backfill, make non-null in a *later*
   release. Not enforced by a test, deliberately: no static check can tell a safe
   non-null column from an unsafe one. It is a review rule, written down before any phase
   needs it.

### The check is proven to fire

There are no `RunPython` migrations in the tree yet, so
`test_tenant03_every_runpython_callable_guards_on_allow_migrate` passes **vacuously**. A
check that can never fail is not a check, so it is accompanied by:

| Synthetic case | Expected |
|---|---|
| unguarded callable | rejected |
| guarded callable | accepted |
| **calls the guard and ignores the answer** | rejected |

The third is the one worth having: `if migration_allowed(...): pass` reads as compliant to
a grep and changes nothing. The check requires a `return` or `raise` inside the `if`.

A fourth test asserts the glob actually finds the repository's migrations, so a layout
change cannot silently make both checks pass forever. And `migration_allowed` itself is
tested in both directions against the real router — a guard that always returned `True`
would make every migration look compliant while doing nothing.

## Deviations from Plan

### 1. [Rule 2 — Correctness] The child process does not read the control plane

See "Two design points" above. Following the plan's listing literally would have made a
test run migrate the developer's real clients.

### 2. The migration file was renamed to the plan's name

`makemigrations` produced `0002_migrationrun_migrationrunresult.py`; the plan's acceptance
criterion names `0002_migrationrun.py`. Renamed before it was applied anywhere, and
`makemigrations --check` confirms the graph is intact.

### 3. `migrate_one` returns `pid`, which the plan's result shape does not list

Added so the process boundary is assertable. See above.

## Verification

| Check | Result |
|---|---|
| `uv run pytest tests/test_migrate_all.py -q` | **0** — 5 passed, 0 pending |
| `uv run pytest tests/test_migration_conventions.py -q` | **0** — 10 passed |
| `uv run pytest tests/test_migration_conventions.py -q -k synthetic` | **0** — 6 passed |
| `uv run pytest -q -m "not slow and not pending"` | **0** — 60 passed, 1.28s |
| `uv run pytest -q --create-db -m "not pending"` | **0** — 71 passed, 6.77s |
| `makemigrations --check --dry-run --settings=config.settings.test` | **0** — no changes, no `tenant_*` connection |
| `manage.py check --settings=config.settings.test` | **0** — no `tenancy.E001` |
| `grep -n "ThreadPoolExecutor" fanout.py` | no match |
| `grep -n "raise" fanout.py` | only in a comment and a docstring |
| `grep -n "connection_params(direct=True)" fanout.py` | line 57 |
| `grep -n "django.setup()" fanout.py` | line 72, inside `migrate_one` |
| `grep -n "mark.pending" tests/test_migrate_all.py` | no match |
| `grep -n "migration-conventions" README.md` | line 100 |

### End to end from a real shell, against Compose

| Step | Exit | Output |
|---|---|---|
| `provision_client --code GATE01 ... --magasin Centre` | **0** | ACTIVE |
| `migrate_all --check` | **0** | `1 ok, 0 failed, 0 behind` |
| roll `magasins` back to zero on GATE01 | — | — |
| `migrate_all --check` | **1** | `0 ok, 0 failed, 1 behind`, row names `GATE01` |
| `migrate_all` (apply, `--parallel 4`) | **0** | `before -`, `after magasins=0001_initial` |
| `migrate_all --check` | **0** | back to head |
| `Client.applied_heads` / `schema_digest` / `schema_checked_at` | — | all updated |
| `deprovision_client --code GATE01 --yes-i-am-sure` | **0** | `pg_database` restored |

## Known Stubs

| Stub | File | Reason |
|---|---|---|
| 4 tests fail with `pytest.fail("pending: ...")` | `tests/test_magasin_scoping.py` (2), `tests/test_backup_restore.py` (2) | Owned by plans 02-06 and 02-07 |
| The Celery variant of `migrate_all` | — | Deliberately not built. Recorded in the command's docstring: add it when a run stops fitting inside a deploy window. A deploy that returns a job id it cannot wait on is not a gate |
| Retention/pruning of `MigrationRun` rows | — | Not needed at any foreseeable volume; noted so it is a decision rather than an oversight |

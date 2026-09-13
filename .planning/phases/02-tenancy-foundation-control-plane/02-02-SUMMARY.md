---
phase: 02-tenancy-foundation-control-plane
plan: 02
subsystem: control-plane-and-wave-0
tags: [tenancy, TENANT-02, TENANT-07, control-plane, fernet, conftest, wave-0]
requires:
  - 02-01 (settings package, static tenant aliases, pending marker, PG_ADMIN_* / TENANCY_FERNET_KEY)
provides:
  - control_plane.Client — the durable record every later plan reads from
  - Fernet-encrypted client database credentials
  - domaine.magasins.Magasin / MagasinScopedQuerySet / MagasinScopedModel
  - plateforme/tenancy/maintenance.py — autocommit psycopg connection direct to PostgreSQL
  - conftest.py with db_all / tenant_a / tenant_b and the stale-database reaper
  - tests/factories.py and the six Wave 0 named test files
affects:
  - 02-03 (router/middleware/tasks — un-pends 12 of these tests)
  - 02-04 (provisioning — writes Client, calls maintenance_connection)
  - 02-05 (migrate_all — iterates Client, writes applied_heads)
  - 02-06 (magasin seeding — un-pends the two TENANT-07 tests)
  - 02-07 (backup/restore — un-pends the two TENANT-09 tests)
tech-stack:
  added: []
  patterns:
    - credentials encrypted with MultiFernet even for a single key, so rotation is an env change
    - database-level CHECK constraints rather than clean() for tenancy invariants
    - explicit magasin projection, never an implicit filter
    - stale test databases reaped at session start, not at teardown
key-files:
  created:
    - plateforme/control_plane/apps.py
    - plateforme/control_plane/models.py
    - plateforme/control_plane/crypto.py
    - plateforme/control_plane/migrations/0001_initial.py
    - domaine/magasins/apps.py
    - domaine/magasins/models.py
    - domaine/magasins/migrations/0001_initial.py
    - plateforme/tenancy/maintenance.py
    - conftest.py
    - tests/factories.py
    - tests/test_control_plane.py
    - tests/test_magasin_scoping.py
    - tests/test_tenancy_router.py
    - tests/test_tenancy_context.py
    - tests/test_provisioning.py
    - tests/test_migrate_all.py
    - tests/test_backup_restore.py
  modified:
    - config/settings/base.py
    - .env
decisions:
  - "CheckConstraint takes condition= on Django 6.1.1; check= is gone, not merely deprecated"
  - "ClientStatus declared at module level, because Meta.constraints cannot see the enclosing class body"
  - "connection_params() reads db_host/db_port from the row; direct=True swaps in PG_ADMIN_*"
  - "the session-start reaper is skipped inside xdist workers, so one worker cannot drop another's databases"
metrics:
  tasks: 3
  commits: 3
  tests-added: 25
  completed: 2026-09-13
---

# Phase 2 Plan 02: Control Plane, Magasin Base & Wave 0 Summary

The control plane's `Client` row — every client's database name, host, port,
Fernet-encrypted credentials and per-app migration heads, with ACTIVE-implies-db_name
enforced by PostgreSQL rather than by `clean()`; the `Magasin` base that Phases 5–7
inherit their scoping conventions from; the one place in the system where a Python string
becomes DDL, quoted through `psycopg.sql.Identifier`; and a test suite that collects with
zero errors while 24 not-yet-implementable tests sit behind `pending` with real
specifications in their docstrings.

## The `Client` field list

Plans 02-03 through 02-07 code against exactly this.

| Field | Type | Note |
|---|---|---|
| `code` | `SlugField(20, unique)` | operator-facing identity |
| `raison_sociale` | `CharField(200)` | |
| `status` | `CharField(16, choices, default=PENDING, db_index)` | |
| `db_name` | `CharField(63, unique, null)` | 63 = PostgreSQL's `NAMEDATALEN - 1` |
| `db_host` | `CharField(255)` | day one, so sharding is a data change |
| `db_port` | `PositiveIntegerField(default=6432)` | PgBouncer by default |
| `db_user` | `CharField(63, null)` | |
| `db_password_encrypted` | `BinaryField(null)` | Fernet token |
| `applied_heads` | `JSONField(default=dict)` | `{app_label: migration_name}` |
| `schema_digest` | `CharField(64, blank)` | sha256 of sorted `applied_heads` |
| `schema_checked_at` | `DateTimeField(null)` | when recorded was last probed |
| `provisioned_at` | `DateTimeField(null)` | |
| `last_error` | `TextField(blank)` | |
| `created_at` / `updated_at` | `DateTimeField(auto_*)` | |

**Status constants** (`ClientStatus`, also reachable as `Client.PENDING` etc.):
`pending`, `creating_db`, `migrating`, `seeding`, `active`, `failed`, `suspended`,
`dropping`, `deleted`. `Client.ROUTABLE_STATUSES == {ACTIVE}` — the invariant that makes
TENANT-05 true is that everything else is invisible to the router.

**Methods:** `set_db_password(plaintext)`, `db_password` (property),
`alias` (property, `f"tenant_{pk}"`), `connection_params(direct: bool = False) -> dict`,
`advance(new_status, *, last_error="")`.

`connection_params()` returns `{"alias", "name", "host", "port", "user", "password"}` —
splattable straight into `register_client_database(**...)`. `direct=False` (the default)
uses the row's own `db_host`/`db_port`, which point at PgBouncer; `direct=True` swaps in
`settings.PG_ADMIN_HOST` / `PG_ADMIN_PORT` for migrations, provisioning and `pg_dump`.

## The resolved `CheckConstraint` keyword: `condition=`

Research assumption A6 was that `check=` is *deprecated* in favour of `condition=`.
Checked against the installed Django 6.1.1 rather than guessed —
`inspect.signature(CheckConstraint.__init__)` returns
`(self, *, condition, name, violation_error_code=None, violation_error_message=None)`.
`check=` is **removed**, not deprecated: passing it is a `TypeError`. Assumption A6 is
resolved and slightly stronger than stated.

Verified live in PostgreSQL, not just in the model:

```
active_client_has_db_name :: CHECK (((NOT ((status)::text = 'active'::text)) OR (db_name IS NOT NULL)))
```

## Tests currently `pending`, and who owns each

24 in total. `grep -rn "mark.pending" tests/` returning nothing is the phase gate.

| Owner plan | Tests |
|---|---|
| **02-03** | `test_tenant04_router_raises_when_no_client_bound`, `test_tenant04_router_never_returns_none`, `test_tenant04_business_models_never_migrate_to_default`, `test_tenant04_tenant_a_cannot_read_tenant_b_data`, `test_tenant04_every_installed_app_is_classified`, `test_tenant04_allow_migrate_never_raises`, `test_tenant04_related_fetch_from_another_tenant_is_refused`, `test_tenant04_context_does_not_leak_between_requests_on_one_thread`, `test_tenant04_middleware_refuses_a_thread_that_arrives_already_bound`, `test_tenant04_middleware_clears_on_the_exception_path`, `test_tenant04_celery_task_without_client_id_fails_closed`, `test_tenant04_celery_task_clears_context_even_when_the_task_raises`, `test_tenant08_connection_count_does_not_scale_with_alias_count` (13) |
| **02-04** | `test_tenant01_provision_client_creates_database_at_migration_head`, `test_tenant05_failed_provisioning_leaves_no_active_client`, `test_tenant05_rerun_after_kill_converges_to_active`, `test_tenant05_rerun_creates_no_second_database`, `test_tenant06_management_command_delegates_to_provision_client` (5) |
| **02-05** | `test_tenant03_migration_fanout_reports_which_clients_are_behind`, `test_tenant03_one_client_failing_does_not_stop_the_others` (2) |
| **02-06** | `test_tenant07_stock_and_caisse_are_scoped_per_magasin`, `test_tenant07_provisioning_seeds_requested_magasins` (2) |
| **02-07** | `test_tenant09_single_client_restore_produces_identical_data`, `test_tenant09_backup_runs_for_every_active_client` (2) |

Two extra router tests beyond the validation map (`allow_migrate_never_raises`,
`related_fetch_from_another_tenant_is_refused`) were added here because plan 02-03's own
acceptance criterion expects seven tests in that file.

## Verified live, not assumed

- **The reaper reaps exactly what it should.** Created `test_client_stale_probe`,
  `test_optique_test_stale_probe` and `optique_do_not_touch_probe`; a pytest run reported
  `reaped 2 stale test database(s)` and left `optique_do_not_touch_probe` standing
  (threat T-02-09).
- **The reaper degrades rather than fails.** With `PG_ADMIN_PORT=1` the session emits a
  `UserWarning` and the four settings-only tests still pass — a pure-settings run does
  not depend on Docker.
- **The maintenance connection does real DDL.** Connected direct to PostgreSQL 18.6,
  `CREATE DATABASE test_maint_probe`, `database_exists` → True, `databases_matching` →
  `['test_maint_probe']`, `drop_database_force` → gone.
- **`db_all` opens all three aliases.** A throwaway test printed
  `default -> test_optique_control`, `tenant_a -> test_optique_test_a`,
  `tenant_b -> test_optique_test_b`, then was deleted.
- **The password really is unreadable from the column.** The test reads
  `db_password_encrypted` through `connections["default"].cursor()`, not through the
  model — the model is exactly the layer that would make a plaintext column look
  encrypted.

## Deviations from Plan

### 1. [Rule 3 — Blocking] `ClientStatus` moved to module level

- **Found during:** Task 1
- **Issue:** the research nests `Status` inside `Client` and references
  `Status.ACTIVE` from `Meta.constraints`. `Meta` is a nested class body and cannot see
  the enclosing class's namespace, so this raised `NameError: name 'Status' is not
  defined` at import.
- **Fix:** `ClientStatus(models.TextChoices)` declared at module level;
  `Client.Status = ClientStatus` and the nine `Client.PENDING`-style shorthands preserve
  every call shape the research and the later plans use.
- **Commit:** `66c400c`

### 2. [Rule 2 — Correctness] The reaper must not run inside xdist workers

- **Found during:** Task 3
- **Issue:** the plan specifies `pytest_sessionstart` force-dropping every database
  matching `test_optique_test_%`. Under `-n 2` that hook runs in **each worker**, and the
  xdist suffix means worker `gw1`'s pattern also matches `test_optique_test_a_gw0` —
  a worker starting a moment later would drop a running worker's databases. The result
  would be exactly Pitfall 8's symptom (green at `-n 0`, flaky at `-n 4`) arriving by a
  different route.
- **Fix:** the hook returns immediately when `session.config` has `workerinput`, which
  exists only on workers. The reaper therefore runs once, in the controlling process,
  before any worker starts. Verified: `pytest -n 2 -q -m "not slow and not pending"`
  exits 0.
- **Commit:** `47002ee`

### 3. [Rule 2 — Correctness] A second prefix guard beside the LIKE pattern

- **Found during:** Task 3
- **Issue:** T-02-09 says a reaper pattern that is too broad destroys developer data, and
  the mitigation asks for "an explicit guard that refuses to drop any name not matching
  the prefixes" *in addition to* the pattern.
- **Fix:** `STALE_TEST_DB_PREFIXES` is checked per name immediately before each DROP, and
  a non-matching name produces a warning instead of a drop. Unreachable given the current
  patterns — which is the point: if someone widens them, this refuses rather than obeys.
- **Commit:** `47002ee`

### 4. Two acceptance-criterion greps required rewording prose, not weakening the check

Two criteria are `grep` patterns that must return nothing, and two docstrings tripped them
by *naming the thing they were warning against*:

- `grep -niE "(xor|...)" plateforme/control_plane/crypto.py` matched the word "XOR" in a
  sentence explaining why not to use one. Reworded to "a byte-mixing trick".
- `grep -rn "django_db_setup" conftest.py tests/` matched a docstring explaining why that
  fixture must never be overridden. Reworded to "pytest-django's database-setup fixture",
  which is exactly the convention plan 02-01 already adopted in
  `config/settings/test.py`.
- `grep -n "_nodb_cursor" plateforme/tenancy/maintenance.py` likewise matched prose
  explaining why not to reuse it. Reworded to "Django's private no-database cursor
  helper".

No check was relaxed; in each case the warning survives in plain English.

## Known Stubs

| Stub | File | Reason |
|---|---|---|
| 24 tests fail with `pytest.fail("pending: implemented by plan 02-0X")` | `tests/` | Deliberate and specified by this plan — each carries a full docstring specification and is deselected from the quick loop. Owner plans tabulated above. |
| `DATABASE_ROUTERS = []` | `config/settings/base.py` | Still 02-03's to fill. |
| `config/urls.py` has empty `urlpatterns` | `config/urls.py` | No application to route yet. |

**One consequence to carry into 02-03:** because `DATABASE_ROUTERS` is still `[]`,
`manage.py migrate --settings=config.settings.local` (plan verification step 5) created
`magasins_magasin` in the local development `optique_control` database. That is correct
for this plan and wrong from 02-03 onward — the local control database should be dropped
and re-migrated once the router is wired, so that the development database matches the
invariant `test_tenant04_business_models_never_migrate_to_default` asserts.

## Verification

| Check | Result |
|---|---|
| `uv run pytest --collect-only -q` | **0** — 34 collected, zero collection errors |
| `uv run pytest -q -m "not slow and not pending"` | **0** — 10 passed, 24 deselected, 0.45s |
| `uv run pytest -n 2 -q -m "not slow and not pending"` | **0** — 10 passed, 0.79s |
| `uv run pytest -q -m "pending" --collect-only` | 24 collected (criterion: ≥13) |
| `uv run pytest tests/test_control_plane.py -q -m "not pending"` | **0** — 4 passed |
| `uv run pytest tests/test_magasin_scoping.py -q -m "not pending"` | **0** — 2 passed |
| `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` | **0** — no changes detected |
| `uv run python manage.py migrate --settings=config.settings.local` | **0** — `control_plane` and `magasins` applied |
| every name in the 02-VALIDATION.md map collectable | **23/23** |
| `grep -rn "django_db_setup" conftest.py tests/` | no match |
| `grep -rn "^from plateforme.tenancy" tests/` | no match |
| `grep -niE "client\s*=\s*models\.ForeignKey" domaine/magasins/models.py` | no match |
| `grep -nE 'f"(CREATE\|DROP) DATABASE' plateforme/tenancy/maintenance.py` | no match |
| `grep -n "_nodb_cursor" plateforme/tenancy/maintenance.py` | no match |
| `grep -c "TENANT_DBS" conftest.py` | 4 (criterion: ≥2) |

---
phase: 02-tenancy-foundation-control-plane
plan: 07
subsystem: backup-restore
tags: [tenancy, TENANT-09, backup, restore, checksum, pg_dump, pg_restore, phase-gate]
requires:
  - 02-04 (provisioner, create_role_if_absent, derive_db_name, schema_digest)
  - 02-05 (migrate_all --check, the deploy gate the phase gate reuses)
  - 02-06 (stock and caisse, so a restore has data worth verifying)
provides:
  - plateforme/control_plane/backup.py — backup_client / restore_client
  - plateforme/control_plane/checksum.py — tenant_checksum / tenant_checksum_detail
  - plateforme/control_plane/storage.py — BackupStorage interface
  - plateforme/control_plane/tasks.py — the Beat fan-out
  - backup_client / restore_client / tenant_checksum commands
  - docs/restore-runbook.md
affects:
  - Phase 1 (four procurement questions, recorded in the runbook)
  - Phase 6 (facture numbering depends on the sequence positions the checksum covers)
tech-stack:
  added: []
  patterns:
    - verification by ordered per-table digest, never by row count
    - restore beside, never in place; the control-plane row is the switch
    - a drill that mutates between backup and restore, so a no-op cannot pass
key-files:
  created:
    - plateforme/control_plane/backup.py
    - plateforme/control_plane/checksum.py
    - plateforme/control_plane/storage.py
    - plateforme/control_plane/tasks.py
    - plateforme/control_plane/migrations/0003_backuprun.py
    - plateforme/control_plane/management/commands/backup_client.py
    - plateforme/control_plane/management/commands/restore_client.py
    - plateforme/control_plane/management/commands/tenant_checksum.py
    - docs/restore-runbook.md
  modified:
    - plateforme/control_plane/models.py
    - plateforme/control_plane/admin.py
    - plateforme/tenancy/provisioner.py
    - config/settings/base.py
    - conftest.py
    - tests/test_backup_restore.py
    - .planning/REQUIREMENTS.md
decisions:
  - "pg_restore connects as the client's role, because --no-owner otherwise leaves objects owned by the restorer"
  - "timestamps carry seconds and object keys carry the BackupRun pk — minute granularity silently overwrites"
  - "a restore refuses an existing target rather than adopting it"
  - "create_role_if_absent converges the password on the control-plane record"
  - "pruning is deliberately not implemented until the retention policy is a legal answer"
metrics:
  tasks: 3
  commits: 3
  tests-added: 19
  completed: 2026-09-13
---

# Phase 2 Plan 07: Backup, Verified Restore & the Phase Gate Summary

TENANT-09 in the strong form the requirement demands: **restoring one client's logical
database alone has been performed and verified**, with the neighbour proven untouched —
by a test, and again by hand against Compose.

The word that made this plan hard is *verified*. Running the drill rather than reading the
plan found four defects, one of which would have produced a restored database nobody could
read.

## The artifact naming scheme

```
client/<code>/<YYYY>/<YYYYMMDDTHHMMSSZ>-<backup_run_pk>.dump
```

Grouped by client then year, so "every backup for this optician" and "everything older
than N years" are prefix listings rather than scans. **Seconds, and the `BackupRun`
primary key** — see Defect 3; the research's minute granularity silently overwrites.

Restore targets: `<db_name>_restore_<YYYYMMDDTHHMMSSZ>`. Deliberately **not** a name
`is_client_database_name` recognises, so `reap_orphan_databases` can never drop a restore
in flight or awaiting acceptance.

### `BackupRun`

| Field | Note |
|---|---|
| `client` | FK PROTECT |
| `started_at` / `finished_at` | the row is created **before** the dump starts |
| `status` | `running` / `ok` / `failed` |
| `bytes`, `sha256`, `object_key` | |
| `schema_digest` | the client's digest **at dump time** |
| `error` | |

A row exists per *attempt*, created first, so a crash mid-dump is a `running` row that
never finished rather than nothing at all. Nobody goes looking for an absence.

## The restore procedure, and the cutover mechanism

`manage.py restore_client --code OPT001 --backup <id|key> [--cutover] [--force]`

1. Refuse if the backup belongs to a different client — a `--code` typo during an incident
   would otherwise be a cross-client leak.
2. Refuse on a `schema_digest` mismatch unless `--force`; digests are only comparable
   within one schema version.
3. Download and verify `sha256` — a corrupted archive fails *here*, not halfway through
   `pg_restore`.
4. **`create_role_if_absent`** — roles are cluster-wide and not in the dump.
5. Create a **new** database, refusing to reuse an existing one.
6. `pg_restore --exit-on-error --no-owner --no-privileges`, **as the client's own role**.
7. `tenant_checksum` on the result, printed, **before** any cutover.
8. Cutover only when asked: one transactional `UPDATE` of `Client.db_name` plus
   `evict_alias`. The old database is **retained**.

**The cutover is the control-plane row.** That is what makes restore reversible: rolling
back is pointing `db_name` at the database that is still sitting there.

Full operator procedure: **`docs/restore-runbook.md`**.

## The drill was executed, twice, two ways

### In the suite

`test_tenant09_single_client_restore_produces_identical_data` — two real clients on one
PostgreSQL instance, distinguishable data in each, A backed up, **A then mutated** (a row
deleted, a column changed, a row inserted), A restored with `--cutover`, then:

- `tenant_checksum(A) == before_A` — the data came back;
- `tenant_checksum(B) == before_B` — **the neighbour was untouched.**

The test asserts the mutation moved the digest *before* going on, so it cannot pass as a
tautology, and asserts `before_a != before_b` so the neighbour check is not vacuous.

### By hand, against Compose

| Step | `tenant_checksum(SMOKE09)` |
|---|---|
| after seeding, captured by backup #3 | `0281b9f0319183053778a9eb84e924e29cea2919ee4d2df906020f1bb14f039b` |
| after mutating (delete a magasin, add another) | `dfcd62271b0f8988e910cc83acaaf9e542c208d14c4de2a8a3fcce47cda25f30` |
| restored into `optique_c000004_restore_20260913T191204Z`, digest printed before cutover | `0281b9f0…` |
| after cutover | `0281b9f0…` — **exact match** |

An earlier pass also confirmed the no-cutover path: the restored database read
`0281b9f0…` while the live one was still `0281b9f0…`-mutated, i.e. the live database was
untouched.

### Measured timings, and why they mean little

Backup ~0.1 s producing a ~14 KB archive; restore including database creation and
checksum ~0.6 s. **These say nothing about a real client.** `pg_restore` rebuilds indexes
rather than copying them, so restore time scales with index count against a database that
will be gigabytes. Re-measure against a real dataset before quoting an RTO. Recorded in
the runbook with the same caveat.

## `tenant_checksum`

```
sha256( sorted( {table: md5(string_agg(md5(t::text) ORDER BY row_md5))} + {__sequences__} ) )
```

Three details, each of which the digest is wrong without, and each with its own test:

| Detail | Why | Test |
|---|---|---|
| the row **hashes** are ordered, not the rows | `pg_restore` does not preserve physical order; an order-dependent digest reports every restore as a failure | `…_is_independent_of_physical_row_order` |
| `SET TIME ZONE 'UTC'`, then restored | `timestamptz` renders per session TZ and every ledger row has a `created_at` | `…_is_reproducible_across_session_timezones` |
| sequences included | a restored database with reset sequences is not identical even when every row matches — and Phase 6's facture numbering depends on counters | `…_includes_sequence_positions` |

Plus `…_detects_a_single_changed_column_value` in both directions (a checksum that cannot
fail is not a checksum; one that is unstable at rest fails every restore), and
`tenant_checksum_detail` localising a change to one table.

## Four defects the drill found

### 1. `--no-owner` produced a database the client could not read

`pg_restore --no-owner` strips the `ALTER OWNER` statements — necessary, because the dump
names an owner that may not exist on the target — but every object then ends up owned by
**whoever ran the restore**. Restoring as the superuser gave:

```
psycopg.errors.InsufficientPrivilege: permission denied for table stock_mouvementstock
```

A perfectly good database the client's own role could connect to and not read — the same
family as Pitfall 10, one step further along. `pg_restore` now connects as
`client.db_user`, which also matches what `migrate` produces during provisioning, so a
restored database is indistinguishable from a provisioned one. Least privilege is a side
effect rather than the reason. (Since PostgreSQL 15 the `public` schema belongs to
`pg_database_owner`, so the database owner has the rights to create in it.)

### 2. A restore would have restored *into* a populated database

Restore targets were named to the minute, and `create_database`'s existence guard —
correct for provisioning, where a killed run must adopt the database it already created —
silently adopted the existing one. `pg_restore` then ran into existing objects and, under
`--exit-on-error`, aborted partway, leaving something that looked restored.

Hit on **exactly the flow the runbook prescribes**: restore to verify, then restore again
to cut over. Timestamps now carry seconds, and a collision is refused outright rather than
adopted.

### 3. Two backups in one minute overwrote each other

The same minute granularity in the object key. Both `BackupRun` rows would still say `ok`,
and one would point at the other's snapshot — in the table whose entire purpose is to make
backup coverage auditable rather than assumed. The key now carries the `BackupRun` primary
key, so it is unique by construction.

### 4. A killed run's leftover role poisoned every later provision

`create_role_if_absent` skipped an existing role, keeping whatever password it already
had, while provisioning generated and stored a new one. The result was
`FATAL: password authentication failed for user "optique_u000013"` from a step nowhere
near the cause. It now issues `ALTER ROLE … PASSWORD` when the role exists: the control
plane is the source of truth for the credential, and a role whose password disagrees with
it is simply unusable. Verified by planting the landmine and watching provisioning
converge. The session reaper also drops stale `test_client_u*` roles, since roles are
cluster-wide and survive their databases.

### And one I caused myself, which is the best evidence for the 02-04 fix

An ad-hoc cleanup script of mine used `starts_with(datname, 'optique_c')` and dropped
**`optique_control`** — the development control plane — minutes after fixing the identical
bug in `reap_orphan_databases`. Recreated from `docker/postgres/init/00-databases.sql` and
`migrate`; no client data existed at the time. It is now a warning box in the runbook. The
production command is safe because it matches prefix **plus exactly six digits**; the
lesson is that `startswith` feels sufficient and is not.

## Deviations from Plan

### 1. [Rule 1 — Bug] `--compress=zstd:9` is now the `BACKUP_COMPRESSION` setting

Compression methods are compiled in, not universal. Homebrew's keg-only libpq answers
*"invalid compression specification: this build does not support compression with ZSTD"*.
`zstd:9` remains the default and was **verified in the Debian `postgresql-client-18` build
the app image ships** (exit 0, `pg_restore --list` parses it) rather than assumed; this
host sets `gzip:9`. The value must be one a *restoring* build also supports, so it is
deployment-wide.

`PG_DUMP_BIN` / `PG_RESTORE_BIN` were added for the same reason: the binaries are not on
this host's PATH. Both default to the bare name, which is what the image provides.

### 2. [Rule 1 — Bug] The row-order test cannot be written across two databases

The plan specifies *"build the same logical rows in two databases in different insertion
orders and assert the digests match."* That cannot pass, and should not: two independently
migrated tenants differ in `django_migrations.applied` and in every `created_at`. Diagnosed
rather than guessed — a throwaway probe reported exactly those two tables.

The property under test is physical row order, and a restore compares one database against
its own earlier state, so the test deletes and re-inserts the same rows with their original
primary keys and timestamps in reverse order, **asserting the heap layout actually changed**
before asserting the digest did not.

### 3. `tenant_checksum` restores the caller's session timezone

The plan says `SET TIME ZONE 'UTC'` on the connection first. It also puts it back. Leaving
UTC behind on a connection that returns to a pool is the session-state hazard the whole
project is careful about (threat T-02-02).

### 4. Three tests beyond the plan's list

`…_restore_never_restores_into_an_existing_database`,
`…_backup_keys_are_unique_even_within_one_second` and
`…_restore_refuses_a_backup_belonging_to_another_client` — the first two pin defects 2 and
3 so they cannot return; the third closes the likeliest operator error during an incident.

---

# Phase 2 gate

Every check in this plan's verification section, run, with its exit code.

| # | Check | Result |
|---|---|---|
| 1 | `uv run pytest -q --create-db` | **exit 0** — **100 passed**, 0 deselected |
| 2 | `uv run pytest -x -q -m "not slow and not pending"` | **exit 0** — 76 passed, 24 deselected, **1.30 s** (budget 30 s) |
| 2b | `uv run pytest -n 2 -q -m "not slow and not pending"` | **exit 0** — 76 passed; xdist does not collide |
| 3 | `uv run python manage.py migrate_all --check` | **exit 0** — `2 ok, 0 failed, 0 behind (2 ACTIVE client(s))`, run against two real provisioned clients rather than vacuously against none |
| 4 | `grep -rn "mark.pending" tests/` | **no match** |
| 5 | `uv run python manage.py check --settings=config.settings.test` | **exit 0** — no issues, no `tenancy.E001` |
| 6 | `uv run python manage.py makemigrations --check --dry-run` | **exit 0** — no changes (both `local` and `test`) |
| 7 | Every named test in the `02-VALIDATION.md` map | **23/23 exist and pass**, enumerated individually |
| 8 | The five research-correction greps | **5/5 pass** |

### 8 in detail — the five mechanical corrections

| Grep | Expected | Result |
|---|---|---|
| `grep -rnE "ensure_defaults\|prepare_test_settings" plateforme/ config/` | nothing | no match |
| `grep -rn "\.reset(" plateforme/tenancy/` | nothing | no match |
| `grep -rn "ATOMIC_REQUESTS" config/settings/` | nothing | no match |
| `grep -rn "del connections.settings" plateforme/` | only `# NEVER` | one line: `registry.py:129: # NEVER: del connections.settings[alias]` |
| `grep -rn "django_db_setup" conftest.py tests/ config/` | nothing | no match |

### 7 in detail — the per-requirement map

| Requirement | Named test(s) | Result |
|---|---|---|
| TENANT-01 | `test_tenant01_provision_client_creates_database_at_migration_head` | pass |
| TENANT-02 | `test_tenant02_control_plane_records_db_name_host_and_schema_version` | pass |
| TENANT-03 | `test_tenant03_migration_fanout_reports_which_clients_are_behind`, `test_tenant03_one_client_failing_does_not_stop_the_others` | pass |
| TENANT-04 | seven named tests (`router_raises_when_no_client_bound`, `router_never_returns_none`, `business_models_never_migrate_to_default`, `context_does_not_leak_between_requests_on_one_thread`, `tenant_a_cannot_read_tenant_b_data`, `celery_task_without_client_id_fails_closed`, `every_installed_app_is_classified`) | pass |
| TENANT-05 | `failed_provisioning_leaves_no_active_client`, `rerun_after_kill_converges_to_active`, `rerun_creates_no_second_database` | pass |
| TENANT-06 | `test_tenant06_management_command_delegates_to_provision_client` | pass |
| TENANT-07 | `test_tenant07_provisioning_seeds_requested_magasins`, `test_tenant07_stock_and_caisse_are_scoped_per_magasin` | pass |
| TENANT-08 | three settings tests **plus the load check** | pass |
| TENANT-09 | `test_tenant09_single_client_restore_produces_identical_data`, `test_tenant09_backup_runs_for_every_active_client` | pass |

### TENANT-08 is now closed

It was left unticked because its fourth named test was `pending`. That test is implemented
and green, and it measures rather than asserts configuration:

```
TENANT-08: 300 aliases, concurrency 4 -> baseline 0, after registration 0, peak 4, settled 0
```

Registering 300 aliases opened **zero** connections; serving all 300 at concurrency 4 held
a **peak of 4**, sampled from `pg_stat_activity` every 5 ms throughout, settling back to 0.
Mutation-checked in 02-03: `CONN_MAX_AGE = 600` does not merely fail the assertion, it
exhausts PostgreSQL's connection slots. **Ticked.**

## All nine TENANT requirements, final state

| Req | State | Evidence |
|---|---|---|
| TENANT-01 | **ticked** | `provision_client`; proven by `pending_plan(alias) == []` |
| TENANT-02 | **ticked** | control plane records db_name, host, `applied_heads` + digest |
| TENANT-03 | **ticked** | `migrate_all [--check]`, both halves, exit codes verified from a shell |
| TENANT-04 | **ticked** | four layered defences, plus `REVOKE CONNECT` below the application |
| TENANT-05 | **ticked** | state machine; rerun converges, proven by `pg_database` counts |
| TENANT-06 | **ticked** | 58-line command, source-level assertion against drift |
| TENANT-07 | **ticked** | multi-magasin provisioning + explicit magasin projection |
| TENANT-08 | **ticked** | 300 aliases → peak 4 connections, measured |
| TENANT-09 | **ticked** | restore drill performed and verified, neighbour untouched |

No exceptions. `grep "^- \[ \] \*\*TENANT-0" .planning/REQUIREMENTS.md` returns nothing.

## Still open — for Phase 1, not for Phase 2

None of these blocks anything built here; the implementation is deliberately
provider-independent. All four are recorded in `docs/restore-runbook.md` where the
operator who hits them will find them.

1. **Does the provider's application role have `CREATEDB`?** (`02-RESEARCH.md` Open
   Question 2 — the highest-value unknown in the phase.) Contained behind the two-method
   `DatabaseProvisioner`; an API implementation costs a day.
2. **Is there a cap on logical databases per instance?** (Open Question 3.) Sets the
   sharding point. `Client.db_host` exists from day one so sharding is a data change.
3. **EU-resident, encrypted-at-rest object storage.** A dump is a complete copy of one
   optician's ordonnances. Gated on LEGAL-02. `BACKUP_STORAGE` is an interface;
   `LocalFilesystemStorage` is honest about being development-only.
4. **Retention is a legal question.** Art. 211 CGI's ten years is a *records* obligation,
   not a backup-rotation obligation. `BACKUP_RETENTION` is a setting with a defensible
   default and **pruning is deliberately not implemented** — a rotation task written
   against a guessed policy deletes things (assumption A5).

## Known Stubs

| Stub | File | Reason |
|---|---|---|
| No backup pruning | — | Deliberate; see open question 4 |
| `LocalFilesystemStorage` only | `plateforme/control_plane/storage.py` | An S3 implementation of the two-method interface; gated on LEGAL-02 |
| No Beat schedule row committed | — | `backup_all_active_clients` is a registered task; the *cadence* is an operator decision made in the `django-celery-beat` admin, which is why it is DB-backed |
| `resolve_client` reads `request.user.client_id` | `plateforme/tenancy/middleware.py` | Phase 3 swaps in the JWT claim; the contract does not change |

## Self-Check

All 9 files claimed created exist on disk. All 3 commits exist in the worktree history.
Every number in this summary was produced by a command run in this session.

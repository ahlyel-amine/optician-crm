---
phase: 02-tenancy-foundation-control-plane
plan: 04
subsystem: provisioning
tags: [tenancy, TENANT-01, TENANT-05, TENANT-06, provisioning, ddl, operator-commands]
requires:
  - 02-01 (settings package, TENANT_DB_LOCALE_PROVIDER / TENANT_DB_ICU_LOCALE, PG_ADMIN_*)
  - 02-02 (control_plane.Client, maintenance_connection, conftest reaper, pending tests)
  - 02-03 (registry, router, context, BUSINESS_APPS)
provides:
  - plateforme/tenancy/provisioner.py — DatabaseProvisioner interface + SqlProvisioner
  - plateforme/control_plane/provisioning.py — provision_client / deprovision_client
  - plateforme/control_plane/schema_version.py — read_applied_heads / pending_plan / is_behind / code_heads / schema_digest
  - plateforme/control_plane/seeding.py — seed_new_client
  - three operator commands and the control-plane admin
  - conftest allow_runtime_tenant_aliases fixture
affects:
  - 02-05 (migrate_all — uses schema_version and the ACTIVE-only rule)
  - 02-06 (seeding — extends seed_new_client and the --magasin path)
  - 02-07 (backup/restore — uses create_role_if_absent, derive_db_name, schema_digest)
  - Phase 12 (self-serve signup calls provision_client from a Celery task)
tech-stack:
  added: []
  patterns:
    - a two-method provisioner interface as containment for an open procurement question
    - status state machine with per-step idempotency instead of a transaction
    - identifiers via psycopg.sql.Identifier, DDL literals via psycopg.sql.Literal
    - names derived from the primary key, so a killed run adopts rather than orphans
key-files:
  created:
    - plateforme/tenancy/provisioner.py
    - plateforme/control_plane/provisioning.py
    - plateforme/control_plane/schema_version.py
    - plateforme/control_plane/seeding.py
    - plateforme/control_plane/admin.py
    - plateforme/control_plane/management/commands/provision_client.py
    - plateforme/control_plane/management/commands/deprovision_client.py
    - plateforme/control_plane/management/commands/reap_orphan_databases.py
    - tests/test_provisioner_sql.py
  modified:
    - config/settings/base.py
    - config/settings/test.py
    - config/urls.py
    - conftest.py
    - tests/test_provisioning.py
decisions:
  - "CREATE DATABASE and CREATE ROLE reject bound parameters; DDL literals use sql.Literal"
  - "ICU locale provider, not LC_COLLATE — the stock postgres image has only en_US.utf8"
  - "database and role name prefixes are settings, so tests cannot adopt a dev client's database"
  - "REVOKE CONNECT FROM PUBLIC at creation — PostgreSQL's default made every client reachable"
  - "reaper predicate is prefix + exactly six digits, never LIKE and never startswith"
metrics:
  tasks: 3
  commits: 3
  tests-added: 15
  completed: 2026-09-13
---

# Phase 2 Plan 04: Provisioning Summary

`provision_client` — a status state machine that creates a client's database, migrates it
to head, seeds its magasins and activates it, and that **converges on rerun** after being
killed at any step rather than rolling back. Plus the two-method `DatabaseProvisioner`
that keeps an open procurement question from becoming a redesign, and three operator
commands of which the important one contains no provisioning logic at all.

Running the acceptance criteria rather than reading them found three defects, one of them
a genuine cross-client exposure. They are the most useful thing in this summary.

## The public surface, for plans 02-05 through 02-07

### `plateforme/control_plane/provisioning.py`

| Name | Contract |
|---|---|
| `provision_client(*, code, raison_sociale, magasins, db_host=None) -> Client` | Idempotent. Returns an ACTIVE client or raises, having marked the row FAILED |
| `deprovision_client(client) -> Client` | Drops the database, advances to DELETED, **keeps the row** |
| `derive_db_name(pk) -> str` | `f"{settings.TENANT_DB_NAME_PREFIX}{pk:06d}"` |
| `derive_db_user(pk) -> str` | `f"{settings.TENANT_DB_USER_PREFIX}{pk:06d}"` |
| `is_client_database_name(name) -> bool` | Prefix **plus exactly six digits**. See defect 1 |

Status sequence, and the only atomic step is the first:

```
PENDING ─► CREATING_DB ─► MIGRATING ─► SEEDING ─► ACTIVE
             │               │            │
             └───────────────┴────────────┴──► FAILED ──► (rerun) ──► ...
                                                 │
                                                 └──► DROPPING ──► DELETED
```

Per-step idempotency, which is why a rerun converges instead of needing a rollback:

| Step | Mechanism |
|---|---|
| Identity | `get_or_create(code=...)`; `db_name` derived from the pk, never regenerated |
| `CREATE ROLE` | `SELECT 1 FROM pg_roles WHERE rolname = %s`, plus `DuplicateObject` caught |
| `CREATE DATABASE` | `SELECT 1 FROM pg_database WHERE datname = %s`, plus `DuplicateDatabase` caught |
| `migrate` | Django's own `django_migrations` table, free |
| Seed | `get_or_create` only — `grep -cE "\.create\(" seeding.py` is 0 |
| Activate | one transactional `UPDATE` on `default` |

### `plateforme/control_plane/schema_version.py`

`read_applied_heads(alias)`, `pending_plan(alias)`, `is_behind(alias)`, `code_heads()`,
`schema_digest(applied_heads)`.

`schema_digest` is filtered to `BUSINESS_APPS`. When `migrate` runs against a tenant alias
every control-plane operation no-ops but the migration **is still recorded** in that
tenant's `django_migrations`, so an unfiltered digest would churn on control-plane-only
changes and two clients at identical business schemas would compare unequal. Confirmed on
the live SMOKE01 client, whose `applied_heads` lists `auth`, `admin`, `sessions`,
`contenttypes` and `django_celery_beat` alongside `magasins`.

### `plateforme/tenancy/provisioner.py`

`DatabaseProvisioner` is an `abc.ABC` with **exactly two** abstract methods,
`create_database` and `drop_database`, pinned by a test. `SqlProvisioner` adds
`create_role_if_absent` (not on the interface — an API provider creates owning roles the
same way it creates databases, so putting it in the contract would make the interface
describe SQL). `get_provisioner()` reads `settings.DATABASE_PROVISIONER`.

## The name derivation, and why the prefix is a setting

```
db_name = f"{settings.TENANT_DB_NAME_PREFIX}{pk:06d}"   # optique_c000047
db_user = f"{settings.TENANT_DB_USER_PREFIX}{pk:06d}"   # optique_u000047
```

Plans 02-05 and 02-07 depend on the `optique_c` prefix; `is_client_database_name` is the
predicate to use rather than a hand-rolled one.

The plan specified the literal `f"optique_c{client.pk:06d}"`, and one acceptance criterion
greps for that string. It is a setting instead, and this is the one criterion in the plan
that is **not** met literally — see Deviations 2. The property the criterion protects —
derivation from the primary key, never from operator input — is unchanged and is what the
rerun tests assert.

## The collation: ICU, `fr-FR`

```sql
CREATE DATABASE "optique_c000047" OWNER "optique_u000047" TEMPLATE template0
  ENCODING 'UTF8' LOCALE_PROVIDER icu ICU_LOCALE 'fr-FR'
```

Settings `TENANT_DB_LOCALE_PROVIDER` (`icu`) and `TENANT_DB_ICU_LOCALE` (`fr-FR`), both
from plan 02-01. Verified on the running stack: the resulting row is
`datlocprovider='i'`, `datlocale='fr-FR'`.

**Phase 4 must validate this against
`test_client10_search_finds_mohamed_mohammed_and_mhamed`.** ICU `fr-FR` gives French
collation and case-insensitive-ish ordering, but it does **not** by itself fold Arabic
transliteration variants (Mohamed / Mohammed / M'hamed). That test will most likely need
`unaccent` plus trigram similarity on top of the collation, not the collation alone.
Setting the collation at `CREATE DATABASE` time is still the right call — retrofitting
per-column collations across a live fleet is expensive — but it is not the whole answer to
CLIENT-10, and assuming it is would be the mistake.

## The provider `CREATEDB` question is still open

`02-RESEARCH.md` Open Question 2 — *does the managed hosting provider's application role
have `CREATEDB`, or must logical databases be created through the provider's API?* — is
unanswered, and it is a **Phase 1 procurement fact**, not a coding decision. It is the one
manual verification in `02-VALIDATION.md`.

It did not block this plan because the containment is structural: `SqlProvisioner` is one
implementation of a two-method interface selected by `settings.DATABASE_PROVISIONER`. If
the provider is API-only, a second implementation costs a day. **Phase 1 must chase this**,
together with Open Question 3 (is there a cap on logical databases per instance?).

## Three defects found by running the criteria

### 1. `reap_orphan_databases` reported the development control plane as an orphan

The first real run against Compose printed:

```
1 database(s) with prefix 'optique_c'; 0 claimed by a Client row; 1 orphan(s).
orphan   optique_control  (dry run; not dropped)
```

`_` is a **single-character wildcard in SQL `LIKE`**, so `datname LIKE 'optique_c%'`
matches `optique_control`. Worse, the belt-and-braces guard the research prescribes —
a per-name `str.startswith(prefix)` — has the identical blind spot, because
`"optique_control".startswith("optique_c")` is also true. Both defences would have failed
together, and with `--yes-i-am-sure` the command would have dropped the control plane.

Fixed with `is_client_database_name`: prefix plus **exactly six digits**, applied both as
`starts_with()` in the query and per name before the drop. A restore target
(`<db_name>_restore_<ts>`, plan 02-07) deliberately does not match either, so the reaper
can never drop a restore in flight.

The test now creates a `<prefix>ontrol` lookalike as bait and asserts it is not reported.

### 2. Any client's role could connect to any other client's database

`deprovision_client` left `optique_u000001` behind, which raised the question of whether
that mattered. It did: **PostgreSQL grants `CONNECT` on a new database to `PUBLIC` by
default**, so every client's login role could open every other client's database. One
`psql` and another optician's ordonnances. The router would never do it — but "the
application would never" is not an isolation boundary, and database-per-client exists
precisely so that the boundary sits below the application.

`SqlProvisioner.create_database` now does, idempotently and also on the already-exists
path:

```sql
REVOKE CONNECT ON DATABASE "optique_c000047" FROM PUBLIC;
GRANT  CONNECT ON DATABASE "optique_c000047" TO "optique_u000047";
```

`test_tenant04_a_client_role_cannot_connect_to_another_clients_database` provisions two
clients and asserts both halves — A opens its own database, and A is refused by B's with
`permission denied`. **Mutation-checked:** removing the revoke makes it fail with
`DID NOT RAISE OperationalError`.

The leftover role is now deliberate: it is harmless, and a restore from backup needs the
credential the control-plane row still holds.

### 3. `deprovision_client` crashed after dropping the database

`evict_alias` raises `django.utils.connection.ConnectionDoesNotExist` when the alias is in
`connections.settings` but was never opened on this thread — not the `AttributeError` /
`KeyError` being caught. The command dropped the database and then died, leaving the row
in `DROPPING`: a database gone, with a row saying it is still going. Guarded properly and
covered by `test_tenant05_deprovision_drops_the_database_but_keeps_the_row`.

## Deviations from Plan

### 1. [Rule 1 — Bug] `CREATE DATABASE` and `CREATE ROLE` reject bound parameters

- **Plan text:** `LC_COLLATE %s LC_CTYPE %s` and *"a **bound parameter** for the password"*.
- **Reality, verified live against PostgreSQL 18.6:** both are utility statements and
  neither accepts parameters. `psycopg.errors.SyntaxError: syntax error at or near "$1"`.
- **Fix:** `psycopg.sql.Literal` for both, which quotes client-side and is equally
  injection-safe. No f-strings; `grep -nE 'f"(CREATE|DROP|ALTER)'` returns nothing.
- **Honest consequence, recorded in the docstring:** the password therefore appears in the
  statement text, so a server running `log_statement = all` (as Compose does) logs it.
  Not a new exposure — PostgreSQL logs bind parameters too — but production must not run
  `log_statement = all`.

### 2. [Rule 2 — Correctness] Database and role prefixes are settings, not literals

- **Criterion not met literally:** `grep -n "optique_c{client.pk" provisioning.py` returns
  nothing. This is the one acceptance criterion in the plan that is not satisfied as
  written, and it is deliberate.
- **Why:** the test suite runs against the same PostgreSQL instance as development, and a
  test control plane starts its primary keys at 1 exactly as a development one does. With
  a shared prefix, a provisioning test would derive `optique_c000001`, **adopt** a
  developer's real first client database — silently, because the existence guard is what
  makes reruns converge — and then drop it in teardown. Data loss with no error.
- **Fix:** `TENANT_DB_NAME_PREFIX` / `TENANT_DB_USER_PREFIX`, `optique_c` / `optique_u` in
  production, `test_client_c` / `test_client_u` under `config/settings/test.py`. The test
  prefix is also already one of `conftest.py`'s `STALE_TEST_DB_PATTERNS`, so a `SIGKILL`ed
  run is collected by the next session rather than leaving something that looks like a
  production client database.

### 3. [Rule 3 — Blocking] The migrate step goes direct to PostgreSQL

The research's listing shows `register_client_database(**client.connection_params())`,
i.e. through PgBouncer. Migrations hold long DDL transactions — the opposite of what a
transaction pooler is for — and the freshly created role is not in PgBouncer's userlist
anyway. Changed to `connection_params(direct=True)`, matching what plan 02-05 already
specifies for the fan-out.

### 4. [Rule 3 — Blocking] `allow_runtime_tenant_aliases`, a new opt-in test fixture

Django's `SimpleTestCase.ensure_connection_patch_method` refuses any alias present in
`connections` but absent from the test case's `databases`. Its escape hatch —
*"dynamically created connections are always allowed"* — tests `alias in connections`,
which is `alias in connections.settings`, and a runtime alias **is** there. `cls.databases`
was frozen at class setup, before the client the test provisions existed. Observed:
`DatabaseOperationForbidden: Database threaded connections to 'tenant_7' are not allowed`.

The fixture widens `cls.databases.__contains__` for `tenant_` aliases only, for the
duration of one test, and restores it afterwards. Iteration is unchanged, so fixture
setup, flushing and teardown behave identically. It is **opt-in**: the guard is
load-bearing for every other test, and only the handful that do real `CREATE DATABASE` —
the ones `.planning/TESTING.md` §3 says should "pay that cost explicitly" — ask for it.
It does not override pytest-django's database-setup fixture; `grep -rn "django_db_setup"`
still returns nothing.

### 5. `config/urls.py` now mounts the admin

Plan 02-02's summary recorded the operator admin as arriving with this plan. It is a
one-line change and it is what makes the admin reachable at all.

## Verification

| Check | Result |
|---|---|
| `uv run pytest tests/test_provisioner_sql.py -q` | **0** — 5 passed |
| `uv run pytest tests/test_provisioning.py -q` | **0** — 10 passed, 0 pending |
| `uv run pytest -q -m "not slow and not pending"` | **0** — 47 passed, 1.10s |
| `uv run pytest -q --create-db -m "not pending"` | **0** — 56 passed, 6 deselected |
| `uv run python manage.py check --settings=config.settings.local` | **0** |
| `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` | **0** — no changes |
| `provision_client --code SMOKE01 ... --magasin Centre` | **0** — ACTIVE, `pending_plan == []`, magasin `CENTRE` seeded |
| `deprovision_client --code SMOKE01 --yes-i-am-sure` | **0** — `pg_database` back to its prior contents |
| `deprovision_client --code SMOKE01` (no flag) | refused with the rule named |
| `reap_orphan_databases` (default) | **0** — dry run, 0 orphans, nothing dropped |
| `grep -n "mark.pending" tests/test_provisioning.py` | no match |
| `grep -cE "(CREATE DATABASE\|maintenance_connection\|sql\.Identifier\|Client\.objects)" .../provision_client.py` | **0** |
| `wc -l < .../provision_client.py` | **58** (budget: 60) |
| `grep -c "abstractmethod" plateforme/tenancy/provisioner.py` | **2** |
| `grep -c "sql.Identifier" plateforme/tenancy/provisioner.py` | **7** |
| `grep -nE 'f"(CREATE\|DROP\|ALTER)' plateforme/tenancy/provisioner.py` | no match |
| `grep -cE "\.create\(" plateforme/control_plane/seeding.py` | **0** |
| `grep -n "db_password_encrypted" plateforme/control_plane/admin.py` | only in `exclude` |

### Mutation checks

| Mutation | Result |
|---|---|
| `call_command("migrate", ...)` removed from `provision_client` | Killed — all six provisioning tests fail |
| `_restrict_connect` removed from `create_database` | Killed — `DID NOT RAISE OperationalError`; client A reached client B |
| Negative control inside the TENANT-01 test: the client is rolled back to zero and `pending_plan` must then be non-empty | Passes — so `pending_plan(alias) == []` is evidence rather than a function that always returns `[]` |

## Known Stubs

| Stub | File | Reason |
|---|---|---|
| 6 tests fail with `pytest.fail("pending: ...")` | `tests/test_migrate_all.py` (2), `tests/test_magasin_scoping.py` (2), `tests/test_backup_restore.py` (2) | Owned by plans 02-05, 02-06, 02-07 |
| `seed_new_client` seeds magasins only | `plateforme/control_plane/seeding.py` | Marked extension point. TVA rates and the facture série are blocked on CLAUDE.md open questions #1 and #2 and belong to Phase 6; branding to Phase 8 |

## Notes for later plans and for Phase 1

- **PgBouncer cannot authenticate a per-client role yet.** `docker/pgbouncer/userlist.txt`
  holds only `optique_app`, so a client's traffic path (`connection_params()`, which points
  at the pooler) will fail SCRAM for `optique_u000047`. Everything in this plan uses
  `direct=True`, so nothing is broken today, but **Phase 3's first real request will hit
  this.** The fix is PgBouncer `auth_query` against `pg_shadow`, which plan 02-01's own
  notes already recommend for production.
- `deprovision_client` deliberately leaves the role. It is harmless now `CONNECT` is
  revoked, and plan 02-07's restore path needs the credential.
- `applied_heads` legitimately contains control-plane app labels. Use `schema_digest`, not
  raw `applied_heads`, for equality.

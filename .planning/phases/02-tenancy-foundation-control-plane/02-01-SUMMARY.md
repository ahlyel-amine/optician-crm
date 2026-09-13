---
phase: 02-tenancy-foundation-control-plane
plan: 01
subsystem: repository-foundation
tags: [tenancy, connection-budget, pgbouncer, settings, compose, TENANT-08]
requires: []
provides:
  - uv-managed Python 3.13 project with an exactly-pinned stack and committed uv.lock
  - config.settings four-module package (base / local / test / production)
  - static tenant_a and tenant_b test aliases
  - Compose topology PostgreSQL 18 + PgBouncer 1.25.2 transaction mode + Redis 8
  - app image carrying postgresql-client-18
  - four permanent TENANT-08 invariant tests
affects:
  - 02-02 (control-plane models, consumes TENANCY_FERNET_KEY)
  - 02-03 (router, middleware, registry — fills DATABASE_ROUTERS and MIDDLEWARE TODOs)
  - 02-04 (provisioning — consumes TENANT_DB_LOCALE_PROVIDER / TENANT_DB_ICU_LOCALE)
  - 02-07 (TENANT-09 backup/restore — consumes postgresql-client-18 in the image)
tech-stack:
  added: [django, djangorestframework, psycopg, celery, django-celery-beat, redis, gunicorn, cryptography, django-environ, sentry-sdk, pytest, pytest-django, pytest-xdist, factory-boy, freezegun]
  patterns:
    - two explicit connection paths — PgBouncer for traffic, direct-to-PostgreSQL for DDL
    - static tenant aliases in test settings rather than a django_db_setup override
    - configuration invariants asserted by tests, not by convention
key-files:
  created:
    - pyproject.toml
    - uv.lock
    - config/settings/base.py
    - config/settings/test.py
    - tests/test_connection_budget.py
    - docker-compose.yml
    - docker/pgbouncer/pgbouncer.ini
    - Dockerfile
  modified: []
decisions:
  - Django pinned 6.1.1, inside the mandated >=6.1,<6.2 boundary
  - django-celery-beat's stale Django<6.1 cap lifted by a uv override, verified working
  - infrastructure package named plateforme/, never platform/
  - ICU locale provider for client databases instead of an OS locale
  - Compose host ports 5435 / 6433 / 6380 / 8010, all bound to 127.0.0.1
metrics:
  tasks: 3
  commits: 4
  tests-added: 5
  completed: 2026-09-13
---

# Phase 2 Plan 01: Repository Foundation & Connection Budget Summary

A uv-managed Python 3.13 repository with an exactly-pinned stack, a four-module settings
package whose database block encodes TENANT-08 as configuration, a Compose topology that
matches production shape (PostgreSQL 18 + PgBouncer 1.25.2 transaction mode + Redis 8),
and four permanent tests that turn red if any of those invariants drift.

## The pinned stack

Versions were re-resolved at install time, not copied from `02-RESEARCH.md`. Every one
matched the research's 2026-09-12 reading except `django-celery-beat` (see Deviations).

### Runtime

| Package | Pinned |
|---|---|
| Python | 3.13.7 (`requires-python = ">=3.13,<3.14"`) |
| `django` | **6.1.1** |
| `djangorestframework` | 3.18.1 |
| `psycopg[binary]` | 3.3.5 |
| `celery` | 5.6.3 |
| `django-celery-beat` | 2.9.0 |
| `redis` | 8.1.0 |
| `gunicorn` | 26.2.0 |
| `cryptography` | 50.0.1 |
| `django-environ` | 0.14.0 |
| `sentry-sdk` | 2.69.1 |

### Dev

| Package | Pinned |
|---|---|
| `pytest` | 9.1.1 |
| `pytest-django` | 4.14.0 |
| `pytest-xdist` | 3.8.0 |
| `factory-boy` | 3.3.3 |
| `freezegun` | 1.5.5 |

Notable transitive pins, locked in `uv.lock`: `asgiref` 3.12.1, `kombu` 5.6.2,
`sqlparse` 0.6.0, `django-timezone-field` 7.2.2.

**Django resolved to 6.1.1, inside the mandated `>=6.1,<6.2`.** This matters beyond
preference: every Django-internals finding the tenancy design rests on
(`make_view_atomic`, `configure_settings`, `close_old_connections`, `prepare_threshold`,
the removal of `ensure_defaults`) was source-verified against 6.1.x. A resolution outside
that range would have required re-verifying the router and registry design.

## Infrastructure

| Component | Image | Host port (all `127.0.0.1`-bound) |
|---|---|---|
| PostgreSQL 18.6 | `postgres:18` | **5435** → 5432 |
| PgBouncer 1.25.2 | `edoburu/pgbouncer:v1.25.2-p0` | **6433** → 6432 |
| Redis 8 | `redis:8` | **6380** → 6379 |
| App (profile `app`, not started by default) | built from `Dockerfile` | **8010** → 8000 |

The plan suggested 5433 / 6433 / 6380 / 8010. **5433 and 5434 were already occupied** on
this machine, as were 8000 (the known `aida-gateway` container), 5432 and 6379, so the
PostgreSQL host port moved to **5435**. Every port was checked against
`lsof -nP -iTCP -sTCP:LISTEN` before being written.

Ports bind to `127.0.0.1` rather than `0.0.0.0` — the threat model lists "Compose host
ports → local network" as a trust boundary, and the PostgreSQL port accepts superuser
logins.

## Why `plateforme/`, not `platform/`

`02-RESEARCH.md` proposes `platform/` for the quarantined infrastructure code.
`platform` is a **Python standard-library module** (`platform.python_version()`,
`platform.machine()`) imported by psycopg, gunicorn, Sentry and Django itself. A
top-level `platform/` package sits on `sys.path[0]` and shadows it, and the failure
surfaces as `AttributeError: module 'platform' has no attribute 'python_version'` from
deep inside a third-party library — far from its cause.

The package is therefore `plateforme/`, which also matches the French `domaine/` sibling.
Every dotted path in `02-RESEARCH.md` beginning `platform.` becomes `plateforme.`,
including the `DATABASE_ROUTERS` entry that plan 02-03 will fill in.

Confirmed empirically inside the built image: `import platform` still returns the
standard library (`platform.python_version()` → `3.13.15`) with `plateforme/` present in
the working directory.

## TENANT-08: the four invariants, each with a test

TENANT-08 is not a feature, it is configuration. Four settings separate "server
connections scale with concurrency" from "server connections scale with client count".

| Invariant | Where | Test |
|---|---|---|
| `CONN_MAX_AGE = 0` | `config/settings/base.py` | `test_tenant08_conn_max_age_is_zero_on_every_alias` |
| no truthy per-request-transaction setting | absent from all of `config/settings/` | `test_tenant08_no_alias_has_atomic_requests` |
| `DISABLE_SERVER_SIDE_CURSORS = True` | `config/settings/base.py` | `test_tenant08_server_side_cursors_are_disabled` |
| `min_pool_size = 0` | `docker/pgbouncer/pgbouncer.ini` | `test_tenant08_pgbouncer_holds_no_idle_connections_per_idle_client` |

The three settings tests iterate `settings.DATABASES` rather than naming aliases, so they
automatically cover `tenant_a`, `tenant_b` and any alias a later phase adds. All four need
no database and run in 0.04s, so they sit in the quick loop permanently.

The PgBouncer test was **mutation-checked**: changing `min_pool_size` to 5 fails it with
the arithmetic in the assertion message. It is not a vacuous assertion.

CLAUDE.md #12 is honoured literally — `ATOMIC_REQUESTS` appears nowhere in
`config/settings/`, not even as `False`, and `grep -rn ATOMIC_REQUESTS config/settings/`
returns nothing. The test asserts the *effective* value is falsy, so the runtime-registered
aliases that plan 02-03 sets explicitly to `False` also satisfy it.

## Verified live, not assumed

- **No connect-time session SQL (T-02-02).** With the server at `timezone=UTC` and
  `log_statement=all`, a Django query through PgBouncer issued **no `SET TIMEZONE`**.
  (Two `SET application_name` lines appear in the log; those are PgBouncer recycling a
  server connection, not Django.)
- **ICU collation works on the stock image.** Against the running stack,
  `CREATE DATABASE collation_probe TEMPLATE template0 LOCALE_PROVIDER icu ICU_LOCALE 'fr-FR'`
  exited 0 and dropped cleanly. This was the acceptance criterion that 02-04's provisioning
  depends on. The stock `postgres` image generates only `en_US.utf8`, so `LC_COLLATE
  'fr_FR.UTF-8'` would have failed with "invalid locale name"; ICU carries its own locale
  data and needs no custom image.
- **PgBouncer wildcard routing.** A client connected through `:6432` to `optique_control`
  with no per-database entry, resolved by the bare `*` fallback, SCRAM authenticated.
- **`pg_dump` matches the server.** The built image reports `pg_dump (PostgreSQL) 18.6`
  against a server of 18.6 — TENANT-09 (plan 02-07) needs the major versions to match.

## Deviations from Plan

### 1. [Rule 3 — Blocking] django-celery-beat cannot see Django 6.1

- **Found during:** Task 1
- **Issue:** `django-celery-beat` 2.9.0 — the version `02-RESEARCH.md` recorded — declares
  `Django<6.1,>=2.2`. The research verified the package's release date but never checked
  its Django constraint. With Django pinned to 6.1.1, uv silently backtracked to
  `django-celery-beat` **2.1.0** (2021), dragging in `pytz` and `django-timezone-field`
  4.2.3, which do not work on a modern Django at all. Resolution succeeded, so this would
  have passed unnoticed into the lockfile.
- **Why it is not a real incompatibility:** 2.9.0 was released 2026-02-28, before Django
  6.1 existed, so the cap is a stale "not yet tested" upper bound. Upstream `main` already
  carries the `Framework :: Django :: 6.1` classifier and has dropped the Django pin from
  `requirements/default.txt` entirely. There is no release carrying that fix yet.
- **Fix:** `[tool.uv] override-dependencies = ["django>=6.1,<6.2"]`, documented inline with
  its evidence and its removal condition. Pins stay exact; nothing is installed from git.
- **Verified, not assumed:** against `django-celery-beat` 2.9.0 + Django 6.1.1 —
  `manage.py check` reports no issues, the `django_celery_beat` migrations apply,
  `PeriodicTask`/`CrontabSchedule` read and write, and `DatabaseScheduler` imports.
- **Alternatives rejected:** downgrading to Django 5.2 LTS (forbidden — would invalidate
  every source-verified Django-internals finding the tenancy design rests on); installing
  from git (breaks the exact-pin requirement); dropping the package (02-07 wants the
  DB-backed schedule in the control plane so per-client schedules are operator-visible).
- **Commit:** `20f471b`

### 2. [Rule 1 — Bug] postgres:18 refuses the pre-18 volume mount path

- **Found during:** Task 3
- **Issue:** `docker compose up` failed — the container exited 1 with *"in 18+, these
  Docker images are configured to store database data in a format which is compatible
  with pg_ctlcluster... there appears to be PostgreSQL data in /var/lib/postgresql/data
  (unused mount/volume)"*.
- **Fix:** the named volume now mounts at `/var/lib/postgresql`, not
  `/var/lib/postgresql/data`. PostgreSQL 18+ images place data in a major-version-specific
  subdirectory so `pg_upgrade --link` does not straddle a mount boundary.
- **Commit:** `0c79d18`

### 3. [Rule 2 — Correctness] Test aliases connect direct to PostgreSQL

- **Found during:** Task 2
- **Issue:** the plan's `_tenant()` shape inherits `HOST`/`PORT` from `default`, which
  points at PgBouncer. Creating and dropping test databases is DDL, and `CREATE DATABASE`
  cannot run through transaction-mode pooling.
- **Fix:** `config/settings/test.py` repoints `default`, `tenant_a` and `tenant_b` at
  `PG_ADMIN_HOST`/`PG_ADMIN_PORT`. This is the same "traffic through PgBouncer, DDL
  direct" rule `base.py` already states, applied to the test path. The `_tenant()`
  function itself is unchanged from the plan's specification. `00-databases.sql`
  correspondingly grants `CREATEDB` to `optique_app`.
- **Commit:** `20e4d13`

### 4. [Rule 1 — Bug] Two comments overstated what `--strict-markers` does

- **Found during:** final verification
- **Issue:** `pyproject.toml` and `README.md` both claimed `--strict-markers` makes a typo
  in a marker name fail. Checked: `-m "not slwo"` exits 0 and selects everything.
  `--strict-markers` validates markers *applied to tests* (`@pytest.mark.slwo` does fail
  collection — verified), not `-m` expressions.
- **Fix:** both comments corrected to state the real guarantee and the real gap.
- **Commit:** `0c79d18`

### 5. Host port for PostgreSQL moved 5433 → 5435

The plan's suggested ports were explicitly "to be verified". 5433 and 5434 were occupied.
See Infrastructure above.

## Notes for later plans

- `DATABASE_ROUTERS` is `[]` with a `TODO(02-03)`. Setting it before the router exists
  would make `makemigrations` fan out across every registered alias.
- `MIDDLEWARE` carries a `TODO(02-03)` marking the exact slot for `TenantMiddleware` —
  strictly **after** `AuthenticationMiddleware`.
- Sentry initialises with `send_default_pii=False` already set, with a `TODO(02-03)` for
  the `before_send` scrubber and the per-event client/magasin tags. PII was disabled now
  rather than later because ordonnances are health data under law 09-08.
- `docker/pgbouncer/userlist.txt` holds a plain-text **development-only** credential, for
  a documented reason: PgBouncer can authenticate a client from a stored SCRAM verifier
  but cannot use that verifier to authenticate itself to PostgreSQL. Production should use
  `auth_query` against `pg_shadow` instead; the file says so.
- `TENANCY_STRICT` and `TENANCY_FERNET_KEY` exist in `base.py` awaiting 02-02/02-03.

## Known Stubs

| Stub | File | Reason |
|---|---|---|
| `test_tenant08_connection_count_does_not_scale_with_alias_count` fails with `pytest.fail("pending: implemented in 02-03")` | `tests/test_connection_budget.py` | Marked `slow` + `pending` and deselected from the quick loop. Needs `register_client_database`, which plan **02-03** builds; that plan removes the `pending` marker and implements the body. Named in `02-VALIDATION.md` as TENANT-08's load check. |
| `config/urls.py` has empty `urlpatterns` | `config/urls.py` | No application to route yet. The control-plane admin is mounted by 02-02. |
| `DATABASE_ROUTERS = []` | `config/settings/base.py` | Deliberate — see Notes above. Filled by 02-03. |

No stub prevents this plan's goal: TENANT-08's configuration invariants are asserted and
passing.

## Verification

| Check | Result |
|---|---|
| `uv run pytest -x -q -m "not slow and not pending"` | **0** — 4 passed, 1 deselected, 0.35s |
| `docker compose up -d --wait` | **0** — `db`, `pgbouncer`, `redis` all healthy |
| `docker compose config --quiet` | **0** |
| `uv run python manage.py check --settings=config.settings.local` | **0** — no issues |
| `test ! -d platform` | **0** |
| every dependency `==` pinned, `uv.lock` committed | **0** — 15/15 exact |
| `SHOW timezone` / `SHOW log_statement` | `UTC` / `all` |
| ICU `CREATE DATABASE` + `DROP DATABASE` | **0** / **0** |
| `grep -n "8000:" docker-compose.yml` | no match |
| `grep -rn "ATOMIC_REQUESTS" config/settings/` | no match |
| `grep -rn "django_db_setup" config/ tests/` | no match |
| `grep -nE '"(pool\|prepare_threshold)"' config/settings/base.py` | no match |
| `docker build` + `pg_dump --version` | **0** — 18.6, matches server |

## Self-Check: PASSED

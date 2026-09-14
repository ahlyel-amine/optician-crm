# Optique

Multi-tenant SaaS for Moroccan opticians. One shared application, **one PostgreSQL database
per client business**.

Project context, non-negotiables and the technology stack: [`CLAUDE.md`](CLAUDE.md).
Phase plans and requirements: [`.planning/`](.planning/).

## Requirements

- Python 3.13 (managed by [`uv`](https://docs.astral.sh/uv/) — `uv python install 3.13`)
- Docker with Compose v2

## Getting started

```bash
uv sync                     # create .venv and install the pinned stack
cp .env.example .env        # then fill in the placeholders
docker compose up -d --wait # PostgreSQL 18 + PgBouncer 1.25 + Redis 8
uv run python manage.py check
```

`.env` is git-ignored and must stay that way: it carries the Fernet key that decrypts every
client's database password.

## Running the tests

This project is test-first. Two commands:

```bash
# Quick loop — run after every task commit. No Docker required, under ~30s.
uv run pytest -x -q -m "not slow and not pending"

# Full suite — run after every wave. Recreates the test databases from scratch.
uv run pytest --create-db
```

Markers:

| Marker | Meaning |
|---|---|
| `slow` | Real DDL, `pg_dump` or `pg_restore`. Runs against Compose, not in the quick loop. |
| `tenancy` | Needs both the `tenant_a` and `tenant_b` aliases. |
| `pending` | The named test exists but its implementation has not landed. The plan that implements it removes the marker. |

`--strict-markers` is on, so applying an undeclared marker to a test fails collection. It does
**not** validate `-m` expressions — `-m "not slwo"` silently matches everything — so copy the
run commands above rather than retyping them.

## Compose host ports

Host port **8000 is occupied on the development machine**, as are 5432–5434 and 6379, so this
project publishes on ports chosen to be free:

| Service | Host port | Container port |
|---|---|---|
| PostgreSQL 18 | `5435` | 5432 |
| PgBouncer 1.25 | `6433` | 6432 |
| Redis 8 | `6380` | 6379 |
| App (when enabled) | `8010` | 8000 |

Web and Celery traffic connects through **PgBouncer** (`6433`). Provisioning, `migrate_all`,
`pg_dump` and `pg_restore` connect **directly to PostgreSQL** (`5435`) — `CREATE DATABASE`
cannot run inside a transaction block, and transaction-mode pooling is the wrong place for DDL.

### PgBouncer credentials

PgBouncer resolves a client's credential with `auth_query` against PostgreSQL, so a newly
provisioned client authenticates through the pooler with **no file edit and no reload**.
`docker/pgbouncer/userlist.txt` is a two-line fallback for the lookup role's own password
and the admin console — never add an `optique_u######` line to it.

The lookup role and its `SECURITY DEFINER` function are created by
`docker/postgres/init/01-pgbouncer-auth.sql`, which Docker runs **only on an empty data
volume**. A cluster created before that file existed needs it applied once, by hand; it is
idempotent, so running it again is harmless:

```bash
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d postgres \
    < docker/postgres/init/01-pgbouncer-auth.sql
```

Symptom if you skip it: `FATAL: bouncer config error` on every pooled connection, and
`tests/test_pgbouncer_auth.py` red.

## Layout

```
config/       Django settings (base / local / test / production), urls, wsgi
plateforme/   Tenancy infrastructure — quarantined from business code
  tenancy/      context, registry, router, middleware
  control_plane/  Client records, provisioning, migrate_all, backups
domaine/      Business domain. Reads as if there is exactly one optician.
tests/
```

The infrastructure package is `plateforme/`, **not** `platform/`: `platform` is a Python
standard-library module (`platform.python_version()`), imported by psycopg, gunicorn and
Sentry. A top-level `platform/` package would sit on `sys.path[0]` and shadow it.

## Operating the fleet

```bash
# Onboard a client business. One command; the Phase 12 self-serve signup calls the
# same function.
manage.py provision_client --code OPT001 --raison-sociale "Optique Centre SARL" \
                           --magasin Centre --magasin Maarif

# The deploy gate. Exits 1 if any ACTIVE client is behind the code's migration head.
manage.py migrate_all --check

# Apply across the fleet. One client failing does not stop the others.
manage.py migrate_all --parallel 4

# Report databases no Client row claims. Dry-run by default.
manage.py reap_orphan_databases
```

**Before writing any migration, read
[`docs/migration-conventions.md`](docs/migration-conventions.md).** Two rules, both
expensive to retrofit once a client is live: every `RunPython` guards on the router (an
unguarded one also executes against the control-plane database), and schema changes are
expand/contract because a fan-out across the fleet leaves it partially migrated for
minutes.

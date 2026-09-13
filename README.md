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

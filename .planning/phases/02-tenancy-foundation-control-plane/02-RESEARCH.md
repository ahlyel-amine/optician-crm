# Phase 2: Tenancy Foundation & Control Plane — Research

**Researched:** 2026-09-12
**Domain:** Database-per-tenant multi-tenancy on Django 6.1 + PostgreSQL 18 + PgBouncer + Celery
**Confidence:** HIGH on Django internals (read from the 6.1.1 source tree, not from memory) · HIGH on PgBouncer arithmetic · MEDIUM on provider-specific backup/restore (TENANT-09) · MEDIUM on the auth-placement decision (it is a decision, not a fact)

---

## Summary

The design sketch in `CLAUDE.md` is directionally right and **wrong in four specific, checkable places**. The biggest correction: `connections.ensure_defaults(alias)` and `connections.prepare_test_settings(alias)` — the two calls the sketch names as the runtime-registration incantation — **were removed from Django in 4.1** (August 2022) and do not exist in 6.1. Every blog post that recommends them predates that refactor. The replacement is to build a fully-defaulted settings dict yourself, which is easy because `settings.DATABASES["default"]` has already been through `ConnectionHandler.configure_settings()` by the time you need it.

Three more corrections, all verified by reading the Django 6.1.1 source tree:

1. **`ATOMIC_REQUESTS = True` is catastrophic here.** `BaseHandler.make_view_atomic()` iterates *every alias in `connections.settings`* and wraps the view in `transaction.atomic(using=alias)` for each one that has `ATOMIC_REQUESTS`. With 300 registered tenant aliases, every request would open 300 transactions. It must stay `False` project-wide, forever, with a test.
2. **`ContextVar.reset(token)` does not clear — it restores the previous value.** If request N leaked a value onto a reused worker thread, request N+1's `finally: reset(token)` faithfully restores the leak. Verified by direct experiment. The `finally` must `set(_UNSET)`, and the middleware must additionally *assert unset on entry* so a leak is loud instead of silent. `CLAUDE.md` non-negotiable #8 says "reset it in a `finally`" — that exact instruction produces the bug it is trying to prevent.
3. **Prepared statements under PgBouncer are already solved by Django.** The psycopg3 backend sets `prepare_threshold = None` explicitly, with the source comment *"Disable prepared statements by default to keep connection poolers working."* The real transaction-pooling hazards that remain are server-side cursors (`DISABLE_SERVER_SIDE_CURSORS = True`) and Django's connect-time `SET TIMEZONE` (eliminate it by setting the Postgres server `timezone = 'UTC'`).

The one genuinely load-bearing decision Phase 2 must make that is **not recorded anywhere**: **where `AUTH_USER_MODEL` lives**. `auth`, `contenttypes`, `admin` and `sessions` are mutually FK-linked and Django requires them in one database. Putting users in tenant databases creates a chicken-and-egg at login (you must know the tenant to find the user) and breaks the operator's Django admin. Recommendation: **control-plane auth**. This must be settled before the router's app-label map can be written, and it constrains Phase 3.

**Primary recommendation:** build seven small, separately testable pieces — a `control_plane` app (models + provisioning state machine), a `tenancy` package (contextvar, registry, router, middleware, Celery task base), a `migrate_all` command, `pg_dump`-based backup/restore commands, a Docker Compose topology that includes PgBouncer, a `conftest.py` that declares `tenant_a`/`tenant_b` **statically in the test settings module** (not via `django_db_setup` gymnastics), and a `Magasin` scoping convention. Never delete aliases from `connections.settings`; evict with `del connections[alias]` instead.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TENANT-01 | A new client business is provisioned with its own database by a single repeatable operation | §4 provisioning state machine; `CREATE DATABASE` outside a transaction (PG 18 docs, VERIFIED); `provision_client` command + service function shared with self-serve |
| TENANT-02 | Control plane records every client database, its host, and its current schema version | §5 `Client` model fields; `applied_heads` JSONB computed from `MigrationExecutor.migration_plan()` |
| TENANT-03 | Migration applied across every client database; operator sees succeeded / failed / behind | §5 `migrate_all` with process-pool fan-out, `MigrationRun` / `MigrationRunResult` control-plane records, `--check` mode |
| TENANT-04 | Code without resolved client context fails immediately rather than falling back to a shared connection | §2 router raising (Django's `_router_func` propagates exceptions — VERIFIED from source); §3 contextvar discipline; backstop = business tables physically absent from `default` |
| TENANT-05 | A failed provisioning attempt leaves no half-created client — completes or rolls back cleanly | §4 status state machine + `DROP DATABASE ... WITH (FORCE)` (PG 13+, VERIFIED); idempotent re-run keyed on `db_name` |
| TENANT-06 | Operator onboards an optician manually via the same provisioning path the self-serve flow will call | §4 — the management command is a thin wrapper over `provision_client(...)`; one code path, two entry points |
| TENANT-07 | Several magasins per client; stock and caisse scoped to a magasin within that client's database | §9 `MagasinScopedModel` + explicit `.for_magasin()` + `UniqueConstraint(fields=["magasin", ...])`; argues against an implicit magasin filter |
| TENANT-08 | Connections pooled so that adding clients does not exhaust the database server's connection limit | §6 PgBouncer wildcard `*` + `CONN_MAX_AGE=0`; arithmetic shows server connections are bounded by **app concurrency, not tenant count** |
| TENANT-09 | Every client database backed up on a schedule; restoring **one** client's logical database performed and verified | §8 `pg_dump -Fc` per database to object storage via Celery Beat; `tenant_checksum` command for the "identical data" assertion; provider-independent |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

Binding. Nothing below contradicts them; where research *sharpens* one it is called out.

| # | Non-negotiable | Phase 2 impact |
|---|---|---|
| 2 | **One database per client business. Never schema-per-client. Never `django-tenants`.** | Verified: no maintained database-per-tenant Django package exists (§State of the Art). Everything below is hand-built. |
| 4 | Stock, caisse and payments are append-only ledgers | Shapes the magasin scoping convention (§9): ledger rows carry `magasin_id`; balances are derived. |
| 6 | Only owner and gérants log in; permissions are per-gérant data | Forces the auth-placement decision (§Open Question 1) into Phase 2. |
| 7 | Money is `Decimal` | No Phase 2 model holds money; the convention is established for Phase 5+. |
| 8 | **Tenant context fails closed and is reset in a `finally`.** A router returning `None` falls through to `default`. Worker threads are reused. | Correct in substance. **Sharpened:** `reset(token)` is the wrong primitive (§3). |
| — | Online only; requests require a connection | No offline state to carry in the tenancy layer. |
| — | Test-first; every non-negotiable has a named test; tests are named after their requirement | §Validation Architecture maps every success criterion to a named test. |
| — | Do not test Django | Tests below assert *our* invariants (router raises, tables absent from `default`, context does not leak), never that Django's ORM works. |
| — | Pin exact versions at project start; verify rather than trusting numbers in the doc | Done — every version below came from the PyPI JSON API on 2026-09-12. |
| — | GSD workflow: no direct repo edits outside a GSD command | Planner should route all file creation through `/gsd-execute-phase`. |

---

## Standard Stack

All versions read from the PyPI JSON API on **2026-09-12** `[VERIFIED: pypi.org/pypi/<pkg>/json]`.

### Runtime

| Package | Version | Released | Purpose | Why this one |
|---|---|---|---|---|
| **Python** | **3.13.x** | — | Language | Django 6.1 requires `>=3.12`; Celery 5.6.3 publishes no `Python :: 3.14` classifier. 3.13 is the only version Django, psycopg, Celery and WeasyPrint all claim. **Do not use 3.14 yet.** |
| `Django` | **6.1.1** | 2026-09-02 | Framework | Current release; mainstream support to Apr 2027, extended to Dec 2027. See §Version strategy. |
| `djangorestframework` | **3.18.1** | 2026-09-07 | API | — |
| `psycopg[binary]` | **3.3.5** | 2026-08-31 | PG driver | Django's postgres backend disables prepared statements only on the psycopg3 path. psycopg2 is legacy; do not use it. |
| `celery` | **5.6.3** | 2026-03-26 | Queue | `task_postrun` is dispatched from a `finally` (VERIFIED in `celery/app/trace.py`) — safe for context teardown. |
| `django-celery-beat` | **2.9.0** | 2026-02-28 | Scheduler | DB-backed schedule in the **control plane**, so per-client schedules are operator-visible. |
| `redis` | **8.1.0** | 2026-07-30 | Broker client | — |
| `gunicorn` | **26.2.0** | 2026-08-24 | WSGI server | WSGI, not ASGI — see §3. |
| `cryptography` | **50.0.1** | 2026-08-25 | Encrypt `db_password` | Fernet. Do not hand-roll. |
| `django-environ` | **0.14.0** | 2026-06-18 | 12-factor settings | Optional; `os.environ` + a small parser is equally fine. |
| `sentry-sdk` | **2.69.1** | 2026-09-08 | Errors | Stack decision says tag every event with client and magasin. Phase 2 installs the `client` tag in the tenancy middleware. |

### Test

| Package | Version | Released | Purpose |
|---|---|---|---|
| `pytest` | **9.1.1** | 2026-06-19 | Runner |
| `pytest-django` | **4.14.0** | 2026-08-10 | Django integration. `django_db_modify_db_settings` is the official mutate-`DATABASES`-before-setup hook. |
| `pytest-xdist` | **3.8.0** | 2025-07-01 | Parallel. **Interacts badly with runtime aliases — Pitfall 8.** |
| `factory_boy` | **3.3.3** | 2025-02-03 | Fixtures. Last release Feb 2025 — stable, slow-moving. |
| `freezegun` | **1.5.5** | 2025-08-09 | Time freezing. Not needed in Phase 2; pin now for Phase 6+. |

### Infrastructure

| Component | Version | Notes |
|---|---|---|
| **PostgreSQL** | **18.x** | `postgresql.org/docs/current` resolves to 18 `[VERIFIED]`. Confirms `CREATE DATABASE` cannot run in a transaction block, `DROP DATABASE ... WITH (FORCE)`, `STRATEGY WAL_LOG` default. |
| **PgBouncer** | **1.25.2** | Released 2026-05-08 `[VERIFIED: releases API]`. Transaction mode + `*` wildcard `[databases]` entry. |
| **Redis** | 8.x | Broker + cache. Never the Django *DB* cache backend — `core/cache/backends/db.py` calls `router.db_for_read` and would hit the fail-closed router. |

### Alternatives considered

| Instead of | Could use | Verdict |
|---|---|---|
| Hand-built tenancy | `django-db-multitenant` | **No.** Last release **2018-02-01** — 8+ years dead. MySQL-oriented (`USE <db>`); its mechanism is session-level, which is incompatible with PgBouncer transaction pooling anyway. `[VERIFIED: PyPI]` |
| Hand-built tenancy | `django-multitenant` (Citus) | **No.** Shared-table + `tenant_id` column. Last release 2023-12-18. Wrong isolation model entirely. `[VERIFIED: PyPI]` |
| Hand-built tenancy | `django-tenants` 3.14.0 (2026-08-05), `django-pgschemas` 1.3.2 (2026-09-06) | **No.** Both actively maintained, both schema-per-tenant, both rejected by non-negotiable #2. |
| PgBouncer | Django 5.1+ built-in pooling (`OPTIONS: {"pool": True}`) | **No, and it is a trap.** `DatabaseWrapper._connection_pools` is a **class-level dict keyed by alias** (`db/backends/postgresql/base.py:191`) — one `psycopg_pool.ConnectionPool` per tenant alias per process. Exactly the "Prisma spawns an engine per database URL" failure mode already in CLAUDE.md's Rejected table. `[VERIFIED: Django 6.1.1 source]` |
| Django 6.1 | Django 5.2 LTS (extended support to Apr 2028) | Judgement call — below. |

### Version strategy (Django 6.1 vs 5.2 LTS)

`[VERIFIED: djangoproject.com/download]` 6.1 mainstream ends Apr 2027, extended Dec 2027. **6.2 LTS ships April 2027**, extended support to April 2030. 5.2 LTS runs to April 2028.

**Recommendation: start on 6.1, plan the 6.2 LTS bump for ~May 2027.** 6.1 → 6.2 is one minor release; 5.2 → 6.2 later is three. The project has no hard deadline and Phase 2 is month one, so LTS stability buys little. This is a recommendation, not a fact — record it as a decision.

**Installation:**
```bash
uv init && uv python pin 3.13
uv add "django==6.1.1" "djangorestframework==3.18.1" "psycopg[binary]==3.3.5" \
       "celery==5.6.3" "django-celery-beat==2.9.0" "redis==8.1.0" \
       "gunicorn==26.2.0" "cryptography==50.0.1" "sentry-sdk==2.69.1"
uv add --dev "pytest==9.1.1" "pytest-django==4.14.0" "pytest-xdist==3.8.0" \
             "factory_boy==3.3.3" "freezegun==1.5.5"
```

---

## Where CLAUDE.md's sketch is wrong or naive

This is the most valuable section. Five corrections, each with its evidence.

| # | CLAUDE.md says | Reality | Evidence |
|---|---|---|---|
| 1 | "register a client's connection into `connections.databases` at runtime, then `connections.ensure_defaults(alias)`" | **`ensure_defaults()` and `prepare_test_settings()` do not exist.** Present in Django 3.2 and 4.0, **gone from 4.1 onwards** (confirmed across 3.2.25, 4.0.10, 4.1.13, 4.2.20, 5.0.14, 5.1.5, 5.2.17, 6.0.8, 6.1.1). Defaults are now applied once, lazily, inside `ConnectionHandler.configure_settings()`; a dict added later gets no defaults and `DatabaseWrapper` will `KeyError`. Also, `connections.databases` is now only a back-compat alias for `connections.settings` — the 6.1 source comment reads *"Maintained for backward compatibility as some 3rd party packages have made use of this private API in the past. It is no longer used within Django itself."* | `[VERIFIED: Django source, django/db/utils.py, 9 tagged versions]` |
| 2 | Non-negotiable #8: "reset it in a `finally`" | `ContextVar.reset(token)` **restores the previous value**, it does not clear. Experiment: `cv.set("LEAKED"); tok = cv.set("current"); cv.reset(tok)` → `cv.get()` returns `"LEAKED"`. On a reused thread carrying a leak from an earlier request, `reset` re-installs the leak. Must be `finally: cv.set(_UNSET)` plus an **assert-unset-on-entry** guard. | `[VERIFIED: executed locally, CPython]` |
| 3 | (silent) `ATOMIC_REQUESTS` | `BaseHandler.make_view_atomic()` loops `connections.settings.items()` and wraps the view in `transaction.atomic(using=alias)` for every alias with `ATOMIC_REQUESTS`. With N registered tenant aliases that is N transactions per request. **`ATOMIC_REQUESTS` must remain `False` everywhere, permanently.** | `[VERIFIED: django/core/handlers/base.py:347-356]` |
| 4 | "Verify PgBouncer transaction pooling against the driver's prepared statements early" | Already handled by Django. `db/backends/postgresql/base.py:310-314` sets `conn_params["prepare_threshold"] = None` with the comment *"Disable prepared statements by default to keep connection poolers working."* The compose-level check is still worth doing, but it is a regression test, not an open risk. The live risks are server-side cursors and connect-time `SET TIMEZONE`. | `[VERIFIED: Django 6.1.1 source]` |
| 5 | "Router — `db_for_read`/`db_for_write` … **raise** when none is bound" | Correct and safe (Django's `_router_func` only swallows `AttributeError` for a *missing method*; a raised exception propagates). But **incomplete in three ways**: (a) `allow_migrate` must **never** raise — `makemigrations` calls it for every (alias × app_label × model) combination; (b) the router must honour the `instance` hint (`instance._state.db`) or related-object fetches cross databases; (c) `.using(alias)` bypasses the router entirely, so the router alone is not a guarantee — the real backstop is that business tables do not exist in `default`. | `[VERIFIED: django/db/utils.py:224-241, core/management/commands/makemigrations.py:145-165, docs/topics/db/multi-db]` |

A sixth, smaller one: CLAUDE.md's claim *"There is no Django equivalent of `stancl/tenancy`"* is **VERIFIED true** for database-per-tenant (§State of the Art).

---

## Architecture Patterns

### Recommended project structure

`platform/` is quarantined from `domaine/` — the existing architecture research already argues this and it holds. Domain code must read as if there is exactly one optician.

```
optique/
├── config/
│   ├── settings/
│   │   ├── base.py            # DATABASES["default"] only; DATABASE_ROUTERS; ATOMIC_REQUESTS never True
│   │   ├── local.py
│   │   ├── test.py            # ALSO declares tenant_a + tenant_b aliases statically  ← key
│   │   └── production.py
│   ├── celery.py              # app + TenantTask base + signal wiring
│   ├── urls.py / wsgi.py
├── platform/
│   ├── control_plane/         # lives on `default` ONLY
│   │   ├── models.py          # Client, ClientDatabase*, MigrationRun, MigrationRunResult, BackupRun
│   │   ├── provisioning.py    # provision_client() state machine  (TENANT-01/05/06)
│   │   ├── admin.py           # operator Django admin
│   │   └── management/commands/
│   │       ├── provision_client.py     # TENANT-06 — thin wrapper
│   │       ├── deprovision_client.py
│   │       ├── migrate_all.py          # TENANT-02/03
│   │       ├── backup_client.py        # TENANT-09
│   │       ├── restore_client.py       # TENANT-09
│   │       └── tenant_checksum.py      # TENANT-09 verification
│   └── tenancy/
│       ├── context.py         # ContextVar + bind/clear/require  ← the whole security model
│       ├── registry.py        # alias building + register_client_database()
│       ├── router.py          # TenantRouter (fail-closed)        (TENANT-04)
│       ├── middleware.py      # TenantMiddleware
│       ├── tasks.py           # TenantTask base                   (TENANT-04 in Celery)
│       └── maintenance.py     # autocommit psycopg connection, direct to Postgres
└── domaine/
    └── magasins/              # Magasin + MagasinScopedModel      (TENANT-07)
```

**Rule:** `domaine/*` never imports from `platform/tenancy` except for the `MagasinScopedModel` base. If tenant-awareness leaks into sales code, every later feature re-learns it.

---

### 1. Runtime database registration (research question 1)

**The pattern.** Build a *complete* settings dict by deep-copying the already-defaulted `default` entry, then override the connection fields.

```python
# platform/tenancy/registry.py
import copy, threading
from django.conf import settings
from django.db import connections

_REGISTER_LOCK = threading.Lock()

def alias_for(client_id: int) -> str:
    return f"tenant_{client_id}"          # keep the prefix — allow_migrate keys off it

def register_client_database(*, alias, name, host, port, user, password) -> str:
    """Idempotent. Safe to call on every request. Returns the alias."""
    existing = connections.settings.get(alias)
    if existing is not None and existing["NAME"] == name and existing["HOST"] == host:
        return alias
    # deepcopy: settings.DATABASES["default"] has already been through
    # ConnectionHandler.configure_settings(), so it carries every key
    # DatabaseWrapper requires. deepcopy, not {**}, because OPTIONS and TEST
    # are nested dicts that would otherwise be shared by reference.
    cfg = copy.deepcopy(settings.DATABASES["default"])
    cfg.update(
        NAME=name, HOST=host, PORT=str(port), USER=user, PASSWORD=password,
        CONN_MAX_AGE=0,                    # PgBouncer owns pooling
        ATOMIC_REQUESTS=False,             # NEVER True — see Pitfall 3
        DISABLE_SERVER_SIDE_CURSORS=True,  # transaction-mode pooling
    )
    cfg["OPTIONS"] = {k: v for k, v in cfg["OPTIONS"].items() if k != "pool"}
    cfg["TEST"] = {**cfg.get("TEST", {}), "NAME": None, "MIRROR": None}
    with _REGISTER_LOCK:
        connections.settings[alias] = cfg
    return alias
```

**Why this shape:**

- `connections.settings` **is** `settings.DATABASES` — the same dict object. `BaseConnectionHandler.configure_settings()` mutates and returns the object it was handed. So registering an alias also makes it visible in `settings.DATABASES`. `[VERIFIED: django/utils/connection.py:47-50 + django/db/utils.py:149-183]`
- The lock is not paranoia about the GIL (a bare `dict.__setitem__` is atomic today); it is because the *check-then-act* is racy and because free-threaded CPython 3.13+/3.14 removes the GIL guarantee. It costs nothing.
- `OPTIONS` must have `pool` stripped — see the class-level `_connection_pools` trap above.

**Thread safety across gunicorn workers.** Two separate questions, with different answers:

| Layer | Scope | Consequence |
|---|---|---|
| `connections.settings` (the dict) | **Process-global**, shared by all threads | Registration in thread A is visible to thread B. Benign — every thread builds the same dict for the same client. Guard with the lock. |
| `connections._connections` (the `DatabaseWrapper` objects) | **Thread-local** — `Local(thread_critical=True)` | Each thread gets its own wrapper and its own socket. No sharing hazard. `[VERIFIED: django/db/utils.py:140-147]` |

Under gunicorn **prefork**, each worker is a separate process with its own registry; registration must happen lazily in each worker. **Do not** pre-register at import time and do not use `preload_app = True` with any pre-registration — forking with open sockets is the classic way to get two processes writing on one connection.

**Cleanup — how the registry does not grow without bound.** The honest answer: *it does grow, and that is fine, provided you evict the right thing.*

- **Do not** `del connections.settings[alias]`. `close_old_connections` (wired to `request_started` **and** `request_finished`) iterates `connections.all(initialized_only=True)`, which iterates `iter(self.settings)`. Removing the settings entry makes the still-open `DatabaseWrapper` in the thread-local invisible to that loop — you leak an open socket permanently. `[VERIFIED: django/db/__init__.py:52-60]`
- **Do** `connections[alias].close(); del connections[alias]`. `BaseConnectionHandler.__delitem__` does `delattr(self._connections, key)` — it drops only the *thread-local wrapper*, leaving the settings entry intact. That is exactly the eviction primitive you want. `[VERIFIED: django/utils/connection.py:63-64]`
- **Cost of leaving aliases registered:** at N = 300 aliases, per request you pay one `make_view_atomic` loop (300 dict lookups) and two `close_old_connections` loops (300 `hasattr` on a `Local` each). That is tens of microseconds. Memory: a closed `DatabaseWrapper` is a few KB; 300 × 16 threads ≈ 30–50 MB worst case, and only for threads that actually touched every tenant. Measure before optimising.
- If you do want eviction, the right trigger is an **LRU in the middleware's `finally`**: track aliases touched by this thread; when the count exceeds a cap (say 50), close-and-`del` the least-recently-used. Do this only if memory is measured to be a problem — it adds a failure mode for zero proven benefit.

---

### 2. Fail-closed routing (research question 2, TENANT-04)

**What Django actually does with a falsy return** — the exact code, so the leak is not hypothetical:

```python
# django/db/utils.py:224-241  (ConnectionRouter._router_func)
for router in self.routers:
    try:
        method = getattr(router, action)
    except AttributeError:
        pass                       # only a MISSING METHOD is swallowed
    else:
        chosen_db = method(model, **hints)
        if chosen_db:
            return chosen_db       # note: truthiness, so "" falls through too
instance = hints.get("instance")
if instance is not None and instance._state.db:
    return instance._state.db
return DEFAULT_DB_ALIAS            # <-- the cross-client leak
```
`[VERIFIED: Django 6.1.1 source]` — an exception raised inside `db_for_read` / `db_for_write` propagates untouched. Raising is safe.

**Where Django calls routers, and whether raising breaks anything:**

| Caller | Method used | Raising safe? |
|---|---|---|
| `QuerySet` / `Model.save` / `Model.delete` / related descriptors | `db_for_read` / `db_for_write` | **Yes — this is the point.** |
| `django.contrib.admin.options` (3 sites) | `db_for_write(self.model)` | Yes, *provided* only control-plane models are registered in the admin. Registering a business model in the operator admin would raise — which is arguably correct, but design it deliberately. |
| `django.contrib.sessions.backends.db` | `db_for_write(Session, instance=obj)` | Only if the router maps `sessions → default`. It must. |
| `django.contrib.auth.management` | `allow_migrate_model(Permission)` | `allow_migrate`, not `db_for_*`. Must not raise. |
| `django.core.cache.backends.db` | `db_for_read` / `db_for_write` | **Do not use the DB cache backend.** Use Redis. |
| `dumpdata` | `allow_migrate_model(using, model)` then `objects.using(using)` — **never `db_for_read`** | Safe. `[VERIFIED: core/management/commands/dumpdata.py:211,217]` |
| `loaddata` | `allow_migrate_model` | Safe. |
| `makemigrations` | `router.allow_migrate(alias, app_label, model_name=...)` for **every alias in `connections` × every app × every model** | **`allow_migrate` must never raise.** See the trap below. |
| System checks (`core/checks/database.py`) | No router calls at all; only `connections[alias].validation.check()` for explicitly-passed aliases | Safe. |
| `migrate` operations (`CreateModel`, `AddField`, `contrib.postgres.operations`) | `allow_migrate_model(connection.alias, model)` | Must not raise. |

**The `makemigrations` trap (verified, and easy to hit).**
```python
# core/management/commands/makemigrations.py:145-148
aliases_to_check = connections if settings.DATABASE_ROUTERS else [DEFAULT_DB_ALIAS]
for alias in sorted(aliases_to_check):
    connection = connections[alias]
    ... loader.check_consistent_history(connection)   # opens a real connection
```
Because this project **will** set `DATABASE_ROUTERS`, `makemigrations` iterates every alias registered in that process and **connects to each**. Mitigation is trivial but must be explicit: **never register tenant aliases in a `makemigrations` process.** Since registration is lazy and request-driven, this happens naturally — but a developer who adds an `AppConfig.ready()` that pre-registers all clients would silently make `makemigrations` fan out to every production database. Write it down and add a comment in `registry.py`.

**The router:**

```python
# platform/tenancy/router.py
from django.conf import settings
from platform.tenancy.context import current_alias, NoTenantBound

CONTROL_PLANE_APPS = frozenset({
    "control_plane", "admin", "auth", "contenttypes", "sessions",
    "messages", "django_celery_beat",
})
BUSINESS_APPS = frozenset({
    "magasins", "clients", "ordonnances", "stock",
    "facturation", "caisse", "achats", "branding",
})
TENANT_ALIAS_PREFIX = "tenant_"

def is_tenant_alias(alias: str) -> bool:
    return alias.startswith(TENANT_ALIAS_PREFIX)

class TenantRouter:
    def _route(self, model, hints):
        app_label = model._meta.app_label
        if app_label in CONTROL_PLANE_APPS:
            return "default"
        if app_label not in BUSINESS_APPS:
            # An app nobody classified. Failing loudly here is the whole point:
            # a new app silently defaulting to `default` is the leak.
            raise ImproperlyClassifiedApp(
                f"App '{app_label}' is in neither CONTROL_PLANE_APPS nor "
                f"BUSINESS_APPS. Classify it in platform/tenancy/router.py."
            )
        alias = current_alias()                       # raises NoTenantBound if unset
        instance = hints.get("instance")
        if instance is not None and instance._state.db:
            # Django's documented default: related fetches follow the instance's db.
            # If the instance came from a DIFFERENT tenant, that is a leak attempt.
            if instance._state.db != alias:
                raise CrossTenantAccess(
                    f"instance from {instance._state.db} accessed while {alias} is bound"
                )
            return instance._state.db
        return alias

    db_for_read = lambda self, model, **hints: self._route(model, hints)
    db_for_write = lambda self, model, **hints: self._route(model, hints)

    def allow_relation(self, obj1, obj2, **hints):
        # Same database only. Never cross a control-plane/tenant boundary.
        return obj1._state.db == obj2._state.db

    def allow_migrate(self, db, app_label, **hints):
        # MUST NOT RAISE — makemigrations calls this for every alias x app x model.
        if app_label in CONTROL_PLANE_APPS:
            return db == "default"
        if app_label in BUSINESS_APPS:
            return is_tenant_alias(db)
        return None   # unknown app: no opinion. Django defaults to True on `default`.
```

Two deliberate asymmetries worth noting to the planner:
- `_route` raises on an unclassified app; `allow_migrate` returns `None` for one. That is not inconsistency — the first is a runtime data path where silence is a leak, the second is a build-time path where raising would break `makemigrations`. A **system check** (`django.core.checks`) should catch unclassified apps at startup instead, so the runtime raise is a backstop nobody ever hits.
- `db_for_read` and `db_for_write` are identical. There are no read replicas in this design and adding one later should be an explicit change, not an accident.

**The backstop that cannot be bypassed.** `.using(alias)` sets `QuerySet._db` and **skips the router entirely** (`db/models/query.py:2134`). So the router is defence #1, not a guarantee. Defence #2 is free and absolute: because `allow_migrate` returns `False` for business apps on `default`, the business tables **are never created in the control-plane database**. A stray `Vente.objects.using("default")` fails with `relation "vente" does not exist`. That is what `test_tenant04_business_models_never_migrate_to_default` really proves, and it is the reason the migration router matters more than the read router.

---

### 3. Tenant context propagation (research question 3)

**`contextvars`, not `threading.local`.** `threading.local` is invisible to `asyncio` tasks and to `sync_to_async` boundaries; `contextvars` works in both and is what asgiref itself uses. `asgiref.local.Local` is a third option — Django uses it for `connections._connections` — but it is more machinery than needed. Use a plain `ContextVar`.

**The leak, demonstrated** (run locally on CPython, `[VERIFIED]`):

```
fresh thread sees:              <unset>      # new threads start with an EMPTY context
req1 (pool thread) ->           client-1
req2 (SAME pool thread) ->      client-1     # <-- the leak. no reset was done.
req3 (sets + reset(token)) ->   client-3
req4 ->                         client-1     # <-- reset RESTORED the earlier leak
```

Two findings, both consequential:
1. A *fresh* thread never sees the parent's value — which is exactly why "a fresh thread per test hides the bug permanently", as TESTING.md §4 says.
2. **`reset(token)` restores the previous value, not "unset".** A `finally: cv.reset(token)` on a thread already carrying a leak re-installs it. Independently confirmed: `cv.set("LEAKED"); tok = cv.set("current"); cv.reset(tok); cv.get()` → `"LEAKED"`.

**The correct middleware shape:**

```python
# platform/tenancy/context.py
import contextvars

class NoTenantBound(RuntimeError): ...
class TenantContextLeak(RuntimeError): ...

_UNSET = object()
_current = contextvars.ContextVar("tenant_alias", default=_UNSET)

def current_alias() -> str:
    alias = _current.get()
    if alias is _UNSET or alias is None:
        raise NoTenantBound("No client bound — database access refused.")
    return alias

def is_bound() -> bool:
    return _current.get() is not _UNSET

def bind(alias: str) -> None:
    _current.set(alias)

def clear() -> None:
    _current.set(_UNSET)          # NOT reset(token) — see above

class tenant_context:
    """Explicit scope for commands, tasks and tests."""
    def __init__(self, alias): self.alias = alias
    def __enter__(self):
        self.prev = _current.get()
        _current.set(self.alias)
        return self.alias
    def __exit__(self, *exc):
        _current.set(self.prev)   # nested scopes DO want the previous value back
        return False
```

```python
# platform/tenancy/middleware.py
class TenantMiddleware:
    """MUST sit after AuthenticationMiddleware and before any view."""
    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        if is_bound():
            # A previous request on this worker thread failed to clear.
            # Loud, not silent: this is the highest-risk bug in the system.
            logger.critical("tenant context leaked onto worker thread", extra={...})
            clear()
            if settings.TENANCY_STRICT:      # True in tests and in CI
                raise TenantContextLeak(...)
        try:
            client = resolve_client(request)   # JWT claim -> control-plane lookup (cached)
            if client is not None:
                register_client_database(**client.connection_params())
                bind(alias_for(client.id))
                sentry_sdk.set_tag("client", client.code)
            return self.get_response(request)
        finally:
            clear()                            # ALWAYS, on every path
```

`resolve_client` returns `None` for unauthenticated / control-plane endpoints (login, health, operator admin). Leaving the context unbound there is correct — any business query on those paths *should* raise.

**Resolution source.** Use the **JWT claim** as primary (`client_id`), with the control-plane `Client` row as the authority for connection params. Do **not** trust a request header. Subdomain is a secondary signal for the web SPA and is worth validating *against* the JWT claim rather than instead of it. `[ASSUMED — this mirrors the prior architecture research, but the JWT-vs-subdomain precedence is a decision, not a verified fact]`

**WSGI vs ASGI — run WSGI.** Nothing in this product needs async (no websockets, no SSE, no streaming). Under ASGI, Django runs sync views through `sync_to_async(..., thread_sensitive=True)`, and asgiref's `SyncToAsync` maintains a **class-level `single_thread_executor = ThreadPoolExecutor(max_workers=1)`** plus per-context executors, running each call inside `context.run(copy_of_caller_context)` and then `_restore_context` copying changes back to the caller. It is careful and it works, but it puts all sync work for an event loop on shared threads and adds a context-copy layer on top of the single most security-critical variable in the system. `[VERIFIED: asgiref 3.12.1 sync.py:37-52, 409, 494-546]`

**Recommendation: `gunicorn --worker-class gthread --workers W --threads T`.** Threads are reused, so the leak guard above is mandatory regardless — but the semantics are simple enough to reason about and to test. Revisit only if a real async requirement appears.

**How the leak is tested.** The test must reuse one thread across two requests. A `ThreadPoolExecutor(max_workers=1)` is the cleanest way — it is exactly what gunicorn's gthread worker does:

```python
def test_tenant04_context_does_not_leak_between_requests_on_one_thread(client_a, client_b):
    pool = ThreadPoolExecutor(max_workers=1)          # ONE thread, reused
    pool.submit(lambda: call_view_as(client_a)).result()
    leaked = pool.submit(lambda: is_bound()).result()
    assert leaked is False
    # and the stronger form: a second request for client_b must not read client_a
    rows = pool.submit(lambda: call_view_as(client_b)).result()
    assert all(r["client"] == client_b.code for r in rows)
```

**Celery.** `task_postrun` is dispatched from inside a `finally:` in Celery's tracer, so it fires even when the task raises `[VERIFIED: celery 5.6.3, celery/app/trace.py:655-661]`. Both a signal pair and a custom `Task` base work. Prefer the **custom base class**, because it also enforces fail-closed on the *argument* side, which signals cannot:

```python
# platform/tenancy/tasks.py
class TenantTask(celery.Task):
    """Every business task inherits this. Never accepts a model instance."""
    abstract = True

    def __call__(self, *args, **kwargs):
        client_id = kwargs.get("client_id")
        if client_id is None:
            raise NoTenantBound(f"{self.name} invoked without client_id — refusing.")
        client = Client.objects.using("default").get(pk=client_id, status=Client.ACTIVE)
        register_client_database(**client.connection_params())
        with tenant_context(alias_for(client.id)):
            return super().__call__(*args, **kwargs)
        # tenant_context.__exit__ restores; nothing leaks into the next task
```
Celery's tracer honours a custom `__call__`: `fun = task if task_has_custom(task, '__call__') else task.run` `[VERIFIED: celery/app/trace.py:374-377]`.

Belt and braces: also connect a `task_prerun` receiver that raises if `is_bound()` is already true at task start — the prefork worker reuses processes, so the same class of leak exists there. Connect receivers in `AppConfig.ready()`, not lazily.

---

### 4. Provisioning (research question 4 — TENANT-01, TENANT-05, TENANT-06)

**The hard constraint, quoted:** *"CREATE DATABASE cannot be executed inside a transaction block."* and *"DROP DATABASE cannot be executed inside a transaction block."* `[VERIFIED: postgresql.org/docs/current/sql-createdatabase.html, sql-dropdatabase.html — PostgreSQL 18]`

So "completes or rolls back cleanly" (TENANT-05) cannot be one atomic transaction. It is a **status state machine with compensating cleanup**, where the control-plane row is the durable record of intent and the only thing that is transactional.

**States:**

```
PENDING ──► CREATING_DB ──► MIGRATING ──► SEEDING ──► ACTIVE
   │             │              │            │
   └─────────────┴──────────────┴────────────┴──► FAILED ──► (rerun) ──► ...
                                                     │
                                                     └──► DROPPING ──► DELETED
```

The invariant that makes TENANT-05 true: **only `ACTIVE` clients are ever routed to or migrated.** A half-provisioned client is simply not visible to the rest of the system. `FAILED` rows are visible to the operator, not to the router.

**The algorithm, and why each step is where it is:**

```python
# platform/control_plane/provisioning.py
def provision_client(*, code, raison_sociale, magasins, db_host=None) -> Client:
    """Idempotent. Safe to rerun after a kill at any point. TENANT-01/05/06."""

    # 1. Reserve identity TRANSACTIONALLY on `default`. This is the only atomic step,
    #    and it is what makes a killed run converge: db_name is derived from the pk,
    #    so a rerun finds the same row rather than creating an orphan.
    with transaction.atomic(using="default"):
        client, created = Client.objects.using("default").get_or_create(
            code=code,
            defaults=dict(raison_sociale=raison_sociale, status=Client.PENDING,
                          db_host=db_host or settings.DEFAULT_DB_HOST,
                          db_port=settings.DEFAULT_DB_PORT),
        )
        if client.status == Client.ACTIVE:
            return client                     # already done — idempotent no-op
        client.db_name = f"optique_c{client.pk:06d}"   # derived, never user input
        client.db_user = f"optique_u{client.pk:06d}"
        if not client.db_password_encrypted:
            client.set_db_password(secrets.token_urlsafe(32))
        client.status = Client.CREATING_DB
        client.save(using="default")

    try:
        # 2. CREATE ROLE + CREATE DATABASE on an AUTOCOMMIT maintenance connection
        #    that goes DIRECT to Postgres, bypassing PgBouncer.
        with maintenance_connection() as cur:        # autocommit=True
            _create_role_if_absent(cur, client.db_user, client.db_password)
            _create_database_if_absent(cur, client.db_name, owner=client.db_user)

        # 3. MIGRATE
        client.advance(Client.MIGRATING)
        register_client_database(**client.connection_params())
        call_command("migrate", database=alias_for(client.pk),
                     interactive=False, verbosity=0)

        # 4. SEED — magasins, TVA defaults, facture série, branding defaults
        client.advance(Client.SEEDING)
        with tenant_context(alias_for(client.pk)):
            seed_new_client(client, magasins)        # idempotent: get_or_create only

        # 5. RECORD SCHEMA VERSION + ACTIVATE (transactional on `default`)
        with transaction.atomic(using="default"):
            client.applied_heads = read_applied_heads(alias_for(client.pk))
            client.status = Client.ACTIVE
            client.provisioned_at = timezone.now()
            client.save(using="default")
        return client

    except Exception as exc:
        Client.objects.using("default").filter(pk=client.pk).update(
            status=Client.FAILED, last_error=repr(exc)[:2000])
        raise
```

**Why a killed-halfway run converges on rerun** — each step is individually idempotent:

| Step | Idempotency mechanism |
|---|---|
| Identity | `get_or_create(code=...)`; `db_name` derived from the pk, never regenerated |
| `CREATE ROLE` | Guarded by `SELECT 1 FROM pg_roles WHERE rolname = %s` |
| `CREATE DATABASE` | Guarded by `SELECT 1 FROM pg_database WHERE datname = %s`; also catch `errors.DuplicateDatabase` |
| `migrate` | Django's own `django_migrations` table makes this idempotent for free |
| Seed | `get_or_create` / `update_or_create` only; no blind `create()` |
| Activate | A single transactional `UPDATE` |

**Orphan cleanup.** A database created in step 2 before a kill is *not* an orphan — its `Client` row exists in `CREATING_DB`/`FAILED` and rerun adopts it. A true orphan is a `pg_database` entry with no matching `Client` row, which only arises from manual meddling. Provide a `reap_orphan_databases --dry-run` command that diffs `pg_database` (filtered to the `optique_c%` prefix) against `Client.db_name` and refuses to drop anything without `--yes-i-am-sure`. Run it as a Celery Beat task in **report-only** mode.

**`maintenance_connection` — build it explicitly, do not reuse Django's private `_nodb_cursor`:**

```python
# platform/tenancy/maintenance.py
import contextlib, psycopg
from psycopg import sql

@contextlib.contextmanager
def maintenance_connection():
    """Autocommit connection to the `postgres` maintenance DB, DIRECT to
    PostgreSQL — never through PgBouncer. CREATE/DROP DATABASE need autocommit,
    and DROP DATABASE ... FORCE cannot work against connections PgBouncer is
    holding on our behalf."""
    conn = psycopg.connect(
        host=settings.PG_ADMIN_HOST, port=settings.PG_ADMIN_PORT,   # 5432, not 6432
        user=settings.PG_ADMIN_USER, password=settings.PG_ADMIN_PASSWORD,
        dbname="postgres", autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()

def _create_database_if_absent(cur, name, owner):
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
    if cur.fetchone():
        return
    # psycopg.sql.Identifier, never f-strings: db names are derived from a pk
    # today, but this is the one place where a string becomes DDL.
    cur.execute(sql.SQL(
        "CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING 'UTF8' "
        "LC_COLLATE 'fr_FR.UTF-8' LC_CTYPE 'fr_FR.UTF-8'"
    ).format(sql.Identifier(name), sql.Identifier(owner)))
```

Notes on the DDL, all `[VERIFIED: PG 18 docs]`:
- `TEMPLATE template0` is required when you specify `ENCODING`/`LC_*` — `template1` is the default and may carry user objects.
- Default `STRATEGY` is `WAL_LOG`, "the most efficient strategy in cases where the template database is small" — correct for an empty template.
- The role must be superuser or have `CREATEDB`.
- Collation is a real decision for a French/Moroccan product: `test_client10_search_finds_mohamed_mohammed_and_mhamed` (Phase 4) depends on it. Setting it here, once, at `CREATE DATABASE` time, is far cheaper than retrofitting per-column collations later.

**Deprovisioning:**
```python
cur.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
```
`WITH (FORCE)` was added in **PostgreSQL 13** `[VERIFIED: PG 13 release notes]` and terminates existing connections. It still fails if prepared transactions or logical replication slots exist. Because PgBouncer holds idle *server* connections per database, you must either go direct to Postgres (as above) or issue `KILL <dbname>` on PgBouncer's admin console first. Going direct is simpler and is what the maintenance connection is for.

**Template databases — a real optimisation, but not the default.** `CREATE DATABASE x TEMPLATE optique_template` turns a ~20 s `migrate` into a ~1 s file copy. Two costs: *"no other sessions can be connected to the template database while it is being copied"* `[VERIFIED: PG 18 docs]`, which serialises provisioning and makes it fail under concurrency; and a template that drifts behind the migration head silently provisions out-of-date clients. **Recommendation: ship `migrate`. Add templates later, guarded by a check that `read_applied_heads(template) == code_heads()`, and only if provisioning latency is measured to be a problem.** At manual-onboarding volumes it never will be.

**TENANT-06 is free** if the layering above is respected: `manage.py provision_client --code OPT001 --raison-sociale "..." --magasin "Centre" --magasin "Maarif"` is a ~30-line `BaseCommand` that parses arguments and calls `provision_client(...)`. The self-serve flow in Phase 12 calls the same function from a Celery task. **Requirement: the command must contain no provisioning logic of its own** — that is the thing the verifier should check.

---

### 5. Migration fan-out (research question 5 — TENANT-02, TENANT-03)

**Reading "is this client behind?" — the exact API:**

```python
# platform/control_plane/schema_version.py
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

def read_applied_heads(alias) -> dict[str, str]:
    """{app_label: latest_applied_migration_name} — the honest schema version."""
    loader = MigrationExecutor(connections[alias]).loader
    heads = {}
    for app_label, name in loader.applied_migrations:
        if heads.get(app_label, "") < name:
            heads[app_label] = name
    return heads

def pending_plan(alias) -> list:
    executor = MigrationExecutor(connections[alias])
    return executor.migration_plan(executor.loader.graph.leaf_nodes())

def is_behind(alias) -> bool:
    return bool(pending_plan(alias))
```

**How `schema_version` should be modelled (TENANT-02).** A single integer or string is not enough — there are several business apps with independent migration chains. Store:

| Field | Type | Meaning |
|---|---|---|
| `applied_heads` | `JSONField` | `{app_label: migration_name}` — the recorded truth after the last successful `migrate` |
| `schema_digest` | `CharField(64)` | `sha256` of the sorted `applied_heads` items — one short value for list views and for equality comparison |
| `schema_checked_at` | `DateTimeField` | When the recorded value was last confirmed against the live database |

Recorded values can drift from reality (someone runs `migrate` by hand). So provide both: a **fast list view** off `applied_heads`, and `migrate_all --check` which actually probes every database and is authoritative. The control plane must show both, and it should show them as distinguishable — "recorded: behind" and "probed: behind" are different facts.

**`migrate_all` — the command:**

```
manage.py migrate_all [--check] [--parallel N] [--client CODE ...] [--fail-fast]
```

| Mode | Behaviour |
|---|---|
| `--check` | Probes every `ACTIVE` client, applies nothing, prints a table, **exits 1 if any client is behind**. This is the CI/deploy gate. |
| default | Applies migrations to every `ACTIVE` client, `--parallel N` at a time, records a `MigrationRunResult` per client. |
| `--fail-fast` | Off by default. **Client 47 failing must not stop clients 48-300** — that is the explicit requirement. |

Exit code is non-zero if any client failed. Output is a per-client table: `code | db_name | host | before | after | status | duration | error`.

**Failure isolation and parallelism — use processes, not threads.**

- **Locking is a non-issue across databases.** DDL locks are per-database; two `migrate` runs against two different databases never contend. `[ASSUMED — follows from PostgreSQL's lock model; not separately verified for every DDL operation]`
- **Process pool, not thread pool.** `call_command("migrate", database=alias)` is I/O-bound so threads would give similar throughput, but a process boundary is what makes "client 47 failing does not affect the rest" structurally true rather than hopefully true: an unhandled exception, a `sys.exit(2)` inside `DatabaseCreation._execute_create_test_db`-style error handling, or a corrupted in-memory migration graph cannot escape a child process. Use `concurrent.futures.ProcessPoolExecutor`, with each child re-registering its own alias (each child has its own `connections`).
- **`--parallel` default: 4.** Each concurrent migration holds 1–2 connections. Go **direct to Postgres**, not through PgBouncer: migrations run long transactions and DDL, which is the opposite of what a transaction pool is for.
- **Alternative shape, worth considering at scale:** `migrate_all` enqueues one Celery task per client and returns a `MigrationRun` id; the operator watches it in the admin. That gives retries and observability for free and is the natural fit once client count is in the hundreds. Recommend building the synchronous command first (it is what a deploy needs) and adding the Celery variant only when a run stops fitting inside a deploy window.

**Two migration-authoring rules this phase must establish, because retrofitting them is painful:**

1. **Every `RunPython` and `RunSQL` must check the router itself.** Django's docs: `model_name` *"is `None` for the `RunPython` and `RunSQL` operations unless they provide it using hints."* `[CITED: docs.djangoproject.com/en/6.1/topics/db/multi-db/]` Without a guard, a data migration written for the tenant schema will also execute against `default`. Convention:
   ```python
   def forwards(apps, schema_editor):
       if not router.allow_migrate(schema_editor.connection.alias, "stock"):
           return
       ...
   ```
   Add a CI check (a simple AST or grep test over `*/migrations/*.py`) that every `RunPython` callable starts with this guard. That is a *our-rule* test, not a Django test, so it belongs in the suite.

2. **Expand/contract migrations.** A fan-out across 300 databases is not instantaneous, so old and new application code must both work against a partially-migrated fleet. Add the column nullable, backfill, then make it non-null in a later release. This is a convention to record in Phase 2 and honour in Phases 4-10.

**A note on what `migrate` records.** When `migrate` runs against a tenant alias, operations for control-plane models become no-ops (each operation calls `allow_migrate_model`), but **the migration is still recorded in that tenant's `django_migrations` table**. That is normal Django behaviour, not a bug, and `read_applied_heads` will therefore list control-plane apps too. Filter to `BUSINESS_APPS` when computing `schema_digest`, or the digest will churn on control-plane-only changes. `[VERIFIED: Django operation `database_forwards` implementations all gate on `allow_migrate_model`]`

---

### 6. PgBouncer and the connection budget (research question 6 — TENANT-08)

**What actually breaks under transaction-mode pooling, and what fixes it:**

| Hazard | Status | Fix |
|---|---|---|
| **Prepared statements** | **Already fixed by Django.** `db/backends/postgresql/base.py:310-314` sets `prepare_threshold=None` — *"Disable prepared statements by default to keep connection poolers working."* | Do nothing. Specifically: **do not** put `prepare_threshold` in `OPTIONS`. (PgBouncer 1.25's `max_prepared_statements`, default 200, would also handle it — but relying on Django's default is one fewer moving part.) `[VERIFIED: Django source + pgbouncer.org/config.html]` |
| **Server-side cursors** | **Real.** Django docs: *"Using a connection pooler in transaction pooling mode (e.g. PgBouncer) requires disabling server-side cursors... Server-side cursors are local to a connection and remain open at the end of a transaction when AUTOCOMMIT is True."* | `DISABLE_SERVER_SIDE_CURSORS: True` on **every** alias, including `default` and including the ones built by `register_client_database`. Consequence: `QuerySet.iterator()` loads everything client-side — fine for an optician's dataset, not fine for an unbounded export. `[VERIFIED: docs.djangoproject.com/en/6.1/ref/databases/]` |
| **Connect-time `SET TIMEZONE`** | **Real but avoidable.** `_configure_timezone` issues `SET TIMEZONE` only when `connection.info.parameter_status("TimeZone") != self.timezone_name`. Under transaction pooling that `SET` lands on a server connection that then returns to the pool carrying it. | Set the PostgreSQL server `timezone = 'UTC'` and `USE_TZ = True` / `TIME_ZONE = "UTC"` in Django. Then the comparison matches and Django issues **zero** session SQL at connect. Verify in Compose with `log_statement = 'all'`. `[VERIFIED: Django source db/backends/postgresql/base.py:364-371]` |
| **`assume_role` / `SET ROLE`** | Avoidable | Do not set `OPTIONS["assume_role"]`. Each client has its own role via `CREATE DATABASE ... OWNER`. |
| **`LISTEN/NOTIFY`, session advisory locks, `SET search_path`** | Would break | None of these are used. The facture counter uses a **row lock inside a transaction** (`select_for_update`), which is transaction-scoped and therefore **safe** under transaction pooling. Worth stating explicitly, because Phase 6 depends on it. |
| **Long-lived client connections** | Real | `CONN_MAX_AGE = 0`. See arithmetic below. |

**PgBouncer configuration — the shape:**

```ini
[databases]
* = host=10.0.0.10 port=5432          ; wildcard fallback: new tenant DBs need no config change

[pgbouncer]
pool_mode = transaction
listen_port = 6432
max_client_conn = 1000                ; must exceed peak app concurrency, generously
default_pool_size = 5                 ; server conns per (user, database) pair
min_pool_size = 0                     ; CRITICAL: idle tenants must hold zero connections
reserve_pool_size = 2
server_idle_timeout = 60              ; aggressive: reap idle server conns fast (default 600)
autodb_idle_timeout = 300             ; reap auto-created wildcard db entries (default 3600)
server_lifetime = 3600
auth_type = scram-sha-256
auth_query = SELECT usename, passwd FROM pg_shadow WHERE usename = $1
```

`[VERIFIED: pgbouncer.org/config.html]` — *"`*` acts as a fallback database: if the exact name does not exist, its value is taken as connection string for the requested database"*, and auto-created entries *"are cleaned up if they stay idle longer than the time specified by `autodb_idle_timeout`"*. **Prefix wildcards such as `tenant_*` are not documented and should not be relied on** — several blog posts show them; the official docs show only `*`.

**The arithmetic — and the key insight.** Pools are keyed by **(user, database)** `[VERIFIED: pgbouncer.org/config.html]`, so N tenant databases on one app user means N pools. The naive reading is "N × default_pool_size server connections" = 300 × 5 = 1500, well over any sane `max_connections`. That reading is **wrong**, for one reason: with `min_pool_size = 0`, a pool holds server connections **only while it has active clients**, and `server_idle_timeout` reaps what is left over.

The real ceiling:

```
Let  W = gunicorn workers,  T = threads per worker
     C_web  = W × T                        # max concurrent in-flight web requests
     K = celery worker processes (--concurrency)
     C_cel  = K
     P = migrate_all --parallel            # only during a deploy, and direct to PG

Concurrent transactions across the whole fleet  ≤  C_web + C_cel
  → PgBouncer server connections in steady state ≤ C_web + C_cel + idle-not-yet-reaped
  → and per tenant, capped at default_pool_size

Concurrent CLIENT connections to PgBouncer (CONN_MAX_AGE = 0) ≤ C_web + C_cel
```

Worked example, sized for "a few hundred clients":

| Quantity | Value | Note |
|---|---|---|
| gunicorn workers × threads | 4 × 8 = **32** | one app host |
| app hosts | 2 | |
| `C_web` | **64** | |
| Celery `--concurrency` | 8 × 2 workers = **16** | |
| `C_cel` | **16** | |
| **Peak concurrent transactions** | **80** | independent of client count |
| Idle-not-yet-reaped slack (`server_idle_timeout = 60`) | ~+40 | conservative |
| **PgBouncer → Postgres server connections** | **~120** | |
| Postgres `max_connections` | **200** | plus `superuser_reserved_connections = 5` |
| **Headroom** | ~40 % | |
| PgBouncer `max_client_conn` | 1000 | ≥ 80 with a large margin |

**Answer to success criterion 5: yes, a few hundred clients fits comfortably, and so would a few thousand** — because server connections scale with *concurrency*, not with *client count*. The two things that break this, and must therefore be tested:

1. **`min_pool_size > 0`** turns the budget into `N × min_pool_size` and blows up linearly with client count. Must be 0.
2. **`CONN_MAX_AGE > 0`** makes each worker thread hold a *client* connection per alias it has ever touched → `C_web × N_touched` client connections against `max_client_conn`. Must be 0.

Both are one-line settings and both deserve an explicit assertion in the test suite (read the effective settings and assert, cheap and permanent).

**Traffic routing:** web + Celery go to PgBouncer on `:6432`. Provisioning, `migrate_all`, `pg_dump`/`pg_restore` and `reap_orphan_databases` go **direct to Postgres on `:5432`**. Two separate sets of settings; make it explicit rather than implicit.

**Compose must match production** (TESTING.md §4 says so and it is right): `postgres:18` + `pgbouncer:1.25` + `redis:8` + app. Note the local machine already has a container bound to **port 8000** — pick different host ports for this project's Compose file.

---

### 7. Testing (research question 7 — drives TESTING.md §3)

**The central correction to TESTING.md §3.** It says *"Ours are registered at runtime, so `pytest-django`'s normal setup knows nothing about them. This has to be solved deliberately, once, in `conftest.py`."* The first half is true of **production**. It does not have to be true of the **test settings module** — and making it true there costs a great deal for no benefit.

**Recommended: declare `tenant_a` and `tenant_b` statically in `config/settings/test.py`.**

```python
# config/settings/test.py
from .base import *          # noqa
import copy

def _tenant(name):
    cfg = copy.deepcopy(DATABASES["default"])
    cfg.update(NAME=name, ATOMIC_REQUESTS=False, CONN_MAX_AGE=0,
               DISABLE_SERVER_SIDE_CURSORS=True)
    cfg["TEST"] = {**cfg.get("TEST", {}), "NAME": f"test_{name}"}
    return cfg

DATABASES["tenant_a"] = _tenant("optique_test_a")
DATABASES["tenant_b"] = _tenant("optique_test_b")

TENANCY_STRICT = True     # context-leak guard raises instead of just logging
```

```python
# conftest.py
TENANT_DBS = ["default", "tenant_a", "tenant_b"]

@pytest.fixture
def tenant_a(db_all):
    with tenant_context("tenant_a"):
        yield "tenant_a"

@pytest.fixture
def tenant_b(db_all):
    """The control. Every isolation test needs a second client whose data must NOT appear."""
    with tenant_context("tenant_b"):
        yield "tenant_b"

@pytest.fixture
def db_all(request):
    request.applymarker(pytest.mark.django_db(databases=TENANT_DBS))
```

Why this is better than overriding `django_db_setup`:

| Property | Static aliases in test settings | Overridden `django_db_setup` |
|---|---|---|
| Create + migrate | `setup_databases(aliases={...})` handles it, honouring `allow_migrate` so each DB gets the right schema | You reimplement it |
| **Teardown, including after a crashed run** | `teardown_databases` + `pytest --create-db` forcibly recreates; `--reuse-db` is opt-in | You reimplement it, and get it wrong |
| **Per-test rollback across both tenants** | Free: `@pytest.mark.django_db(databases=[...])` builds a `TestCase` subclass with `databases = [...]`, wrapping every listed alias in a transaction | Free only if you also route through the marker |
| **pytest-xdist `_gw0` suffixing** | Free: `django_db_modify_db_settings_xdist_suffix` runs over `settings.DATABASES` | **Broken.** That fixture runs *before* `django_db_modify_db_settings`, so aliases you add in the override never get the worker suffix — xdist workers then collide on the same test databases |
| Exercises the runtime-registration code path | **No** — this is the one real gap | Yes |

Close the gap deliberately with a small number of `@pytest.mark.slow` tests that do real provisioning against real `CREATE DATABASE` (`test_tenant01_*`, `test_tenant05_*`, `test_tenant09_*`). Those are the tests that *should* pay the cost, exactly as TESTING.md §3 says.

`[VERIFIED: pytest_django/fixtures.py v4.14.0 — `django_db_setup` calls `setup_databases(aliases=_get_databases_for_setup(...))`; `django_db_modify_db_settings` is a documented no-op hook; `_django_db_helper` builds a `TestCase`/`TransactionTestCase` subclass with the marker's `databases`]`

**Teardown after a crashed run.** `teardown_databases` runs in `django_db_setup`'s teardown and pytest-django already wraps it in `try/except` that downgrades failures to a warning. The residual risk TESTING.md names — a crashed run leaving `test_*` databases behind — is handled by:
- `pytest --create-db` in CI (never `--reuse-db`), which makes `setup_databases(keepdb=False)` drop and recreate;
- a `pytest_sessionfinish` hook that force-drops with `DROP DATABASE ... WITH (FORCE)` via the maintenance connection, because `teardown_databases` uses a normal `DROP DATABASE` and fails if a leaked connection is still attached;
- an `autouse=True, scope="session"` fixture that, at session *start*, drops any `test_optique_%` database found in `pg_database`. Cleaning up at start is more reliable than cleaning up at end, because a `SIGKILL` never gets to run your teardown.

**The thread-reuse leak test.** See §3 — a `ThreadPoolExecutor(max_workers=1)` reused across two requests. Three details that decide whether it reproduces the bug:
1. **One thread, two requests.** A fresh thread starts with an empty context and hides the bug permanently (verified).
2. **The two requests must be for *different* clients.** Same-client reuse passes even when leaking.
3. **The assertion must be on data, not on the variable.** `assert is_bound() is False` catches a missing `clear()`. It does *not* catch a `reset(token)` that restores an older leak. Assert that request 2 sees only client B's rows.

Also add the cheap negative test of the guard itself: bind a value, call the middleware, assert it raises `TenantContextLeak` under `TENANCY_STRICT`.

**`TestCase` vs `TransactionTestCase`** — TESTING.md §4 is correct and applies from Phase 6. In Phase 2 it bites once: provisioning tests run real `CREATE DATABASE`, which cannot run inside the transaction `TestCase` opens. Those tests need `@pytest.mark.django_db(transaction=True)`.

---

### 8. Backup and restore of one logical database (research question 8 — TENANT-09)

**The requirement is explicit that per-instance PITR does not satisfy it.** That is correct and it settles the approach: **implement per-client logical backup and restore ourselves**, provider-independent. Two reasons beyond the requirement text: (a) a provider feature can only be *assumed* to work, and TENANT-09 says "performed and verified — not assumed"; (b) it keeps the hosting decision (Phase 1 / LEGAL-02) from becoming a hard dependency of Phase 2.

`[VERIFIED: postgresql.org/docs/current/app-pgdump.html]` — *"pg_dump only dumps a single database"*; roles and tablespaces are cluster-wide and need `pg_dumpall`; it *"makes consistent exports even if the database is being used concurrently"*; `--compress` supports gzip / lz4 / zstd / none; `-Fd` is the only format supporting `--jobs`.

**Backup (scheduled — Celery Beat, control plane):**
```bash
pg_dump --host=$PG_ADMIN_HOST --port=5432 --username=$PG_ADMIN_USER \
        --dbname=optique_c000047 \
        --format=custom --compress=zstd:9 --no-owner --no-privileges \
        --file=/tmp/optique_c000047-20260912T0300Z.dump
```
Then upload to object storage under a `client/<code>/<date>` prefix and record a `BackupRun` row (client, started, finished, bytes, sha256, object key, status). `--no-owner --no-privileges` matters: the restore target may be a different role, and without these `pg_restore` emits `ALTER OWNER` statements that fail.

Roles are **not** in the dump. Provisioning already creates the role, and `restore_client` must create it if absent — otherwise a disaster-recovery restore onto a fresh instance produces a database nobody can connect to. This is the single most commonly missed step in logical restore and it should be in the runbook and in the test.

**Restore one client, one database:**
```bash
createdb --host=$PG_ADMIN_HOST --username=$PG_ADMIN_USER --owner=optique_u000047 \
         --template=template0 --encoding=UTF8 optique_c000047_restore
pg_restore --host=$PG_ADMIN_HOST --username=$PG_ADMIN_USER \
           --dbname=optique_c000047_restore --no-owner --no-privileges \
           --exit-on-error --jobs=4 /tmp/optique_c000047-....dump
```
Restore into a **new** database name, verify, then cut over by updating `Client.db_name` (a single transactional `UPDATE` on `default`) — never restore in place over a live database. This makes restore reversible and makes the control-plane row the switch.

**Verifying "identical data" — the part TENANT-09 actually turns on.** Row counts are not enough. Build a `tenant_checksum` command:

```sql
-- for each base table in the public schema, ordered by table_name
SET TIME ZONE 'UTC';   -- timestamptz renders per session TZ; without this the digest is not reproducible
SELECT md5(string_agg(row_md5, '' ORDER BY row_md5))
FROM (SELECT md5(t::text) AS row_md5 FROM <table> t) s;
```
Order the row hashes rather than the rows, so the digest is independent of physical row order (which `pg_restore` does not preserve). Fold the per-table digests into one, and **include sequences** — `SELECT schemaname, sequencename, last_value FROM pg_sequences ORDER BY 1,2` — because a restored database with reset sequences is not identical even when every row matches.

Two known caveats to write into the command's docstring: `t::text` renders `float` and `numeric` differently (this project is `Decimal`/`numeric` everywhere, so it is fine), and a column added by a later migration changes every digest (so digests are only comparable within one schema version — record `schema_digest` alongside).

**The test:**
```python
@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant09_single_client_restore_produces_identical_data(...):
    a = provision_client(code="REST-A", ...)   # real databases
    b = provision_client(code="REST-B", ...)
    seed_distinguishable_data(a); seed_distinguishable_data(b)
    before_a, before_b = tenant_checksum(a), tenant_checksum(b)
    key = backup_client(a)
    mutate_after_backup(a)                     # so a no-op "restore" cannot pass
    restore_client(a, key, cutover=True)
    assert tenant_checksum(a) == before_a      # restored
    assert tenant_checksum(b) == before_b      # and the neighbour was untouched
```
`mutate_after_backup` is what makes this a real test rather than a tautology, and the `before_b` assertion is what proves per-database restore rather than per-instance restore.

**Retention.** Art. 211 CGI's 10 years is a *records* obligation, not a backup-rotation obligation — do not conflate them or backup cost explodes. A defensible policy: daily for 30 days, monthly for 12 months, annual for 10 years, all in EU object storage, encrypted at rest. `[ASSUMED — the mapping from a records-retention obligation to a backup schedule is a legal question for the Phase 1 lawyer, not a technical one. Flag it; do not lock it in a plan.]`

**Provider angle, for Phase 1 procurement rather than Phase 2 code.** Scaleway documents that each logical database in an instance is backed up and can be restored separately, and that restores are *logical* (raw table data, indexes rebuilt), so restore time scales with index count `[CITED: scaleway.com/en/docs/managed-databases-for-postgresql-and-mysql/how-to/manage-backups/ — MEDIUM confidence, read via search summary not the page itself]`. Treat that as a *bonus*, not the implementation. Two questions still block procurement, and they belong to Phase 1:
- Does the provider's app role have `CREATEDB`, i.e. can we `CREATE DATABASE` over SQL, or must provisioning call the provider's API? **If it is API-only, `_create_database_if_absent` becomes a provider adapter and TENANT-01 changes shape.** This is the highest-value unknown in the whole phase.
- Is there a cap on logical databases per instance?

Design defensively: put `create_database` / `drop_database` behind a two-method `DatabaseProvisioner` interface with a `SqlProvisioner` implementation now. A provider-API implementation then costs a day, not a redesign.

---

### 9. Multi-magasin scoping (research question 9 — TENANT-07)

Magasins are a **column inside the client's database**, not a database. The temptation is to mirror the tenant pattern — an implicit `magasin` contextvar and a default manager that filters. **Do not.** The asymmetry is real:

| | Client | Magasin |
|---|---|---|
| Isolation boundary | The database connection | A column |
| Legitimate cross-scope reads | **Never** | **Constantly** — the owner's dashboard, réappro across magasins, and possibly one facture série for the whole company |
| Right default | Fail closed | Explicit |

An implicit magasin filter would silently return partial data to the owner's dashboard — a wrong number with no error, which is worse than a crash. And open question #2 in CLAUDE.md ("is a facture série per magasin legal, or one continuous série per company?") is unresolved, so **the model must not assume either answer**.

**The convention to establish now:**

```python
# domaine/magasins/models.py
class Magasin(models.Model):
    code   = models.CharField(max_length=20, unique=True)
    nom    = models.CharField(max_length=120)
    adresse = models.TextField(blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    actif  = models.BooleanField(default=True)
    # NO client FK: the database IS the client. A client_id column here would be
    # a second, contradictory source of truth and an invitation to filter by it.

class MagasinScopedQuerySet(models.QuerySet):
    def for_magasin(self, magasin):
        return self.filter(magasin=magasin)
    def for_magasins(self, magasins):
        return self.filter(magasin__in=magasins)

class MagasinScopedModel(models.Model):
    """Every model whose rows belong to one magasin inherits this.
    Stock movements, caisse entries, ventes, séries de facturation."""
    magasin = models.ForeignKey(
        "magasins.Magasin", on_delete=models.PROTECT,   # PROTECT: ledgers are append-only
        related_name="+", db_index=True,
    )
    objects = MagasinScopedQuerySet.as_manager()

    class Meta:
        abstract = True
```

Rules that go with it, and that later phases must not re-invent:

1. **`on_delete=PROTECT`,** not `CASCADE`. Non-negotiable #4 makes stock and caisse append-only ledgers; a cascading delete of a magasin would erase fiscal history. Deactivate (`actif = False`), never delete.
2. **Scoped uniqueness.** Anything unique "within a magasin" is `UniqueConstraint(fields=["magasin", "<field>"], name="uniq_<model>_magasin_<field>")`, never `unique=True` on the field alone. Getting this wrong makes two magasins unable to use the same article reference.
3. **Every magasin-scoped index is composite and leads with `magasin`** — `Index(fields=["magasin", "date"])`. An index on `date` alone is near-useless once there are several magasins.
4. **The permission layer (Phase 3) resolves *which* magasins,** and the caller passes them: `Mouvement.objects.for_magasins(request.user.magasins_autorises)`. Phase 2 provides the queryset method; Phase 3 provides the list. Keeping those separate is what stops the projection layer from being re-invented in each module.
5. **Seeding.** `provision_client` creates at least one magasin (`--magasin` may be repeated). A client with zero magasins is not a valid state; enforce it with a check in `seed_new_client`.
6. **Test now, not later:** `test_tenant07_stock_and_caisse_are_scoped_per_magasin` — two magasins in one client, a movement in each, and `for_magasin(m1)` returns exactly one.

---

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| Encrypting `db_password` | XOR / base64 / a home-made AES wrapper | `cryptography.fernet.Fernet` with the key from the environment | Authenticated encryption, key rotation via `MultiFernet`. This is a credential for a database holding health data. |
| Quoting a database or role name into DDL | f-strings / `%` formatting | `psycopg.sql.Identifier` | The only place in the system where a Python string becomes DDL. |
| Applying `DATABASES` defaults to a runtime alias | Copying Django's `configure_settings` list by hand | `copy.deepcopy(settings.DATABASES["default"])` then override | Django's default list changes between releases (`CONN_HEALTH_CHECKS` arrived in 4.1). Copying the already-defaulted entry is version-proof. |
| Creating / migrating / dropping **test** databases | A bespoke `django_db_setup` | Static aliases in test settings + `setup_databases`/`teardown_databases` | You would reimplement `--create-db`, `--reuse-db`, xdist suffixing and mirroring, and the xdist suffix in particular you will get wrong. |
| Tracking which migrations are applied | A hand-rolled version integer bumped by hand | `MigrationExecutor.migration_plan(graph.leaf_nodes())` + `loader.applied_migrations` | Django already maintains `django_migrations`; a parallel counter is a second truth that will drift. |
| Per-database backup | `SELECT *` to CSV | `pg_dump --format=custom` | Consistent snapshot, sequences, constraints, indexes, partial restore. |
| Comparing a restored database | Row counts | Ordered per-table `md5` digest + `pg_sequences` | Row counts pass while column values are wrong. |
| Retrying a failed provision | `while True` with `sleep` | The status state machine + idempotent steps + operator rerun | A retry loop around a non-idempotent operation creates orphan databases. |
| Connection pooling | An app-side per-tenant pool manager with LRU | PgBouncer in transaction mode | The prior architecture research proposed an app-side LRU pool manager. With `CONN_MAX_AGE = 0` and PgBouncer it is unnecessary — and it is also the shape Django's own `OPTIONS["pool"]` takes, which is the trap in §Standard Stack. |
| Per-tenant Celery Beat schedules | A custom scheduler | `django-celery-beat` in the control plane, one periodic task that fans out `client_id`s | Operator-visible, editable, and keeps the tenant-id-in-payload discipline. |

**Key insight:** in this domain almost every "just write a small helper" instinct produces something that is *nearly* right and fails at exactly the moment that matters — a crash mid-provision, a restored database that looks fine, a leak on the one reused thread. Prefer the boring primitive that has already handled the edge case.

---

## Common Pitfalls

### Pitfall 1 — `ensure_defaults()` no longer exists
**What goes wrong:** you copy the canonical runtime-registration snippet from any pre-2022 source; it raises `AttributeError: 'ConnectionHandler' object has no attribute 'ensure_defaults'`. Worse, you "fix" it by deleting the call, and then `DatabaseWrapper.__init__` raises `KeyError: 'ATOMIC_REQUESTS'` from somewhere unrelated.
**Why:** removed in Django 4.1; defaults moved into `configure_settings()`, which runs once, lazily.
**Avoid:** `copy.deepcopy(settings.DATABASES["default"])`.
**Warning sign:** any `KeyError` naming a `DATABASES` key.

### Pitfall 2 — `reset(token)` restores a leak instead of clearing it
**What goes wrong:** the leak test passes locally (fresh threads) and production quietly serves client A's data to client B.
**Why:** `ContextVar.reset` is "undo this set", not "clear".
**Avoid:** `finally: cv.set(_UNSET)`; assert-unset on middleware entry; test on a reused thread with two *different* clients and assert on data.
**Warning sign:** a leak test that only asserts `is_bound() is False`.

### Pitfall 3 — `ATOMIC_REQUESTS = True`
**What goes wrong:** latency grows linearly with client count; Postgres shows hundreds of idle-in-transaction sessions; PgBouncer pools saturate.
**Why:** `make_view_atomic` iterates every alias in `connections.settings`.
**Avoid:** never set it. Add `test_tenant08_no_alias_has_atomic_requests` reading the effective settings.
**Warning sign:** `idle in transaction` in `pg_stat_activity` on databases nobody requested.

### Pitfall 4 — `makemigrations` fans out to every production database
**What goes wrong:** `manage.py makemigrations` on a process that pre-registered all clients opens a connection to each and runs `check_consistent_history`.
**Why:** `aliases_to_check = connections if settings.DATABASE_ROUTERS else [DEFAULT_DB_ALIAS]`.
**Avoid:** never register tenant aliases outside a request / task / explicit command. Never pre-register in `AppConfig.ready()`.
**Warning sign:** `makemigrations` is slow, or warns `Got an error checking a consistent migration history` for an alias you did not expect.

### Pitfall 5 — deleting an alias from `connections.settings` leaks a socket
**What goes wrong:** connections accumulate on the Postgres side with no matching Django connection; eventually `FATAL: too many connections`.
**Why:** `close_old_connections` iterates `connections.all(initialized_only=True)`, which iterates `self.settings`. Remove the settings entry and the still-open wrapper becomes invisible to the loop.
**Avoid:** `connections[alias].close(); del connections[alias]` — `__delitem__` drops only the thread-local wrapper.
**Warning sign:** `pg_stat_activity` count drifting upward across a long-running worker's life.

### Pitfall 6 — `OPTIONS: {"pool": True}` inherited from `default`
**What goes wrong:** memory and connection count both explode with client count.
**Why:** `_connection_pools` is class-level and keyed by alias — one `psycopg_pool` per tenant per process.
**Avoid:** `register_client_database` strips `pool` from `OPTIONS` (already in the snippet above).
**Warning sign:** `psycopg_pool` in a memory profile, or a connection count that tracks client count rather than traffic.

### Pitfall 7 — a router that raises in `allow_migrate`
**What goes wrong:** `makemigrations` and `migrate` crash with your own exception, from deep inside Django, for an alias you were not thinking about.
**Why:** `allow_migrate` is called across every alias × app × model.
**Avoid:** `db_for_read`/`db_for_write` raise; `allow_migrate` returns `True`/`False`/`None`. Add a startup system check for unclassified apps so the runtime raise is never reached in practice.

### Pitfall 8 — pytest-xdist collides on test databases
**What goes wrong:** `-n 4` produces random `DuplicateTable` / `does not exist` failures in tenancy tests only.
**Why:** `django_db_modify_db_settings_xdist_suffix` appends `_gw0`… to `DATABASES` entries **before** `django_db_modify_db_settings` runs. Aliases you add in an override of the latter never get a suffix, so all four workers share `test_optique_test_a`.
**Avoid:** declare tenant aliases statically in the test settings module.
**Warning sign:** the suite is green at `-n 0` and flaky at `-n 4`.

### Pitfall 9 — `.using()` bypasses the router
**What goes wrong:** a developer silences `NoTenantBound` in a management command with `.using("default")` and gets a confusing `relation does not exist` — or, if the business tables *were* migrated to `default` by a router mistake, silently reads nothing and writes into the control plane.
**Why:** `QuerySet.using()` sets `_db` and the router is never consulted.
**Avoid:** the `allow_migrate` rule that keeps business tables out of `default` is the real guarantee. `test_tenant04_business_models_never_migrate_to_default` must assert on `information_schema.tables` of the `default` database, not on router return values.

### Pitfall 10 — restoring without the role
**What goes wrong:** restore onto a fresh instance succeeds, then nothing can connect.
**Why:** `pg_dump` does not dump roles; they are cluster-wide.
**Avoid:** `restore_client` creates the role if absent, exactly as `provision_client` does. Test it by restoring into a database owned by a role created during the test.

### Pitfall 11 — session state under transaction pooling
**What goes wrong:** intermittent, unreproducible wrong-timezone or wrong-role behaviour under load only.
**Why:** anything `SET` at connect time rides on a server connection that then serves other clients.
**Avoid:** server `timezone = 'UTC'`; no `assume_role`; no `SET search_path` anywhere; `DISABLE_SERVER_SIDE_CURSORS = True`. Verify with `log_statement = 'all'` in Compose and assert that a request issues no `SET`.

### Pitfall 12 — an unclassified new app silently lands on `default`
**What goes wrong:** Phase 7 adds a `caisse` app, nobody updates `BUSINESS_APPS`, `allow_migrate` returns `None`, Django defaults to `True`, and the caisse tables are created in the control-plane database.
**Why:** `ConnectionRouter.allow_migrate` returns `True` when every router returns `None`.
**Avoid:** a Django system check that fails at startup if any installed non-Django app label is in neither set. Cheap, permanent, and it protects every future phase.

---

## Code Examples

### Settings — the non-negotiable database block
```python
# config/settings/base.py
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("CONTROL_PLANE_DB_NAME"),
        "USER": env("CONTROL_PLANE_DB_USER"),
        "PASSWORD": env("CONTROL_PLANE_DB_PASSWORD"),
        "HOST": env("PGBOUNCER_HOST"),
        "PORT": env("PGBOUNCER_PORT", default="6432"),
        "CONN_MAX_AGE": 0,                    # PgBouncer owns pooling  (TENANT-08)
        "ATOMIC_REQUESTS": False,             # NEVER True             (Pitfall 3)
        "DISABLE_SERVER_SIDE_CURSORS": True,  # transaction pooling    (TENANT-08)
        "OPTIONS": {},                        # no "pool", no "prepare_threshold"
    }
}
DATABASE_ROUTERS = ["platform.tenancy.router.TenantRouter"]

USE_TZ = True
TIME_ZONE = "UTC"        # must match the PostgreSQL server's `timezone` setting,
                         # or Django issues SET TIMEZONE on every connect

# Direct-to-PostgreSQL, for provisioning / migrate_all / pg_dump only.
PG_ADMIN_HOST = env("PG_ADMIN_HOST")
PG_ADMIN_PORT = env.int("PG_ADMIN_PORT", 5432)
```

### The system check that protects every future phase
```python
# platform/tenancy/checks.py
from django.apps import apps
from django.core.checks import Error, register

@register()
def check_every_app_is_classified(app_configs, **kwargs):
    from platform.tenancy.router import CONTROL_PLANE_APPS, BUSINESS_APPS
    errors = []
    for cfg in apps.get_app_configs():
        if cfg.name.startswith("django."):
            continue
        if cfg.label not in CONTROL_PLANE_APPS and cfg.label not in BUSINESS_APPS:
            errors.append(Error(
                f"App '{cfg.label}' is classified as neither control-plane nor business.",
                hint="Add it to CONTROL_PLANE_APPS or BUSINESS_APPS in "
                     "platform/tenancy/router.py. An unclassified app defaults to "
                     "the control-plane database, which is a cross-client leak.",
                id="tenancy.E001",
            ))
    return errors
```

### Control-plane model (TENANT-02)
```python
# platform/control_plane/models.py
class Client(models.Model):
    PENDING, CREATING_DB, MIGRATING, SEEDING = "pending", "creating_db", "migrating", "seeding"
    ACTIVE, FAILED, SUSPENDED, DROPPING, DELETED = "active", "failed", "suspended", "dropping", "deleted"

    code            = models.SlugField(max_length=20, unique=True)
    raison_sociale  = models.CharField(max_length=200)
    status          = models.CharField(max_length=16, default=PENDING, db_index=True)

    db_name         = models.CharField(max_length=63, unique=True, null=True)  # PG identifier limit
    db_host         = models.CharField(max_length=255)                          # day one — enables sharding
    db_port         = models.PositiveIntegerField(default=6432)
    db_user         = models.CharField(max_length=63, null=True)
    db_password_encrypted = models.BinaryField(null=True)                       # Fernet

    applied_heads   = models.JSONField(default=dict)   # {app_label: migration_name}
    schema_digest   = models.CharField(max_length=64, blank=True)
    schema_checked_at = models.DateTimeField(null=True)

    provisioned_at  = models.DateTimeField(null=True)
    last_error      = models.TextField(blank=True)

    class Meta:
        constraints = [
            # An ACTIVE client must have a database. Cheap, and it is the
            # database-level statement of TENANT-05's invariant.
            models.CheckConstraint(
                condition=~models.Q(status="active") | models.Q(db_name__isnull=False),
                name="active_client_has_db_name",
            ),
        ]
```
(`CheckConstraint(condition=...)` — `check=` was deprecated in Django 5.1. `[ASSUMED — verify against the 6.1 release notes when writing the migration]`)

### Fan-out worker (TENANT-03)
```python
# platform/control_plane/management/commands/migrate_all.py  (core loop)
def _migrate_one(client_pk: int) -> dict:
    """Runs in a child PROCESS. Its own connections registry, its own failures."""
    django.setup()
    client = Client.objects.using("default").get(pk=client_pk)
    alias = register_client_database(**client.connection_params(direct=True))  # port 5432
    before = read_applied_heads(alias)
    started = time.monotonic()
    try:
        call_command("migrate", database=alias, interactive=False, verbosity=0)
        after = read_applied_heads(alias)
        return {"pk": client_pk, "status": "ok", "before": before, "after": after,
                "seconds": time.monotonic() - started}
    except Exception as exc:
        return {"pk": client_pk, "status": "failed", "error": repr(exc)[:2000],
                "seconds": time.monotonic() - started}
    # NOTE: no re-raise. Client 47 failing must not stop clients 48..300.
```

---

## State of the Art

| Old approach | Current approach | When changed | Impact here |
|---|---|---|---|
| `connections.ensure_defaults(alias)` + `prepare_test_settings(alias)` | Deep-copy an already-defaulted entry; defaults applied once in `configure_settings()` | **Django 4.1**, Aug 2022 | Invalidates essentially every runtime-tenant-registration blog post and CLAUDE.md's sketch |
| `connections.databases` | `connections.settings` (`databases` kept as a back-compat alias; *"no longer used within Django itself"*) | Django 4.1 | Cosmetic, but signals the private API is on notice |
| psycopg2 | psycopg3 (`psycopg[binary]`) | Django 4.2 added the backend; psycopg2 is legacy | Only psycopg3 gets `prepare_threshold=None`, which is what makes PgBouncer transaction mode work out of the box |
| PgBouncer breaks prepared statements | Two independent fixes: Django defaults `prepare_threshold=None`; PgBouncer 1.21+ has `max_prepared_statements` (default **200** in 1.25) | 2023–2025 | The "verify prepared statements against PgBouncer early" task is a regression test, not an open risk |
| No pooling in Django | `OPTIONS: {"pool": True}` (psycopg_pool) | Django 5.1 | **Do not use** with database-per-tenant — one pool per alias, class-level |
| `models.CheckConstraint(check=...)` | `condition=` | Django 5.1 (`check` deprecated) | Affects the control-plane model's constraint syntax |
| `DROP DATABASE` fails while connected | `DROP DATABASE ... WITH (FORCE)` | PostgreSQL 13 | Makes deprovision and test teardown reliable |

**Deprecated / do not reach for:**
- `django-db-multitenant` — last release 2018-02-01; MySQL-shaped; session-state mechanism incompatible with transaction pooling.
- `django-tenants`, `django-pgschemas` — maintained, schema-based, rejected by non-negotiable #2.
- App-side per-tenant connection pools with LRU eviction (proposed in `.planning/research/ARCHITECTURE.md`) — superseded by PgBouncer + `CONN_MAX_AGE = 0`.

---

## Assumptions Log

Claims that were **not** verified in this session. Each needs confirmation before it becomes a locked decision.

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | Django 6.1 (not 5.2 LTS) is the right starting version, bumping to 6.2 LTS ~May 2027 | Standard Stack | Low — a 6.1→6.2 bump instead of staying on 5.2; a few days of work at most |
| A2 | The JWT `client_id` claim is the primary tenant-resolution source, subdomain secondary | §3 | Medium — changes the middleware and the login flow; settle with the Phase 3 auth design |
| A3 | `AUTH_USER_MODEL` should live in the control plane | Open Question 1 | **High** — reversing it after Phase 3 means re-homing auth, contenttypes, admin and sessions across databases |
| A4 | DDL locks are per-database, so parallel `migrate` across tenant databases never contends | §5 | Low — if wrong, reduce `--parallel` to 1; the failure mode is slowness, not corruption |
| A5 | Backup retention of daily-30 / monthly-12 / annual-10y satisfies art. 211 CGI | §8 | Medium — a legal question for the Phase 1 lawyer; affects storage cost, not architecture |
| A6 | `CheckConstraint(condition=...)` is the correct 6.1 spelling | Code Examples | Trivial — the migration will fail loudly |
| A7 | `fr_FR.UTF-8` collation at `CREATE DATABASE` time is the right choice for Moroccan-French name search | §4 | Medium — retrofitting collation across an existing fleet is expensive; validate against `test_client10_*` (Phase 4) with real Arabic-transliterated names before locking |
| A8 | Scaleway's per-logical-database restore works as documented | §8 | Low for Phase 2 (the implementation is provider-independent); high for Phase 1 procurement |
| A9 | `gthread` with W=4, T=8 is the right gunicorn shape | §6 | Low — a tuning parameter; the arithmetic holds for any C |

---

## Open Questions

### 1. Where does `AUTH_USER_MODEL` live? — **blocks the router, must be answered in Phase 2**

**What we know.** `[CITED: docs.djangoproject.com/en/6.1/topics/db/multi-db/]` — *"`auth` models — `User`, `Group` and `Permission` — are linked together and linked to `ContentType`, so they must be stored in the same database as `ContentType`"*, and *"`admin` depends on `auth`, so its models must be in the same database as `auth`."* One `AUTH_USER_MODEL` per project. So this is a single, all-or-nothing choice for four apps.

**What's unclear.** Nothing in `CLAUDE.md`, `PROJECT.md` or `ROADMAP.md` states it. Phase 3 ("Comptes, Permissions & App Shell") assumes it.

**Recommendation: control plane (`default`).** Three reasons, in order of weight:
1. **Login is chicken-and-egg otherwise.** With per-tenant users, authenticating `POST /api/token/` requires knowing the tenant *before* you can find the user — so the client must supply a tenant hint, which is a value you cannot trust before authentication. With control-plane users it is one global lookup, and the issued JWT then carries `client_id`.
2. **The operator's Django admin needs a `User`.** With per-tenant users there is no database in which the operator exists.
3. `sessions`, `contenttypes` and `admin` come along, and all three are much simpler on one database.

**Cost, stated honestly:** user rows for all clients share one table, so a missing `client_id` filter there is a cross-client read. Mitigation: users are reached only through `request.user` (already scoped by the JWT) and through the Phase 3 projection layer; add `test_perm_user_queryset_is_always_client_scoped`. Note the control plane holds **no health data** — ordonnances stay in the tenant database, which is what the CNDP exposure is actually about.

### 2. Does the managed provider allow `CREATE DATABASE` over SQL? — **blocks TENANT-01's implementation shape**
**Known:** `CREATE DATABASE` needs superuser or `CREATEDB`; managed providers commonly withhold superuser.
**Unclear:** whether the Scaleway/OVH app role has `CREATEDB`, or whether logical databases can only be created through the provider API/console.
**Recommendation:** put `create_database` / `drop_database` behind a `DatabaseProvisioner` interface with a `SqlProvisioner` implementation now, so a provider-API implementation is a day's work. Raise this with Phase 1 procurement — it is the highest-value unknown in this phase.

### 3. Is there a cap on logical databases per instance?
**Unclear** for the chosen provider. `.planning/research/HOSTING.md` already flags "Scaleway caps logical databases per instance too low" as a documented risk.
**Recommendation:** `db_host` is on the `Client` model from day one (CLAUDE.md already says this) so sharding is a data change, not a migration. Ask the provider during Phase 1; do not block Phase 2.

### 4. Where do per-gérant permission grants live?
Follows from Q1 but is not the same question. If users are control-plane, grants could live beside them (simple, one query at auth time) or in the tenant database (co-located with the magasins they reference). **Defer to Phase 3** — Phase 2 only needs `BUSINESS_APPS`/`CONTROL_PLANE_APPS` to be extensible.

### 5. Sentry tagging and personal data
CLAUDE.md wants every Sentry event tagged with client and magasin. With health data in scope, event *bodies* must not carry ordonnance values. **Recommendation:** enable `send_default_pii = False` and add a `before_send` scrubber in Phase 2, while the tagging is being wired — retrofitting a scrubber after a leak is not a fix.

---

## Environment Availability

Probed on the development machine, 2026-09-12.

| Dependency | Required by | Available | Version | Fallback |
|---|---|---|---|---|
| Python 3.13 | Django 6.1 + Celery 5.6 | ✗ | 3.12.12 and 3.14.6 present; **3.13 absent** | `uv python install 3.13` — uv 0.8.19 is present |
| `uv` | Dependency management | ✓ | 0.8.19 | — |
| Docker Engine | Compose topology | ✓ | 28.3.3, daemon running | — |
| PostgreSQL 18 | Everything | ✗ (no local server) | — | Docker Compose `postgres:18` |
| `psql` / `pg_dump` / `pg_restore` | TENANT-09 | ✗ (no client binaries) | — | `brew install libpq` for local use; in production run them **inside the app image** (the image must therefore include `postgresql-client-18`, matching the server major version — a mismatched `pg_dump` refuses to dump a newer server) |
| PgBouncer 1.25 | TENANT-08 | ✗ | — | Docker Compose |
| Redis 8 | Celery broker | ✗ | — | Docker Compose |
| Node 22 | Phase 3 SPA | ✓ | v22.21.1 | — |
| git | — | ✓ | 2.39.5 | — |

**Missing with no fallback:** none.

**Notes for the planner:**
- **Port 8000 on the host is already occupied** by an unrelated container (`aida-gateway`). Pick a different host port in this project's Compose file, or Wave 0 will fail on first `docker compose up`.
- The app image must ship `postgresql-client-18` for TENANT-09. Add this to the Dockerfile task, not as an afterthought.

---

## Validation Architecture

### Test framework

| Property | Value |
|---|---|
| Framework | `pytest` 9.1.1 + `pytest-django` 4.14.0 |
| Config file | **None yet — Wave 0.** Create `pyproject.toml [tool.pytest.ini_options]` with `DJANGO_SETTINGS_MODULE = "config.settings.test"` |
| Quick run (per task commit) | `uv run pytest -x -q -m "not slow"` |
| Full suite (per wave merge) | `uv run pytest --create-db` |
| Marks | `slow` (real `CREATE DATABASE` / `pg_dump`), `tenancy` (needs both tenants) |

### Success criteria → observable verification

| Roadmap criterion | How it is observably verified | Automated? |
|---|---|---|
| 1. Single repeatable provisioning operation; comes up at current schema version; same path for manual onboarding | `test_tenant01_provision_client_creates_database_at_migration_head` — `provision_client()`, then assert `pending_plan(alias) == []` and `Client.status == ACTIVE`. Plus `test_tenant06_management_command_delegates_to_provision_client` — patch `provision_client`, run the command, assert it was called once and the command module contains no DDL | yes (`slow`) |
| 2. A run killed halfway leaves no half-created client; rerun converges | `test_tenant05_failed_provisioning_leaves_no_active_client` — patch `call_command("migrate")` to raise, assert `status == FAILED` and the client is invisible to the router. Then `test_tenant05_rerun_after_kill_converges_to_active` — unpatch, rerun with the same `code`, assert one `Client`, one database, `ACTIVE`. Then `test_tenant05_rerun_creates_no_second_database` — count `pg_database WHERE datname LIKE 'optique_c%'` before and after | yes (`slow`) |
| 3. Control plane lists every client DB, host, schema version; a migration run reports per-client succeeded/failed/behind | `test_tenant02_control_plane_records_db_name_host_and_schema_version`. `test_tenant03_migration_fanout_reports_which_clients_are_behind` — two clients, roll one back one migration, assert `migrate_all --check` exits 1 and names exactly that client. `test_tenant03_one_client_failing_does_not_stop_the_others` — make client 2 of 3 fail, assert clients 1 and 3 are `ok` and the exit code is non-zero | yes (`slow`) |
| 4. No-context code refuses to run; permanent CI guardrail against cross-client leaks | `test_tenant04_router_raises_when_no_client_bound`. `test_tenant04_router_never_returns_none`. `test_tenant04_business_models_never_migrate_to_default` — query `information_schema.tables` on `default` and assert **zero** business tables (the bypass-proof backstop). `test_tenant04_context_does_not_leak_between_requests_on_one_thread` — one `ThreadPoolExecutor(max_workers=1)`, two different clients, assert on **data**. `test_tenant04_tenant_a_cannot_read_tenant_b_data`. `test_tenant04_celery_task_without_client_id_fails_closed`. `test_tenant04_every_installed_app_is_classified` — runs the system check | yes |
| 5. Several magasins with stock and caisse scoped per magasin; a few hundred clients stay inside the connection budget | `test_tenant07_provisioning_seeds_requested_magasins`. `test_tenant07_stock_and_caisse_are_scoped_per_magasin`. For the budget: `test_tenant08_conn_max_age_is_zero_on_every_alias`, `test_tenant08_no_alias_has_atomic_requests`, `test_tenant08_server_side_cursors_are_disabled` (settings assertions, permanent and free) **plus** a `slow` load check: register 300 aliases, drive N concurrent requests against Compose, and assert `SELECT count(*) FROM pg_stat_activity` stays under a threshold that does not scale with the alias count | partly — the load check is `slow` and runs against Compose, not in the unit suite |
| — (TENANT-09) | `test_tenant09_single_client_restore_produces_identical_data` — §8. `test_tenant09_backup_runs_for_every_active_client` — the Beat task enqueues exactly the `ACTIVE` clients | yes (`slow`) |

### Sampling rate
- **Per task commit:** `uv run pytest -x -q -m "not slow"` — must stay under ~30 s.
- **Per wave merge:** `uv run pytest --create-db` — full suite including `slow`, against Compose.
- **Phase gate:** full suite green, plus `manage.py migrate_all --check` exiting 0, before `/gsd-verify-work`.

### Wave 0 gaps
Nothing exists yet — this is a greenfield repository. Wave 0 must create, in this order:
- [ ] `pyproject.toml` with `[tool.pytest.ini_options]`, `DJANGO_SETTINGS_MODULE`, and the `slow` / `tenancy` markers
- [ ] `config/settings/{base,local,test,production}.py` — with the static `tenant_a` / `tenant_b` aliases in `test.py`
- [ ] `docker-compose.yml` — `postgres:18` (with `timezone=UTC`, `log_statement=all`), `pgbouncer:1.25`, `redis:8`; **host port ≠ 8000**
- [ ] `conftest.py` — `db_all`, `tenant_a`, `tenant_b`, the session-start stale-test-database reaper
- [ ] `tests/test_tenancy_router.py`, `tests/test_tenancy_context.py`, `tests/test_provisioning.py`, `tests/test_migrate_all.py`, `tests/test_backup_restore.py`, `tests/test_magasin_scoping.py`
- [ ] `tests/factories.py` — `ClientFactory`, `MagasinFactory`
- [ ] Framework install: `uv add --dev pytest==9.1.1 pytest-django==4.14.0 pytest-xdist==3.8.0 factory_boy==3.3.3 freezegun==1.5.5`

---

## Security Domain

### Applicable ASVS categories

| ASVS category | Applies | Standard control for this phase |
|---|---|---|
| V1 Architecture | **yes** | Tenant isolation is the architectural control. Documented threat: a request whose tenant context is unresolved reaching a business query. Mitigation is layered: router raises → business tables absent from `default` → integration test. |
| V2 Authentication | partly | Deferred to Phase 3, **except** that the tenant-resolution source must be an authenticated claim, never a client-supplied header. That constraint is set here. |
| V3 Session Management | partly | `sessions` on `default`; `SESSION_COOKIE_SECURE`, `HttpOnly`, `SameSite=Lax`. JWT lifetimes in Phase 3. |
| V4 Access Control | **yes — the core of this phase** | Horizontal (cross-tenant) access control. Fail-closed router + contextvar + the absent-tables backstop. Per-gérant vertical control is Phase 3. |
| V5 Input Validation | **yes** | `db_name` / `db_user` are **derived from the primary key**, never from user input, and reach DDL only through `psycopg.sql.Identifier`. This is the single injection surface in Phase 2. |
| V6 Cryptography | **yes** | `db_password` encrypted with `cryptography.fernet.Fernet`, key from the environment, never in git, never in the control-plane database. Never hand-rolled. `secrets.token_urlsafe(32)` for generation. |
| V7 Error Handling & Logging | **yes** | `NoTenantBound` must never leak a client identifier into an HTTP response body. A leak detection must log at CRITICAL and page. Sentry `send_default_pii = False` + a `before_send` scrubber, because health data is in scope. |
| V9 Communications | yes | TLS to Postgres (`sslmode=require` at minimum); PgBouncer on a private network or a unix socket. Law 09-08 health data. |
| V10 Malicious Code | n/a | — |
| V12 Files | n/a | Phase 9. |
| V14 Configuration | **yes** | `DEBUG = False` in production; `ATOMIC_REQUESTS` never True; `min_pool_size = 0`; `CONN_MAX_AGE = 0`. Each is asserted by a test, so configuration drift turns the suite red. |

### Known threat patterns for Django + PostgreSQL database-per-tenant

| Pattern | STRIDE | Standard mitigation |
|---|---|---|
| Cross-tenant read via unbound context falling back to `default` | Information Disclosure | Fail-closed router; business tables never created on `default` |
| Cross-tenant read via a leaked contextvar on a reused worker thread | Information Disclosure | `set(_UNSET)` in `finally` + assert-unset on entry + a thread-reuse test |
| Cross-tenant read via a Celery task invoked without `client_id` | Information Disclosure | `TenantTask.__call__` refuses; `task_postrun` clears |
| Cross-tenant write via a stale `instance._state.db` on a related fetch | Tampering | Router raises `CrossTenantAccess` when the hint disagrees with the bound alias |
| SQL injection into `CREATE DATABASE` / `CREATE ROLE` | Tampering / Elevation | `psycopg.sql.Identifier`; names derived from the pk |
| Tenant-id spoofing via a request header or an unsigned parameter | Spoofing | Resolution from the signed JWT claim only |
| Credential disclosure from the control-plane database | Information Disclosure | Fernet-encrypted `db_password`; key outside the database |
| Connection exhaustion → platform-wide outage triggered by client growth | Denial of Service | PgBouncer transaction mode, `min_pool_size = 0`, `CONN_MAX_AGE = 0`, plus the settings assertions |
| A restore overwriting a live neighbouring database | Tampering | Restore into a new database name, verify, then cut over via `Client.db_name` |
| Health data in error telemetry | Information Disclosure | `send_default_pii = False` + `before_send` scrubber |

---

## Sources

### Primary (HIGH confidence)
- **Django 6.1.1 source tree** (sdist from PyPI, read directly): `django/db/utils.py` (`ConnectionHandler`, `ConnectionRouter._router_func`, `allow_migrate`), `django/utils/connection.py` (`BaseConnectionHandler.__getitem__` / `__delitem__`, `Local(thread_critical)`), `django/db/__init__.py` (`close_old_connections`), `django/core/handlers/base.py:347` (`make_view_atomic`), `django/db/backends/postgresql/base.py` (`prepare_threshold`, `_configure_timezone`, `_connection_pools`), `django/db/models/query.py` (`using`, `DISABLE_SERVER_SIDE_CURSORS`), `django/core/management/commands/{makemigrations,dumpdata}.py`, `django/test/utils.py` (`setup_databases`), `django/core/checks/database.py`
- Django source across tags 3.2.25 / 4.0.10 / 4.1.13 / 4.2.20 / 5.0.14 / 5.1.5 / 5.2.17 / 6.0.8 / 6.1.1 — used to date the removal of `ensure_defaults` / `prepare_test_settings` to **4.1**
- **pytest-django 4.14.0 source**: `pytest_django/fixtures.py` (`django_db_setup`, `django_db_modify_db_settings*`, `_django_db_helper`, `_get_databases_for_setup`)
- **asgiref 3.12.1 source**: `asgiref/sync.py` (`_restore_context`, `SyncToAsync.single_thread_executor`, `context.run`)
- **Celery 5.6.3 source**: `celery/app/trace.py` — `send_postrun` inside a `finally`; `task_has_custom(task, '__call__')`
- https://docs.djangoproject.com/en/6.1/ref/databases/ — PgBouncer transaction pooling, `DISABLE_SERVER_SIDE_CURSORS`, `CONN_MAX_AGE`, `OPTIONS["pool"]`
- https://docs.djangoproject.com/en/6.1/topics/db/multi-db/ — router return semantics, `allow_migrate`, `RunPython`/`RunSQL` hints, auth/contenttypes/admin co-location, `instance._state.db`
- https://www.djangoproject.com/download/ — supported versions and LTS dates (6.1, 6.0, 5.2 LTS; 6.2 LTS Apr 2027)
- https://www.postgresql.org/docs/current/sql-createdatabase.html — transaction-block restriction, `TEMPLATE`, `STRATEGY`, `CREATEDB`
- https://www.postgresql.org/docs/current/sql-dropdatabase.html — `FORCE`, transaction-block restriction
- https://www.postgresql.org/docs/current/app-pgdump.html — single-database scope, `--compress`, `-Fd --jobs`, roles not dumped
- https://www.pgbouncer.org/config.html — `pool_mode`, `max_client_conn`, `default_pool_size`, `min_pool_size`, `max_db_connections`, `server_idle_timeout`, `max_prepared_statements`, `*` fallback, `autodb_idle_timeout`, (user, database) pool keying
- PyPI JSON API, 2026-09-12 — every version and release date in §Standard Stack
- Local experiment (CPython) — contextvar thread-reuse leak and `reset(token)` restore semantics
- Local environment probe — Python, uv, Docker, Node, absent Postgres/PgBouncer/Redis, occupied port 8000

### Secondary (MEDIUM confidence)
- https://www.postgresql.org/docs/13/release-13.html — `DROP DATABASE ... FORCE` introduced in PG 13
- Scaleway Managed Database backup documentation — per-logical-database restore, logical (not physical) backups. Read via search summary rather than the page itself; the page for managing logical databases returned 404 on direct fetch
- `.planning/research/{ARCHITECTURE,PITFALLS,HOSTING}.md` — prior project research, used for scale expectations and the connection-exhaustion failure mode

### Tertiary (LOW confidence — flagged, not relied on)
- Blog posts recommending `tenant_*` prefix wildcards in PgBouncer's `[databases]` section. The official documentation shows only the bare `*` fallback. **Do not rely on prefix wildcards.**
- Blog posts on Django runtime tenant registration. Every one found still recommends `ensure_defaults()`, which has not existed since Django 4.1. Treat the entire genre as stale.

---

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|---|---|---|
| Runtime registration (Q1) | **HIGH** | Read from the 6.1.1 source; the removal of `ensure_defaults` confirmed across nine tagged versions |
| Fail-closed routing (Q2) | **HIGH** | Router call sites enumerated by grepping the source; `makemigrations`, `dumpdata` and admin behaviour each read directly |
| Context propagation (Q3) | **HIGH** | Leak and `reset` semantics reproduced locally; asgiref and Celery behaviour read from source |
| Provisioning (Q4) | **HIGH** on PostgreSQL constraints, **MEDIUM** on the exact state machine | DDL constraints quoted from PG 18 docs; the state machine is a design recommendation, not a citation |
| Migration fan-out (Q5) | **MEDIUM-HIGH** | APIs verified from source; the process-pool recommendation and the no-cross-database-lock claim are reasoned, not measured |
| PgBouncer budget (Q6) | **HIGH** on settings and semantics, **MEDIUM** on the specific numbers | Every setting quoted from pgbouncer.org and the Django source; W/T/K values are illustrative and must be load-tested |
| Testing (Q7) | **HIGH** | pytest-django fixture graph read from source, including the xdist ordering hazard |
| Backup / restore (Q8) | **MEDIUM** | `pg_dump` semantics verified; the checksum technique and the Scaleway capability are recommendation and citation respectively, neither executed |
| Magasin scoping (Q9) | **MEDIUM** | A design recommendation; correct, but a judgement call rather than a verified fact |
| Package landscape | **HIGH** | Maintenance status read from the PyPI release index |

**Research date:** 2026-09-12
**Valid until:** 2026-10-12 for versions (Django, DRF, psycopg and pytest all released within the last two weeks — re-check `uv lock` at project start). The Django-internals findings are valid for the 6.1 line; **re-verify `make_view_atomic`, `configure_settings` and `close_old_connections` when upgrading to 6.2 LTS.**

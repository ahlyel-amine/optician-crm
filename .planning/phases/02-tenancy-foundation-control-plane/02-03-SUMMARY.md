---
phase: 02-tenancy-foundation-control-plane
plan: 03
subsystem: tenancy-core
tags: [tenancy, TENANT-04, TENANT-08, router, middleware, celery, sentry, security]
requires:
  - 02-01 (settings package, static tenant aliases, TENANCY_STRICT, connection budget)
  - 02-02 (control_plane.Client, Magasin, conftest fixtures, the Wave 0 named tests)
provides:
  - plateforme/tenancy/context.py — _UNSET sentinel, current_alias/bind/clear/is_bound, tenant_context
  - plateforme/tenancy/registry.py — alias_for, register_client_database, evict_alias
  - plateforme/tenancy/router.py — TenantRouter, CONTROL_PLANE_APPS, BUSINESS_APPS, is_tenant_alias
  - plateforme/tenancy/checks.py — tenancy.E001
  - plateforme/tenancy/middleware.py — TenantMiddleware, resolve_client
  - plateforme/tenancy/tasks.py — TenantTask and the task_prerun leak guard
  - plateforme/tenancy/telemetry.py — before_send scrubber
  - config/celery.py — the Celery application
affects:
  - 02-04 (provisioning — uses register_client_database, alias_for, Client.advance)
  - 02-05 (migrate_all — uses connection_params(direct=True) and allow_migrate)
  - 02-06 (magasin seeding — extends BUSINESS_APPS)
  - 02-07 (backup/restore — Celery tasks inherit TenantTask)
  - Phase 3 (replaces resolve_client's lookup with a signed JWT client_id claim)
tech-stack:
  added: []
  patterns:
    - fail closed everywhere — the router raises, the task refuses, the middleware guards
    - the physical absence of business tables in `default` as the defence a bypass cannot defeat
    - a system check as the mechanism that keeps a classification list honest across phases
    - mutation testing on every security-critical assertion
key-files:
  created:
    - plateforme/tenancy/context.py
    - plateforme/tenancy/registry.py
    - plateforme/tenancy/router.py
    - plateforme/tenancy/checks.py
    - plateforme/tenancy/apps.py
    - plateforme/tenancy/middleware.py
    - plateforme/tenancy/tasks.py
    - plateforme/tenancy/telemetry.py
    - config/celery.py
    - tests/test_tenancy_registry.py
    - tests/test_telemetry.py
    - tests/tenant_tasks.py
  modified:
    - config/__init__.py
    - config/settings/base.py
    - conftest.py
    - tests/test_tenancy_context.py
    - tests/test_tenancy_router.py
    - tests/test_connection_budget.py
decisions:
  - "clear() is set(_UNSET); the token-based undo appears nowhere under plateforme/tenancy"
  - "tenant_context restores on exit, request and task teardown clears — two operations, never unified"
  - "no LRU alias eviction: evict_alias exists, nothing calls it on a schedule"
  - "resolve_client reads the authenticated principal only; Phase 3 swaps in a JWT claim"
  - "the tenancy django_db marker is applied at collection time, not from a fixture body"
metrics:
  tasks: 3
  commits: 3
  tests-added: 22
  completed: 2026-09-13
---

# Phase 2 Plan 03: The Fail-Closed Tenancy Layer Summary

TENANT-04 in four layered defences: the router raises rather than falling through, the
context clears rather than restoring, business tables are physically absent from the
control-plane database, and an unclassified app fails `manage.py check`. Plus the Celery
fail-closed task base, a Sentry scrubber that keeps the tag and drops the body, and the
load check that finally puts a number on TENANT-08 — **300 aliases, peak 4 connections.**

## Public API, for plans 02-04 through 02-07

### `plateforme/tenancy/context.py`

| Name | Contract |
|---|---|
| `NoTenantBound` | Raised when database access is attempted unbound |
| `TenantContextLeak` | Raised when a thread or process arrives already bound |
| `CrossTenantAccess` | Raised when an instance hint disagrees with the bound alias |
| `current_alias() -> str` | The bound alias, or **raises** `NoTenantBound` |
| `is_bound() -> bool` | |
| `bind(alias)` / `clear()` | `clear()` is `_current.set(_UNSET)` |
| `tenant_context(alias)` | Context manager; **restores** the outer scope on exit |

### `plateforme/tenancy/registry.py`

| Name | Contract |
|---|---|
| `alias_for(client_id) -> str` | `f"tenant_{client_id}"` — the prefix is load-bearing |
| `register_client_database(*, alias, name, host, port, user, password) -> str` | Idempotent; opens no connection |
| `evict_alias(alias)` | `connections[alias].close()` then `del connections[alias]` |
| `TENANT_ALIAS_PREFIX` | `"tenant_"` |

### `plateforme/tenancy/router.py`

`TenantRouter` with `db_for_read` / `db_for_write` (identical, deliberately — there are no
read replicas and adding one must be an explicit change), `allow_relation`,
`allow_migrate`, plus `is_tenant_alias(alias)` and `ImproperlyClassifiedApp`.

### `plateforme/tenancy/middleware.py`

`TenantMiddleware(get_response)` and `resolve_client(request) -> Client | None`.

### `plateforme/tenancy/tasks.py`

`TenantTask` (`abstract = True`) — every business task inherits it and must be invoked
with a `client_id` kwarg. Never pass a model instance.

## `CONTROL_PLANE_APPS` / `BUSINESS_APPS`, and how a later phase extends them

```python
CONTROL_PLANE_APPS = frozenset({
    "control_plane", "admin", "auth", "contenttypes", "sessions",
    "messages", "django_celery_beat", "rest_framework", "tenancy",
})
BUSINESS_APPS = frozenset({"magasins"})
```

`rest_framework` and `tenancy` are load-bearing. The check exempts only apps whose
`AppConfig.name` starts with `django.`, and neither of those does —
`test_tenant04_every_django_contrib_app_is_skipped_by_the_check` asserts exactly that, so
the reason survives even if the membership is edited.

**To extend:** add the new app's *label* to `BUSINESS_APPS` (Phase 5 `stock`, Phase 6
`facturation`, Phase 7 `caisse`) in the same commit that adds it to `INSTALLED_APPS`.
Forgetting is not possible: `manage.py check` fails with `tenancy.E001` on the next run.

## The `resolve_client` contract

Returns the ACTIVE `Client` for the request, or `None`.

- **Source: the authenticated principal, never the request.** `request.user.client_id`
  today; Phase 3 replaces it with a signed JWT `client_id` claim. The contract does not
  change — server-verified identity in, `Client` row out. A subdomain may later become a
  *secondary* signal validated **against** the claim, never instead of it (T-02-13).
- **`None` for unauthenticated endpoints**, health checks and the operator admin. Leaving
  the context unbound there is correct: a business query on those paths *should* raise.
- **Only ACTIVE clients resolve.** PENDING / CREATING_DB / MIGRATING / SEEDING / FAILED /
  SUSPENDED are invisible to the router. That is what makes TENANT-05 true.

`test_tenant04_middleware_never_reads_the_tenant_from_the_request` reads the module source
and requires zero `request.META` / `headers` / `GET` / `POST` matches, because the failure
mode is a line added later, not a wrong answer today.

## The measured connection budget

```
TENANT-08: 300 aliases, concurrency 4 -> baseline 0, after registration 0, peak 4, settled 0
```

Three claims, each asserted separately:

1. **Registering 300 aliases opened zero connections** — `after_registration == baseline`.
   Construction is lazy, so a process that knows every client still holds nothing.
2. **Peak 4 while serving all 300 at concurrency 4.** A monitor thread sampled
   `pg_stat_activity` every 5 ms throughout, so this is an observed peak rather than a
   quiet reading taken afterwards.
3. **Settled back to 0.** Nothing outlived the work.

The test creates and drops its own `test_client_budget_<pid>` database (prefixed so the
session-start reaper collects it after a kill) rather than borrowing a pytest-django one,
because `TransactionTestCase` refuses connections to any alias outside its declared
`databases` — and every alias here is created at runtime, which is the point.

**It is not vacuous.** Per-request teardown calls the real `close_old_connections`, the
function Django wires to `request_finished`, rather than closing each alias by hand.
Changing `CONN_MAX_AGE` from `0` to `600` in the registry did not merely fail an
assertion — PostgreSQL answered **`FATAL: remaining connection slots are reserved for
roles with the SUPERUSER attribute`**. The TENANT-08 production incident, reproduced on a
laptop by editing one line.

## The backstop, verified at the PostgreSQL level

| Database | `control_plane_client` | `magasins_magasin` |
|---|---|---|
| `test_optique_control` (default) | present | **ABSENT** |
| `test_optique_test_a` (tenant) | **ABSENT** | present |

`test_tenant04_business_models_never_migrate_to_default` asserts the absence; its
companion `test_tenant04_business_tables_do_exist_on_a_tenant_alias` asserts the presence,
so a run in which nothing migrated anywhere cannot pass trivially. This is the only
defence a `.using("default")` bypass cannot defeat (T-02-19).

The development `optique_control` database was cleaned to match: plan 02-02's
`migrate --settings=config.settings.local` had created `magasins_magasin` there while
`DATABASE_ROUTERS` was still `[]`. The table was dropped, the migration record removed and
`migrate` re-run; `magasins.0001_initial` is now recorded as applied on `default` with no
table created, which is normal Django behaviour for a migration whose every operation is
gated by `allow_migrate_model`.

## Mutation testing

Every security-critical assertion was mutation-checked. Three of the five mutants exposed
a weakness in the test rather than confirming it, and each was fixed.

| # | Mutation | First result | Action |
|---|---|---|---|
| 1 | `copy.deepcopy` -> `{**default}` in the registry | **Survived.** The depth-one `is not` assertion passed, because `register_client_database` reassigns `OPTIONS` and `TEST` on its way past anyway. | Test strengthened to depth two plus a behavioural mutate-and-compare. Mutant then killed. |
| 2 | `clear()` -> a token-based undo | Killed, with the intended message. | — |
| 3 | `clear()` removed from the middleware's `finally` | Killed — but by the *entry guard*, not by the data assertion. | The leak test gained a third request that binds **no** client; see below. |
| 4 | `clear()` removed **and** the entry guard disabled | **Survived** at first: with `bind()` overwriting, an authenticated second request rebinds and looks correct. | The third (anonymous) request now catches it, reporting `An unauthenticated request on the reused thread read ['B-MAG']`. |
| 5 | A fresh thread per request | **Survived.** | See below — the reason is worth its own section. |
| 6 | `CONN_MAX_AGE = 600` on runtime aliases | Killed, by exhausting PostgreSQL's connection slots. | — |

### `threading.get_ident()` is recycled, and it made the reuse guard useless

The leak test asserts that all submissions ran on one thread, because a fresh thread per
request hides the bug permanently. That guard was written with
`threading.get_ident()` — and mutation 5, which starts and joins a new thread per request,
**passed**: CPython reuses the OS-level identifier once a thread has exited, so four
distinct threads reported one identity.

The guard now records `threading.current_thread().name`. `Thread.__init__` assigns names
from a monotonic counter, so two distinct `Thread` objects never share one, while a reused
pool worker keeps its name across submissions. Re-running mutation 5 now fails with
*"The submissions ran on 4 different threads."*

This is exactly the failure the plan warned about — *"a version that spawns a fresh thread
per request passes against broken code and is worse than no test"* — and the only reason
it was caught is that the mutant was actually run rather than reasoned about.

## Deviations from Plan

### 1. [Rule 1 — Bug] The tenancy `django_db` marker has to be applied at collection time

- **Found during:** Task 2
- **Issue:** the `db_all` fixture applies `pytest.mark.django_db(databases=TENANT_DBS)`
  from inside its own body, as `02-RESEARCH.md` §7 specifies. pytest-django decides which
  test databases to **create** in its session-scoped setup fixture, reading each collected
  item's `django_db` marker — a decision taken before any fixture body runs. It happens to
  work when the first database test in a session is a tenancy one, which is why it went
  unnoticed in 02-02. Running `pytest tests/test_tenancy_router.py`, whose first database
  test asks only for `default`, created only `default`; the tenancy tests that followed
  then connected to **`optique_test_a`** — the *production* database name — and failed
  with `database "optique_test_a" does not exist`. Against a real deployment that is a
  test suite writing to a live database.
- **Fix:** a `pytest_collection_modifyitems` hook in `conftest.py` marks every item
  requesting `db_all`, `tenant_a` or `tenant_b`. The fixture keeps its `applymarker` as an
  idempotent belt-and-braces. **Still not an override of the database-setup fixture** —
  the aliases remain static in `config/settings/test.py`, so creation, migration,
  teardown, per-test rollback and xdist `_gw0` suffixing all keep working, and
  `grep -rn "django_db_setup" conftest.py tests/` still returns nothing.
- **Commit:** `a526e25`

### 2. [Rule 3 — Blocking] The middleware and task tests bind the static test aliases

- **Found during:** Task 3
- **Issue:** the leak test was first written with the middleware registering a genuine
  runtime alias (`tenant_<pk>`) onto the tenant databases. Django refuses it:
  `DatabaseOperationForbidden: Database threaded connections to 'tenant_6' are not allowed
  in this test`. `TransactionTestCase` blocks any alias outside its declared `databases`,
  and Django's "dynamically created connections are always allowed" escape hatch checks
  `alias in connections`, which is true for anything in `connections.settings` — exactly
  where `register_client_database` puts it.
- **Fix:** an autouse `bound_to_test_aliases` fixture redirects two names and only two —
  `alias_for`, so a client binds `tenant_a` or `tenant_b`, and `register_client_database`,
  which becomes a no-op because those aliases are already declared. The middleware's and
  the task's own logic runs untouched: entry guard, ACTIVE-only resolution, bind,
  `finally: clear()`.
- **Why this does not weaken the test:** the three load-bearing properties survive — one
  reused thread, two genuinely different client *databases*, assertions on data. It is
  also precisely what `.planning/TESTING.md` §3 prescribes: *"Runtime registration is
  tested separately, not used as the fixture."* Separately is `tests/test_tenancy_registry.py`
  and the 300-alias load check, both of which call `register_client_database` for real.
- **Commit:** `66be981`

### 3. [Rule 1 — Bug] The leak test needs `transaction=True`, for the reason TESTING.md names

- **Found during:** Task 3
- **Issue:** with a plain `django_db` marker the test failed with `NoTenantBound`, because
  `TestCase` wraps the test in a transaction on the **main** thread's connection and the
  pool thread holds a different one. It could not see the uncommitted `Client` rows, so
  `resolve_client` returned `None` and nothing bound. A failure for a reason unrelated to
  leaking — the exact trap `.planning/TESTING.md` §4 describes.
- **Fix:** `@pytest.mark.django_db(transaction=True, databases=TENANT_DBS)`, with the
  reason in the docstring. The pool worker also calls `close_old_connections()` in a
  `finally`, which is what Django's WSGI handler does at `request_finished` — calling the
  middleware directly skips that signal, and a pool thread holding its connection open
  blocked the test-database teardown.
- **Commit:** `66be981`

### 4. [Rule 2 — Correctness] The Sentry scrubber was going to ship untested

- **Found during:** Task 3
- **Issue:** the plan specifies `telemetry.before_send` as the mitigation for T-02-17
  (ordonnance data reaching Sentry) but names no test for it. An untested scrubber
  silently stops covering a field the moment a model gains one — and the evidence that it
  stopped is a leak of health data to a third party.
- **Fix:** `tests/test_telemetry.py`, four tests: clinical and personal values are
  redacted in request bodies, **frame locals are scrubbed** (the path
  `send_default_pii = False` does not cover — a traceback through a serializer carries
  exactly what the request carried), non-sensitive locals are *not* redacted (a scrubber
  that redacts everything gets turned off), the `client` / `magasin` tags survive, and a
  sparse event does not raise inside `before_send` (an exception there makes the SDK drop
  the scrubbing, silently).
- **Commit:** `66be981`

### 5. `task_prerun` is connected from `ready()`, not merely by module import

- **Found during:** Task 3 review
- **Issue:** the receiver was registered by a module-level decorator in `tasks.py`, which
  only fires when something imports that module — task autodiscovery, eventually. The plan
  says *"Connect receivers in `TenancyConfig.ready()`, not lazily."*
- **Fix:** `TenancyConfig.ready()` imports `plateforme.tenancy.tasks`. `ready()` still
  registers no alias and touches no database.
- **Commit:** `66be981`

### 6. Three acceptance-criterion greps needed prose reworded, not checks relaxed

Same pattern as plan 02-02: the criteria are greps that must return nothing, and the
docstrings tripped them by *naming the thing they warn against*.

- `grep -rn "\.reset(" plateforme/tenancy/` matched `context.py`'s module docstring, which
  the same task also *requires* to contain the reproduction. Rewritten as
  `cv.set("LEAKED")` / `tok = cv.set("current")` / "undo that set with `tok`" — the
  experiment is still legible, the grep is clean.
- `grep -rnE "ensure_defaults|prepare_test_settings" plateforme/ config/` matched
  `registry.py`'s explanation. Reworded to describe the two removed helpers, with a
  pointer to `tests/test_tenancy_registry.py`, where the names **are** spelled out — so a
  developer searching for them still lands on the test that proves the replacement works,
  which is a better destination than the code that does not call them.
- `grep -n "_nodb_cursor" plateforme/tenancy/maintenance.py` (plan 02-02) likewise.

### 7. Plan verification #1 is stated for the end of the phase, not the end of this wave

`uv run pytest -q --create-db` cannot exit 0 yet: 11 tests remain `pending` for plans
02-04 through 02-07 and fail by design, which is the convention plan 02-02 established.
The form that is meaningful now — `uv run pytest -q --create-db -m "not pending"` — exits
0 with **41 passed, 11 deselected**. This plan's own success criterion (no `pending`
markers in the three files it owns) is met exactly: 24 pending tests before, 11 after,
and the 13 removed are precisely the 13 this plan owned.

## Known Stubs

| Stub | File | Reason |
|---|---|---|
| 11 tests fail with `pytest.fail("pending: implemented by plan 02-0X")` | `tests/test_provisioning.py` (5), `tests/test_migrate_all.py` (2), `tests/test_magasin_scoping.py` (2), `tests/test_backup_restore.py` (2) | Owned by plans 02-04 / 02-05 / 02-06 / 02-07. Each carries a full docstring specification. |
| `config/urls.py` has empty `urlpatterns` | `config/urls.py` | No application to route yet; the operator admin arrives with 02-04. |
| `resolve_client` reads `request.user.client_id` | `plateforme/tenancy/middleware.py` | Deliberate and documented. Phase 3 builds the user model and the JWT; the contract — server-verified identity in, `Client` row out — does not change. |

No stub prevents this plan's goal. TENANT-04 holds under all four defences.

## Verification

| Check | Result |
|---|---|
| `uv run pytest -q --create-db -m "not pending"` | **0** — 41 passed, 11 deselected, 1.76s |
| `uv run pytest -q -m "not slow and not pending"` | **0** — 40 passed, 1.03s (budget: 30s) |
| `uv run pytest -n 2 -q -m "not slow and not pending"` | **0** — xdist does not collide |
| `uv run pytest tests/test_tenancy_router.py -q --create-db` | **0** — 9 passed, 0 pending |
| `uv run pytest tests/test_tenancy_context.py -q --create-db` | **0** — 11 passed, 0 pending |
| `uv run pytest tests/test_tenancy_registry.py -q` | **0** — 6 passed |
| `test_tenant08_connection_count_does_not_scale_with_alias_count -m slow` | **0** — peak 4 for 300 aliases |
| `uv run python manage.py check --settings=config.settings.test` | **0** — no issues, no `tenancy.E001` |
| `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` | **0** |
| `grep -rnE "ensure_defaults\|prepare_test_settings" plateforme/ config/` | no match |
| `grep -rn "\.reset(" plateforme/tenancy/` | no match |
| `grep -rn "del connections.settings" plateforme/` | only the `# NEVER` comment |
| `grep -rn "mark.pending" tests/test_tenancy_router.py tests/test_tenancy_context.py tests/test_connection_budget.py` | no match |
| `grep -nE "request\.(META\|headers).*(tenant\|client)" plateforme/tenancy/middleware.py` | no match |
| `magasins_magasin` in `test_optique_control` | **ABSENT** |
| `magasins_magasin` in `test_optique_test_a` | present |

### A note on `makemigrations` and the static test aliases

Under `config.settings.test`, `makemigrations --check` exits 0 but emits
`RuntimeWarning: Got an error checking a consistent migration history ... for database
connection 'tenant_a'`. That is Pitfall 4's warning sign, and here it is benign and
explained: `tenant_a` / `tenant_b` are declared statically by plan 02-01 so the suite has
two tenants, and their non-test `NAME`s do not exist as real databases. Confirmed that
**no runtime alias is registered at import** under either settings module:

- `config.settings.local` — aliases at import: `['default']`; `tenant_*`: `[]`
- `config.settings.test` — aliases at import: `['default', 'tenant_a', 'tenant_b']`;
  runtime `tenant_<pk>` aliases: `[]`

`makemigrations --check --dry-run --settings=config.settings.local`, which is what a
developer and CI actually run, connects to `default` only and exits 0 silently.

## Self-Check: PASSED

All 29 claimed files exist on disk. All seven claimed commits exist in the worktree history
(`66c400c`, `392a052`, `47002ee`, `1b8e22c`, `4355401`, `a526e25`, `66be981`). Every
measured number in this summary was produced by a command run in this session, not
estimated.

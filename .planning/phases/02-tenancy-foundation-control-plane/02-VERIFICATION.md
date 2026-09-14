---
phase: 2
slug: tenancy-foundation-control-plane
verified: 2026-09-14T00:00:00Z
reverified: 2026-09-14T10:15:00Z
status: verified
score: 5/5 roadmap success criteria verified; the one gap found on 2026-09-14 is closed
overrides_applied: 0
gaps: []
closed_gaps:
  - truth: "A client business with several magasins keeps database connections inside budget when a few hundred clients are provisioned and touched (Roadmap SC5, second half; TENANT-08)"
    status: closed
    closed_at: 2026-09-14T10:15:00Z
    closed_by:
      - "4673472 fix(02-08): resolve PgBouncer credentials by auth_query, not by a static file"
      - "276f77a fix(02-08): keep client roles out of the maintenance database"
      - "502a4c9 test(02-08): observe the connection budget with real per-client credentials"
    evidence:
      - "docker/postgres/init/01-pgbouncer-auth.sql — unprivileged `pgbouncer_auth` role plus a SECURITY DEFINER lookup function owned by `postgres`, EXECUTE granted to that role alone and revoked from PUBLIC, `search_path` pinned. `pg_shadow` is superuser-only, so auth_query never touches it directly and auth_user is never a superuser."
      - "docker/pgbouncer/pgbouncer.ini — `auth_user` / `auth_dbname` / `auth_query`. `auth_dbname = pgbouncer_auth_db` is load-bearing: PgBouncer runs auth_query inside the database the client asked for, so with one database per client the function would otherwise have to be installed into every client database, including ones created after the fact."
      - "docker/pgbouncer/userlist.txt — reduced to a two-line fallback (auth_user's own password, which cannot itself be looked up, and the admin console, which PgBouncer serves rather than PostgreSQL). `test_tenant08_no_client_role_is_written_into_the_static_auth_file` fails if a per-client role is ever added."
      - "tests/test_pgbouncer_auth.py — seven tests. A provisioned client authenticates through the PgBouncer container as its own optique_u###### role with no file edit and no reload; cross-client access is still refused through the pooler; a wrong password is still refused; the lookup function is unreachable by PUBLIC and by client roles; three distinctly-credentialed clients get three pools and hold zero server connections while idle."
      - "Verified from an empty data volume: `docker compose down -v && docker compose up -d` runs both init scripts and the full suite passes with zero manual steps (107 passed)."
    mutation_checks:
      - "REVOKE EXECUTE ON FUNCTION public.pgbouncer_get_auth(text) FROM pgbouncer_auth -> 3 pooled tests red with `FATAL: bouncer config error`"
      - "auth_query pointed at a misspelled function name -> 3 pooled tests red"
      - "auth_dbname commented out -> 4 tests red, confirming the function is genuinely absent from client databases"
      - "pool_mode = session -> the budget test red with `3 idle clients are pinning 3 server connection(s)`"
    residual: >
      The fleet-scale half of SC5 (a few *hundred* clients) still rests on the
      `min_pool_size = 0` + `server_idle_timeout` arithmetic plus the 300-alias Django-side
      test, because reaping is time-based and not cheaply observable in a unit test. What
      changed is that the mechanism it rests on — per-(user, database) pools with genuinely
      distinct credentials, and zero server connections held by an idle client — is now
      observed against the running pooler rather than quoted from documentation.
    original_finding: >
      (Recorded as found on 2026-09-14, before closure.)
      PgBouncer, as shipped, cannot authenticate any dynamically provisioned client role.
      docker/pgbouncer/userlist.txt contains only the single static development user
      (optique_app); auth_type is scram-sha-256 with auth_file, and no auth_query is
      configured, even though 02-RESEARCH.md's own PgBouncer recommendation and
      docker/pgbouncer/userlist.txt's own comment both specify auth_query against
      pg_shadow as the production fix. Every real client's web/Celery traffic path
      (Client.connection_params(direct=False)) points at PgBouncer and authenticates as
      that client's own optique_u###### role — which PgBouncer will refuse. This is not
      a hypothetical: 02-04-SUMMARY.md states it explicitly under "Notes for later
      plans" — "PgBouncer cannot authenticate a per-client role yet... Phase 3's first
      real request will hit this" — and no plan in Phase 2 closes it.
      The flagship connection-budget test that is supposed to prove TENANT-08/SC5
      (test_tenant08_connection_count_does_not_scale_with_alias_count) does not exercise
      this at all: under config/settings/test.py, "default", tenant_a and tenant_b are
      all pointed directly at PostgreSQL (PG_ADMIN_HOST/PORT), bypassing PgBouncer
      entirely, and the 300 synthetic aliases in that test all share one identical
      USER/PASSWORD rather than 300 distinct per-client credentials. So the test proves
      Django's own connection lifecycle discipline (CONN_MAX_AGE=0, lazy DatabaseWrapper
      construction) is sound, which is real and valuable, but it does not prove — and
      cannot currently prove — that a fleet of genuinely credentialed clients can
      authenticate through the pooler at all, let alone stay inside budget while doing
      so. The roadmap's own wording is "provisioning a few hundred clients and touching
      them all keeps database connections inside budget" — "touching them" through the
      real traffic path is exactly the part that is unverified and currently broken.
    original_artifacts:
      - path: "docker/pgbouncer/pgbouncer.ini"
        issue: "auth_type = scram-sha-256 with a static auth_file; no auth_query configured against pg_shadow, so a role created after the file was written cannot authenticate."
        resolution: "auth_user = pgbouncer_auth, auth_dbname = pgbouncer_auth_db, auth_query = SELECT username, password FROM public.pgbouncer_get_auth($1)."
      - path: "docker/pgbouncer/userlist.txt"
        issue: "Contains only optique_app. Its own comment states the production fix (auth_query) is not applied here."
        resolution: "Now a documented two-line fallback for auth_user's own credential and the admin console. A per-client role in it turns the suite red."
      - path: "tests/test_connection_budget.py"
        issue: "test_tenant08_connection_count_does_not_scale_with_alias_count and every other TENANT-08 test connect directly to PostgreSQL under test settings (config/settings/test.py overrides HOST/PORT to PG_ADMIN_HOST/PORT for default, tenant_a and tenant_b), so PgBouncer's actual per-tenant-credential authentication path is never exercised by the suite."
        resolution: "Left as it is — creating and dropping test databases is DDL and must stay off the pooler. tests/test_pgbouncer_auth.py is the companion that exercises the pooled path with real per-client credentials."
    original_missing:
      - item: "Configure PgBouncer with auth_query = SELECT usename, passwd FROM pg_shadow WHERE usename = $1 (and an auth_user role with pg_read_all_settings/pg_shadow read access), as 02-RESEARCH.md already specifies for production, and drop the static userlist.txt from anything but a documented dev fallback."
        status: done
        note: "Implemented, with one deliberate departure from the wording: the query does NOT read pg_shadow directly. pg_shadow is superuser-only, so the literal form would force auth_user to be a superuser and make the pooler's stored credential the keys to the cluster. A SECURITY DEFINER function does the privileged read instead, with EXECUTE granted to pgbouncer_auth alone. (There is also no such thing as a pg_shadow read role; pg_read_all_settings is about GUCs, not credentials.)"
      - item: "A test that provisions a real client, then makes at least one request through the actual PgBouncer container using that client's own db_user/db_password (not the shared default credential), and asserts the connection succeeds."
        status: done
        note: "test_tenant08_newly_provisioned_client_authenticates_through_pgbouncer, plus six companions covering cross-client refusal through the pooler, wrong-password refusal, the lookup function's privileges, and the per-(user, database) pool observation."
deferred: []
human_verification: []
---

# Phase 2: Tenancy Foundation & Control Plane — Verification Report

**Phase Goal:** A new client business is a provisioning operation, not a deployment, and no code can ever touch data without knowing which client it belongs to
**Verified:** 2026-09-14
**Status:** verified — the one gap found on 2026-09-14 was closed the same day
**Re-verification:** Yes — see "Gap Closure" below. The original finding is preserved
verbatim throughout; nothing in it has been rewritten to look better in hindsight.

## Summary

This is a genuinely strong piece of engineering. The tenancy layer's core security
property — fail-closed context, no token-based reset, `allow_migrate` as the absolute
backstop, the below-the-application `REVOKE CONNECT ... FROM PUBLIC` fix — is real,
tested with a positive and negative case per claim, and the tests are honest about what
they prove versus what they assume (mutation checks are recorded, not merely claimed).
The provisioning state machine, migration fan-out, and per-client backup/restore with
checksum verification (not row counts, not exit codes) all hold up under direct reading
of the code, not just the summaries.

One real gap survives independent reading: **PgBouncer, as configured, cannot
authenticate any client role the provisioner creates**, and the test suite's TENANT-08
evidence is built entirely on a path that bypasses PgBouncer, so this was never caught by
the suite itself. It is honestly self-documented in 02-04-SUMMARY.md as a known
unresolved issue — which is why this is a gap to close, not a hidden defect — but it sits
squarely inside what Roadmap Success Criterion 5 promises ("touching them all keeps
database connections inside budget") and it is not owned by any later Phase 2 plan or by
Phase 3's stated scope. Left as-is, Phase 3's first authenticated request against a real
provisioned client will fail to connect.

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | An operator provisions a new client business with a single repeatable operation, at the current schema version, and uses the same path for manual onboarding | VERIFIED | `provision_client()` (plateforme/control_plane/provisioning.py) is the single function called by both `manage.py provision_client` (58 lines, no provisioning logic, asserted by `test_tenant06_management_command_delegates_to_provision_client`) and — by contract — Phase 12's self-serve flow. `pending_plan(alias) == []` is asserted, not merely "no exception raised". |
| 2 | A provisioning attempt killed halfway leaves no half-created client; rerunning converges to complete or none | VERIFIED | Per-step idempotency (role/database existence checks, `django_migrations` for migrate, `get_or_create` for seed, one transactional UPDATE for activation) is real, not asserted-only. `test_tenant05_rerun_after_kill_converges_to_active` kills at the migrate step (post CREATE DATABASE/ROLE) and proves convergence on rerun; `test_tenant05_rerun_creates_no_second_database` proves no orphan. FAILED clients are proven invisible to the router's own query, not merely status-flagged. |
| 3 | The control plane lists every client database/host/schema version, and migration fan-out reports succeeded/failed/behind per client | VERIFIED | `migrate_all` distinguishes `ok`/`failed`/`behind` as three named states (not "success/failure"), persists them per client in `MigrationRunResult`, and both halves are tested: `test_tenant03_migration_fanout_reports_which_clients_are_behind` proves the gate is clean before the mutation and red after (not "always red"); `test_tenant03_one_client_failing_does_not_stop_the_others` uses a real process-pool fan-out (not `--parallel 1`) and asserts three result rows, which is what actually distinguishes "attempted and failed" from "silently skipped". |
| 4 | Code with no resolved client context refuses to run, proven by a permanent cross-client-leak guardrail test in CI | VERIFIED | `current_alias()` raises rather than falling back to `default`; the router raises on an unclassified app and is backstopped by `allow_migrate` + `tenancy.E001`, which is the real absolute defence (bypassing `.using()` still hits "relation does not exist" on `default`). The reused-thread leak test asserts on **data**, on a **genuinely reused thread** (`Thread.name`, not `get_ident()`, which is recycled), with a third "resolves nothing" request that is what actually catches a `bind()`-only leak. `REVOKE CONNECT ... FROM PUBLIC` closes the below-the-application hole and is proven both positively (A connects to its own DB) and negatively (A refused by B's DB), with a mutation check confirming the test fails if `_restrict_connect` is removed. |
| 5a | A client business with several magasins is created with stock and caisse scoped per magasin | VERIFIED | `seed_new_client` refuses zero magasins; `for_magasin`/`for_magasins` are explicit projections (deliberately not implicit, with the unscoped-manager half of the test asserted too, which is the harder direction to get right); `on_delete=PROTECT` is enforced and tested against a real `ProtectedError`. |
| 5b | Provisioning a few hundred clients and touching them all keeps connections inside budget | VERIFIED (was PARTIAL) | Django-side half unchanged and still proven directly against `pg_stat_activity`. PgBouncer-side half closed: `auth_query` resolves each client's own credential from PostgreSQL, so a client provisioned minutes ago authenticates through the pooler with no file edit and no reload (`test_tenant08_newly_provisioned_client_authenticates_through_pgbouncer`), and three distinctly-credentialed clients get three `(user, database)` pools while holding zero server connections when idle (`test_tenant08_idle_clients_hold_no_server_connection_through_pgbouncer`, read from PgBouncer's own `SHOW POOLS`). See "Gap Closure". |

**Score:** 5/5 verified. (At the initial verification: 4/5 fully verified, 1 partial.)

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `plateforme/tenancy/context.py` | fail-closed contextvar, no token-reset | VERIFIED | `_UNSET` sentinel, `clear()` never `reset(token)`; grep for `reset(` returns nothing in this module |
| `plateforme/tenancy/router.py` | raise on unbound, `allow_migrate` absolute backstop | VERIFIED | Raises `NoTenantBound`/`CrossTenantAccess`/`ImproperlyClassifiedApp`; `allow_migrate` never raises, by design |
| `plateforme/tenancy/middleware.py` | resolve from principal, clear in finally, entry guard | VERIFIED | `finally: clear()`; entry guard logs CRITICAL and self-heals unless `TENANCY_STRICT` |
| `plateforme/tenancy/tasks.py` | Celery fails closed on missing client_id | VERIFIED | `task_prerun` receiver is the prefork-process equivalent of the middleware guard |
| `plateforme/tenancy/provisioner.py` | two-method interface, injection-safe SQL, PUBLIC-CONNECT fix | VERIFIED | `sql.Identifier`/`sql.Literal` throughout, no f-strings; `_restrict_connect` applied on both create and existence-adopt paths |
| `plateforme/control_plane/provisioning.py` | idempotent state machine | VERIFIED | Per-step idempotency documented and matches the implementation exactly |
| `plateforme/control_plane/fanout.py` | process-isolated migration fan-out | VERIFIED | `spawn` context, no module-level Django import, child never touches control plane |
| `plateforme/control_plane/checksum.py` | ordered per-table md5 + sequences | VERIFIED | Matches TENANT-09's closure note exactly: ordered row hashes, UTC pinning, sequences included |
| `plateforme/control_plane/backup.py` | verified single-client restore, PUBLIC-CONNECT applied to restore target | VERIFIED | Restore target created via the same `provisioner.create_database`, so `_restrict_connect` applies; restore connects as the client's own role, not superuser |
| `docker/pgbouncer/pgbouncer.ini` + `userlist.txt` | production-shaped PgBouncer auth | VERIFIED (was **STUB**) | `min_pool_size=0`, `pool_mode=transaction` etc. unchanged and still correct. `auth_user`/`auth_dbname`/`auth_query` now resolve every client credential from PostgreSQL; `userlist.txt` is down to the two credentials that provably cannot come from a query (auth_user's own, and the admin console's). |
| `docker/postgres/init/01-pgbouncer-auth.sql` | the server side of `auth_query` | VERIFIED (new) | Unprivileged `pgbouncer_auth` role; `SECURITY DEFINER` lookup owned by `postgres` with a pinned `search_path`; `EXECUTE` revoked from PUBLIC and granted to the one role; `CONNECT` on the maintenance database revoked from PUBLIC. Runs clean on an empty volume and is idempotent by hand. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `TenantMiddleware` | `TenantRouter` | `bind(alias_for(client.pk))` → `current_alias()` | WIRED | Traced end to end; reused-thread test proves it under the actual failure condition |
| `provision_client` | `SqlProvisioner._restrict_connect` | `create_database()` call | WIRED | Applied on both the create path and the existing-database adopt path |
| `Client.connection_params(direct=False)` | PgBouncer | HOST/PORT = `PGBOUNCER_HOST`/`PORT`, USER/PASSWORD = client's own role | WIRED (was **NOT WIRED in practice**) | `auth_query` resolves the client's credential from `pg_shadow` through a SECURITY DEFINER function, so the role the provisioner created minutes ago authenticates with no pooler change. Proven end to end against the running container, and mutation-checked four ways. |
| `SqlProvisioner._restrict_connect` | the pooled path | PgBouncer opens its own server connection as the client's role | WIRED | PgBouncer authenticates the client and then logs in to PostgreSQL as that same role, so the `REVOKE CONNECT` still bites: client A through the pooler is refused by client B's database with `permission denied for database ...`. Asserted by `test_tenant04_client_role_cannot_reach_another_clients_database_through_pgbouncer`, with B's own credential succeeding in the same test so "refused" cannot mean "nothing works". |
| `restore_client` | `tenant_checksum` | pre-cutover verification | WIRED | Verification happens before cutover, and the test mutates data first so a no-op restore cannot pass |
| `migrate_all` | `fanout.migrate_fleet` | per-client process isolation | WIRED | Process-pool proven by PID capture and a genuinely broken middle client |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|---|---|---|---|
| TENANT-01 | Single repeatable provisioning operation | SATISFIED | `provision_client`, tested against migration head, not error-absence |
| TENANT-02 | Control plane records db/host/schema version | SATISFIED | `Client` model fields + admin list display |
| TENANT-03 | Fan-out reports succeeded/failed/behind | SATISFIED | Three distinct states, both halves tested honestly |
| TENANT-04 | Fail-closed context, no shared-connection fallback | SATISFIED | Router raises; below-application `PUBLIC CONNECT` fix closes the one hole a prior review missed |
| TENANT-05 | Killed provisioning converges, no half-created client | SATISFIED | Kill point (mid-migrate) is representative given the per-step idempotency design; each other step's idempotency mechanism is independently verifiable from the code and is exercised by adjacent tests (rerun-is-noop, deprovision) |
| TENANT-06 | Manual onboarding uses the self-serve path | SATISFIED | Source-level test pins the command at 58 lines with zero provisioning primitives |
| TENANT-07 | Multi-magasin, stock/caisse scoped per magasin | SATISFIED | Explicit projection, both the scoped and unscoped halves tested |
| TENANT-08 | Connections pooled, budget independent of client count | SATISFIED (was **PARTIALLY SATISFIED**) | Django-side discipline unchanged; PgBouncer-side per-client authentication now functional and proven. The one nuance stated plainly: "a few hundred" clients is still an arithmetic claim resting on `min_pool_size = 0` and `server_idle_timeout`, because reaping is time-based. What is no longer an arithmetic claim is the mechanism underneath it — distinct credentials, distinct pools, zero server connections held by an idle client — which is now read out of the pooler itself. |
| TENANT-09 | Per-client backup and verified single-client restore | SATISFIED | Checksum-based, not exit-code-based; neighbour-isolation proven, which is the part that actually distinguishes per-database restore from per-instance PITR |

No orphaned requirements: all nine TENANT IDs are claimed by a plan and none appear in REQUIREMENTS.md's Phase 2 mapping without a corresponding plan claim.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `docker/pgbouncer/userlist.txt` | whole file | Single static dev credential standing in for the production `auth_query` design | ~~Blocker (for real multi-tenant traffic)~~ **RESOLVED 2026-09-14** | Closed by `auth_query`. A regression is now a red test rather than a code review: `test_tenant08_no_client_role_is_written_into_the_static_auth_file` reads the file's credential lines (not its comments) and fails on any per-client role. |
| `plateforme/tenancy/middleware.py` / `tasks.py` | `TENANCY_STRICT` branch | Production default (`TENANCY_STRICT=False`) self-heals rather than refuses on a detected leak; this branch is untested (test settings force `TENANCY_STRICT=True`) | Info | Not a leak — clear() happens before the current request's resolution — but the fail-open production default is untested and worth a dedicated test asserting the self-heal path itself doesn't regress into serving stale context |
| Append-only enforcement (`MouvementStock`, `EcritureCaisse`) | model level | No DB-level `REVOKE UPDATE/DELETE` or trigger; "append-only" is presently a Python-discipline guarantee (no update/delete method exposed), not enforced below the application | Info (deferred) | Explicitly documented as Phase 5/7 territory in the models' own docstrings; consistent with Roadmap Phase 2 scope, which only requires scoping, not immutability enforcement. Flagged only because it is the same *class* of gap as the PUBLIC-CONNECT issue (Python-only guarantee) — worth remembering when Phase 5/7 build on this base, since the pattern that bit Phase 2 (an assumption enforced only above the database) is exactly the pattern here too. |

### Human Verification Required

None. Everything above is resolvable by reading code and by running the two additional automated checks recommended in the gap.

## Gaps Summary

Four of five roadmap success criteria are fully and honestly earned — the tenancy layer's
hard security properties (fail-closed context, the PUBLIC CONNECT fix, process-isolated
migration fan-out, checksum-verified restore) are real, not merely claimed, and the tests
are calibrated to catch the specific ways each of them could be faked. This is a
higher-than-usual bar to have met.

The one gap is specific and self-contained: **PgBouncer cannot authenticate a
per-client role today**, and the phase's own flagship connection-budget test proves a
real but narrower claim (Django's connection lifecycle is disciplined) while silently
substituting a shared credential and a direct-to-PostgreSQL path for the actual
multi-tenant pooling story SC5 describes. This was self-diagnosed by the executor in
02-04-SUMMARY.md and explicitly flagged as something "Phase 3's first real request will
hit" — but no plan in Phase 2 or Phase 3's stated scope owns closing it, so it is
reported here rather than assumed to be someone else's problem. The fix is already
specified in this phase's own research (`auth_query` against `pg_shadow`) and is a
small, well-understood change; it should land before Phase 3 builds the first real
authenticated request path, not be discovered when that request fails.

**Status: closed, same day. See "Gap Closure" below.**

## Gap Closure (2026-09-14)

### What was wrong

`Client.connection_params(direct=False)` — the path every web request and every Celery
task takes — points at PgBouncer and authenticates as the client's own
`optique_u######` role. PgBouncer was configured with `auth_type = scram-sha-256` and a
static `auth_file` containing one hand-written development credential. Reproduced before
touching anything: provision a real client, connect to `127.0.0.1:6433` with its own
credential, and PgBouncer answers `FATAL: SASL authentication failed`.

### What changed

**`docker/postgres/init/01-pgbouncer-auth.sql` (new).** A `pgbouncer_auth` login role with
no other privilege at all, and a `SECURITY DEFINER` lookup function owned by `postgres`:

```sql
CREATE OR REPLACE FUNCTION public.pgbouncer_get_auth(p_usename text)
RETURNS TABLE (username text, password text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$ SELECT s.usename::text, s.passwd::text
      FROM pg_catalog.pg_shadow AS s WHERE s.usename = p_usename; $$;
REVOKE ALL ON FUNCTION public.pgbouncer_get_auth(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.pgbouncer_get_auth(text) TO pgbouncer_auth;
```

Three details that are not decoration:

- **Not `SELECT usename, passwd FROM pg_shadow WHERE usename = $1`**, which is the shape
  the gap report and most documentation quote. `pg_shadow` is superuser-only, so the
  literal form forces `auth_user` to be a superuser and makes the pooler's own stored
  credential the keys to the cluster. This is a deliberate departure from the wording of
  the fix, in the direction the wording was reaching for.
- **Output columns are `username`/`password`, not `usename`/`passwd`.** In a
  `RETURNS TABLE` function the output parameter names are in scope inside the body, so
  reusing `pg_shadow`'s own column names makes every reference ambiguous and the function
  fails to create.
- **`SET search_path` is pinned.** An unpinned `SECURITY DEFINER` function lets anyone who
  can create objects in an earlier schema shadow an unqualified name and have it executed
  as the owner — here, as a superuser.

**`docker/pgbouncer/pgbouncer.ini`.** `auth_user = pgbouncer_auth`,
`auth_dbname = pgbouncer_auth_db`, `auth_query = SELECT username, password FROM
public.pgbouncer_get_auth($1)`, plus a named `pgbouncer_auth_db` entry in `[databases]`.

`auth_dbname` is the subtle one and is the reason this is not a two-line change. PgBouncer
runs `auth_query` **inside the database the client asked for**. With one database per
client that would mean installing the function into every client database — and into every
client database created after the fact, which is precisely the deployment step being
removed. It must name a `[databases]` entry; the bare `*` fallback does not satisfy it.

**`docker/pgbouncer/userlist.txt`.** Down to the two credentials that provably cannot come
from a query: `auth_user`'s own (PgBouncer has to authenticate in order to run the lookup,
so the credential it runs the lookup with cannot itself be looked up) and the admin console
(served by PgBouncer, not PostgreSQL, so no query is involved).

**One thing deliberately unchanged.** Provisioning still uses
`connection_params(direct=True)`. `CREATE DATABASE` and `CREATE ROLE` cannot run through
transaction pooling, and `DROP DATABASE ... WITH (FORCE)` cannot terminate the server
connections PgBouncer holds. DDL stays on the direct path.

**One thing added that the gap did not ask for** (Rule 2 — a security requirement created
by the change itself). `auth_query` puts a superuser-owned function that returns any role's
SCRAM verifier into the `postgres` database, and PostgreSQL grants `CONNECT` on every
database to PUBLIC. `REVOKE ALL ... FROM PUBLIC` on the function is what stops the call;
`REVOKE CONNECT ON DATABASE postgres FROM PUBLIC` (granted back to `optique_app` and
`pgbouncer_auth` explicitly) stops the caller getting near it. This is the same default-
grant trap `SqlProvisioner._restrict_connect` already closes for client databases — the
maintenance database had been left out. Confirmed real before fixing: an ordinary role
returned `has_database_privilege(..., 'postgres', 'CONNECT') = t`.

### Evidence

`tests/test_pgbouncer_auth.py` — seven tests, all against the running Compose stack.

| Test | What it proves |
|---|---|
| `test_tenant08_newly_provisioned_client_authenticates_through_pgbouncer` | A client provisioned seconds ago queries its own database through the pooler as its own role. Asserts the role is **absent from `userlist.txt` before connecting**, so the test cannot pass because somebody pasted the credential in. |
| `test_tenant04_client_role_cannot_reach_another_clients_database_through_pgbouncer` | Isolation survives the pooled path. A is refused by B's database with `permission denied`; A reaches its own, and B reaches its own, in the same test. |
| `test_tenant04_credential_lookup_is_reachable_only_by_the_pooler` | The lookup is `SECURITY DEFINER` with a pinned `search_path`; PUBLIC and client roles have neither `EXECUTE` on it nor `CONNECT` to the database it lives in — then opens a real connection to confirm the privilege bits match reality. |
| `test_tenant08_wrong_password_is_still_refused_through_pgbouncer` | `auth_query` verifies rather than waves through. Same role, same database, same moment: only the password differs between the refusal and the success. |
| `test_tenant08_idle_clients_hold_no_server_connection_through_pgbouncer` | Three clients, three distinct credentials, read from PgBouncer's own `SHOW POOLS`: three `(user, database)` pools, `sv_active = 0` while all three are connected and idle. |
| `test_tenant08_pgbouncer_resolves_credentials_by_query_not_by_file` | `auth_query`/`auth_user`/`auth_dbname` are configured, and `auth_query` does not read `pg_shadow` directly. |
| `test_tenant08_no_client_role_is_written_into_the_static_auth_file` | No per-client role in `userlist.txt`. Reads credential lines only — the file's own comments name the forbidden shape in order to forbid it. |

**Mutation checks.** A test that passes against a broken pooler is worth nothing, which is
how this gap survived the phase. Each mutation was applied to the running stack and
reverted:

| Mutation | Result |
|---|---|
| `REVOKE EXECUTE ON FUNCTION public.pgbouncer_get_auth(text) FROM pgbouncer_auth` | 3 pooled tests red — `FATAL: bouncer config error` |
| `auth_query` pointed at a misspelled function name | 3 pooled tests red |
| `auth_dbname` commented out | 4 tests red, confirming the function really is absent from client databases and `auth_dbname` is load-bearing |
| `pool_mode = session` | budget test red: *"3 idle clients are pinning 3 server connection(s)"* |

**From-scratch check.** `docker compose down -v && docker compose up -d` runs both init
scripts on an empty volume in order, and the full suite passes with **zero** manual steps.
**Full suite: 107 passed** (was 100; +7 new tests, no existing test modified).

### What is still an arithmetic claim

SC5 says "a few *hundred* clients". Reaping idle server connections is governed by
`server_idle_timeout` and is time-based, so the fleet-scale ceiling is still an argument
from `min_pool_size = 0` plus the 300-alias Django-side test, not a direct observation.
What is no longer an argument is the mechanism it rests on: per-`(user, database)` pools
with genuinely distinct credentials, and zero server connections held by a connected but
idle client, are now read out of the pooler itself. Stated here rather than quietly
rounded up.

---
*Verified: 2026-09-14 · Gap closed and re-verified: 2026-09-14*
*Verifier: Claude (gsd-verifier)*

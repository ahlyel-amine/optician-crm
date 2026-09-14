---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: paused
stopped_at: Phase 2 complete and verified. The one verification gap (PgBouncer could not authenticate a provisioned client role) is closed by auth_query; 02-VERIFICATION.md records the evidence. Full suite 107 passed.
last_updated: "2026-09-14T10:02:51.519Z"
last_activity: 2026-09-13
progress:
  total_phases: 12
  completed_phases: 1
  total_plans: 7
  completed_plans: 7
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-09)

**Core value:** The counter completes a sale end to end — client, ordonnance, payment including acompte, landing in that magasin's caisse — producing a facture legally valid in Morocco every time.
**Current focus:** Phase 2 — Tenancy Foundation & Control Plane (Phase 1 continues in parallel as a calendar track)

## Current Position

Phase: 2 of 12 (Tenancy Foundation & Control Plane)
Plan: 3 of 7 complete in current phase (02-01, 02-02, 02-03; next is 02-04)
Status: Paused for review before provisioning creates real client databases
Last activity: 2026-09-13

Progress: [████░░░░░░] 43%

## Performance Metrics

**Velocity:**

- Total plans completed: 1
- Average duration: ~1 session
- Total execution time: ~1 session

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 2 | 1 of 7 | 1 session | 1 session |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 2 P02 | 1 session | 3 tasks | 17 files |
| Phase 2 P03 | 1 session | 3 tasks | 18 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Online only, permanently — no offline phase exists; sale creation is idempotent and the facture number is server-issued from a locked counter row, never a database sequence
- [Roadmap]: One database per client business; magasins live inside it — Phase 2 is unretrofittable and comes first in build order
- [Roadmap]: Permissions (Phase 3) precede the feature surface so the single projection layer exists before modules invent their own filtering
- [Roadmap]: Manual onboarding (TENANT-06) lands in Phase 2, so a real optician uses the product long before self-serve billing in Phase 12
- [02-01]: Infrastructure package is `plateforme/`, never `platform/` — a top-level `platform/` shadows the stdlib module that psycopg, gunicorn and Sentry import. Every `platform.*` dotted path in 02-RESEARCH.md becomes `plateforme.*`
- [02-01]: Django pinned 6.1.1 (inside the mandated >=6.1,<6.2) — the tenancy design rests on Django internals source-verified against 6.1.x
- [02-01]: `django-celery-beat` 2.9.0's stale `Django<6.1` cap lifted by a documented `[tool.uv] override-dependencies`, verified working rather than assumed; remove when a release lifts it upstream
- [02-01]: Client databases use the PostgreSQL 18 ICU locale provider (`LOCALE_PROVIDER icu ICU_LOCALE 'fr-FR'` with `TEMPLATE template0`), not an OS locale — the stock postgres image generates only `en_US.utf8`
- [02-01]: Compose host ports 5435 / 6433 / 6380 / 8010, all bound to 127.0.0.1 (8000, 5432-5434 and 6379 are occupied on the dev machine)
- [Roadmap]: Phase 1 is a parallel calendar track — only LEGAL-02 (hosting jurisdiction) gates build work
- [Phase 02-02]: CheckConstraint takes condition= on Django 6.1.1; check= is removed, not merely deprecated (research assumption A6 resolved)
- [Phase 02-02]: Client.connection_params(direct=False) uses the row's db_host/db_port (PgBouncer); direct=True swaps in PG_ADMIN_* for DDL, migrations and pg_dump
- [Phase 02-02]: The session-start stale-database reaper is skipped inside pytest-xdist workers, so one worker cannot drop another's test databases
- [Phase 02-03]: clear() is set(_UNSET); the token-based ContextVar undo appears nowhere under plateforme/tenancy. tenant_context restores on exit, request/task teardown clears — never unified
- [Phase 02-03]: CONTROL_PLANE_APPS must include rest_framework and tenancy — the tenancy.E001 check exempts only django.* names. A later phase adds its app label to BUSINESS_APPS in the same commit as INSTALLED_APPS
- [Phase 02-03]: resolve_client reads the authenticated principal only, never a header or subdomain; Phase 3 swaps the lookup for a signed JWT client_id claim without changing the contract
- [Phase 02-03]: TENANT-08 measured, not assumed: 300 registered aliases at concurrency 4 gave a peak of 4 server connections and settled to 0; CONN_MAX_AGE=600 exhausts PostgreSQL's connection slots
- [Phase 02-03]: The tenancy django_db marker is applied in pytest_collection_modifyitems, not from a fixture body — pytest-django decides which test databases to create before any fixture runs
- [Phase 02-08]: PgBouncer resolves client credentials by auth_query against a SECURITY DEFINER function (docker/postgres/init/01-pgbouncer-auth.sql), never by userlist.txt — a provisioned client needs no pooler edit and no reload. auth_dbname is required, or auth_query runs inside the client's own database where the function does not exist

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 6] Four open questions block the facturation schema and need a Moroccan comptable, not research: TVA rate on optical goods after the 2026 reform, série per magasin vs per company, TVA treatment of the acompte, and whether the facture is issued at commande or délivrance. Start these during Phase 1.
- [Phase 1] CNDP prior authorization is reported at 2-4 months and the Moroccan merchant contract at weeks to months. Both must be in flight from day one or they become the launch critical path.
- [Phase 12] Recurring card-on-file on Moroccan rails is a vendor claim and needs sandbox proof; if false, billing falls back to invoice plus payment link per period.

## Session Continuity

Last session: 2026-09-14T10:02:51.516Z
Stopped at: Phase 2 complete and verified. The one verification gap (PgBouncer could not authenticate a provisioned client role) is closed by auth_query; 02-VERIFICATION.md records the evidence. Full suite 107 passed.
Resume file: None

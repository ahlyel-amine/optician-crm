# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-09)

**Core value:** The counter completes a sale end to end — client, ordonnance, payment including acompte, landing in that magasin's caisse — producing a facture legally valid in Morocco every time.
**Current focus:** Phase 2 — Tenancy Foundation & Control Plane (Phase 1 continues in parallel as a calendar track)

## Current Position

Phase: 2 of 12 (Tenancy Foundation & Control Plane)
Plan: 1 of 7 complete in current phase
Status: Wave 1 complete — paused for user review before Wave 2 (02-02)
Last activity: 2026-09-13 — 02-01 executed: repository bootstrapped on Python 3.13.7 / Django 6.1.1 with an exactly-pinned stack, Compose topology up (PostgreSQL 18 + PgBouncer 1.25.2 transaction mode + Redis 8), TENANT-08 connection-budget invariants asserted and green

Progress: [█░░░░░░░░░] 1%

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

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 6] Four open questions block the facturation schema and need a Moroccan comptable, not research: TVA rate on optical goods after the 2026 reform, série per magasin vs per company, TVA treatment of the acompte, and whether the facture is issued at commande or délivrance. Start these during Phase 1.
- [Phase 1] CNDP prior authorization is reported at 2-4 months and the Moroccan merchant contract at weeks to months. Both must be in flight from day one or they become the launch critical path.
- [Phase 12] Recurring card-on-file on Moroccan rails is a vendor claim and needs sandbox proof; if false, billing falls back to invoice plus payment link per period.

## Session Continuity

Last session: 2026-09-09
Stopped at: ROADMAP.md and STATE.md created; REQUIREMENTS.md traceability filled in
Resume file: None

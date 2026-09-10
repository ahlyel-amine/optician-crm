# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-09)

**Core value:** The counter completes a sale end to end — client, ordonnance, payment including acompte, landing in that magasin's caisse — producing a facture legally valid in Morocco every time.
**Current focus:** Phase 1 — Legal & Compliance Track

## Current Position

Phase: 1 of 12 (Legal & Compliance Track)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-09-09 — Roadmap created, 76 v1 requirements mapped across 12 phases

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

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

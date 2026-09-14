<!-- GSD:project-start source:PROJECT.md -->
## Project

**Optician Management Platform**

A multi-tenant SaaS for Moroccan opticians. One platform where an optician business runs its whole day — clients and their ordonnances, stock, fournisseurs and achats, facturation, and a per-magasin caisse — on both web and mobile. Each client business gets its own database, may run one or several magasins, and appears under their own branding.

**Core Value:** The counter can complete a sale end to end — find or create the client, attach the ordonnance, take payment (including an acompte), and have it land in that magasin's caisse — producing a facture that is legally valid in Morocco every time.

### Constraints

- **Legal — invoicing**: Moroccan TVA and a gapless, chronological, duplicate-free facture series (art. 145 CGI). Gaps are treatable as fraud, and this is the client's tax exposure caused by our software.
- **Legal — health data**: ordonnances are sensitive data under law 09-08 — prior authorization is **art. 12-1-a + art. 21** (NOT art. 23, which is security/sous-traitant). Whether the art. 22 derogation to a simple déclaration applies, and whether the optician or the platform must file, are both unresolved: `.planning/research/CNDP.md`.
- **Legal — retention**: 10 years (art. 211 CGI), which constrains offboarding and the cost model
- **Locale**: MAD and French UI — drives formatting and vocabulary
- **Connectivity**: the application requires a connection. Sale submission must still be idempotent, since a retried request on a flaky link must never mint a second facture number.
- **Platforms**: web and mobile at full parity — one shared codebase and API rather than two products
- **Tenancy**: one shared application, one database per client — every request must resolve to the right client database, migrations must fan out across all of them, and a leak across clients is a security failure, not a bug
- **Payments**: Moroccan rails for subscriptions; recurring card-on-file is a vendor claim that must be proven in sandbox before the billing model depends on it
- **Timeline**: no hard deadline — build it right rather than fast
<!-- GSD:project-end -->

## Scope & Status

**92 v1 requirements across 12 phases.** Nothing is built yet — Phase 1 (legal filings, calendar-driven)
and Phase 2 (tenancy foundation) are next.

- Requirements and full traceability: `.planning/REQUIREMENTS.md`
- Phase structure, goals and success criteria: `.planning/ROADMAP.md`
- Phases flagged as needing research before planning: 1, 6, 7, 12

## Non-negotiables

Decisions already taken, with reasons recorded in `.planning/PROJECT.md`. Do not quietly reverse one
inside a phase plan — raise it instead.

1. **Online only, permanently.** No offline mode, no local storage, no sync layer. Sale submission is
   still idempotent, because a retried request must never mint a second facture number.
2. **One database per client business.** Never schema-per-client. **Never `django-tenants`** — it is
   schema-based and would silently reverse this.
3. **The facture number is server-issued** from a counter row locked `FOR UPDATE` inside the inserting
   transaction. Never a Postgres `SEQUENCE` (it gaps on rollback), never issued by a client.
4. **Stock, caisse and payments are append-only ledgers** with derived balances. No mutable
   `quantite` / `solde` / `montant_paye` columns. Corrections are compensating entries.
5. **A chèque is not cash until `encaissé`.** Post-dated chèques are normal here; counting one as cash
   on the day it is taken makes the caisse balance wrong.
6. **Only the optician (owner) and gérants log in.** Floor vendeurs never sign in — a vendeur is a field
   on a sale. Permissions are granted per gérant individually, as data, not as role tiers.
7. **Money is `Decimal`**, never float. TVA is per article, never a hardcoded global rate.
8. **Tenant context fails closed, and is cleared — not `reset()` — in a `finally`.**
   `ContextVar.reset(token)` restores the *previous* value, so on a reused worker thread it
   re-installs an earlier request's client. Verified. Use `set(_UNSET)` plus an assert-unset-on-entry
   guard. A router returning `None` falls through to `default`, which is a cross-client leak.
9. **The facture is itemised** — monture and verres on separate lines. AMO reimburses per line, so a
   single lump line under-reimburses the customer.
10. **Devis, facture and avoir are one document model**, built together in Phase 6.
11. **User accounts live in the control-plane database, with one shared login address.** Django needs
    `auth`/`contenttypes`/`admin` in a single database, and self-serve signup creates an account before
    the client database exists. The dividing line: the **control plane holds identity, business
    membership and permission grants**; the **client database holds all business data**, ordonnances
    included. Isolation is about the health and commercial data, not the login row.
12. **PostgreSQL's defaults are permissive — every new database and privileged object needs an
    explicit `REVOKE`.** `CONNECT` is granted to `PUBLIC` on every new database, and `EXECUTE` to
    `PUBLIC` on every new function. Three separate cross-access holes in this project came from that
    single default: client databases reachable by any client role, the `postgres` maintenance database
    reachable by any role, and a `SECURITY DEFINER` function returning SCRAM verifiers. All three were
    invisible to code review because the guarantee they broke was written in Python, one layer above.
    **When you add a database, a role or a `SECURITY DEFINER` function, write the `REVOKE` in the same
    change, and add a test that connects as the wrong principal and is refused.**
13. **Permission grants are stored per (gérant, magasin, permission).** The owner may override
    permissions per magasin, so the storage shape must support that from day one — the UI defaults to
    one uniform checklist across granted magasins and surfaces per-magasin override only on request.
    Do not "simplify" this to one permission set per gérant; reversing it is a data migration.
14. **Money renders as `1 800,00 MAD`** — U+00A0 non-breaking space, decimal comma. Django's `fr`,
    browser ICU `fr-FR` and ICU `fr-MA` all disagree here, so the format is pinned explicitly on both
    server and client from one shared fixture. Never rely on a locale default.
15. **Never set `ATOMIC_REQUESTS = True`.** `BaseHandler.make_view_atomic()` iterates *every* alias in
    `connections.settings` and wraps the view in `transaction.atomic(using=alias)` for each — with 300
    clients registered that is 300 transactions per request. Use explicit `atomic()` blocks instead.

## Testing

**This project is test-first.** Full strategy: `.planning/TESTING.md`. The short version:

- Write the test before the implementation, aimed at **invariants, not coverage**. Every
  non-negotiable above has a named test; reversing a decision must turn the suite red.
- **Name tests after their requirement** — `test_fact03_numbers_have_no_gaps_under_concurrency` —
  so requirement-to-test traceability is free.
- **Do not test Django.** Test our rules, not the framework's.
- Three traps that make tests pass against broken code: Django's `TestCase` wraps each test in a
  transaction so `select_for_update()` never contends (numbering tests need
  `transaction=True` and real threads); a fresh thread per test hides context leaks (the leak test
  must reuse one thread across two requests); and asserting on floats passes while the money is wrong.
- The tenancy fixtures provide **two** tenants, never one — isolation cannot be tested against a
  single client.
- No coverage percentage target.

Phase 1 has no tests by design — its evidence is documentary (filing references, the hosting
decision). Test code starts in Phase 2.

## Open Questions Blocking Phase 6

Need a Moroccan comptable, not more research. Start them during Phase 1.

1. Which TVA rate applies to montures, verres, lentilles and prestations after the 2026 reform
2. Whether a facture série per magasin is legal, or one continuous série per company is required
3. TVA treatment of the acompte, and whether a facture d'acompte needs its own fiscal number
4. Whether the facture is issued at commande or at délivrance


<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

Decided 2026-09-10 after reviewing the stack research. The research files recommend Laravel and an
offline sync layer; **both were superseded** — see "Rejected" below.

| Layer | Choice |
|---|---|
| Language | Python |
| Backend | Django + Django REST Framework |
| Database | PostgreSQL, **one database per client business** |
| Pooling | PgBouncer in transaction mode; Django `CONN_MAX_AGE = 0` |
| Tenancy | Hand-built: control-plane app, runtime connection registry, fail-closed `DATABASE_ROUTERS`, `migrate_all` command |
| Queue / scheduler | Celery + Celery Beat on Redis |
| PDF A4 | WeasyPrint (facture, bon de commande) |
| Web | React + Vite + TypeScript SPA |
| API types | `drf-spectacular` → OpenAPI → generated TypeScript client |
| Mobile | Expo (React Native) at Phase 11, against the same API and generated client |
| Auth | **Django session authentication** for the web SPA — not JWT. `TenantMiddleware` reads `request.user` at middleware time, but DRF authenticates inside `APIView.initial()`, *after* all middleware — so under JWT nothing binds and every business query raises `NoTenantBound`. Verified against the installed DRF. Sessions change zero lines of the Phase 2 tenancy layer. Mobile (Phase 11) is not blocked: `DEFAULT_AUTHENTICATION_CLASSES` is a list. |
| Money | `Decimal` / `DecimalField` — never float, never binary float |
| Errors | Sentry, every event tagged with client and magasin |
| Payments | Chari Pay primary, CMI fallback, behind one gateway interface |

**Pin exact versions at project start.** The research verified PostgreSQL 18.6 as current; Django and
the JS packages were never version-checked for this stack, so verify them rather than trusting a
number written here.

### The tenancy layer is yours to build (~2-3 weeks)

There is no Django equivalent of `stancl/tenancy`. What you build:

1. **Control plane** in the default database: `Client` with `db_name`, `db_host`, `db_port`, `db_user`,
   encrypted `db_password`, `status`, `schema_version`. `db_host` from day one.
2. **Connection registry** — build the alias config from
   `copy.deepcopy(settings.DATABASES["default"])`, which has already been through
   `configure_settings()` and carries every key `DatabaseWrapper` needs, then override NAME/HOST/etc.
   **`connections.ensure_defaults()` and `prepare_test_settings()` were removed in Django 4.1** — do
   not call them. `CONN_MAX_AGE = 0` so PgBouncer owns pooling. To evict an alias use
   `connections[alias].close()` then `del connections[alias]`; **never** `del
   connections.settings[alias]`, which orphans an open socket because `close_old_connections`
   iterates `settings`.
3. **Router** — `db_for_read`/`db_for_write` read the alias from a `contextvar` and **raise** when none
   is bound. Returning `None` falls through to `default`, which is a silent cross-client leak.
   `allow_migrate` keeps control-plane apps on `default` and business apps off it.
4. **Middleware** — resolve client, set the contextvar, and **clear it in a `finally`**. Worker threads
   are reused, so a missed reset means the next request reads the previous client's database. This is
   the single highest-risk line in the layer.
5. **Provisioning** — `CREATE DATABASE` cannot run inside a transaction block, so this is a status
   state machine with compensating cleanup, not one atomic transaction. The same function serves
   manual onboarding (TENANT-06) and later self-serve signup.
6. **`migrate_all` command** — loop active clients, `migrate --database=<alias>`, record
   `schema_version`, report who failed and who is behind (TENANT-02, TENANT-03).
7. **Celery** — never pass model instances; pass `client_id` plus primary keys and re-bind context in a
   prerun hook. A task with no context must fail closed.

Tests that must exist: router raises with no context; `allow_migrate` keeps the two schemas apart;
context does not leak between two requests on one worker thread; no tenant table is ever touched on
the `default` connection.

### Rejected, and why

| Rejected | Why |
|---|---|
| **Laravel 13 + `stancl/tenancy`** | The package genuinely saves ~3 weeks of security-critical tenancy work and was the research's recommendation. Outweighed by Django fluency on a 12-phase solo project, plus the admin, WeasyPrint and native `Decimal`. |
| **NestJS + Drizzle** | No tenancy package, no admin, no decimal type on a fiscal product. Its one-language advantage is recovered by generating a typed TS client from `drf-spectacular`. |
| **`django-tenants`** | Schema-per-client via `search_path`. Contradicts the database-per-client decision. **Do not reach for it** when the hand-built layer feels like work. |
| **Prisma** | One client instance per database URL spawns a query engine each; memory blows up across many clients. |
| **One universal Expo Router app (React Native Web)** | Chosen in the research largely to share an offline sync client, which no longer exists. RNW is weakest at dense tables, keyboard flows and print CSS — exactly the counter UI — and mobile is Phase 11, so it would cost ten phases of friction to serve a late requirement. |
| **Gotenberg / Puppeteer sidecar** | Unnecessary once WeasyPrint is available; deletes a container from the deployment. |
| **Offline sync of any kind** (purpose-built, PowerSync, ElectricSQL, CRDTs, RxDB) | Offline is out of scope permanently. |

### What survived from the research

- Facture numbers come from a **counter row locked `FOR UPDATE`** inside the inserting transaction
  (`select_for_update()` in `transaction.atomic()`) — **never a Postgres `SEQUENCE`**, which gaps on
  rollback. The stack research's mention of sequences for numbering is wrong and contradicted by the
  architecture and pitfalls research.
- PgBouncer is mandatory, not optional, with a database per client.
- Sale creation must be idempotent so a retried request cannot mint a second facture number.
- Verify PgBouncer transaction pooling against the driver's prepared statements early, in Compose.

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

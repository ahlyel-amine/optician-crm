<!-- GSD:project-start source:PROJECT.md -->
## Project

**Optician Management Platform**

A multi-tenant SaaS for Moroccan opticians. One platform where an optician business runs its whole day — clients and their ordonnances, stock, fournisseurs and achats, facturation, and a per-magasin caisse — on both web and mobile. Each client business gets its own database, may run one or several magasins, and appears under their own branding.

**Core Value:** The counter can complete a sale end to end — find or create the client, attach the ordonnance, take payment (including an acompte), and have it land in that magasin's caisse — producing a facture that is legally valid in Morocco every time.

### Constraints

- **Legal — invoicing**: Moroccan TVA and a gapless, chronological, duplicate-free facture series (art. 145 CGI). Gaps are treatable as fraud, and this is the client's tax exposure caused by our software.
- **Legal — health data**: ordonnances require CNDP prior authorization before processing, on a 2–4 month calendar
- **Legal — retention**: 10 years (art. 211 CGI), which constrains offboarding and the cost model
- **Locale**: MAD and French UI — drives formatting and vocabulary
- **Connectivity**: the application requires a connection. Sale submission must still be idempotent, since a retried request on a flaky link must never mint a second facture number.
- **Platforms**: web and mobile at full parity — one shared codebase and API rather than two products
- **Tenancy**: one shared application, one database per client — every request must resolve to the right client database, migrations must fan out across all of them, and a leak across clients is a security failure, not a bug
- **Payments**: Moroccan rails for subscriptions; recurring card-on-file is a vendor claim that must be proven in sandbox before the billing model depends on it
- **Timeline**: no hard deadline — build it right rather than fast
<!-- GSD:project-end -->

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
| Auth | DRF with short-lived JWT (`djangorestframework-simplejwt`) |
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
2. **Connection registry** — register a client's connection into `connections.databases` at runtime,
   then `connections.ensure_defaults(alias)`. `CONN_MAX_AGE = 0` so PgBouncer owns pooling.
3. **Router** — `db_for_read`/`db_for_write` read the alias from a `contextvar` and **raise** when none
   is bound. Returning `None` falls through to `default`, which is a silent cross-client leak.
   `allow_migrate` keeps control-plane apps on `default` and business apps off it.
4. **Middleware** — resolve client, set the contextvar, and **reset it in a `finally`**. Worker threads
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

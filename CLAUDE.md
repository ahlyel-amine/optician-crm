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

## TL;DR — The Prescription
| Layer | Choice |
|---|---|
| Backend | **Laravel 13** (PHP 8.4) + **stancl/tenancy v3.10** multi-database |
| DB | **PostgreSQL 18.6**, one database per client business, PgBouncer transaction pooling |
| Offline sync | **Purpose-built server-authoritative command sync over local SQLite.** No CRDT. No PowerSync/Electric (blocked by DB-per-tenant). |
| Local store | `expo-sqlite` (native) + `sqlocal`/`opfs-sahpool` (web), one **Drizzle** schema |
| Web + Mobile | **One Expo Router 57 universal app** (React Native Web), NativeWind 4 |
| PDF A4 | **Gotenberg 8.36** sidecar (legal facture, bon de commande) + `expo-print` (bon provisoire offline) |
| Paiement | **Chari Pay (ChariBaaS)** primary, **CMI** fallback, behind a `PasserelleDePaiement` interface. Not Cashier. |
| Hosting | EU region (Paris/Marseille), CNDP art. 43 declaration filed |
## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **PHP** | 8.4 | Backend language | Laravel 13 requires ≥8.3; 8.4 is the current supported line. Solo-dev velocity for CRUD-heavy business software is unmatched. |
| **Laravel** | 13.31.0 (2026-09-08) | Backend framework | Released 2026-03-17, zero breaking changes from 12. The only mainstream framework with a **battle-tested database-per-tenant package**, which is your hardest structural constraint. Queues, scheduler, policies, mail all included — a solo dev cannot afford to assemble these. |
| **stancl/tenancy** | v3.10.1 (2026-08-05) | Multi-database tenancy | Supports `illuminate/support ^13.0`. ~9.8M installs. Gives you: automatic tenant DB creation on signup, per-request connection switching (`DatabaseTenancyBootstrapper`), `tenants:migrate` fan-out across every client DB, and tenant-aware cache/queue/filesystem prefixes. This is *exactly* the two capabilities you listed as required, off the shelf. Building it yourself is 3–4 weeks and a security surface. |
| **PostgreSQL** | 18.6 (2026-08-13) | Database engine | Per-tenant DBs, real transactions, sequences for facture numbering, `unaccent`+`pg_trgm` for French name search, native `uuidv7()` (new in 18) for monotonic client-generated IDs. MySQL would work; Postgres wins on sequences, partial indexes, and `unaccent`. |
| **PgBouncer** | 1.24+ | Connection pooling | Mandatory, not optional, with DB-per-tenant. See "Tenancy: the connection math" below. |
| **Redis** | 7.4 / Valkey 8 | Queue + cache | Backing for Horizon. stancl/tenancy prefixes keys per tenant automatically. |
| **Laravel Horizon** | 5.49.0 | Queue supervision | Migration fan-out, sync batch processing, dunning jobs — all queued. You need the dashboard when a migration fails on tenant #47 of 300. |
| **Expo (SDK)** | 57.0.21 (2026-06-30) | Universal app runtime | RN 0.86, React 19.2. Web is a first-class target since Metro replaced Webpack; Expo Router runs the same file-based routes on web, iOS and Android. This is how you get parity without writing the app twice. |
| **Expo Router** | 57.0.20 | Routing (all 3 platforms) | File-based routes shared across web/native. Deep links and web URLs from one route tree. |
| **NativeWind** | 4.2.6 | Styling | Tailwind classes compiled to native styles at build time; works on RNW. Lower ceremony than Tamagui and a much smaller thing to learn/maintain solo. |
| **Drizzle ORM** | 0.45.2 | Local SQLite schema + queries | One TS schema definition compiled for both `expo-sqlite` (native) and `sqlocal` (web). `useLiveQuery` re-renders on table change — this is what makes the offline UI feel live. |
| **Gotenberg** | 8.36.0 (2026-08-14) | A4 PDF rendering | Chromium-in-a-container behind an HTTP API. Full CSS fidelity for the facture, French accents and per-tenant logo/colors for free. Keeps Chromium out of the PHP image. |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `spatie/laravel-permission` | 8.3.0 | Rôles + permissions (owner/vendeur) | Inside the **tenant** DB. **Do not enable `teams` mode** — teams exist for shared-DB tenancy; with DB-per-tenant, the permission tables are already tenant-scoped. Scope by `magasin_id` in your policies, not by teams. |
| `laravel/sanctum` | 4.x | API auth for web SPA + native | Issue **long-lived, per-device revocable tokens**. Critical: an access token must not expire mid-offline-shift. Do not use short-lived JWT + refresh — a device offline for 8 hours cannot refresh. Revocation happens server-side on next contact. |
| `spatie/laravel-pdf` | 2.13.1 | PDF wrapper | Optional convenience over Gotenberg/Browsershot. Plain HTTP to Gotenberg is also fine and has fewer moving parts. |
| `spatie/laravel-data` | 4.x | Typed DTOs for sync commands | Gives you one PHP class per command with validation, mirroring the Zod schema on the client. |
| `sqlocal` | 0.18.0 | SQLite in the browser | Wraps official `@sqlite.org/sqlite-wasm` with the **`opfs-sahpool` VFS** and ships a Drizzle adapter. **Requires no COOP/COEP headers** — this is the whole reason to pick it (see Pitfall #3). |
| `expo-sqlite` | 57.0.2 | SQLite on device | **Native only.** Stable and fast on iOS/Android/tablet. Its web target is documented as *alpha and may be unstable* — do not ship it. |
| `expo-print` | 57.0.1 | Offline document printing | `printToFileAsync({ html })` on native, `window.print()` on web. This is how a vendeur prints a **bon provisoire** with no internet. |
| `expo-updates` (EAS Update) | SDK 57 | OTA JS updates | A solo dev supporting shops across Morocco cannot ship a store binary for every bug fix. |
| `zod` | 4.6.0 | Command payload validation | Shared between UI and queue writer; mirrored server-side by `spatie/laravel-data`. |
| `@tanstack/react-query` | 5.102.8 | Online data fetching | For the *online-only* parts of the app (achats, fournisseurs, rapports). Do not route offline data through it — that goes through SQLite. |
| `react-native-mmkv` | 4.3.2 | Small key/value (cursors, session) | Sync high-water marks, last magasin, auth token. Fast, synchronous, works on web. |
| `i18next` + `expo-localization` | latest | i18n scaffolding | French-only in v1, but wire it now so Arabic later is translation work, not a rewrite. Format money with `Intl.NumberFormat('fr-MA', { style:'currency', currency:'MAD' })`. |
| `sentry` (`sentry/sentry-laravel`, `@sentry/react-native`) | latest | Error tracking | Non-negotiable when your users are shops you can't visit. Tag every event with `tenant_id` + `magasin_id`. |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| Docker Compose | Local Postgres + Redis + Gotenberg + PgBouncer | Match prod topology locally or the pooling bugs surface in production. |
| Laravel Pint + PHPStan (level 6+) | PHP static analysis | Catch tenant-context leaks (a query running against the central DB by accident). |
| Pest 3 | PHP tests | Write a test that asserts *no* tenant query ever hits the central connection. |
| Biome / ESLint + TypeScript 5.9 | TS lint/types | `strict: true`. Money types as branded `Centimes`. |
| Maestro | E2E on device | The one flow worth E2E-testing: airplane mode → sell → reconnect → verify facture number. |
| EAS Build | iOS/Android binaries | No Mac-in-CI headaches. |
## Installation
# --- Backend (api/) ---
# --- Universal app (app/) ---
# --- Services ---
## The Offline Layer — The Crux
### Verdict
### Why not a sync engine (PowerSync / ElectricSQL / Zero)
### Why not CRDTs (Automerge, Yjs, Ditto, Loro)
### What to build instead — concrete design
- Every syncable tenant table carries `sync_seq bigint` (from a per-tenant Postgres sequence, bumped on every write) and `deleted_at` (soft delete, so deletions propagate).
- Response returns changed rows + new high-water cursor. Client stores the cursor in MMKV.
- Syncable set: `clients`, `ordonnances`, `articles` (+ prix de vente, **never prix d'achat** — vendeurs must not see margins, and if it's not on the device it can't leak), `stock` for that magasin, `parametres`, branding.
- Deliberately dumb, cheap to debug, and works over any transport.
| Column | Meaning |
|---|---|
| `id` | UUIDv7, client-generated — time-ordered **and** the idempotency key |
| `type` | `CreerClient` \| `EnregistrerOrdonnance` \| `EnregistrerVente` \| `AjouterEntreeCaisse` \| `EncaisserSolde` |
| `payload` | JSON, validated by a shared Zod schema |
| `magasin_id`, `utilisateur_id` | context |
| `sequence_appareil` | per-device monotonic counter → preserves intra-device causal order |
| `horodatage_local` | when the vendeur actually did it |
| `etat` | `en_attente` \| `envoyé` \| `accepté` \| `rejeté` |
- Offline, the device produces a **bon/ticket provisoire** with a device-local reference (`MAG1-A3-000042`). It is *not* a facture and must not be labelled as one.
- On server acceptance, the legal number comes from `nextval()` on a **per-(magasin, exercice) Postgres sequence, inside the same transaction** that persists the vente. One writer, one sequence, no gaps.
- The device gets the real number back and can then render/print the true facture.
- Both references are stored, so a customer holding a provisional ticket is matchable.
- **Accepted consequence:** facture numbers follow *server acceptance order*, not sale order. Store `date_vente` and `date_emission` separately and print `date_emission`. **Have a Moroccan comptable sign off on this before v1 ships** — it is the one design decision where being wrong means reissuing a client's books.
- **Trap: do NOT pre-lease number blocks to devices.** ("Device A gets 1001–1050 to use offline.") Every unused number in an expired lease is a gap, and Article 145 gaps carry fraud risk. Leasing only works if you also implement recorded voids with an audit trail — much more work than server-side assignment, for a worse outcome.
### Honest cost
### The one thing that would change this answer
## Tenancy: The Connection Math and Migration Fan-Out
- **Expand/contract only.** Never a single destructive migration across N databases — a failure at tenant 47 leaves 253 on the old schema and 46 on the new.
- Store `schema_version` on the central `tenants` row; alert on drift; make `tenants:migrate --tenants=…` retryable.
- Central DB holds: `tenants`, `abonnements`, `paiements`, `factures_saas`, `cluster`. Everything else lives in the tenant DB.
## A4 PDF Generation
| Document | Where | How |
|---|---|---|
| **Facture A4** (legal, numbered) + **Bon de commande** | Server | HTML/Blade template → **Gotenberg 8.36** (Chromium) → PDF, archived to object storage |
| **Bon provisoire** (offline sale receipt) | Device | `expo-print.printToFileAsync({ html })` on native, `window.print()` on web |
## Moroccan Payment Gateway Integration
### Recommendation: Chari Pay (ChariBaaS) primary, CMI fallback, both behind one interface
| Gateway | Recurring / tokenization | Developer experience | Onboarding | Verdict |
|---|---|---|---|---|
| **Chari Pay (ChariBaaS)** | **Yes** — card-on-file tokenization, automated recurring collection, configurable retry, webhooks | Modern REST API, Swagger docs, **sandbox** | ~1–3 days, no setup fee | **Primary.** Also supports DamaneCash, ChaabiCash, Maroc Pay for non-carded customers. |
| **CMI** | **No recurring** | Legacy proprietary protocol, limited docs, **no sandbox** | 2–6 weeks, 500–2000 MAD setup | **Fallback + trust play.** The CMI logo reassures Moroccan buyers and it accepts every Moroccan bank card. |
| **Payzone** | Yes | Proprietary protocol, docs released post-contract | 2–3 weeks | Skip at your volume — built for high-volume enterprise merchants. |
| **AmanPay** | No | Simple kit, non-developer oriented | 3–5 days | Skip — no recurring means no subscription product. |
| **Stripe / Paddle** | Yes | Excellent | — | **Skip — locally issued Moroccan cards are poorly served.** PROJECT.md already decided this correctly. |
### Build your own subscription engine — do not use Laravel Cashier
- Central-DB `abonnements` table: `statut` ∈ `essai | actif | impayé | suspendu | résilié`, `periode_fin`, `token_carte` (gateway token — **never the PAN**), `tentatives`.
- A daily scheduled command charging subscriptions where `periode_fin <= today`.
- Dunning: 3 retries over ~7 days, French email at each step.
- Suspension = tenant becomes **read-only**. Never delete or detach a client's database on non-payment; opticians have legal retention obligations on their factures and you are holding their books.
- Webhook endpoint with signature verification + idempotency on the gateway event ID.
## Hosting & Data Residency
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Laravel 13 + stancl/tenancy | **NestJS/Hono + Drizzle (full-TypeScript)** | If sharing TVA/total/rounding logic verbatim between server and offline device matters more to you than tenancy plumbing. Genuine advantage — but you build DB-per-tenant routing, migration fan-out, tenant-aware queues and cache yourself. Choose it only if you're markedly stronger in TS than PHP. |
| One universal Expo app | **Separate React+Vite+shadcn web + Expo mobile, sharing `packages/noyau`** | If desktop back-office density (achats, stock tables, rapports) proves painful in React Native Web. You'd still share the domain model, API client, local DB and sync engine — only the UI splits. Cost: ~1.6× UI work and constant parity drift, which is exactly what PROJECT.md's parity requirement is guarding against. |
| DB-per-tenant | **Schema-per-tenant in one Postgres** | If you later decide PowerSync is worth it. Unlocks wildcard schemas (v1.24.0+) and deletes most of your sync code. Costs you easy per-client backup/restore and makes one bad `search_path` a cross-tenant leak. |
| Gotenberg | **spatie/browsershot** | Low volume, want one fewer container. Same Chromium fidelity, Node + Chromium in your app image. |
| Chari Pay | **CMI direct** | If Chari Pay's sandbox doesn't deliver on recurring, or if buyers demand the CMI logo. Product cost: renewal becomes a manual redirect payment each period, not an automatic charge. |
| Custom command sync | **RxDB 16.x** | If you'd rather buy the replication protocol. It's genuinely backend-agnostic (pull/push handlers over your own HTTP), works on RN and web, and would work with DB-per-tenant — unlike PowerSync/Electric. But the fast storages (OPFS, native SQLite, Expo filesystem) are **commercially licensed premium plugins**, and it still won't solve server-assigned facture numbering. Reasonable if the queue mechanics scare you more than the license cost. |
| NativeWind | **Tamagui** | Large design system, heavy animation, very large component trees. Its compiler is faster at runtime; the learning and maintenance cost is much higher for one developer. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **CRDTs (Automerge, Yjs, Loro, Ditto)** for stock/caisse/facture | Automatic convergence is the *bug* here — converges stock to a value no transaction justifies, and cannot express server-assigned numbering or "reject this" | Server-authoritative command queue |
| **PowerSync / ElectricSQL** *with DB-per-tenant* | PowerSync docs: one instance **does not** support multiple separate Postgres databases ("planned"). Electric needs one replication slot per DB. One instance per optician = ops/cost trap | Custom command sync — or switch to schema-per-tenant first |
| **WatermelonDB** | Last commit August 2025; issues and PRs going unanswered. Its docs already tell you the sync server is entirely yours to build | `expo-sqlite` + `sqlocal` + your own queue |
| **`expo-sqlite` on web** | Documented as **alpha, may be unstable**, and requires `COOP: same-origin` + `COEP: credentialless` for SharedArrayBuffer | `sqlocal` with `opfs-sahpool` — no COOP/COEP needed |
| **Prisma** for DB-per-tenant | One client instance per database URL, pool explosion across N tenants, `migrate deploy` is CLI-only (shell-out to fan out) | Eloquent (Laravel) or Drizzle (TS) |
| **`wkhtmltopdf`** | Archived Jan 2023, last release 2020, unpatched CVSS 9.8 SSRF | Gotenberg |
| **dompdf / mPDF** | CSS too weak for a branded multi-page A4 invoice | Gotenberg |
| **Laravel Cashier** | Stripe/Paddle/Lemon Squeezy only; not adaptable to a Moroccan gateway | Your own `abonnements` state machine |
| **Stripe / Paddle** | Poor acceptance of locally issued Moroccan cards | Chari Pay / CMI |
| **Firebase / Firestore** offline | No relational queries or transactions across the shapes accounting needs; data leaves the EU (CNDP problem); costs scale with reads | Postgres + local SQLite |
| **MongoDB Realm / Atlas Device Sync** | Deprecated — MongoDB sunset Device Sync; Realm is a dead end | — |
| **Floats for money** | Rounding drift in TVA and acompte balances, in a legal document | `integer` centimes everywhere, in Postgres *and* SQLite |
| **`teams` mode in spatie/laravel-permission** | Built for shared-DB tenancy; redundant when the permission tables already live in a per-client DB, and adds a `team_id` you must thread everywhere | Plain mode inside the tenant DB; scope by `magasin_id` in policies |
| **Meilisearch / Algolia** in v1 | Another per-tenant index to provision, migrate and pay for | Postgres `unaccent` + `pg_trgm` — handles "Ben Ali"/"benali"/"BENALI" fine at optician scale |
| **Trusting a tenant header** | Cross-client data leak — a security failure, not a bug | Resolve tenant from the auth token claim; verify the header against it |
## Stack Patterns by Variant
- Adopt **PowerSync** with wildcard schemas (`tenant_%`, v1.24.0+, Postgres-only) + JWT schema claim
- Because it deletes most of the custom sync layer — the largest cost line in the project — in exchange for weaker per-client isolation and harder per-client backup/restore
- Split only the UI: keep `packages/noyau` (domain model, API client, Drizzle schema, sync engine) shared, add a React + Vite + shadcn web app
- Because the expensive, correctness-critical code stays single-sourced; only pixels diverge
- Fall back to CMI + email-driven manual renewal, keeping the `PasserelleDePaiement` interface
- Because a worse renewal UX beats no Moroccan card acceptance, and the interface makes it a driver swap
- Shard by `tenants.cluster`, add a second Postgres cluster + PgBouncer pair
- Because the ceiling is PgBouncer's per-(user, database) pools and Postgres `max_connections`, not disk
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `laravel/framework` v13.31 | PHP ≥ 8.3 | Laravel 13 released 2026-03-17; bug fixes to Q3 2027, security to Q1 2028. Zero breaking changes from 12. |
| `stancl/tenancy` v3.10.1 | `illuminate/support ^10\|^11\|^12\|^13`, PHP ^8.0 | Verified on Packagist 2026-08-05. Laravel 13 supported. |
| `spatie/laravel-permission` 8.3.0 | Laravel 13 | Install **before** first tenant migration — retrofitting the tables across N live tenant DBs is painful. |
| Expo SDK 57 | React Native 0.86, React 19.2 | Released 2026-06-30; intentionally zero breaking changes from 56. |
| `expo-sqlite` 57 | Native stable; **web alpha** | Web needs COOP/COEP + Metro WASM config. Don't ship the web target. |
| `sqlocal` 0.18 | Modern Chrome/Safari 16.4+/Firefox 111+ | `opfs-sahpool` needs **no** COOP/COEP. Single connection, exclusive DB lock — one tab writes. Safari Incognito has no OPFS: detect and degrade to online-only with a clear French banner. |
| `drizzle-orm` 0.45.2 | `expo-sqlite` + `sqlocal` | One schema, two drivers. `useLiveQuery` is native-driver only — on web, invalidate manually after writes. |
| PostgreSQL 18.6 | PgBouncer 1.24+ | Postgres 19 was in beta mid-2026 — stay on 18 (18.6 released 2026-08-13). Native `uuidv7()` is new in 18. |
| Gotenberg 8.36 | Any HTTP client | 8.30.0+ ships a rationalized Noto font stack (Latin/Greek/Cyrillic/CJK + color emoji). |
## Open Questions / Flags for Later Research
## Sources
- Packagist API — `laravel/framework` v13.31.0 (2026-09-08), `stancl/tenancy` v3.10.1 (2026-08-05, requires `illuminate/support ^13.0`), `spatie/laravel-permission` 8.3.0, `spatie/laravel-pdf` 2.13.1, `laravel/horizon` v5.49.0
- npm registry — `expo` 57.0.21, `expo-router` 57.0.20, `expo-sqlite` 57.0.2, `drizzle-orm` 0.45.2, `nativewind` 4.2.6, `sqlocal` 0.18.0, `zod` 4.6.0, `expo-print` 57.0.1, `@tanstack/react-query` 5.102.8
- https://docs.powersync.com/sync/advanced/schemas-and-connections — **verified**: one instance does not support multiple separate Postgres databases ("planned"); wildcard schemas v1.24.0+, Postgres-only
- https://docs.expo.dev/versions/latest/sdk/sqlite/ — SDK 57; web support **alpha**; requires COOP/COEP for SharedArrayBuffer
- https://sqlite.org/wasm/doc/trunk/persistence.md — `opfs-sahpool` requires no cross-origin isolation headers
- https://powersync.com/blog/sqlite-persistence-on-the-web — May 2026 VFS landscape, browser support matrix, Safari Incognito/OPFS caveat
- https://www.postgresql.org/about/news/postgresql-18-released-3142/ — PG 18 (2025-09-25); 18.6 current (2026-08-13); `uuidv7()`
- https://github.com/gotenberg/gotenberg/releases — 8.36.0 (2026-08-14)
- https://www.cndp.ma/loi-09-08/ + https://www.cndp.ma/wp-content/uploads/2023/12/CNDP-Transfert-Etranger.pdf — Law 09-08 Art. 43, transfer formalities, adequacy list
- https://www.fiscamaroc.com/dispositions-communes-208/article-145-tenue-de-la-comptabilite-214.htm + https://fatouraplus.com/en/guide-auto-entrepreneur/mentions-obligatoires-facture-maroc-art-145/ — Art. 145: continuous chronological series, no gaps, each number used once; ICE vendeur + client mandatory
- https://www.upsilon-consulting.com/facturation-electronique-maroc-2026/ + https://hisab.ma/fr/docs/mandate-2026 + https://neoexpertise.net/e-invoicing-in-morocco/ — e-invoicing clearance model, UBL 2.1/CII, phased timeline (**sources disagree on TPE date: 2027 vs 2028**)
- https://laravel-news.com/laravel-13 — Laravel 13 released 2026-03-17, PHP 8.3 min
- https://expo.dev/changelog/sdk-57 — SDK 57, RN 0.86, 2026-06-30
- https://rxdb.info/replication.html + https://github.com/pubkey/rxdb — backend-agnostic pull/push replication; premium storage plugins
- https://procedure.tech/blogs/react-native-offline-first/ + https://rxdb.info/articles/alternatives/watermelondb-alternative.html — WatermelonDB last commit Aug 2025, maintenance decline
- https://pdf4.dev/blog/wkhtmltopdf-alternatives-2026 — wkhtmltopdf archived Jan 2023, unpatched CVSS 9.8 SSRF
- https://planetscale.com/blog/scaling-postgres-connections-with-pgbouncer — pools are per (user, database); `default_pool_size` semantics
- https://www.baas.ma/en/saas-subscription-payment-morocco + https://www.baas.ma/fr/blog/comparatif-passerelle-paiement-maroc — Chari Pay recurring/tokenization/sandbox claims, gateway comparison table (published by Chari, i.e. an interested party)
- https://digitoyou.com/blog/paiement-en-ligne-maroc-cmi-stripe-2026/ — CMI onboarding times and DX complaints
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
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

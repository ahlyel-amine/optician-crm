> **⚠️ SUPERSEDED — the stack below was NOT adopted.**
>
> Decided 2026-09-10. **Django + Django REST Framework (Python)**, PostgreSQL with one database per
> client, PgBouncer, Celery + Celery Beat on Redis, **WeasyPrint** for A4 PDF, a **React + Vite +
> TypeScript SPA** for web with a typed client generated from `drf-spectacular`, and **Expo mobile at
> Phase 11** against the same API. Chari Pay primary with CMI fallback still stands.
>
> Not adopted: Laravel, `stancl/tenancy`, the universal Expo Router / React Native Web app, Gotenberg,
> Drizzle, `expo-sqlite`, `sqlocal`, and **every offline-sync recommendation** — offline is out of scope
> permanently. `django-tenants` is also rejected: it is schema-per-client and contradicts the
> database-per-client decision. The tenancy layer is hand-built on Django's router (~2-3 weeks).
>
> One correction that matters: this file suggests Postgres **sequences** for facture numbering. That is
> wrong and contradicted by ARCHITECTURE.md and PITFALLS.md — a `SEQUENCE` gaps on rollback, which
> art. 145 forbids. Use a counter row locked `FOR UPDATE` inside the inserting transaction.
>
> Kept for its reasoning, its comparisons and its sources. `.planning/PROJECT.md` and `CLAUDE.md` are
> authoritative.

# Stack Research

**Domain:** Multi-tenant SaaS de gestion pour opticiens (Maroc) — POS/caisse offline-capable, web + mobile à parité
**Researched:** 2026-09-09
**Confidence:** MEDIUM-HIGH (versions HIGH, offline-sync design HIGH, passerelle de paiement MEDIUM, fiscalité MEDIUM-LOW)

---

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

The single biggest cost in this project is the sync layer. Everything else is a solved problem.

---

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

---

## Installation

```bash
# --- Backend (api/) ---
composer create-project laravel/laravel api "^13.0"
composer require stancl/tenancy:^3.10 \
                 spatie/laravel-permission:^8.3 \
                 spatie/laravel-data:^4.0 \
                 laravel/sanctum:^4.0 \
                 laravel/horizon:^5.49 \
                 sentry/sentry-laravel
composer require --dev pestphp/pest laravel/pint phpstan/phpstan larastan/larastan

php artisan tenancy:install     # publishes config + tenant migrations dir
php artisan vendor:publish --provider="Spatie\Permission\PermissionServiceProvider"

# --- Universal app (app/) ---
npx create-expo-app@latest app --template default   # SDK 57
cd app
npx expo install expo-router expo-sqlite expo-print expo-localization expo-updates
npm install drizzle-orm sqlocal zod @tanstack/react-query react-native-mmkv \
            nativewind@^4.2 i18next react-i18next @sentry/react-native
npm install -D drizzle-kit tailwindcss@^3.4 typescript

# --- Services ---
docker run -d -p 3000:3000 gotenberg/gotenberg:8.36 gotenberg --api-timeout=60s
```

---

## The Offline Layer — The Crux

### Verdict

**Build a purpose-built, server-authoritative command sync over local SQLite. Do not adopt a general-purpose sync engine. Do not use CRDTs.**

This is the opposite of the fashionable 2026 answer, and it is correct here for three independent reasons.

### Why not a sync engine (PowerSync / ElectricSQL / Zero)

**1. Your tenancy model blocks them — this is a hard, verified blocker.**
PowerSync's own docs state plainly that one PowerSync Service instance **does not support multiple separate Postgres databases**; that capability is listed as *"planned… will be available in a future release."* What it *does* support (v1.24.0+, Postgres-only) is **wildcard schemas** — `tenant_%` matching many *schemas inside one database*, designed for schema-per-tenant. ElectricSQL has the same shape of constraint: it syncs from a Postgres via logical replication, so N client databases means N replication slots and N Electric instances.

Running one sync-service instance per optician is an ops and cost trap for a solo developer. Betting the architecture on an unshipped feature is worse.

**2. They sync rows; your problem is sequences and aggregates.**
Facture numbering, the caisse balance, and stock quantity are all *server-authoritative*. Article 145 CGI requires a **continuous, chronological, gap-free series where each number is used exactly once, with gaps treatable as fraud**. Two devices offline cannot both mint "the next number." No row-level sync engine models "this field is assigned by the server on acceptance" — you would write that logic yourself anyway, but now on top of a replication pipeline you don't control and can't easily debug when a shop calls at 6pm.

**3. Your offline surface is narrow.**
Read PROJECT.md again: offline means *find/create client, attach ordonnance, take payment incl. acompte, land it in the magasin's caisse*. Achats, fournisseurs, compte fournisseur, rapports and réappro are all online-only work done in the back office. You need to sync maybe 6 tables and 5 commands — not the schema. A sync engine's value is proportional to how much you sync; here it's low and the integration cost is high.

### Why not CRDTs (Automerge, Yjs, Ditto, Loro)

CRDTs converge automatically. For inventory and money, **automatic convergence is the bug, not the feature.** A CRDT counter will happily converge stock to a number no transaction ever justified, and it has no vocabulary for "reject this: the frame was already sold" or "the server assigns this number." CRDTs are right for collaborative documents and presence. They are wrong for an accounting ledger. Ditto is genuinely used in POS, but it's a commercial CRDT mesh at enterprise pricing and would still leave you writing the numbering authority.

### What to build instead — concrete design

**Local store (one Drizzle schema, two drivers):**

```ts
// packages/local-db/schema.ts  — shared, one definition
// native: drizzle(openDatabaseSync('optique.db'))          via expo-sqlite
// web:    drizzle(new SQLocalDrizzle('optique.db').driver)  via sqlocal (opfs-sahpool)
```

**Path A — Read cache (pull).** Server exposes `GET /sync/pull?magasin={id}&depuis={curseur}`.
- Every syncable tenant table carries `sync_seq bigint` (from a per-tenant Postgres sequence, bumped on every write) and `deleted_at` (soft delete, so deletions propagate).
- Response returns changed rows + new high-water cursor. Client stores the cursor in MMKV.
- Syncable set: `clients`, `ordonnances`, `articles` (+ prix de vente, **never prix d'achat** — vendeurs must not see margins, and if it's not on the device it can't leak), `stock` for that magasin, `parametres`, branding.
- Deliberately dumb, cheap to debug, and works over any transport.

**Path B — Write queue (push) — commands, not row diffs.** Local append-only table:

| Column | Meaning |
|---|---|
| `id` | UUIDv7, client-generated — time-ordered **and** the idempotency key |
| `type` | `CreerClient` \| `EnregistrerOrdonnance` \| `EnregistrerVente` \| `AjouterEntreeCaisse` \| `EncaisserSolde` |
| `payload` | JSON, validated by a shared Zod schema |
| `magasin_id`, `utilisateur_id` | context |
| `sequence_appareil` | per-device monotonic counter → preserves intra-device causal order |
| `horodatage_local` | when the vendeur actually did it |
| `etat` | `en_attente` \| `envoyé` \| `accepté` \| `rejeté` |

`POST /sync/push` takes a batch, applies commands in `sequence_appareil` order, one DB transaction per command, and returns a per-command result. A `UNIQUE` index on `id` server-side makes replay free — a device that loses the response and retries produces no duplicate. **The client never deletes a command until it is acked.**

**Facture numbering — the legally load-bearing part.**
- Offline, the device produces a **bon/ticket provisoire** with a device-local reference (`MAG1-A3-000042`). It is *not* a facture and must not be labelled as one.
- On server acceptance, the legal number comes from `nextval()` on a **per-(magasin, exercice) Postgres sequence, inside the same transaction** that persists the vente. One writer, one sequence, no gaps.
- The device gets the real number back and can then render/print the true facture.
- Both references are stored, so a customer holding a provisional ticket is matchable.
- **Accepted consequence:** facture numbers follow *server acceptance order*, not sale order. Store `date_vente` and `date_emission` separately and print `date_emission`. **Have a Moroccan comptable sign off on this before v1 ships** — it is the one design decision where being wrong means reissuing a client's books.
- **Trap: do NOT pre-lease number blocks to devices.** ("Device A gets 1001–1050 to use offline.") Every unused number in an expired lease is a gap, and Article 145 gaps carry fraud risk. Leasing only works if you also implement recorded voids with an audit trail — much more work than server-side assignment, for a worse outcome.

**Stock.** The device holds a *cached, indicative* quantity — label it `stock indicatif (hors ligne)` in the UI. The `EnregistrerVente` command carries `article_id + quantité`; the server decrements. **If it goes negative, accept the sale anyway** and raise an `écart de stock` for the owner. The customer already walked out with the frame; rejecting a completed sale is strictly worse than an inventory discrepancy the owner can reconcile.

**Caisse.** It's an append-only ledger — the one aggregate that is genuinely conflict-free. Two devices appending entries just both append. **Balance is always `SUM(entrées) - SUM(sorties)`, computed, never a stored mutable number.** PROJECT.md already decided the caisse is a running ledger with no Z-close; that decision is what makes offline caisse tractable. Keep it.

**Rejection UI.** A `Synchronisation` screen listing queued count, last successful sync, and any `rejeté` commands with a French reason and a resolution action. Design the server to accept-and-flag rather than reject wherever possible, so this screen is nearly always empty — but it must exist, or a rejected sale vanishes silently.

### Honest cost

**4–8 weeks of solo-dev time for a correct v1**: pull cursor + push queue + reconnect/backoff + rejection UI + the airplane-mode E2E test. Then an ongoing tax: **every new syncable entity forces two decisions** (does it pull? which commands write it?). Budget it as its own roadmap phase, sequenced *before* any feature that depends on it, and prototype the sell-offline-reconnect loop end to end before building any other screen. If that loop isn't solid, nothing built on it is.

### The one thing that would change this answer

If you ever relax "one database per client" to **"one Postgres schema per client"** (same isolation from the app's point of view, one physical DB), PowerSync's wildcard schemas make it a genuine, supported option and you could delete most of the above. That is a business/trust decision about isolation, not a technical one — so it's yours to make, not mine. Flagging it because the cost difference is measured in weeks. Note the trade-off honestly: schema-per-tenant makes per-client backup/restore and "delete this client's data" meaningfully harder, and one bad `search_path` is a cross-tenant leak.

---

## Tenancy: The Connection Math and Migration Fan-Out

**Identification.** Do **not** identify tenants by subdomain alone — a native app has no subdomain. Use `InitializeTenancyByRequestData` with a header, but **resolve the tenant from the authenticated token's claim and verify the header against it server-side.** A tenant header trusted on its own is a cross-client data leak, which PROJECT.md correctly calls a security failure rather than a bug. Add a global test that asserts every tenant route is behind that middleware.

**Migrations.** `php artisan tenants:migrate`, queued through Horizon, run as a deploy step. Non-negotiable practices:
- **Expand/contract only.** Never a single destructive migration across N databases — a failure at tenant 47 leaves 253 on the old schema and 46 on the new.
- Store `schema_version` on the central `tenants` row; alert on drift; make `tenants:migrate --tenants=…` retryable.
- Central DB holds: `tenants`, `abonnements`, `paiements`, `factures_saas`, `cluster`. Everything else lives in the tenant DB.

**Pooling — the real ceiling.** PgBouncer pools are per **(user, database)** pair, so N tenant databases means N pools. Configure `default_pool_size = 3`, `min_pool_size = 0`, `server_idle_timeout ≈ 60s` so idle opticians (most of them, most of the time) hold zero server connections. Without this, 300 tenants × a default pool size will exhaust `max_connections` long before you have real load. Practical ceiling is low thousands of tenant DBs per cluster — so **add a `cluster` column to `tenants` from day one** and you can shard later without a migration.

⚠️ PgBouncer transaction mode + PDO prepared statements is a known friction point. Either set `PDO::ATTR_EMULATE_PREPARES => true` in the connection options, or run `pool_mode = session` for the tenant pool and accept lower multiplexing. Verify this in your Docker Compose before you ship, not after. *(MEDIUM confidence — verify empirically.)*

---

## A4 PDF Generation

**Two documents, two renderers, on purpose.**

| Document | Where | How |
|---|---|---|
| **Facture A4** (legal, numbered) + **Bon de commande** | Server | HTML/Blade template → **Gotenberg 8.36** (Chromium) → PDF, archived to object storage |
| **Bon provisoire** (offline sale receipt) | Device | `expo-print.printToFileAsync({ html })` on native, `window.print()` on web |

The legal facture can only be rendered server-side, because the number only exists server-side. This falls out of the numbering design rather than being an extra constraint — and it's a feature: only one code path can ever produce a document labelled *Facture*.

Template essentials: `@page { size: A4; margin: 15mm }`, CSS Paged Media for multi-page line-item tables with repeated headers, embedded Noto/DejaVu for French diacritics, per-tenant logo and color injected as CSS variables. Mandatory mentions per Article 145: ICE **du vendeur et du client**, IF, numéro de patente/taxe professionnelle, montant HT, base TVA, taux, montant TVA, TTC.

**Why Gotenberg over `spatie/browsershot`:** keeps Chromium and Node out of the PHP image, gives one place to pin fonts (8.30.0+ ships a rationalized Noto stack covering Latin/Greek/Cyrillic/CJK), and scales horizontally as its own container. Browsershot is fine at low volume and is a reasonable simplification if you want one less container.

**Do not use `wkhtmltopdf`** — archived January 2023, last release 2020, carries an unpatched CVSS 9.8 SSRF. **Do not use dompdf/mPDF** — CSS support too weak for a tenant-branded invoice with a multi-page table; you will spend more time fighting layout than you saved on the container.

⚠️ **Make the TVA rate a per-article field, not a global constant.** I could not confirm the applicable Moroccan rate for verres correcteurs / dispositifs d'optique médicale (LOW confidence — sources returned French, not Moroccan, rules). Modelling it per-article supports 0/7/10/20% lines on one facture and costs nothing now; hardcoding 20% is a schema migration across every client DB when you find out otherwise. Confirm with a Moroccan expert-comptable.

---

## Moroccan Payment Gateway Integration

### Recommendation: Chari Pay (ChariBaaS) primary, CMI fallback, both behind one interface

| Gateway | Recurring / tokenization | Developer experience | Onboarding | Verdict |
|---|---|---|---|---|
| **Chari Pay (ChariBaaS)** | **Yes** — card-on-file tokenization, automated recurring collection, configurable retry, webhooks | Modern REST API, Swagger docs, **sandbox** | ~1–3 days, no setup fee | **Primary.** Also supports DamaneCash, ChaabiCash, Maroc Pay for non-carded customers. |
| **CMI** | **No recurring** | Legacy proprietary protocol, limited docs, **no sandbox** | 2–6 weeks, 500–2000 MAD setup | **Fallback + trust play.** The CMI logo reassures Moroccan buyers and it accepts every Moroccan bank card. |
| **Payzone** | Yes | Proprietary protocol, docs released post-contract | 2–3 weeks | Skip at your volume — built for high-volume enterprise merchants. |
| **AmanPay** | No | Simple kit, non-developer oriented | 3–5 days | Skip — no recurring means no subscription product. |
| **Stripe / Paddle** | Yes | Excellent | — | **Skip — locally issued Moroccan cards are poorly served.** PROJECT.md already decided this correctly. |

⚠️ **MEDIUM confidence on Chari Pay.** The capability claims come substantially from the vendor's own marketing pages. **Open a sandbox account and prove the tokenized recurring charge + webhook flow before you build the billing phase on it.** That verification is cheap and it de-risks a load-bearing dependency.

### Build your own subscription engine — do not use Laravel Cashier

Cashier only speaks Stripe/Paddle/Lemon Squeezy. It is not adaptable to a Moroccan gateway; wrapping it costs more than replacing it. What you actually need is small:

- Central-DB `abonnements` table: `statut` ∈ `essai | actif | impayé | suspendu | résilié`, `periode_fin`, `token_carte` (gateway token — **never the PAN**), `tentatives`.
- A daily scheduled command charging subscriptions where `periode_fin <= today`.
- Dunning: 3 retries over ~7 days, French email at each step.
- Suspension = tenant becomes **read-only**. Never delete or detach a client's database on non-payment; opticians have legal retention obligations on their factures and you are holding their books.
- Webhook endpoint with signature verification + idempotency on the gateway event ID.

Put both drivers behind a `PasserelleDePaiement` interface (`initierPaiement`, `debiterToken`, `verifierWebhook`) from day one. Gateway switching in Morocco is likely enough within three years that the abstraction pays for itself.

---

## Hosting & Data Residency

Host in an **EU region — Paris or Marseille** (Scaleway, OVH, Hetzner). Marseille has the best latency to Morocco of the major EU regions. **Do not use a US region.**

⚠️ Moroccan **Law 09-08 (CNDP)**: Article 43 permits transfer abroad only to states offering sufficient protection. The CNDP's published list includes **France, Spain, Germany, Belgium, the Netherlands, Portugal, Italy** — but *preliminary formalities must be respected* (a transfer declaration/authorization). Penalties for unauthorized transfer run to 3 months–1 year imprisonment and 20,000–200,000 MAD. **File the CNDP transfer declaration before onboarding your first paying client**, and consult a Moroccan lawyer — you are a data controller for optician clients' patients' health-adjacent prescription data, which is the sensitive end of the spectrum. *(MEDIUM confidence — legal, verify with counsel.)*

Object storage (logos, archived facture PDFs) on an S3-compatible EU endpoint (Scaleway Object Storage), same region.

---

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

---

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

---

## Stack Patterns by Variant

**If you relax "one database per client" to "one schema per client":**
- Adopt **PowerSync** with wildcard schemas (`tenant_%`, v1.24.0+, Postgres-only) + JWT schema claim
- Because it deletes most of the custom sync layer — the largest cost line in the project — in exchange for weaker per-client isolation and harder per-client backup/restore

**If React Native Web proves too weak for the back office:**
- Split only the UI: keep `packages/noyau` (domain model, API client, Drizzle schema, sync engine) shared, add a React + Vite + shadcn web app
- Because the expensive, correctness-critical code stays single-sourced; only pixels diverge

**If Chari Pay's sandbox doesn't deliver recurring:**
- Fall back to CMI + email-driven manual renewal, keeping the `PasserelleDePaiement` interface
- Because a worse renewal UX beats no Moroccan card acceptance, and the interface makes it a driver swap

**If you exceed ~1,000 tenant databases on one cluster:**
- Shard by `tenants.cluster`, add a second Postgres cluster + PgBouncer pair
- Because the ceiling is PgBouncer's per-(user, database) pools and Postgres `max_connections`, not disk

---

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

⚠️ **Cross-language duplication risk.** With a PHP server and TS clients, TVA and total calculations exist twice. Mitigate concretely: keep a single `calculs.cases.json` fixture in the repo (inputs → expected HT/TVA/TTC/arrondi, including acompte and multi-rate cases) and run it as a test suite in **both** Pest and Vitest. A divergence then fails CI instead of printing a facture that disagrees with the customer's ticket.

---

## Open Questions / Flags for Later Research

1. **⚠️ Moroccan e-invoicing mandate (HIGH impact, MEDIUM confidence).** Morocco is rolling out mandatory e-invoicing under Article 145 CGI, reinforced by the Loi de Finances 2026 — a **clearance model** where the DGI must pre-validate each invoice, in **UBL 2.1 or UN/CEFACT CII** XML, with vendor and buyer ICE validated. Timeline: large enterprises Jan 2026, then progressive extension to SMEs/TPE in **2027–2028** (sources disagree on exact dates — one says Jan 2027 for PME/TPE, another says 2027–2028). Your customers are TPE, so this lands mid-product-life, and a clearance model is in direct tension with offline invoicing. **Do not build it into v1**, but: keep the facture entity clean enough to serialize to UBL 2.1, capture buyer ICE as a first-class field now, and revisit this before mid-2027. Non-compliant invoices carry 500 MAD each, capped at 50,000 MAD/year.
2. **TVA rate for optical goods (LOW confidence).** Unresolved — model per-article and confirm with an expert-comptable.
3. **Facture numbering vs. chronology (needs professional sign-off).** Server-assignment-on-sync means number order ≠ sale-date order. Confirm acceptability with a Moroccan comptable before v1 ships.
4. **Chari Pay recurring (MEDIUM confidence).** Vendor-marketing sourced. Prove in sandbox before the billing phase.
5. **PgBouncer transaction mode + Laravel PDO prepared statements.** Verify empirically in Docker Compose before production.

---

## Sources

**HIGH confidence (official docs / registries, fetched 2026-09-09):**
- Packagist API — `laravel/framework` v13.31.0 (2026-09-08), `stancl/tenancy` v3.10.1 (2026-08-05, requires `illuminate/support ^13.0`), `spatie/laravel-permission` 8.3.0, `spatie/laravel-pdf` 2.13.1, `laravel/horizon` v5.49.0
- npm registry — `expo` 57.0.21, `expo-router` 57.0.20, `expo-sqlite` 57.0.2, `drizzle-orm` 0.45.2, `nativewind` 4.2.6, `sqlocal` 0.18.0, `zod` 4.6.0, `expo-print` 57.0.1, `@tanstack/react-query` 5.102.8
- https://docs.powersync.com/sync/advanced/schemas-and-connections — **verified**: one instance does not support multiple separate Postgres databases ("planned"); wildcard schemas v1.24.0+, Postgres-only
- https://docs.expo.dev/versions/latest/sdk/sqlite/ — SDK 57; web support **alpha**; requires COOP/COEP for SharedArrayBuffer
- https://sqlite.org/wasm/doc/trunk/persistence.md — `opfs-sahpool` requires no cross-origin isolation headers
- https://powersync.com/blog/sqlite-persistence-on-the-web — May 2026 VFS landscape, browser support matrix, Safari Incognito/OPFS caveat
- https://www.postgresql.org/about/news/postgresql-18-released-3142/ — PG 18 (2025-09-25); 18.6 current (2026-08-13); `uuidv7()`
- https://github.com/gotenberg/gotenberg/releases — 8.36.0 (2026-08-14)
- https://www.cndp.ma/loi-09-08/ + https://www.cndp.ma/wp-content/uploads/2023/12/CNDP-Transfert-Etranger.pdf — Law 09-08 Art. 43, transfer formalities, adequacy list

**MEDIUM confidence (multiple independent sources agreeing):**
- https://www.fiscamaroc.com/dispositions-communes-208/article-145-tenue-de-la-comptabilite-214.htm + https://fatouraplus.com/en/guide-auto-entrepreneur/mentions-obligatoires-facture-maroc-art-145/ — Art. 145: continuous chronological series, no gaps, each number used once; ICE vendeur + client mandatory
- https://www.upsilon-consulting.com/facturation-electronique-maroc-2026/ + https://hisab.ma/fr/docs/mandate-2026 + https://neoexpertise.net/e-invoicing-in-morocco/ — e-invoicing clearance model, UBL 2.1/CII, phased timeline (**sources disagree on TPE date: 2027 vs 2028**)
- https://laravel-news.com/laravel-13 — Laravel 13 released 2026-03-17, PHP 8.3 min
- https://expo.dev/changelog/sdk-57 — SDK 57, RN 0.86, 2026-06-30
- https://rxdb.info/replication.html + https://github.com/pubkey/rxdb — backend-agnostic pull/push replication; premium storage plugins
- https://procedure.tech/blogs/react-native-offline-first/ + https://rxdb.info/articles/alternatives/watermelondb-alternative.html — WatermelonDB last commit Aug 2025, maintenance decline
- https://pdf4.dev/blog/wkhtmltopdf-alternatives-2026 — wkhtmltopdf archived Jan 2023, unpatched CVSS 9.8 SSRF
- https://planetscale.com/blog/scaling-postgres-connections-with-pgbouncer — pools are per (user, database); `default_pool_size` semantics

**LOW confidence (vendor marketing — verify before committing):**
- https://www.baas.ma/en/saas-subscription-payment-morocco + https://www.baas.ma/fr/blog/comparatif-passerelle-paiement-maroc — Chari Pay recurring/tokenization/sandbox claims, gateway comparison table (published by Chari, i.e. an interested party)
- https://digitoyou.com/blog/paiement-en-ligne-maroc-cmi-stripe-2026/ — CMI onboarding times and DX complaints

---
*Stack research for: Multi-tenant optician SaaS, Morocco*
*Researched: 2026-09-09*

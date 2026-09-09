# Architecture Research

**Domain:** Multi-tenant vertical SaaS (retail optician management) — database-per-tenant, offline-capable POS/caisse, web + mobile parity, Moroccan fiscal invoicing
**Researched:** 2026-09-09
**Confidence:** MEDIUM-HIGH (tenancy, offline sync, permissions: HIGH; Moroccan fiscal specifics: MEDIUM — verified against Art. 145 CGI text and DGI e-invoicing reform coverage, but a Moroccan accountant should confirm the acompte/TVA treatment before v1 ships)

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                                 │
│  ┌────────────────────────┐        ┌────────────────────────────┐    │
│  │  Web app (navigateur)  │        │  Mobile app (tel/tablette) │    │
│  │  IndexedDB / OPFS      │        │  SQLite                    │    │
│  └───────────┬────────────┘        └─────────────┬──────────────┘    │
│              │      ┌──────────────────────┐     │                   │
│              └─────►│  LOCAL STORE + FILE  │◄────┘                   │
│                     │  D'ATTENTE (outbox)  │                         │
│                     │  vente / caisse /    │                         │
│                     │  paiement en attente │                         │
│                     └──────────┬───────────┘                         │
└────────────────────────────────┼─────────────────────────────────────┘
                                 │ HTTPS — JWT (tenant_id, user_id)
                                 │ idempotency-key + client UUID
┌────────────────────────────────▼─────────────────────────────────────┐
│                          API LAYER (one shared app)                   │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ 1. Auth  → 2. Tenant Resolver → 3. Connection Router            │  │
│  │            (JWT claim / subdomain)   (per-tenant pool, LRU)     │  │
│  │                    FAIL-CLOSED: no tenant context = no DB       │  │
│  └────────────────────────────────┬───────────────────────────────┘  │
│  ┌────────────────────────────────▼───────────────────────────────┐  │
│  │ 4. Permission Gate (data-driven, per tenant, per magasin)      │  │
│  └────────────────────────────────┬───────────────────────────────┘  │
│  ┌──────────────┬─────────────────▼──────────┬──────────────────┐    │
│  │ Sync Gateway │      Domain Services        │  Document/PDF    │    │
│  │ push mutations│  Vente · Caisse · Stock    │  Facture A4      │    │
│  │ pull changes  │  Client/Ordonnance         │  Bon de commande │    │
│  │ (projections) │  Achat/Fournisseur         │  branding tenant │    │
│  └──────────────┴──────────────┬──────────────┴──────────────────┘    │
│  ┌───────────────────────────────▼─────────────────────────────────┐  │
│  │  NUMEROTATION SERVICE  — sole allocator of legal facture numbers │  │
│  │  serialized per (magasin, série, exercice) — gapless by design   │  │
│  └───────────────────────────────┬─────────────────────────────────┘  │
└──────────────────────────────────┼───────────────────────────────────┘
                                   │
┌──────────────────────┐   ┌───────▼──────────────────────────────────┐
│  CONTROL PLANE DB    │   │        TENANT DATABASES (1 per client)    │
│  (central, shared)   │   │  ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  tenants + db_host   │──►│  │ opticien │ │ opticien │ │ opticien │  │
│  identity → tenant   │   │  │    A     │ │    B     │ │    C     │  │
│  subscriptions       │   │  │ magasins │ │ magasins │ │ magasins │  │
│  schema_version      │   │  │ stock    │ │ stock    │ │ stock    │  │
│  provisioning jobs   │   │  │ caisse   │ │ caisse   │ │ caisse   │  │
│  platform metrics    │   │  │ factures │ │ factures │ │ factures │  │
└──────────────────────┘   │  │ roles    │ │ roles    │ │ roles    │  │
         ▲                 │  └──────────┘ └──────────┘ └──────────┘  │
         │                 └───────────────────▲──────────────────────┘
┌────────┴──────────────────────────────────────┴──────────────────────┐
│  BACKGROUND WORKERS (tenant-aware jobs)                               │
│  provisioning · migration fan-out · rappels · relances sync · métriques│
└───────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Control plane DB** | Tenant registry, `db_host`/`db_name` per tenant, identity→tenant mapping, subscription/billing state, per-tenant `schema_version`, provisioning + migration job state, aggregated platform metrics | Single central Postgres. Never contains optician business data. |
| **Tenant resolver** | Turn an inbound request into exactly one tenant identity, before any data access | Middleware. Primary source: signed JWT claim. Secondary: subdomain (web). Never a raw client header. |
| **Connection router** | Hold and hand out a connection to the resolved tenant's database; evict idle ones | Per-tenant connection manager with small pools (2–5) + LRU eviction. `db_host` read from control plane so tenants can later be sharded across Postgres instances. |
| **Fail-closed guard** | Refuse to execute any tenant-scoped query when no tenant context is bound | A repository/base-model rule that throws rather than falling back to the central connection. The single most important isolation control. |
| **Provisioning service** | Signup → create database → run migrations → seed (rôles, permissions, magasin par défaut, série de facturation, taux TVA, branding defaults) → mark active | Idempotent async job, resumable, with `status` visible to the signup UI. |
| **Migration fan-out runner** | Apply schema changes to every tenant database; track and report which tenants are behind | Queued job per tenant, bounded concurrency, per-tenant version in control plane, expand/contract migrations so old and new app code both work mid-rollout. |
| **Permission gate** | Evaluate `permission × magasin` for the authenticated user on every mutation and every read of sensitive fields | Data-driven RBAC: code-defined permission catalog, tenant-owned roles. Server-side, always. |
| **Numérotation service** | Sole allocator of legal facture/avoir numbers. Serializes allocation and guarantees no gaps and no duplicates | Row lock (`SELECT … FOR UPDATE`) or advisory lock on a `sequence` row, inside the same transaction that inserts the document. |
| **Stock ledger** | Append-only `mouvement_stock` per magasin; current quantity is derived, never authoritative on its own | Immutable movement rows + a materialized `stock_magasin` snapshot updated in the same transaction. |
| **Caisse ledger** | Append-only cash entries in/out per magasin with a running balance; daily/monthly totals read off it | Immutable `entree_caisse` rows. No Z-close (explicitly out of scope). |
| **Sync gateway** | Accept queued device mutations idempotently; serve permission-filtered change sets back down | Two endpoints: `POST /sync/mutations` (batch, idempotent) and `GET /sync/changes?since=` (cursor). Returns per-item results, not one all-or-nothing status. |
| **Local store + outbox** | Keep the counter working with no connection: read cached working set, write local records, queue mutations durably | SQLite (mobile) / IndexedDB or OPFS (web) behind one shared repository interface. |
| **Document renderer** | Produce facture A4 and bon de commande with tenant branding | Server-side PDF for the facture (canonical, archived). Client-side render for the offline bon de commande / reçu d'acompte. |
| **Reminder engine** | Réappro thresholds, échéances fournisseur, relances client | Scheduled tenant-aware jobs iterating active tenants. |

---

## Recommended Project Structure

Monorepo. Structure below assumes a TypeScript stack; the *shape* transfers to Laravel/PHP or any other choice — what matters is that the domain lives in one server-side place and the platforms share a generated contract.

```
apps/
├── api/                         # the one shared application
│   ├── src/
│   │   ├── platform/            # tenancy machinery — no business logic
│   │   │   ├── tenancy/         # resolver, connection router, context
│   │   │   ├── provisioning/    # signup → database → migrate → seed
│   │   │   ├── migrations/      # fan-out runner + tenant schema_version
│   │   │   ├── billing/         # subscription, CharriPay/CMI webhooks
│   │   │   └── control-plane/   # central DB models
│   │   ├── domaine/             # French vocabulary — the business core
│   │   │   ├── client/          # client, ordonnance (OD/OG, sphère…)
│   │   │   ├── stock/           # article, mouvement, inventaire, réappro
│   │   │   ├── vente/           # vente, ligne, paiement, acompte
│   │   │   ├── facturation/     # facture, avoir, TVA, numerotation/
│   │   │   ├── caisse/          # entrée, solde, totaux
│   │   │   ├── achat/           # fournisseur, bon de commande, réception,
│   │   │   │                    #   compte fournisseur, prix d'achat
│   │   │   └── rappel/          # réappro, échéance, relance client
│   │   ├── autorisation/        # permission catalog + role evaluation
│   │   ├── sync/                # mutation ingest, change feed, projections
│   │   ├── documents/           # PDF facture / bon de commande, branding
│   │   └── http/                # controllers, middleware pipeline
│   └── migrations/
│       ├── central/             # control plane schema
│       └── tenant/              # per-client schema (fans out)
├── web/                         # web shell
└── mobile/                      # Expo shell
packages/
├── contrat/                     # API types + validation schemas (generated
│                                #   from OpenAPI or shared Zod) — one source
├── domaine-partage/             # pure calculations safe to run on device:
│                                #   totaux TTC/TVA, solde caisse, formatage
│                                #   MAD/dates, validation ordonnance
├── stockage-local/              # repository interface + SQLite/IndexedDB impls
├── sync-client/                 # outbox, retry/backoff, cursor, conflict queue
└── ui/                          # shared components if RNW; tokens+branding if not
```

### Structure Rationale

- **`platform/` is quarantined from `domaine/`.** Tenancy is infrastructure. If tenant-awareness leaks into the sales code, every future feature has to re-learn it. Domain services should be written as if there is exactly one optician.
- **`domaine/` uses French names.** PROJECT.md is explicit that translating the vocabulary invites confusion; the code model is where that promise is actually kept or broken.
- **`facturation/numerotation/` is its own module** because it is the one place where a bug is a legal problem, and because it must remain the *only* writer of facture numbers.
- **`sync/` sits beside the domain, not inside it.** Sync calls domain services; domain services know nothing about devices. Otherwise offline concerns metastasize.
- **`packages/contrat/` exists so web and mobile cannot drift.** Parity is a build-time guarantee (one generated client) rather than a discipline.
- **`packages/domaine-partage/` holds only pure functions.** Anything with an invariant (numbering, stock, permissions) stays server-side even if a device could compute it.

---

## Architectural Patterns

### Pattern 1: Fail-closed tenant context

**What:** A request-scoped, immutable tenant context bound by middleware. Any data access without it throws.
**When to use:** Always, from the first commit. This is not retrofittable — by the time you have 40 query call sites, you cannot prove any of them are safe.
**Trade-offs:** Slight ceremony in tests (every test must bind a tenant). Worth it: PROJECT.md calls a cross-client leak "a security failure, not a bug."

```typescript
// platform/tenancy/context.ts
export function db(): TenantDb {
  const ctx = tenantContext.get();
  if (!ctx) throw new Error('Aucun tenant résolu — accès base refusé');
  return pool.for(ctx.tenantId);       // routes to that client's database
}

// Isolation test that must exist from day one:
// as user of tenant A, every endpoint returns 404/403 for tenant B's ids.
```

### Pattern 2: Server-allocated legal number, device-allocated local reference

**What:** The device never invents a facture number. It creates the sale with a client-generated UUID and a human-readable *local* reference; the server allocates the fiscal number when the document reaches it.
**When to use:** Any jurisdiction demanding a continuous series (Morocco, France, Spain, Portugal).
**Trade-offs:** The customer does not walk out with a facture during an outage. Resolved below — the optician workflow already hands over a bon de commande at order time.

```typescript
// facturation/numerotation/service.ts — the ONLY writer of numero
async function allouer(magasinId: string, type: 'FACTURE'|'AVOIR', exercice: number) {
  return db().transaction(async (tx) => {
    const s = await tx.selectForUpdate('serie_document',
      { magasin_id: magasinId, type, exercice });   // serializes concurrent sync
    const numero = s.dernier_numero + 1;
    await tx.update('serie_document', s.id, { dernier_numero: numero });
    return `${s.prefixe}/${exercice}/${String(numero).padStart(5, '0')}`;
  });
  // Allocation and document INSERT share one transaction:
  // rollback consumes nothing → no gap; unique(serie_id, numero) → no duplicate.
}
```

### Pattern 3: Append-only ledgers, derived balances

**What:** Stock and caisse are immutable event logs (`mouvement_stock`, `entree_caisse`). Current quantity and current solde are derived, and maintained as a snapshot updated in the same transaction as the movement.
**When to use:** Whenever offline devices can inject historical facts out of order. Which is exactly this system.
**Trade-offs:** More rows, and totals need a snapshot to stay fast. In exchange, a late-arriving offline sale is a normal append, not a destructive update — the reason last-write-wins is disqualified for money and stock.

```typescript
// A synced offline sale is an append, never an overwrite:
await tx.insert('mouvement_stock', {
  magasin_id, article_id, quantite: -ligne.quantite, type: 'VENTE',
  vente_id, cree_le_appareil: device.ts, enregistre_le: serverNow()  // both clocks
});
await tx.exec(`UPDATE stock_magasin SET quantite = quantite - $1 ...`); // may go < 0
```

### Pattern 4: Idempotent mutation ingest with per-item results

**What:** Every device mutation carries a client-generated UUID and an idempotency key. The server stores `(tenant, idempotency_key) → response` and replays the stored response on retry. The batch endpoint returns a result *per item* — accepted, duplicate, rejected-permanent, retryable.
**When to use:** Mandatory. Flaky Moroccan shop connectivity guarantees the "did my POST land?" case, and a double-inserted sale is a double stock decrement plus a double caisse entry.
**Trade-offs:** Requires the API to be designed this way *before* offline work starts — which is why phase ordering below insists on it.

### Pattern 5: Permission-filtered sync projections

**What:** The device pulls DTO projections shaped by the user's permissions, not raw table rows.
**When to use:** Here, non-negotiably. PROJECT.md: opticians will not let vendeurs see prix d'achat or margins. If sync replicates the `article` table, `prix_achat` lands in the vendeur's local SQLite and the permission model is decorative.
**Trade-offs:** You cannot use an off-the-shelf table-replication sync engine (see Anti-Pattern 3). You write the change feed yourself. Smaller payloads is the consolation prize.

### Pattern 6: Permissions as tenant data over a code-defined catalog

**What:** Permission *keys* are a constant list shipped with the app (`vente.creer`, `caisse.lire`, `achat.prix_achat.lire`, `rapport.revenu.lire`, …) and synced into each tenant DB by migration. *Roles* are rows the owner can edit.
**When to use:** From the moment the first permission-gated feature exists.
**Trade-offs:** A new permission means a migration touching every tenant DB — acceptable, and it keeps the catalog reviewable in code.

```
role(id, nom, est_systeme)              -- 'owner' est_systeme=true, non éditable
role_permission(role_id, permission_cle)
utilisateur_role(utilisateur_id, role_id)
utilisateur_magasin(utilisateur_id, magasin_id)   -- portée, orthogonale au rôle
```

The `owner` role is implicitly all-permissions and locked — otherwise an owner can edit themselves out of their own account, in a database only you can repair.

---

## Data Flow

### Request Flow (online)

```
[Vendeur: encaisser]
    ↓
[UI] → [API client] → Auth → Tenant Resolver → Connection Router → Permission Gate
                                                                          ↓
                                                        [Service Vente] (transaction)
                                                                          ↓
                          ┌───────────────┬────────────────┬──────────────┴─────┐
                          ↓               ↓                ↓                    ↓
                   mouvement_stock   entree_caisse     paiement       Numérotation
                          │               │                │              → facture
                          └───────────────┴────────────────┴────────────────────┘
                                                  ↓ commit
[UI: facture numérotée] ← [DTO] ← [projection filtrée par permissions]
```

### Offline Flow (the one that matters)

```
[Vendeur, connexion coupée]
    ↓
[UI] écrit dans le store local (SQLite/IndexedDB) :
      vente(uuid, statut='EN_ATTENTE_NUMEROTATION', reference_locale='BC-M01-P02-000137')
      mouvement_stock local (quantité affichée décrémentée)
      entree_caisse locale (solde affiché mis à jour)
    ↓
[Impression] Bon de commande / Reçu d'acompte — document NON fiscal, avec la
      référence locale. Le client repart avec ça.
    ↓
[Outbox] mutation persistée : {uuid, idempotency_key, payload, tentatives}
    ↓  … connexion revenue …
[POST /sync/mutations]  ──► serveur : rejoue idempotent, revalide permissions,
                                       écrit les mouvements réels,
                                       ALLOUE le numéro de facture
    ↓
[Réponse par item] {uuid → {statut:'accepte', numero:'FA/2026/M01/00412'}}
    ↓
[Device] met à jour la vente locale, la facture devient imprimable/ré-imprimable.
         Anomalies (stock négatif, permission révoquée) → file de réconciliation.
```

### Key Data Flows

1. **Tenant resolution:** JWT `tenant_id` → control plane lookup (cached) → `db_host`/`db_name` → pooled connection. One direction only; tenant DBs never call the control plane.
2. **Stock:** every quantity change enters as a `mouvement_stock` row. Réception (+) from achats, vente (−) from the counter, ajustement (±) from inventaire. `stock_magasin.quantite` is a cache of that sum.
3. **Caisse:** paiement → `entree_caisse` (+/−). Solde and daily/monthly totals are aggregations, never a stored mutable balance.
4. **Ordonnance → commande spéciale:** the structured prescription is copied (snapshotted, not referenced) onto the supplier order line, so a later prescription edit cannot silently change what was ordered.
5. **Change feed down:** `GET /sync/changes?since=cursor` returns permission-filtered, magasin-scoped projections of the working set (clients, articles, stock snapshot, ordonnances récentes) — not history, not the whole tenant.

---

## The Collision: Offline Sales vs Gapless Legal Numbering

This is the hardest constraint in the project. Resolved explicitly.

### The legal ground

Article 145 CGI requires invoices to be "pré-numérotés et tirés d'une série continue ou édités par un système informatique selon une série continue." The same article provides the escape hatch this design uses: **for retail sales to consumers, a ticket/receipt may substitute for a facture** provided it carries the date, seller identity, description, quantity, price and TVA mention. Separately, the DGI e-invoicing reform makes the invoice legally valid only after DGI pre-validation — large companies from 2026, SMEs/TPEs in 2027–2028. Both point the same way: **a document produced on a disconnected device is provisional by nature; the fiscal document is minted centrally.**

### Where the number is assigned

**On the server, inside the same transaction that persists the facture. Never on the device.**

One `serie_document` row per `(magasin, type, exercice)`, locked with `SELECT … FOR UPDATE` (or a Postgres advisory lock) for the duration of that transaction. Concurrent syncs from three devices serialize on that row. `UNIQUE (serie_id, numero)` is the backstop. Because the number is only consumed by a transaction that commits, and a committed transaction always produces the document, the series is gapless and duplicate-free by construction.

Series are scoped **per magasin** (`FA/2026/M01/00412`). Article 145's wording is singular ("une série continue"), so each magasin's series must itself be continuous; per-magasin series are standard commercial practice and keep two shops from contending on one counter. Avoirs use their own series (`AV/…`). *Flagged for accountant confirmation: whether the client's fiscal setup prefers one series per company rather than per magasin. Keep it configurable in the `serie_document` table so this is a data change, not a code change.*

### What the offline device shows before it has a number

- The vente exists locally with `statut = 'EN_ATTENTE_NUMEROTATION'` and `numero_facture = null`.
- It displays and prints a **bon de commande / reçu d'acompte** — a non-fiscal document already in v1 scope — carrying a **référence locale** `BC-{magasin}-{poste}-{seq}`. That reference is device-scoped, allowed to have gaps, and has no fiscal meaning. It exists so staff and customer can talk about the same order.
- This is not a workaround; it is the optician workflow. The customer orders lenses, pays an acompte, and returns days later to collect. **The facture is normally issued at retrait, which is a second visit and almost always online.** The rare fully-offline walk-out sale (accessory, contact lens box) gets its facture printed or emailed once the shop reconnects.
- The UI must never show a fake number, a greyed placeholder that looks like a number, or "FA/2026/…" with pending digits. Staff will read it to a customer.

### Ordering caveat, stated honestly

Numbers follow *issuance* order, not sale order: a device offline from 10:00 to 18:00 gets numbers after sales that happened at 14:00 on a connected counter. Mitigations:
1. The facture carries both `date_operation` (Art. 145 requirement — the sale) and `date_facturation` (allocation). The series is chronological in `date_facturation`, which is the field the sequence actually tracks.
2. Bound the window: sync on reconnect, and raise a "retard de synchronisation" alert to the owner past a threshold (say 24h).
3. Hard-block year-boundary drift: a device holding unsynced sales as the exercice rolls over must warn loudly, because the series resets per year.

### Rejected alternatives (and why)

| Alternative | Why rejected |
|---|---|
| Device allocates from its own per-poste series | Legally defensible in France (NF525) but Art. 145's singular "série continue" makes it riskier in Morocco, and a lost/wiped device leaves a permanent unexplainable hole in the series. |
| Pre-leased blocks of numbers per device | Unused numbers in an unreturned lease *are* gaps. Reissuing them breaks chronology. Trades a certain failure for an intermittent one. |
| Renumber/compact on sync | Reissuing a number already printed and handed to a customer is worse than any problem it solves. |

---

## The Collision: Stock vs Offline Concurrency (oversell)

### The stated answer

**The server never rejects a synced sale for insufficient stock. Stock is allowed to go negative, and negative stock is an alert, not an error.**

The reasoning: by the time a sale syncs, the frame has left the shelf in the customer's hand. A rejection would invalidate a document the shop already honoured. The sale is a *fact being reported*, not a *request being authorised*.

### How it works

1. **Ledger, not counter.** `mouvement_stock` is append-only. A late offline sale is an append with the device timestamp preserved and the server receipt timestamp recorded. No blind quantity overwrite — a replayed absolute quantity would clobber movements that happened in between.
2. **Prevention on the device, advisory only.** The local snapshot shows availability. At zero, the vendeur sees "Stock épuisé selon la dernière synchronisation — vérifier le rayon" and can proceed. Software must not out-argue the shelf.
3. **Detection on the server.** Any movement driving `stock_magasin.quantite` below zero writes an `anomalie_stock` row: article, magasin, ventes en cause, écart. It surfaces in an owner-facing réconciliation queue.
4. **Resolution by inventaire.** The owner counts and posts an `AJUSTEMENT` movement. The ledger keeps the full trail: what was sold, what was actually there, what was corrected.
5. **Same-unit double sale is largely physical-impossible.** Two counters in one magasin cannot both hand over the same single frame. The real exposure is fungible bulk stock (lentilles, produits d'entretien) where a negative balance simply means "reorder now" — which is what the réappro reminder already does.
6. **Explicitly deferred:** device-to-device stock reservation over the shop LAN, and unit-level serialised tracking for frames. Most Moroccan opticians run one or two counters; this is complexity looking for a customer.

**Concurrency is handled where it exists:** the *server-side* transaction. Movement insert plus snapshot update happen atomically; the snapshot update uses `SET quantite = quantite - $1` so concurrent syncs compose rather than clobber.

---

## Web + Mobile Parity: what is shared, what is not

| Concern | Where it lives | Why |
|---|---|---|
| Business invariants — numbering, stock, permissions, totaux/TVA, soldes | **Server only** | Anything a device could compute, a tampered device could compute wrong. |
| API contract, types, validation schemas | **Shared package**, one source (OpenAPI-generated or shared Zod) | Parity becomes a build-time guarantee instead of a discipline. |
| Pure calculations for offline display — TTC/TVA preview, running solde, MAD/date formatting, ordonnance field validation | **Shared package** (`domaine-partage`) | The counter must show a correct total offline; the server recomputes authoritatively at sync. |
| Outbox, retry/backoff, sync cursor, conflict queue | **Shared package** (`sync-client`) over a storage interface | This logic is subtle and must not be written twice. |
| Local persistence engine | **Per platform** — SQLite (mobile) / IndexedDB or OPFS (web) | Behind one repository interface so `sync-client` stays platform-agnostic. |
| Background sync trigger | **Per platform** — Expo task/background fetch vs Service Worker | OS-level, irreducibly different. |
| Printing | **Split** — server PDF for facture; client render for offline bon de commande | The facture must be canonical and archived; the bon de commande must work with no network. |
| Screens/navigation, secure storage, notifications, camera | **Per platform** | Native affordances. |

**Recommendation:** a single Expo / React Native + react-native-web codebase behind Expo Router, with `apps/web` and `apps/mobile` as thin shells over shared packages. This is the strongest available lever for one solo developer holding a full-parity requirement — RNW on Expo SDK 54+ is reported production-grade in 2026 (MEDIUM confidence; corroborated by multiple 2026 sources, not by first-hand benchmark).

**Honest trade-off:** dense back-office surfaces — rapports, stock lists, compte fournisseur — are where RNW is weakest, and those are exactly the owner's screens on a desktop. **Fallback:** separate Next.js web + Expo mobile, still sharing `contrat`, `domaine-partage`, `stockage-local` and `sync-client`. The architecture is unchanged either way because the seam is the API plus the shared packages; the UI shell is replaceable. STACK.md owns the final call.

---

## Suggested Build Order

Ordering is driven by three hard dependencies: **nothing is safe before tenant isolation**, **nothing is correct before permissions**, and **offline must be retrofitted onto a working online flow — but only if the API was designed for it from the start.**

| # | Component | Depends on | Why here |
|---|---|---|---|
| 0 | **Tenancy foundation** — control plane DB, tenant resolver, connection router, fail-closed guard, migration fan-out, provisioning job, cross-tenant isolation test suite | — | Every table created before this exists gets retrofitted. The isolation test is part of this phase, not a later hardening pass. |
| 1 | **Identity, rôles, permissions, magasins** — permission catalog, tenant-owned roles, `utilisateur_magasin` scoping, owner/vendeur seeds | 0 | Every subsequent feature is permission-gated. Adding permissions after five features means auditing five features. |
| 2 | **Référentiels** — clients, ordonnances (OD/OG structuré, historique), articles/catalogue | 1 | Read-heavy, no sync complexity. Establishes the French domain model everything else hangs off. |
| 3 | **Stock ledger** — mouvements, snapshot, inventaire/ajustement, seuils | 2 | Vente writes stock movements, so the ledger must exist first. Online only at this stage. |
| 4 | **Vente + facturation + caisse, ONLINE ONLY** — vente, lignes, paiement, acompte, numérotation service, séries, TVA, caisse ledger | 3 | Get the fiscal core provably correct on a good connection before adding a partition-tolerance problem on top. **Non-negotiable constraint on this phase:** the API must already use client-generated UUIDs and idempotency keys, and vente must already tolerate `numero = null` with `statut = EN_ATTENTE_NUMEROTATION`. Skipping that turns phase 5 into a rewrite. |
| 5 | **Couche hors ligne** — local store, outbox, batch idempotent ingest, change feed with permission projections, conflict/anomalie queue, offline UI states, bon de commande printed locally | 4 | The core value proposition. Deserves its own phase and its own deep research. Likely the highest-risk phase in the project. |
| 6 | **Achats** — fournisseurs, bon de commande, réception (→ stock +), compte fournisseur, prix d'achat (permission-gated), marges | 3, 1 | Réception is the legitimate stock-increase path; until then stock is seeded by ajustement. Prix d'achat is the sharpest test of the permission model. |
| 7 | **Documents & branding** — facture A4 PDF, bon de commande, logo/couleurs per tenant | 4, 6 | Needs final document shapes. Do not let branding block the transactional core. |
| 8 | **Rappels** — réappro, échéances fournisseur, relances client/ordonnance | 3, 6, 2 | Needs thresholds, échéances and ordonnance dates to exist. |
| 9 | **Abonnement & self-serve** — signup flow, trial, CharriPay-style payment, subscription lifecycle gating | 0 | Provisioning exists from phase 0 and can be triggered manually until here. Billing is control-plane work, decoupled from the domain. |
| 10 | **Parité mobile & durcissement** — packaging, background sync tuning, perf on cheap Android, offline soak testing | 5 | Real-world validation of phase 5 under a real device fleet. |

**Flexible edges:** 6 (achats) can swap with 5 (hors ligne) if early customers turn out to buy on the achats/marges story rather than the offline story. 7 and 8 can slide. **0, 1 and 4 → 5 cannot move.**

---

## Scaling Considerations

Realistic scale for this product is tens to low hundreds of tenants, each with 1–5 magasins and 1–10 users. Database-per-tenant is well matched to that range and stops being comfortable in the thousands.

| Scale | Architecture adjustments |
|---|---|
| 1–50 tenants | One Postgres instance, one app instance, one worker. Migration fan-out runs in minutes. Nothing exotic. |
| 50–500 tenants | Connection count is the first real pressure: cap per-tenant pools at 2–3, LRU-evict idle tenants, put PgBouncer between app and Postgres. Migration fan-out becomes a queued job per tenant with bounded concurrency and a "tenants behind" dashboard. Per-tenant backup/restore needs to be a scripted operation, not a manual one. |
| 500+ tenants | Shard tenants across multiple Postgres instances — cheap only because `tenants.db_host` existed from day one. Split workers per queue (sync ingest vs rappels vs migrations). Push per-tenant metrics into the control plane so platform dashboards never fan out queries across every database. |

### Scaling Priorities

1. **First bottleneck: connections.** Separate databases multiply pools. Fix with small pools + LRU eviction + PgBouncer before it becomes an outage.
2. **Second bottleneck: migration fan-out duration and partial failure.** Fix with per-tenant queued jobs, recorded versions, resumability, and expand/contract migrations so a half-migrated fleet is still a working fleet.
3. **Third bottleneck: sync ingest bursts.** Every shop reconnecting after a regional outage syncs at once. Fix with a queue in front of ingest, per-tenant rate limits, and jittered client retry — never a naive fixed-interval retry, which produces a retry storm.
4. **Not a bottleneck:** query performance inside a tenant. An optician's dataset is small. Do not optimise here.

---

## Anti-Patterns

### Anti-Pattern 1: Allocating the facture number on the device

**What people do:** Let the offline POS assign `FA/2026/00413` so the customer leaves with a "real" invoice.
**Why it's wrong:** Two devices collide, a wiped device leaves a permanent hole, and a number printed and handed over can never be corrected. This is a legal exposure under Art. 145, not a data-quality issue.
**Do this instead:** Server allocates at sync inside the document transaction. The device prints a non-fiscal bon de commande carrying a local reference.

### Anti-Pattern 2: Blocking or rejecting a sale on stock availability

**What people do:** Return `409 stock insuffisant` when an offline sale syncs.
**Why it's wrong:** The goods are already gone. You are rejecting reality and leaving the shop with a document your system refuses to recognise.
**Do this instead:** Always accept. Allow negative stock. Emit an `anomalie_stock` into a réconciliation queue and let an inventaire/ajustement close it.

### Anti-Pattern 3: Using an off-the-shelf table-replication sync engine

**What people do:** Reach for PowerSync / ElectricSQL / WatermelonDB-with-table-sync because "offline is solved."
**Why it's wrong here — two independent reasons.** (a) These engines attach to Postgres via logical replication slots at the *server* level; database-per-tenant means one instance/slot per tenant database against a `max_replication_slots` ceiling, and cost scaling per tenant. (b) More fundamentally, they replicate *rows*. Replicating the `article` table puts `prix_achat` in the vendeur's local SQLite — silently defeating the permission requirement that PROJECT.md calls a product requirement.
**Do this instead:** Purpose-built sync over your own API — idempotent batch mutation ingest up, permission-filtered DTO projections down, cursor-based. More work, but it is the only design that satisfies both constraints. *(Their local-database and conflict-handling ideas remain worth borrowing.)*

### Anti-Pattern 4: Hardcoded role checks

**What people do:** `if (user.role === 'owner')` scattered across services.
**Why it's wrong:** PROJECT.md requires owner-customizable permissions. Every hardcoded check is a place customization silently doesn't apply — and the divergence between what the UI hides and what the API allows is where the margin leak happens.
**Do this instead:** `autoriser(user, 'achat.prix_achat.lire', magasinId)` everywhere, over the data-driven catalog. The client's cached permission set drives UI only; the server re-checks every call.

### Anti-Pattern 5: Falling back to the central connection when tenant context is missing

**What people do:** A default connection so background jobs and CLI commands "just work."
**Why it's wrong:** It turns a missing-context bug into a cross-tenant data leak or a write into the wrong database — silently.
**Do this instead:** Throw. Tenant-aware jobs carry the tenant id in the payload and re-bind context on pickup.

### Anti-Pattern 6: Building the offline layer first

**What people do:** Start local-first because it's the hard part and the differentiator.
**Why it's wrong:** You end up debugging domain rules and sync semantics simultaneously, and every domain change means reworking sync. The domain shape is still moving in month one.
**Do this instead:** Build the online domain first (phases 3–4), but design the API for offline from the start — client UUIDs, idempotency keys, nullable facture number, append-only ledgers. Those four decisions are what make phase 5 a retrofit instead of a rewrite.

### Anti-Pattern 7: Trusting the device clock, or last-write-wins on financial records

**What people do:** Order events by device timestamp; resolve conflicts by newest wins.
**Why it's wrong:** Device clocks drift and are user-settable. LWW on money or stock silently destroys a transaction that actually happened.
**Do this instead:** Store both `cree_le_appareil` and the server-stamped `enregistre_le`; use server time for anything fiscal. Financial records are append-only, so there is nothing to conflict — corrections are new entries (avoir, ajustement), never edits.

### Anti-Pattern 8: Cross-database queries for platform analytics

**What people do:** Loop every tenant database to build an admin dashboard.
**Why it's wrong:** Linear in tenant count, fails whenever one tenant is mid-migration or offline.
**Do this instead:** Tenant-aware jobs push aggregated metrics into the control plane. Dashboards read one database.

---

## Integration Points

### External Services

| Service | Integration pattern | Notes |
|---|---|---|
| CharriPay / CMI (abonnements) | Redirect/hosted checkout + signed webhook → control plane subscription state | Control plane only; never touches tenant DBs. Webhooks must be idempotent — treat as another mutation ingest. International gateways are unreliable for Moroccan-issued cards (PROJECT.md constraint). |
| DGI e-invoicing (future) | Clearance model: submit UBL 2.1 / UN-CEFACT CII, invoice legally valid only after DGI validation | Not required for TPE opticians in 2026 (large companies first, SMEs/TPEs 2027–2028). **Cheap now, expensive later:** model the facture with ICE vendeur + ICE acheteur, per-rate TVA breakdown, unit prices, and a `statut_fiscal` field with room for `valide_dgi` + external id/QR. Note it also *validates* this architecture: a centrally minted, centrally cleared invoice is exactly where the reform is heading. |
| SMS / WhatsApp (rappels) | Async worker jobs, provider behind an interface | Moroccan SMS deliverability varies; keep the provider swappable. |
| Object storage | Tenant-prefixed keys for branding assets and archived facture PDFs | Prefix isolation must be enforced server-side, never from a client-supplied path. |
| Push notifications | Expo push (mobile) / Web Push | Useful signal: "synchronisation en retard sur le poste 2". |

### Internal Boundaries

| Boundary | Communication | Notes |
|---|---|---|
| Control plane ↔ tenant DB | No direct link. App resolves connection metadata from control plane, then talks to the tenant DB. | One direction only. Never a cross-database join or foreign key. |
| Sync gateway ↔ domain services | Direct calls, inside the domain transaction | Sync is a delivery mechanism. Domain services must not know a device exists. |
| Numérotation ↔ facturation | Numérotation is called *inside* the facture-insert transaction | The rule that makes gaplessness structural rather than aspirational. |
| Vente ↔ stock/caisse | Same transaction, three appends | A sale that decrements stock but not the caisse is worse than a failed sale. |
| Domain ↔ permission gate | Gate at the HTTP boundary + sensitive-field filtering in projections | Two layers: endpoint authorisation and field-level redaction. Prix d'achat needs both. |
| Web/mobile ↔ API | Generated client from one contract | The mechanism that makes parity structural. |

---

## Confidence & Open Questions

| Area | Confidence | Basis |
|---|---|---|
| Database-per-tenant mechanics (resolution, pooling, migration fan-out) | HIGH | Consistent 2026 practitioner sources; mature tooling exists (e.g. stancl/tenancy fans out migrations, makes queues/caches tenant-aware). |
| Server-side gapless numbering | HIGH | Standard document-sequence practice (Oracle/Zuora gapless sequencing: numbers consumed only by successfully committed documents). |
| Offline sync patterns (outbox, idempotency, per-item results, dead-letter) | HIGH | Convergent across multiple independent 2026 sources. |
| Sync engines vs database-per-tenant | MEDIUM-HIGH | Replication-slot limits confirmed in PowerSync and Electric docs; the per-tenant-database consequence is my inference, not a vendor statement. |
| Art. 145 CGI "série continue" + ticket-as-substitute for retail | MEDIUM-HIGH | Read from the article text; secondary sources add "chronologique et sans interruption" as the DGI reading. |
| Whether per-magasin series is fiscally accepted in Morocco | **MEDIUM — open question** | Widespread commercial practice, but Art. 145's singular wording is not explicit. Kept as configuration in `serie_document`. **Confirm with a Moroccan accountant before v1.** |
| TVA treatment of the acompte (encaissement vs débit), and whether a facture d'acompte is required | **LOW — open question** | Not resolved by this research. Affects whether the acompte itself needs a fiscal number. Materially changes the offline flow if it does. Resolve early. |
| RNW/Expo web-mobile parity being production-grade in 2026 | MEDIUM | Multiple 2026 sources agree; not independently verified. Treat as a stack decision with a documented fallback. |

**Flag for phase-level research:** phase 5 (couche hors ligne) is the highest-risk phase and warrants its own deep research pass — specifically the change-feed cursor design, dead-letter handling, and offline soak testing on low-end Android.

---

## Sources

- [Article 145 - Tenue de la comptabilité (texte CGI)](https://www.fiscamaroc.com/dispositions-communes-208/article-145-tenue-de-la-comptabilite-214.htm) — HIGH
- [Facturation électronique Maroc 2026 : le guide DGI complet (Hisab)](https://hisab.ma/fr/docs/mandate-2026) — MEDIUM-HIGH
- [Facturation électronique au Maroc 2026 : Guide de la Réforme DGI (AMDE)](https://amde.ma/facturation-electronique-au-maroc/) — MEDIUM
- [Mentions obligatoires d'une facture au Maroc (art. 145 CGI)](https://fatouraplus.com/en/guide-auto-entrepreneur/mentions-obligatoires-facture-maroc-art-145/) — MEDIUM
- [Building a Multi-Tenant SaaS in 2026: Architecture, Pitfalls, and Production Patterns (GSoft)](https://gsoftconsulting.com/en/blog/building-multi-tenant-saas-2026) — MEDIUM
- [Multi-Tenant Architecture: Database Per Tenant vs Shared Schema (2026)](https://dev.to/young_gao/multi-tenant-architecture-database-per-tenant-vs-shared-schema-1n2e) — MEDIUM
- [Tenancy for Laravel — Queues / tenant-aware jobs](https://tenancyforlaravel.com/docs/v3/queues/) — HIGH (reference implementation of fan-out + tenant-aware workers)
- [How to design an RBAC model for multi-tenant SaaS (WorkOS)](https://workos.com/blog/how-to-design-multi-tenant-rbac-saas) — MEDIUM-HIGH
- [Roles and Permissions Schema Design for Multi-Tenant RBAC (Schemity)](https://schemity.com/blog/design-roles-and-permissions-for-multi-tenant-rbac/) — MEDIUM
- [The Hidden Problems of Offline-First Sync: Idempotency, Retry Storms, and Dead Letters](https://dev.to/salazarismo/the-hidden-problems-of-offline-first-sync-idempotency-retry-storms-and-dead-letters-1no8) — MEDIUM
- [Designing a Reliable Data Synchronization Layer (DZone)](https://dzone.com/articles/data-sync-design) — MEDIUM
- [PowerSync — Postgres Maintenance (replication slot limits)](https://docs.powersync.com/usage/lifecycle-maintenance/postgres-maintenance) — HIGH
- [Electric — Deployment (publication + replication slot)](https://electric-sql.com/docs/guides/deployment) — HIGH
- [React Native Offline-First in 2026: WatermelonDB vs RxDB vs PowerSync](https://procedure.tech/blogs/react-native-offline-first/) — MEDIUM
- [Cloud POS Offline Mode: Keep Inventory Sync Safe During Outages (ChannelDock)](https://channeldock.com/en/blogs/cloud-pos-offline-mode-inventory-sync/) — MEDIUM (timestamped stock events vs blind quantity replay)
- [Create sequential and gapless billing document numbers (Zuora)](https://knowledgecenter.zuora.com/Zuora_Billing/B_Set_up_Zuora_Billing/Configure_billing_settings/Billing_document_settings/Create_sequential_and_gapless_billing_document_numbers) — HIGH (temporary numbers before posting)
- [Oracle — Document Sequences (gapless sequencing)](https://docs.oracle.com/en/cloud/saas/financials/24a/fafcf/document-sequences.html) — HIGH
- [Adding an offline POS number for unsynced documents (ERPNext #6298)](https://github.com/frappe/erpnext/issues/6298) — MEDIUM (prior art: local reference for unsynced docs)
- [React Native Web + Expo Guide (2026)](https://reactnativerelay.com/article/react-native-web-expo-cross-platform-2026) — MEDIUM

---
*Architecture research for: multi-tenant optician management SaaS (Morocco)*
*Researched: 2026-09-09*

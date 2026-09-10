> **⚠️ Read with two later decisions in mind.**
>
> 1. **Offline is out of scope permanently** — ignore every offline, sync, local-storage, provisional
>    document and device-conflict recommendation below. What survives: server-issued facture numbers
>    from a counter row locked `FOR UPDATE`, append-only ledgers, and idempotent sale creation.
> 2. **The stack is Django + DRF**, not Laravel — with PostgreSQL (one database per client),
>    Celery, WeasyPrint, a React + Vite web SPA, and Expo mobile at Phase 11. Any Laravel, PHP or
>    React Native Web specifics below do not apply; the reasoning usually still does.
>
> `.planning/PROJECT.md` and `CLAUDE.md` are authoritative.

# Pitfalls Research

**Domain:** Multi-tenant SaaS for Moroccan opticians — DB-per-client, offline-capable caisse/POS, web + mobile, legally-valid Moroccan facturation
**Researched:** 2026-09-09
**Confidence:** MEDIUM-HIGH overall (HIGH on engineering pitfalls, MEDIUM on Moroccan legal specifics — secondary sources dominate, see Sources)

> **Read this first.** Four things in this project can force a rewrite rather than a fix:
> 1. Legal facture numbering colliding with offline creation (design decision, must be made in Phase 1, not the facturation phase).
> 2. Morocco's DGI e-invoicing clearance mandate landing on your customer segment in 2027.
> 3. Database-per-tenant migrations/provisioning built as a script instead of a control plane.
> 4. The offline sync payload leaking `prix d'achat` to vendeurs — a permissions failure hiding inside the offline feature.
>
> Everything else on this list is expensive. These four are structural.

## Suggested phase vocabulary

The roadmap doesn't exist yet, so pitfall→phase mapping below uses these working names. Adjust to the real roadmap:

| Ref | Working phase name |
|-----|--------------------|
| P0 | Legal & compliance groundwork (runs in parallel, calendar-bound, not code) |
| P1 | Tenancy foundation + control plane (provisioning, migration fan-out, tenant resolution) |
| P2 | Domain core (clients, ordonnances, catalogue, stock as a ledger, money primitives) |
| P3 | Permissions & roles (must precede feature surface, not follow it) |
| P4 | Sale + facturation + caisse, **online only** |
| P5 | Achats, fournisseurs, compte fournisseur |
| P6 | Offline sync engine (sale path only) |
| P7 | Mobile client |
| P8 | Self-serve signup, subscription, billing |
| P9 | Reminders, branding, reporting |

---

## Critical Pitfalls

### Pitfall 1: Assigning the legal facture number on the offline device

**What goes wrong:**
The vendeur completes a sale offline. The app needs to print something, so it allocates a facture number locally — from a per-device counter, a pre-allocated block, or worse a "next number I last saw from the server." When devices sync, you get duplicates (two magasins both issued `2026-000412`), gaps (a device pre-allocated 100 numbers and used 7), and non-chronological sequences (facture `...0420` dated before `...0415`). Under article 145 of the Moroccan CGI the numbering must be sequential, chronological and gap-free; gaps and duplicates are exactly the pattern a DGI inspector reads as concealed revenue. A single tenant with broken numbering across an exercice is not a bug report — it is their tax exposure, caused by your software.

**Why it happens:**
The requirement "the counter works offline" gets read as "everything the counter produces works offline," including the legal document. Nobody separates *completing a sale* from *issuing a legal invoice*. They are different acts with different constraints and they got merged because in the online happy path they happen in the same second.

**How to avoid:**
Split the document model in Phase 1, before any facture code exists:

- **Offline-creatable, no legal sequence:** the sale/commande itself, the acompte receipt, the bon de commande, a non-fiscal customer copy. These carry a client-generated UUID and a human-readable *local reference* that is visibly not a facture number (e.g. `BC-MAG2-2026-0912-A7F3`). Print them with wording that does not claim to be a facture.
- **Server-issued only, single writer per series:** the facture number. Allocated at the moment the sale reaches the server, from one counter row per (tenant, series, exercice) taken under `SELECT ... FOR UPDATE` (not a Postgres `SEQUENCE` — sequences legitimately leave gaps on rollback, which is the exact thing you must not have). The facture date is the server date at issuance.
- Consequence to accept and design the UX around: **a facture created during an outage is issued when the shop reconnects.** For a Moroccan optician selling to walk-in retail clients this is nearly always fine — the fiscal document a private individual needs is not usually issued at the counter, and the acompte/pickup flow already spans days. Make this an explicit product decision with a UI for "factures en attente d'émission," not an accident.
- If a tenant genuinely needs an instant facture while offline (a B2B client demanding it on the spot), the honest answer in v1 is: that operation requires connectivity. Say so in the UI. Do not fake it.

**Do NOT do:** per-device number blocks, "reserve 50 numbers," or renumbering at sync. Renumbering rewrites documents already handed to customers.

**Cancellation:** never delete or renumber an issued facture. Corrections are a *facture d'avoir* with its own separate series referencing the original. Make delete physically impossible on issued factures (DB-level, not just app-level).

**Warning signs:**
- A `facture_number` column that is nullable and writable from the client sync payload.
- A `nextInvoiceNumber` value cached on the device.
- Any test that produces two factures with the same number and passes because the assertion is on the sale, not the number.
- Discovering during the offline phase that you need to "handle" numbering — by then the document model is already wrong.

**Phase to address:** P1 (document model + counter design), enforced in P4, stress-tested in P6.

---

### Pitfall 2: Building facturation blind to Morocco's DGI e-invoicing mandate

**What goes wrong:**
You ship a facturation module in 2026 that renders a PDF and stores a total. Then the DGI clearance regime reaches your customers — small opticians fall into the last wave, reported around January 2027 for enterprises under 10M MAD turnover — and every invoice must be transmitted to the DGI platform as structured XML (UBL 2.1 / UN-CEFACT CII), validated *before* being handed to the customer, to be legally valid. Your stored data cannot produce that XML: the client has no ICE field, TVA is one lump total instead of split per rate, line items lack the required identifiers, and the facture has no lifecycle states for "transmitted / cleared / rejected by DGI." The entire module gets rebuilt, and every historical invoice is unconvertible.

**Why it happens:**
The mandate isn't in force yet for this segment, so it reads as "later." But clearance is not a bolt-on — it changes the facture from a document you own to a document the tax authority co-signs, which changes its state machine.

**Status honestly stated (MEDIUM confidence, verify before building):** the legal basis is article 145-IX of the CGI. As of March 2026 sources report the implementing *décret* had been submitted to the Secrétariat Général du Gouvernement but **not yet published in the Bulletin Officiel**, and no official turnover thresholds or penalties for e-invoicing specifically had been published. The commonly cited calendar (large enterprises 2026-01, medium 2026-07, SMEs/micro 2027-01) comes from consulting-firm commentary, not published text. Dates like this slip. **Do not build the DGI integration in v1. Do build so it costs weeks, not a rewrite.**

**How to avoid:**
Make the facture "clearance-ready" without doing clearance:

- Store the facture as **structured data**, with the PDF as a derived artifact. If your only durable record is a rendered PDF, you are already stuck.
- Capture every article-145 mention as its own field: ICE of the seller (per tenant) and of the client (15 digits, mandatory for B2B), IF, RC, patente/taxe professionnelle, numéro de facture, date, designation and quantity per line, unit price HT, **TVA broken out per rate**, total HT / total TVA / total TTC, mode de paiement.
- Give the facture an explicit lifecycle: `brouillon → émise → (transmise → validée | rejetée) → avoir émis`. Even if only the first two states are reachable in v1, the column and the transitions exist.
- Never hardcode a TVA rate in code. TVA rates belong to the product/line and must be stored *as applied at the time of the invoice*, because rates change: the 2024 reform converged Morocco onto two rates, 20% and 10%, eliminating 7% and 14% by 2026. A hardcoded 20% is a landmine; a rate looked up live and applied retroactively to old invoices is worse.
- **Open question you must resolve with a Moroccan expert-comptable, not with search:** what rate applies to montures, verres correcteurs, lentilles, solutions d'entretien, and to prestations (adaptation, montage). Research did not find an authoritative answer, and getting this wrong on every invoice for every client is a liability you cannot patch retroactively. Treat as a P0 blocking question.

**Warning signs:**
- Client record has no ICE field.
- One `tva_amount` column on the facture header.
- Facture identity is the PDF file.
- Line items store only a price, not a rate.

**Phase to address:** P0 (confirm rates + mandate status with an accountant), P2/P4 (data model shape). Actual DGI integration is a future milestone.

---

### Pitfall 3: Discovering CNDP authorization for health data at launch

**What goes wrong:**
Ordonnances — sphère, cylindre, axe, addition, acuity — are health data about identified individuals. Under Moroccan law 09-08, processing of health data requires **prior authorization** from the CNDP, not the simple declaration that ordinary processing requires (art. 23). Reported review time for a sensitive-data authorization file is 2–4 months. A solo developer discovers this the week before onboarding the first paying optician, and either launches non-compliant or waits a quarter with a finished product.

**Why it happens:**
It is calendar time, not build time, so it never appears on an engineering roadmap. And "we're just an optician's stock tool" hides the fact that the prescription table is a medical record.

**How to avoid:**
- Start the CNDP file in **P0, in parallel with the first line of code.** It costs almost nothing to start early and cannot be compressed later.
- Resolve the role question explicitly with counsel: in a multi-tenant SaaS the optician is plausibly the *responsable de traitement* and you the *sous-traitant*, which shapes who files what — but you cannot assume your clients will each file correctly, and your onboarding flow may need to prompt/assist them. This affects the signup flow (P8), so decide it before designing signup.
- Decide hosting jurisdiction early; cross-border transfer of Moroccan personal data has its own CNDP regime. Choosing a non-Moroccan cloud region is a legal decision, not just a latency one, and it is very expensive to reverse once tenant databases exist.
- Build the data-subject mechanics into the schema now: per-client export, rectification, and the ability to answer "what do you hold about this person" across a tenant DB.

**Warning signs:** the word CNDP does not appear anywhere in the plan. No named jurisdiction for hosting. No legal budget line.

**Phase to address:** P0, running continuously. Blocks P8 (real paying customers).

---

### Pitfall 4: Migration fan-out treated as a for-loop

**What goes wrong:**
`for db in tenants; do migrate $db; done`. It works at 5 tenants. At 200 it fails on tenant 63 (lock timeout, a tenant with 400k stock movements, a connection blip), leaves 137 tenants on the old schema and 62 on the new, and there is no record of which is which. The app now serves two schema versions and crashes for half your customers. Worse: you run it manually from a laptop, it takes 40 minutes, and a deploy went out in the middle.

**Why it happens:**
DB-per-tenant makes migrations look like the same problem N times. They are not — they are a *distributed* problem with partial failure as the normal case.

**How to avoid:**
Build a real migration runner in P1, as a deliverable with its own acceptance criteria:

- A **tenant registry** in a control-plane database recording, per tenant: connection info, current schema version, migration status, last error, provisioning state. Schema version is authoritative data, not inferred.
- Migrations are **idempotent and resumable**. Re-running the fan-out picks up only tenants behind the target version.
- **Every migration is backwards-compatible with the previous app version** (expand/contract: add nullable column → deploy code that writes both → backfill → deploy code that reads new → drop old, as separate releases). This is non-negotiable because you will *always* have tenants mid-fan-out. Do not combine a schema change and a large backfill in one migration — that is the classic hours-long lock.
- Concurrency limit + per-tenant timeout + retry with backoff + a dead-letter list a human reviews.
- A **canary set**: your own test tenants migrate first, automatically, and the fan-out aborts if they fail.
- Observability: a dashboard/CLI answering "how many tenants are on version N" in one query.
- Design the schema so migrations are rare and additive. Every avoided migration is 200 avoided operations.

**Warning signs:**
- No place that stores per-tenant schema version.
- A migration that both alters a table and backfills it.
- You cannot answer "is tenant X migrated?" without connecting to tenant X.
- Migrations run from a developer machine.

**Phase to address:** P1, before any domain table exists. Verification: create 200 throwaway tenants, kill the runner mid-fan-out, restart, confirm convergence.

---

### Pitfall 5: Provisioning failures mid-signup leaving zombie tenants

**What goes wrong:**
Signup creates the account row, calls the payment gateway, then runs `CREATE DATABASE` + 60 migrations + seed data inside the HTTP request. It takes 90 seconds, the request times out at 30, the user retries, and now there are two half-created tenants — one charged, one with a database and no owner user, one with an owner and no database. The user's first experience of your self-serve product is a broken account requiring the manual setup you promised to eliminate.

**Why it happens:**
Provisioning is modeled as a function call. It is a multi-system saga (billing + control plane + database cluster + email + storage) with independent failure modes.

**How to avoid:**
- Signup is an **explicit state machine** persisted in the control plane: `pending → db_created → migrated → seeded → billing_active → ready`, with `failed_at_step` and an error payload. Every step is idempotent and keyed by a signup ID.
- Provisioning is **asynchronous**. The HTTP request returns immediately; the user sees a "préparation de votre espace" screen that polls. This also makes slow steps acceptable.
- Use `CREATE DATABASE ... TEMPLATE tenant_template` where the template is a database kept at the current schema version, instead of running the full migration chain per signup. Orders of magnitude faster and removes the longest failure window. Keep the template updated as part of the fan-out.
- A **reconciler** job sweeps stuck signups and either advances or cleans them up. Zombie tenants must be found by the system, not by the customer.
- **Ordering:** provision *before* charging, or use trial-first so the first successful charge happens after the tenant exists. Never charge then fail to deliver.
- Reserve/validate the tenant identifier (subdomain, database name) atomically up front. And **never interpolate a user-supplied string into a database name or connection string** — allowlist `[a-z0-9_]`, prefix it, and generate rather than accept.

**Warning signs:** provisioning code inside a controller; no signup status column; no way to retry a failed signup without SQL.

**Phase to address:** P1 (provisioning mechanics), P8 (signup flow on top of it). Verification: chaos-test by failing each step and asserting the reconciler converges.

---

### Pitfall 6: Connection pool exhaustion across N tenant databases

**What goes wrong:**
Each tenant DB gets its own pool of 10 connections. At 100 tenants that's 1,000 connections from one app instance; run 3 instances and you're at 3,000 against a Postgres `max_connections` of 100–500. You get `FATAL: sorry, too many connections` and the whole platform — every tenant — goes down, triggered by growth rather than load.

**Why it happens:**
Pools are per connection string. DB-per-tenant multiplies connection strings. The multiplication is silent until it isn't, and it scales with *tenant count*, not traffic — so load testing one tenant never reveals it.

**How to avoid:**
- **PgBouncer in transaction mode** in front of the cluster. Know the catch: PgBouncer maintains a separate server pool per (user, database) pair, so 500 tenant DBs still means 500 server pools. Tune `max_db_connections`, `default_pool_size` small (2–5), `server_idle_timeout` aggressive, and rely on the fact that most tenants are idle at any moment.
- App-side: a **pool manager with LRU eviction and a hard global cap** — a bounded map of tenant → small pool, closing idle tenant pools. Not one pool per tenant held forever.
- Because transaction-mode pooling breaks session state: **no `SET search_path`, no session-level variables, no prepared statement reliance** across the pooler. If your tenancy mechanism depends on session state, it will silently cross tenants under pooling. This constraint should shape the tenancy implementation in P1.
- Set an explicit **tenant-per-cluster budget** now (e.g. "≤300 tenant DBs per Postgres instance") and design the tenant registry to hold a cluster/host per tenant from day one, so sharding later is a data change rather than a rewrite. Also budget for the per-database overhead you don't think about: autovacuum workers, catalog bloat, and backup jobs multiplying by tenant count.
- Background jobs are the usual culprit: a nightly job that opens every tenant DB at once. Bound its concurrency separately.

**Warning signs:** connection count grows when you add customers, not traffic. `pg_stat_activity` full of idle connections spread thinly across many databases. Nightly job hour correlates with errors.

**Phase to address:** P1. Verification: a load test that provisions 200 tenants and touches all of them within a minute; assert connection count stays under budget.

---

### Pitfall 7: No per-tenant restore path

**What goes wrong:**
One optician's staff deletes six months of stock movements, or a bad tenant-scoped migration corrupts one client's data. You have cluster-level PITR — which can restore *everything* to a point in time, meaning you'd roll back 200 innocent tenants to recover one. You either refuse to help the customer or you take an outage for everybody. Separately, a tenant churns, you drop their database, and you have just destroyed records article 211 of the CGI obliges them to keep for **ten years** (with reported penalties of 50,000 MAD per exercice plus taxation d'office for failure to produce them).

**Why it happens:**
Backups get configured at the infrastructure layer, where the unit is the cluster. The unit that matters commercially and legally is the tenant.

**How to avoid:**
- **Two layers:** cluster PITR for disaster recovery *and* scheduled per-tenant logical dumps (`pg_dump` per tenant DB) with independent retention. Per-tenant dumps are what you actually use.
- **Rehearse a single-tenant restore to a scratch database before launch** and write down the runbook. An untested restore is not a backup.
- **Offboarding is an archive, not a drop.** On churn: produce a durable export the client can keep (their factures as PDFs + structured data), retain the archive for the legal period, and only then decommission. Put the retention obligation in the terms and the deletion pipeline. Fold this into pricing — 10 years of cold storage per churned tenant is a real cost.
- **No hard deletes of fiscal documents, ever**, at any layer including tenant-initiated "delete my data." Soft-delete/anonymize personal fields; keep the accounting record. (Note the tension with CNDP erasure rights — resolve with counsel in P0; legal retention normally wins over erasure for fiscal records, but say so explicitly.)

**Warning signs:** backup strategy described only as "managed Postgres has backups." No restore rehearsal. A `DELETE FROM factures` path anywhere. Offboarding designed as `DROP DATABASE`.

**Phase to address:** P1 (backup + archive design), P8 (offboarding/churn flow).

---

### Pitfall 8: Cross-tenant data leak through ambient tenant context

**What goes wrong:**
Tenant identity lives in a request-scoped global. Then: a background job runs without a request and picks up the last-set value; a cached repository or a memoized connection outlives the request; an admin/support tool queries "the current tenant" while impersonating; a websocket connection keeps a stale tenant. One optician sees another optician's clients. Per the project's own constraint, that is a security failure — and the kind that ends a B2B SaaS by word of mouth in a small market.

**Why it happens:**
Ambient context is convenient and works perfectly in the request path, which is the only path anyone tests.

**How to avoid:**
- **Tenant identity travels with the unit of work as an explicit parameter**, not as a global. A repository/query cannot be constructed without a tenant handle. Make the type system or the constructor enforce it.
- **No default/fallback connection.** If tenant resolution fails, the request fails. There must be no "if no tenant then use the main DB" branch.
- Every background job carries its tenant in the job payload and re-resolves it.
- **A permanent guardrail test:** seed two tenants with distinguishable data, run the entire integration suite against tenant A, assert zero rows of tenant B were ever readable. Add a dev/CI mode that logs the tenant of every query and fails on a query with no tenant.
- Support/impersonation is a separate audited code path with an explicit, time-boxed, logged grant — never a boolean flag on your own user.

**Warning signs:** a `CurrentTenant` static/thread-local. Jobs that call `Tenant.current`. Any code path that can produce a query with no tenant.

**Phase to address:** P1, with the guardrail test as a phase deliverable. Re-verified in P6 (sync endpoints are a fresh opportunity to leak) and P8.

---

### Pitfall 9: Duplicate sales from sync retries

**What goes wrong:**
The device posts a sale, the response is lost to a dropped connection, the device retries, the server creates a second sale. Result: stock decremented twice, caisse credited twice, potentially two factures for one transaction — which, given Pitfall 1, is also a numbering violation. The customer is not double-charged (cash already changed hands) so nobody notices until the caisse doesn't reconcile at end of month.

**Why it happens:**
Retry is added as reliability engineering without the idempotency that makes retry safe. And "it succeeded but I didn't hear back" is the failure mode people forget.

**How to avoid:**
- **The idempotency key is generated on the device at the moment the sale is created**, not at send time, and is the sale's permanent identity (a UUID/ULID). Retrying = re-sending the same key. This is exactly why a client-generated reference works: it exists before the network is involved.
- The server keeps a dedupe record per (tenant, key) and **replays the original response** on a duplicate — it must return success with the same result, not a 409 and certainly not a 500. The client must be able to treat a retried success as a success.
- The sale's *effects* (stock movement, caisse entry, facture issuance) are derived from the sale within one transaction, so a deduped sale produces no second effect. Never let the device send the effects separately.
- Apply the same key discipline to every mutating sync operation, including corrections and payments against an existing sale.

**Warning signs:** server-generated primary keys for records that originate offline. A sync endpoint that errors on replay. Dedupe implemented by comparing field values ("same amount + same minute") instead of a key.

**Phase to address:** P6, but the client-generated ID must be the sale's PK from P2 — retrofitting identity is painful.

---

### Pitfall 10: Trusting device clocks

**What goes wrong:**
A tablet's clock is two days off (dead battery, manual change, wrong timezone). Its sales land in the wrong day's caisse total, appear out of chronological order relative to other devices, and — if the device date drives the facture date — produce a legally non-chronological invoice sequence. Conflict resolution based on "latest timestamp wins" silently lets the wrong device win every conflict.

**Why it happens:**
`Date.now()` is right there, and in testing all devices agree.

**How to avoid:**
- **Store both, always, and never conflate them:** `created_at_device` (user-facing metadata, "when the vendeur says it happened") and `received_at_server` (authoritative, monotonic-ish). Every synced record has both.
- **Ordering and conflict resolution use server-assigned monotonic version numbers**, never device time. If you need cross-device causal order without the server, use hybrid logical clocks — but for this project server-assigned sequence is enough and much simpler.
- **The legal facture date is the server date at issuance** (consistent with Pitfall 1). The device date can be shown as "date de vente" on the sale, but it must not drive the fiscal document.
- Measure and record the **clock offset per device** at every sync. Surface a warning in the app when offset exceeds a threshold ("l'heure de cet appareil est incorrecte") — this is cheap and catches the problem at the counter.
- Caisse daily totals are computed on a defined timezone (Africa/Casablanca) using the authoritative date, with an explicit rule for a sale made at 23:55 offline and synced at 09:00 the next day. Decide the rule; don't let it emerge.

**Warning signs:** a single `date` column with no source distinction. Sorting or `MAX()` on device timestamps. Any "last write wins" using client time.

**Phase to address:** P2 (both columns exist from the start), enforced in P6.

---

### Pitfall 11: Stock modeled as a mutable quantity column

**What goes wrong:**
`products.quantity` is an integer that sales decrement and réceptions increment. Then offline sales arrive out of order, an inventory count happens, a réception is corrected, and the number is wrong with **no way to find out why**. You cannot reconstruct history, cannot explain a discrepancy to the owner, and cannot correctly apply a late-arriving offline sale (do you decrement now? that puts it in the wrong day). Concurrent offline sales at two magasins on the last frame produce an oversell you can neither prevent nor explain.

**Why it happens:**
A quantity column is the obvious model, and it works until writes stop being ordered and online.

**How to avoid:**
- **Stock is a ledger of `mouvements_de_stock`** (vente, réception, retour, ajustement d'inventaire, transfert entre magasins, casse), scoped to (magasin, article). Quantity on hand is **derived** — a materialized/cached aggregate you can always recompute from the ledger. A late offline sale is just an event with an earlier effective date; the ledger absorbs it naturally.
- **Accept that offline sales can oversell. You cannot prevent it — stop trying.** Two disconnected devices cannot coordinate. Design for *detection and reconciliation*: allow the derived quantity to go negative, flag it loudly, and produce an "écarts de stock" queue for the owner with the movements that caused it. A system that silently rejects a synced sale to protect stock accuracy is worse — it deletes a real transaction where real money changed hands.
- Never let sync **reject** a sale for stock reasons. The sale happened. Record it, then flag the inconsistency.
- Give each device an "availability as of last sync" indicator so the vendeur knows the number is stale rather than believing a confident wrong number.
- Réception mismatches (ordered 10, received 8, one broken) are their own movements referencing the bon de commande — never "edit the bon de commande to match reality." The gap between commandé and reçu is exactly the data the compte fournisseur needs.

**Warning signs:** a `quantity` column written by more than one code path. A `CHECK (quantity >= 0)` constraint (it will reject real synced sales). No way to answer "why is this 3 and not 5."

**Phase to address:** P2 — this is a schema decision that cannot be retrofitted cheaply. Verification in P6 with concurrent-device simulation.

---

### Pitfall 12: Money as floats, and rounding decided implicitly

**What goes wrong:**
Prices stored as floats; `0.1 + 0.2` shows up in a total. TVA computed on the invoice total in one place and per line in another, so the printed lines don't add to the printed total — which, on a fiscal document that must show TVA ventilated per rate, is a compliance defect, not a cosmetic one. Acompte balances drift by centimes and never settle to zero, so "reste à payer: 0,01 MAD" haunts the client list forever.

**Why it happens:**
Floats are the default numeric type. Rounding is never explicitly decided, so each developer/each screen decides differently.

**How to avoid:**
- **Integer centimes end to end** (MAD subdivides into 100 centimes). Database, API, offline store, mobile. One shared money type in the domain layer used by web, mobile and server.
- **Decide the rounding point once and write it down:** TVA computed and rounded per line, then summed (recommended, matches per-rate ventilation), with a documented rounding mode. Same code on server and client so the offline device and the server agree to the centime.
- **Property/invariant tests:** `sum(line_totals) == total_ht`, `sum(tva_by_rate) == total_tva`, `total_ht + total_tva == total_ttc`, for randomized baskets including odd prices and mixed rates.
- **Never store a derived monetary value that can be recomputed differently elsewhere.** `reste_à_payer` is derived from the payments ledger, not a column that gets updated.
- Store the TVA **rate applied**, not just the amount, per line (see Pitfall 2).
- Discounts (remises) are the classic corruptor: a percentage discount on a line vs on the basket produces different per-line TVA. Pick one, model it explicitly as a line-level amount after distribution.

**Warning signs:** `float`/`double`/`REAL` in any money column. Currency formatting logic in more than one place. A stored balance column.

**Phase to address:** P2 (money primitives), enforced in P4.

---

### Pitfall 13: The caisse drifting from reality

**What goes wrong:**
The caisse has a `balance` column that every operation updates. Then: a sale is edited and the balance is adjusted twice; an offline sale syncs and adds an entry *and* re-updates the balance; a card payment gets added to the cash caisse (it never touched the drawer); an acompte is recorded as full payment. Within a month the owner's caisse balance bears no relation to the cash in the drawer, and since the product's whole premise is "a running ledger of the actual cash," the product is now lying about its core value.

**Why it happens:**
A balance column is faster to read and feels natural. And the mapping from "payment mode" to "cash movement" is assumed obvious rather than enumerated.

**How to avoid:**
- **Append-only ledger; balance is always `SUM(entries)`** for that magasin, optionally cached with a recompute path. No mutable balance.
- **Corrections are compensating entries**, referencing what they correct, with a reason and an author. Never edit or delete a past entry. This also gives the owner an audit trail, which matters given the vendeur/owner trust boundary.
- **Enumerate every payment mode × its caisse impact in a table you can point at**: espèces → caisse entry; carte → no cash entry (or a separate encaissement journal); chèque → not cash on hand until deposited; virement → no caisse entry; crédit/reste à payer → no entry until paid. Get this reviewed by an actual optician before building. Putting card sales in the cash caisse is the single most common version of this bug.
- **Every entry has exactly one cause** (a sale, a payment, a supplier payment, a manual entrée/sortie de caisse) recorded as a foreign key. An entry with no cause is a bug you can query for.
- Sync must be idempotent at the *entry* level, not just the sale level — otherwise Pitfall 9 shows up here as a double credit.
- The project explicitly excludes a formal clôture Z. Fine — but still provide a **read-only "état de caisse" for a date range** with entries listed, so the owner can eyeball it against the drawer. Without a reconciliation view, drift is undetectable until it's large.

**Warning signs:** a `solde` / `balance` column with `UPDATE` statements. Entries without a source reference. Card payments in the cash total.

**Phase to address:** P4. Verification: replay a day of mixed-mode sales including offline ones and assert derived balance equals expected cash.

---

### Pitfall 14: Acompte and partial payment arithmetic

**What goes wrong:**
The classic optician flow — deposit at order, balance at pickup, sometimes a third payment — gets modeled as `acompte_amount` and `paid` boolean on the sale. Then: a second partial payment has nowhere to go; a refund of an acompte on a cancelled commande has nowhere to go; a client who pays for one pair and part of another can't be represented; the reste à payer is stored and diverges. Meanwhile the *fiscal* question — when is the facture issued and when is TVA due, at order or at delivery — was never asked, so the TVA period is wrong.

**Why it happens:**
The happy path is two payments, and two payments fit in two columns.

**How to avoid:**
- **Payments are a ledger** of `(commande/facture, montant, mode, date, encaissé_par, magasin, référence)`. `Reste à payer` is derived. Refunds are negative entries with a reason. This is the same shape as stock and caisse — three ledgers, one pattern, learn it once.
- Model the **commande** (order, with acompte) and the **facture** as separate things with a link. The acompte receipt is not a facture. This falls directly out of Pitfall 1's document split, which is why that decision belongs in P1.
- **Ask an accountant in P0:** for an optician, is the facture issued at the commande or at the délivrance, and when is the TVA due (débits vs encaissements)? Morocco's TVA regime distinguishes régime des débits from régime des encaissements, and the answer changes what your software must produce. Getting this wrong misstates every client's TVA declaration.
- Partial payments taken offline are subject to Pitfall 9 — key them individually.
- Handle the long tail explicitly: cancelled commande with acompte kept vs refunded, client who never returns, a balance settled at a different magasin than where the acompte was taken (which magasin's caisse gets the cash? the answer is "the one that received it" — make sure the model allows it).

**Warning signs:** `acompte` as a column on the sale. A `paid` boolean. A stored `remaining` value. No refund path.

**Phase to address:** P2 (payments ledger), P4 (flow).

---

### Pitfall 15: Permissions-as-data, and the offline payload that ignores them

**What goes wrong, in the order it usually goes wrong:**

1. **The offline sync payload leaks everything.** To work offline, the device downloads the catalogue. The catalogue rows contain `prix_d_achat`. Now every vendeur's phone holds the owner's purchase prices and margins — the exact thing the project says opticians will not tolerate. The API endpoints were carefully permission-checked; the sync bundle was not, because it's "just data for offline." **This is the highest-probability serious failure in this project**, because it sits at the intersection of two features built in different phases by the same person months apart.
2. **Checks in the UI only.** The margin column is hidden in the front end but present in the JSON, the CSV export, the print payload, and the mobile cache.
3. **New permissions default to allow.** You add "voir les achats" in a later release; existing tenants' custom vendeur roles don't have the key, the check is `!== false`, and every vendeur on the platform gains access on deploy day.
4. **New permissions never reach existing tenants.** Inverse of the above: permissions live in tenant databases, so adding one requires a migration fan-out (Pitfall 4). Miss a tenant and the owner can't grant a capability that exists in the UI.
5. **The owner locks themselves out** by editing the owner role's "manage roles" permission. Support ticket requiring you to open their database.
6. **Magasin scope is forgotten.** "Peut voir la caisse" is granted — of *which* magasin? A vendeur at magasin 2 sees magasin 1's takings. Scope is a second axis and it is routinely collapsed into the permission string.
7. **Field-level needs don't fit action-level permissions.** "Can see the article" but "cannot see its prix d'achat and marge" is a *field* rule, not an action rule. A permission system that only guards endpoints cannot express the project's central trust requirement.

**How to avoid:**
- **Permission keys are a fixed catalogue declared in code**, versioned with the app. Roles are tenant data that map to that catalogue. Unknown keys in tenant data are ignored; missing keys are **deny by default**. Never let tenants invent permission keys.
- Adding a permission is a **fan-out migration with an explicit per-tenant default policy** written down in the migration.
- **Two axes minimum:** capability × magasin scope (`all` | specific list). The owner is `all` by construction.
- **Field-level redaction happens in one place** — a serialization/projection layer that takes the actor and strips fields — not in each endpoint. `prix_d_achat`, `marge`, and cross-magasin revenue are redacted fields; enumerate them as a list in code.
- **The offline sync bundle is built by the same projection layer as the API.** Write this down as a hard rule in P3 and re-verify in P6. Test: log in as vendeur, dump the entire local device database, grep for a purchase price. That test should exist in CI.
- The **owner role is immutable and undeletable**; there must always be ≥1 user with full admin. Enforce at the domain level with a clear error, not a DB constraint that produces a 500.
- Enforce at the **query layer** (magasin scope applied to every query builder), so forgetting a check produces no rows rather than all rows.
- Log permission changes — the trust boundary is between colleagues who share an office.

**Warning signs:** permission strings stored free-form. Any `if (user.role === 'owner')` in code (roles are data now; check capabilities). A sync endpoint that returns whole table rows. Export/print paths that bypass the API serializers.

**Phase to address:** **P3, before the feature surface is large** — retrofitting field-level redaction across 40 endpoints is far worse than building it before there are 40. Re-verified as an explicit gate in P6.

---

### Pitfall 16: Offline data loss when a device is lost, wiped, or reinstalled

**What goes wrong:**
A tablet holds 30 unsynced sales — real cash, already collected. It's stolen, factory-reset, or the app is reinstalled after an update, or the vendeur logs out and the app "helpfully" clears local storage. The sales are gone: no facture, no caisse entry, no stock movement, and no way to know what was lost. On mobile, OS-level storage eviction under disk pressure can do this without anyone touching the device.

**Why it happens:**
Local storage is treated as a cache. It is, temporarily, the *only* copy of a financial record.

**How to avoid:**
- **Sync opportunistically and aggressively.** Attempt on every network state change, on app foreground, on a short timer, after every sale. The window where data exists only locally must be minimized, not merely tolerated.
- **Never clear local data on logout, update, or session expiry while unsynced records exist.** Logout with pending items must warn and refuse, or preserve the queue outside the session-scoped store.
- **Prominent pending indicator** — the number of unsynced sales and the age of the oldest, visible on the main screen. The default state of the app should let the user see at a glance what is not yet safe.
- **Escalating pressure and a hard cap.** After N pending items or H hours, the app nags; past a limit it warns strongly ("vos ventes ne sont pas sauvegardées"). Optionally block new offline sales past an extreme threshold — a deliberate product decision, because blocking the counter is the thing you promised not to do. Communicate the tradeoff to the shop rather than deciding silently.
- **Offer a paper/manual escape hatch:** the printed offline document carries the local reference, so a lost sale can be re-entered from the customer's copy.
- Use durable storage (SQLite, not localStorage / non-persisted IndexedDB); request persistent storage permission on web.

**Warning signs:** logout clears the DB. No pending counter. Sync only on a manual button. Local store is localStorage or an in-memory cache.

**Phase to address:** P6, with the pending-count UI as a non-negotiable deliverable.

---

### Pitfall 17: Offline sync that cannot be tested

**What goes wrong:**
Sync is verified by turning airplane mode on and off a few times. The bugs that matter — two devices selling the last frame, a partial sync interrupted mid-batch, a duplicate arriving three days late, a device with a skewed clock, an operation that fails permanently and blocks the queue behind it (head-of-line blocking) — are combinatorial and never reproduce by hand. They surface in production as money that doesn't add up, discovered weeks later with no way to reconstruct what happened.

**Why it happens:**
Sync testing looks like manual QA. It is actually a distributed-systems test problem, and it's easy to defer because the happy path demos beautifully.

**How to avoid:**
Treat the test harness as a **first-class deliverable of P6, built before the sync engine is finished**:

- A **deterministic simulation** with a seeded RNG: N virtual devices, a controllable network that can partition, delay, reorder, duplicate, and fail requests, and a virtual clock per device (including skew).
- **Invariants asserted after every simulated run**, regardless of scenario: no duplicate facture numbers; facture numbers contiguous per series; caisse balance == sum of entries; stock == sum of movements; every device-created sale exists exactly once on the server; sum of payments per commande matches.
- **Named scenarios** kept as regression tests: two devices sell the last item; device syncs after 3 days offline; app killed mid-sync; a permanently-failing operation (validation error) does not block the queue behind it; device clock 48h off; the same sale retried 5 times.
- **A dead-letter queue with visibility.** Operations that can never succeed must land somewhere a human sees, not retry forever or be dropped. Modeling sync as binary success/failure is the standard cause of infinite retry loops and silent loss.
- Server-side: keep the raw inbound sync payloads for a retention window. When a shop says "a sale is missing," you need forensics.

**Warning signs:** no sync tests in CI. Sync correctness argued rather than asserted. No dead-letter concept. "We'll test it with real shops."

**Phase to address:** P6, harness first.

---

### Pitfall 18: Ordonnance modeled as loose numbers

**What goes wrong:**
Sphère, cylindre, axe, addition, écart pupillaire are stored as free-text or unconstrained floats. Then: a cylinder is entered in plus-convention while the labo expects minus (transposition), producing a wrong lens; an axis of 175 is typed 17; addition is applied to the wrong eye; écart pupillaire is stored as one binocular number when the labo needs monoculaire for progressives; OD/OG gets confused with OD/OS. Because the ordonnance feeds the commande spéciale to the fournisseur, each error is a physical remake — real cost, and the shop blames your software. Separately, a renewal *overwrites* the existing ordonnance, destroying the history the product promises and making renewal reminders impossible.

**Why it happens:**
It looks like five number fields. It's a domain with conventions, valid ranges, and a sign ambiguity that changes the meaning of the value.

**How to avoid:**
- **Fix and document the sign convention** (cylindre négatif is standard practice) and store the convention with the record. Offer transposition as a display helper, never as silent conversion.
- **Constrain and validate at entry**: sphère typically −20.00..+20.00 in 0.25 steps; cylindre 0..−10.00 in 0.25 steps; axe integer 0..180 (not 0..360); addition +0.75..+4.00; EP per eye, in mm, with a plausible range. Reject or warn on out-of-range instead of passing garbage to a labo.
- **Écart pupillaire monoculaire par œil**, with binocular derived — not the reverse.
- **Ordonnances are append-only versions**, never updated in place. A renewal creates a new record; the old one stays, dated. This is required for the renewal reminder and for "make the same glasses again."
- **Record the prescriber and its type.** Moroccan regulation (dahir on the profession d'opticien-lunetier, per secondary sources) requires a doctor's ordonnance for subjects under 16, for acuity ≤6/10 after correction, and for strong ametropia or presbyopia inconsistent with age; otherwise the optician may determine correction by the subjective method. So the model needs `source: ordonnance médicale (with prescriber + date) | réfraction opticien` — not an assumption that every prescription came from an ophthalmologist. Client date of birth is therefore a meaningful field, and a warning for under-16 without a medical ordonnance is a genuinely useful, differentiating feature.
- The **commande spéciale to the fournisseur must render an unambiguous, human-readable prescription block** with eye labels, signs and convention stated. Have a real optician review that output before shipping.

**Warning signs:** prescription fields as strings. No axis range validation. An `UPDATE ordonnances` statement. No prescriber field.

**Phase to address:** P2. Verification: an optician reviews sample commande spéciale output.

---

### Pitfall 19: Self-serve subscriptions on Moroccan payment rails

**What goes wrong:**
The v1 bar is "signup, subscription, onboarding with no manual setup." Then reality: card payment in Morocco requires a **merchant contract in your company's name with a CMI-partner acquiring bank**, which requires a registered Moroccan company (RC, ICE, professional bank account) and takes administrative weeks-to-months that no amount of coding compresses. Reported costs sit around 1.5–3.5% per transaction plus setup fees of roughly 500–5,000 MAD and possible monthly fees (MEDIUM/LOW confidence — vendor and blog sources, negotiate and verify directly). Truly automatic recurring billing with card-on-file is **not a given** on Moroccan rails the way it is with Stripe; aggregators (Payzone, ChariPay/ChariBaaS) advertise tokenization, subscriptions, retries and dunning, but these are vendor claims that must be validated against a real contract and sandbox before the roadmap depends on them. Meanwhile Stripe/Paddle do not reliably serve locally-issued Moroccan cards, so the usual fallback isn't there.

**Why it happens:**
Payment integration is scheduled as a late phase and assumed to be an API problem. Most of it is a paperwork-and-lead-time problem.

**How to avoid:**
- **Start the company + bank + gateway paperwork in P0**, in parallel with development. It is the longest lead-time item in the entire project and it is not code.
- **Validate the recurring-billing claim with a sandbox contract before designing the billing model.** If true card-on-file recurring isn't available, the product falls back to *invoice + payment link per period* — which changes onboarding, dunning, and churn UX substantially. Discovering this in P8 is a phase-sized surprise.
- **Design the subscription layer gateway-agnostic**: your own subscription/period/invoice model with the gateway behind an interface. You will likely change or add providers.
- **Never let billing block the shop from selling.** A subscription check failure, an expired card, or your billing service being down must degrade to a banner, never to a blocked caisse. An optician who cannot serve a customer because your Stripe-equivalent had a 500 will churn immediately and tell other opticians. Entitlement is cached locally with a long grace period.
- **Dunning is a designed flow, not an error path**: retry schedule, notification in French, grace period, then read-only (never data deletion — see Pitfall 7).
- **You must issue your own compliant Moroccan factures to your subscribers**, with TVA and sequential numbering, subject to the same rules and the same coming e-invoicing mandate. Budget for it; consider using your own facturation engine (good dogfooding) but note your own numbering series is separate from any tenant's.
- Offer bank transfer / virement as a first-class annual option. In this market it may outperform cards for B2B, and it de-risks the whole gateway dependency.

**Warning signs:** the roadmap has "integrate payments" as a two-week task. No company registered. Recurring billing assumed from marketing pages. Subscription status checked synchronously on the sale path.

**Phase to address:** P0 (paperwork, immediately), P8 (implementation).

---

### Pitfall 20: The scope itself — a solo developer building a platform, an ERP, a sync engine, and two clients

**What goes wrong:**
This is the pitfall most likely to actually kill the project, so it gets stated plainly. The v1 bar as written contains, independently:

- a multi-tenant **control plane** (provisioning, migration fan-out, per-tenant backup/restore, tenant registry) — a platform product;
- an **ERP-shaped domain**: clients, ordonnances, stock, fournisseurs, achats, compte fournisseur, facturation, caisse, reminders — six or seven modules, each of which is a small product;
- a **legally-valid fiscal document engine** in a specific jurisdiction, with a compliance mandate arriving mid-build;
- an **offline-first sync engine** — genuinely one of the hardest categories in application engineering;
- a **customizable permission system** with field-level redaction and magasin scoping;
- **two client platforms at full feature parity**;
- **self-serve signup + subscription billing** on payment rails that require months of paperwork;
- and per-tenant branding on UI and printed documents.

Any one of the first five is a multi-month effort for one person. Together, with no team, this is plausibly a multi-year v1 — and the specific failure mode isn't "it takes long," it's **building all of it to 80% and having zero of it validated by a paying optician**, because the self-serve platform bar means nothing ships until everything ships.

The second failure mode is **sequencing**: building offline sync early (it's the interesting problem) before the domain model is stable, which means every domain change ripples through the sync engine and its test harness.

**How to avoid:**
- **Decouple "first paying customer" from "self-serve platform."** These are different milestones. Manually provisioning the first 5–10 tenants is a few hours of your time each and buys months of validation. The self-serve requirement is a *scaling* requirement, not a *validation* requirement. Keep it as the platform bar; do not let it gate first revenue. Concretely: P8 can come late, provided P1 built the provisioning primitives that P8 wraps in a UI.
- **Build the tenancy foundation properly first anyway** (P1) — that part genuinely cannot be retrofitted, and it's what the manual provisioning script calls.
- **Build online-only first, through a complete sale** (P2→P4). The domain model must be stable *before* the sync engine exists, or you will pay for every schema change twice.
- **Scope offline to the sale path only.** Sell, take payment, record the caisse entry, look up a client and their ordonnance, look up stock read-only. **Not** offline: achats, réception, fournisseur management, role editing, reporting, article creation. Every additional offline entity multiplies conflict cases. Write this boundary into the roadmap as a hard constraint, because it will be tempting to widen it.
- **Mobile: choose the cheapest path to parity you can live with.** "Full parity on two platforms" for one developer means either a shared codebase (PWA installed to home screen, or React Native/Flutter with a shared domain layer) or a permanently late mobile app. Decide the sharing strategy in P1 — the offline store, money type, permission projection and validation should be written once. Note the PWA-on-iOS storage caveat interacts with Pitfall 16.
- **Sequence by risk, not by interest.** The riskiest unknowns are: the legal/fiscal answers (P0, calendar-bound), the tenancy foundation (P1, unretrofittable), the permission projection (P3, unretrofittable at scale), then offline (P6, hard but self-contained if the domain is stable). Payment rails (P0 paperwork) run alongside everything.
- **Defer aggressively within modules.** Reminders, branding, reporting, monthly totals — real value, zero structural risk, safe to move to the end. Do not build them while the sale path is incomplete.
- **Set a validation checkpoint:** get a real optician using the online-only version in their shop before the offline engine is built. Their feedback will change the domain model, and you want that change to happen *before* it costs you a sync engine rewrite.

**Warning signs:** month 8 with nothing in a real shop. Building the sync engine before a complete online sale works end to end. "Full parity" mobile started before the web app's domain is stable. Reminders/branding built while facturation is unfinished.

**Phase to address:** roadmap structure itself. This pitfall is a constraint on phase *ordering*, not a task in any phase.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Mutable `quantity` / `solde` columns instead of ledgers | Simple reads, fast to build | Unreconstructable state once offline writes arrive; no audit trail; owner cannot be shown *why* | Never — this is the schema decision that defines the project |
| Facture number allocated client-side | Instant printing offline | Legal non-compliance for your customers; unrepairable retroactively | Never |
| Floats for money | Any ORM default | Centime drift, totals that don't reconcile, invalid fiscal documents | Never |
| Permission checks in the UI/endpoint rather than a projection layer | Ships each screen faster | Field-level leaks via export, print, and the offline bundle; retrofit touches every endpoint | Never, given prix d'achat is the core trust requirement |
| Migration fan-out as a shell loop | Works at 5 tenants | Split-brain schema across the fleet; unrecoverable without manual per-tenant SQL | Only before the first external tenant, and only with a dated ticket to replace it |
| Provisioning inside the signup request | One less moving part | Zombie tenants, charged-but-undelivered accounts, support load | Only while you provision manually and no self-serve signup exists |
| Manual tenant provisioning (no self-serve) | Months of roadmap saved; earlier revenue | Doesn't scale past ~20 tenants; your time per customer | **Recommended** for the first 5–10 customers — the deliberate trade that de-risks the whole project |
| PDF as the durable facture record | Simple, matches what users see | Cannot produce UBL for the DGI mandate; cannot re-render with corrected branding; no queryable fiscal data | Never — store structured, derive the PDF |
| Single shared Postgres instance for all tenants | Cheap, simple ops | Noisy-neighbour, connection ceiling, one incident affects everyone | Yes for v1, provided the tenant registry holds a per-tenant host from day one |
| Offline for read-only lookups but not writes, in an early version | Removes all conflict handling | Doesn't meet the core value promise | Acceptable as an *intermediate* release; not as v1's end state |
| No dead-letter queue in sync ("just retry") | Less code | Infinite retry loops, head-of-line blocking, silent data loss | Never in a money path |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| CMI (via bank) | Assuming it's an API signup like Stripe; scheduling it as a dev task | It's a merchant contract with an acquiring bank requiring a registered Moroccan company; start paperwork in P0, weeks-to-months lead time |
| Payzone / ChariPay (aggregators) | Trusting marketing claims of recurring billing, tokenization, dunning | Validate in a sandbox against a real contract before the billing model depends on it; design gateway-agnostic |
| Any payment gateway | Synchronous subscription check on the sale path | Cache entitlement locally with a long grace period; billing failure must never block a sale |
| DGI e-invoicing (future) | Planning to "add it later" to a PDF-based facture | Store structured, article-145-complete data with a clearance lifecycle now; integrate when the décret and technical specs are actually published |
| DGI e-invoicing | Building against blog-reported dates and thresholds | The décret was unpublished as of March 2026; re-verify against the Bulletin Officiel and DGI portal before committing roadmap time |
| CNDP | Treating it as a privacy-policy page | Health data needs *prior authorization* (2–4 months), not a declaration; also decide hosting jurisdiction before tenant DBs exist |
| Fournisseur / labo ordering | Emailing a free-text prescription | Structured, convention-explicit prescription block on the bon de commande, reviewed by an optician |
| Email/SMS for reminders | Sending from a generic sender; ignoring local deliverability and consent | Per-tenant sender identity, opt-out on client records, and a Moroccan SMS provider — client follow-up messages are marketing to a data subject |
| PgBouncer | Session-level state (`SET search_path`, session vars) under transaction pooling | Tenancy must not depend on session state; pass tenant explicitly per unit of work |
| Managed Postgres provider | Assuming `CREATE DATABASE` is unrestricted and unlimited | Verify per-instance database limits, `CREATE DATABASE` permissions, and whether their backup tooling is per-cluster only, **before** committing to DB-per-tenant |
| Object storage (logos, PDFs) | Shared bucket with tenant-guessable paths | Per-tenant prefixes with signed URLs; never serve tenant assets from a public path derived from a sequential ID |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| One connection pool per tenant DB | `FATAL: too many connections` correlated with customer count, not traffic | PgBouncer transaction mode + bounded LRU app-side pool manager + global cap | ~50–150 tenants per app instance, depending on pool size |
| Migration fan-out serial and blocking | Deploys take hours; deploy window during business hours breaks shops | Concurrent bounded runner, resumable, backwards-compatible migrations, canary tenants | ~100 tenants |
| Nightly job opening every tenant DB at once | Errors clustered at a fixed hour | Bounded concurrency for cross-tenant jobs, staggered scheduling | ~100 tenants |
| Per-database overhead (autovacuum workers, catalog, backup jobs) | Rising baseline CPU/IO with no traffic change | Budget tenants per cluster; per-tenant host in the registry from day one | Low thousands of DBs per instance |
| Derived stock/caisse recomputed from the full ledger on every read | Slow product list, slow caisse screen, worsening monthly | Cached aggregate (per magasin/article) updated transactionally, with a recompute-from-ledger path | ~50–100k movements per tenant, i.e. year 2 for a busy shop |
| Full-catalogue sync bundle on every device sync | Mobile data cost, slow sync, battery; shops on 3G | Delta sync with a server-assigned change cursor; full bootstrap only on first install | ~2–5k articles, or any shop on a weak connection |
| Unbounded offline queue replay | Device offline for days then a multi-minute sync that can be interrupted | Batched, resumable, checkpointed sync with per-batch acknowledgement | 200+ pending operations |
| Owner "all magasins" reports as N per-magasin queries | Owner dashboard slow, worsens with each new magasin | Aggregate in one query within the tenant DB (this is precisely why magasins share a DB — use it) | 5+ magasins |
| PDF generation synchronous in the request | Timeouts when printing a facture | Generate async or keep the renderer warm; cache the artifact | Immediately under any load |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Tenant identity as ambient/global state | Cross-tenant data exposure — a business-ending failure in a small market | Tenant travels with the unit of work; no default connection; permanent two-tenant guardrail test in CI |
| Tenant identifier interpolated into a database name or connection string | SQL/connection-string injection at provisioning time | Generate identifiers server-side; strict allowlist; never accept user input into a DB name |
| Offline sync bundle bypassing the permission projection | Vendeur's device holds `prix d'achat`, margins, cross-magasin revenue — the exact trust boundary the product sells | One projection layer for API, export, print and sync; CI test that dumps a vendeur device DB and greps for purchase prices |
| Unencrypted local device storage | Lost/stolen tablet exposes client health data (ordonnances) and sales | OS-level encryption + app-level encryption of the local store; remote-wipe/device-revocation via token invalidation |
| Long-lived device tokens with no revocation | Ex-employee's phone keeps syncing and reading client data | Per-device registration, owner-visible device list, one-click revoke, short-lived access tokens with refresh |
| Ordonnance data treated as ordinary business data | It is health data under law 09-08 — sensitive category, CNDP prior authorization, higher breach consequences | Classify it explicitly; restrict access by permission; audit reads if feasible; include it in the CNDP filing |
| Hard-deleting client data on a privacy request | Destroys fiscal records you're required to keep 10 years (art. 211 CGI) | Anonymize personal fields, retain the accounting record; document the policy with counsel |
| Tenant-supplied SVG logo rendered inline | Stored XSS across that tenant's users, and into generated PDFs | Accept raster only (or sanitize/rasterize SVG server-side); serve from a separate origin; size and dimension limits |
| Tenant branding colors injected into CSS | CSS injection; also unreadable UI | Parse and validate as color values; inject as CSS custom properties, never as raw strings |
| Support/impersonation as a flag on your own account | Silent, unaudited access to customer businesses | Separate audited, time-boxed grant; visible to the tenant; logged |
| Control-plane database reachable with tenant-level credentials | One compromised tenant path reaches every tenant's connection info | Separate credentials and network path for the control plane; tenant connection secrets encrypted at rest |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No visible offline/sync state | Vendeur doesn't know if a sale is safe; discovers loss days later | Persistent indicator: online/offline, pending count, oldest pending age — prominent, not buried in settings |
| Offline document that looks like a facture | Customer receives something that isn't legally a facture; confusion and disputes | Clearly labelled "Bon de commande / Reçu d'acompte", with the facture issued and delivered after sync; explain in the UI |
| Showing a confident stock number offline | Vendeur promises a frame that was sold at the other magasin an hour ago | Show stock with an "as of last sync" qualifier when stale; visually distinguish stale data |
| Anglicised or translated domain terms | Staff can't map the software to their job; training cost; the project explicitly warns against this | Keep French domain vocabulary in UI *and in code*: ordonnance, magasin, caisse, fournisseur, facture, acompte, bon de commande, réappro |
| Making the vendeur choose the magasin on every action | Constant friction, and eventually a sale posted to the wrong caisse | Bind magasin to the device/session; changing it is a deliberate, visible act |
| Reminder features that fire indiscriminately | Notification fatigue; owner turns everything off; the feature dies | Thresholds configurable per tenant; digest rather than per-event; respect client opt-out |
| Full-parity mobile that's a shrunken desktop UI | Unusable at the counter, staff go back to the computer | Design the mobile *sale path* for one-handed counter use; parity means capability, not identical layout |
| Prescription entry as free-form fields | Typos become wrong lenses and costly remakes | Steppers/pickers with valid increments, range validation, and a review step before the labo order |
| Silent conflict resolution | Owner discovers a changed record with no explanation | Surface conflicts and stock écarts in an explicit review queue with what happened and who did it |
| Onboarding that dumps an empty system on a new tenant | Optician abandons during trial | Guided setup: magasin, TVA settings, a starter catalogue/fournisseur import, first sale walkthrough — this *is* the self-serve product |

## "Looks Done But Isn't" Checklist

- [ ] **Facturation:** often missing the avoir (credit note) path with its own series, and a delete-prevention guarantee at the DB level — verify you cannot delete or renumber an issued facture through *any* path, and that a cancelled facture produces an avoir.
- [ ] **Facturation:** often missing the full article-145 mention set — verify ICE (seller and B2B client), IF, RC, taxe professionnelle, TVA ventilated per rate, mode de paiement all print, and are stored as data not just rendered text.
- [ ] **Facture numbering:** often missing the concurrency case — verify two simultaneous issuances under load produce contiguous numbers with zero duplicates and zero gaps, including across an exercice boundary.
- [ ] **Offline sync:** often missing the retry-after-lost-response case — verify a duplicate submission returns the original result, not an error and not a second sale.
- [ ] **Offline sync:** often missing the permanently-failing operation — verify a rejected operation lands in a dead-letter queue and does not block the operations behind it.
- [ ] **Offline sync:** often missing the permission projection — verify a vendeur's device store contains no prix d'achat, marge, or other-magasin data.
- [ ] **Caisse:** often missing the payment-mode mapping — verify a card sale does not increase the cash balance and a crédit does not either.
- [ ] **Caisse:** often missing recompute — verify the displayed balance equals the sum of entries after a day mixing online, offline, corrections and refunds.
- [ ] **Stock:** often missing the negative case — verify an oversell from two offline devices is recorded (not rejected) and surfaces in an écarts queue.
- [ ] **Stock:** often missing réception mismatch — verify partial and over-delivery against a bon de commande, and that the compte fournisseur reflects received, not ordered.
- [ ] **Acompte:** often missing the third payment, the refund, and the cross-magasin settlement — verify reste à payer is derived and reaches exactly zero.
- [ ] **Permissions:** often missing non-API surfaces — verify exports, PDFs, print payloads, reports and the sync bundle all apply the same redaction.
- [ ] **Permissions:** often missing lockout protection — verify the owner cannot remove their own admin capability and that ≥1 full admin always exists.
- [ ] **Permissions:** often missing magasin scope — verify a vendeur scoped to magasin 2 cannot read magasin 1's caisse, stock or clients through any endpoint.
- [ ] **Tenancy:** often missing partial-failure recovery — verify the migration runner resumes after being killed mid-fan-out and converges every tenant.
- [ ] **Tenancy:** often missing restore — verify you have actually restored one tenant to a point in time, into a scratch DB, following a written runbook.
- [ ] **Signup:** often missing the failure paths — verify each provisioning step can fail and be retried, and that the reconciler cleans up zombies without a human.
- [ ] **Signup:** often missing what happens after — verify a brand-new tenant can reach a first completed sale without support.
- [ ] **Branding:** often missing print — verify tenant logo and name appear on the generated facture and bon de commande, not only in the web UI.
- [ ] **Mobile:** often missing the reinstall/logout case — verify unsynced sales survive an app update, a logout attempt, and a background kill.
- [ ] **Billing:** often missing degradation — verify the caisse still works when the payment provider is unreachable and when a subscription is past due.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Facture numbering broken in production (gaps/duplicates) | **HIGH** — possibly unrecoverable | Stop issuance immediately. Documents already given to customers cannot be renumbered. Work with an expert-comptable on a régularisation (typically avoirs + reissue), disclose to the affected tenant, then fix the model. This is why it must be right in P1. |
| E-invoicing arrives and the facture data is unstructured | HIGH | Rebuild the facture model; historical invoices may be unconvertible and must be handled by whatever transitional rule the DGI provides. Mitigated to LOW if the structured/lifecycle design was in place. |
| Tenants split across schema versions after a failed fan-out | MEDIUM | Query the tenant registry for laggards, resume the runner; if the registry doesn't exist, inspect each DB manually — this is the cost of skipping P1. Roll the app back to the version compatible with the older schema first. |
| Zombie/half-provisioned tenants | LOW–MEDIUM | Reconciler sweep + manual cleanup script; refund or complete the charged ones. Cheap if the signup state machine exists, painful if not. |
| Cross-tenant leak discovered | HIGH (reputational, legal) | Contain, determine scope from query logs, notify affected tenants and likely the CNDP, then add the guardrail test. Recovery is mostly non-technical. |
| Duplicate sales already synced | MEDIUM | Detect by idempotency key or by sale fingerprint; reverse with compensating entries in stock and caisse (never delete); reconcile with the shop. Add keys and backfill. |
| Stock drifted from physical reality | LOW | Physical inventory count → an `ajustement d'inventaire` movement per article. Trivial *if* stock is a ledger; near-impossible to explain if it's a mutable column. |
| Caisse balance drifted | LOW–MEDIUM | Recompute from the ledger; if the ledger itself has phantom or missing entries, reconstruct from sales + payments and record compensating entries with a reason. |
| Unsynced sales lost with a device | MEDIUM | Re-enter from the customer's printed copy using its local reference; the reference is what makes this recoverable at all. Otherwise the money is unaccounted for. |
| Connection exhaustion outage | LOW (once) | Add/tune PgBouncer, cut app pool sizes, restart. Recurs until the pool manager is bounded. |
| Payment gateway can't do recurring billing | MEDIUM | Pivot to invoice + payment link per period; rework onboarding and dunning UX. LOW if the billing layer was gateway-agnostic. |
| Permission model can't express field-level rules | HIGH | Retrofit a projection layer across every serialization surface. This is why P3 precedes the feature surface. |
| Wrong TVA rate applied historically | HIGH | Régularisation with the tax authority per affected tenant, potentially avoirs on every affected facture. Prevent in P0 by confirming rates with an accountant. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Facture number allocated offline | P1 (document model + counter), P4, P6 | Concurrency test: 0 duplicates, 0 gaps; a facture cannot be created by the sync payload |
| 2. Blind to DGI e-invoicing mandate | P0 (confirm status), P2/P4 (data shape) | Can emit a complete article-145 structured record + UBL-shaped export from stored data alone |
| 3. CNDP authorization for health data | P0, continuous | Filing submitted before the first external tenant; hosting jurisdiction decided and documented |
| 4. Migration fan-out as a loop | P1 | Kill the runner mid-fan-out over 200 tenants; restart; all converge; registry answers "who is behind" |
| 5. Provisioning failure mid-signup | P1 (mechanics), P8 (flow) | Fail-inject each step; reconciler converges with no human action |
| 6. Connection pool exhaustion | P1 | 200 tenants touched within a minute; connection count under budget; no session-state dependency |
| 7. No per-tenant restore / illegal deletion | P1, P8 (offboarding) | A rehearsed single-tenant PITR into a scratch DB, with a written runbook; churn produces an archive, not a drop |
| 8. Cross-tenant leak | P1 (permanent guardrail), re-check P6, P8 | Two-tenant suite asserts zero cross-reads; CI fails on any query without a tenant |
| 9. Duplicate sales on retry | P2 (client-generated IDs), P6 | Same key sent 5× produces one sale, one caisse entry, one stock movement, identical responses |
| 10. Clock skew | P2 (both timestamps), P6 | Simulation with 48h-skewed device: correct caisse day, correct chronological numbering |
| 11. Stock as mutable quantity | P2 | Derived quantity recomputes exactly from the ledger after out-of-order offline arrivals; oversell surfaces in an écarts queue |
| 12. Float money / implicit rounding | P2 | Property tests on randomized baskets: lines sum to totals; server and device agree to the centime |
| 13. Caisse drift | P4 | Mixed-mode day replay: derived balance == expected cash; card/crédit excluded |
| 14. Acompte/partial payment arithmetic | P2 (payments ledger), P4 | Three payments + a refund + cross-magasin settlement reaches exactly zero |
| 15. Permissions-as-data + sync leak | **P3, before the feature surface grows**; gate in P6 | Vendeur device store contains no prix d'achat; new permissions default-deny; owner cannot self-lock |
| 16. Offline data loss on device loss/reinstall | P6, P7 | Unsynced sales survive update, logout attempt, and background kill; pending count visible |
| 17. Untestable sync | P6 (harness first) | Named scenarios in CI with invariants asserted every run; dead-letter queue visible |
| 18. Loose ordonnance model | P2 | Range/convention validation; append-only versions; an optician approves the commande spéciale output |
| 19. Moroccan payment rails | P0 (paperwork), P8 | Sandbox proves recurring billing before the model depends on it; caisse works with billing down |
| 20. Scope & sequencing | Roadmap structure | A real optician uses the online-only version in their shop before the sync engine is built |

## Open Questions Requiring a Human Expert (not more search)

These could not be resolved authoritatively and each one, answered wrong, is expensive:

1. **Which TVA rate(s) apply** to montures, verres correcteurs, lentilles, produits d'entretien, and to optician services in Morocco post-2026 reform. → Expert-comptable. Blocks P2/P4.
2. **Is a separate numbering series per magasin legally acceptable**, or must a tenant maintain one continuous series across all its magasins? This determines whether the counter is per (tenant, série) or per (tenant, magasin) and it is a schema decision. Search found no authoritative answer. → Expert-comptable. Blocks P1.
3. **When is the facture issued and TVA due** for an optician's acompte-then-delivery flow — régime des débits vs encaissements, and does the acompte itself require a fiscal document? → Expert-comptable. Blocks P4.
4. **Current status of the e-invoicing décret** and the confirmed calendar/thresholds for the sub-10M-MAD segment. → DGI / Bulletin Officiel, re-check quarterly.
5. **CNDP: controller vs processor split** in a multi-tenant health-data SaaS, whether you file or your clients do (or both), and permitted hosting jurisdictions. → Privacy counsel. Blocks first external tenant.
6. **Whether card-on-file recurring billing is actually available** to a small Moroccan SaaS via CMI/Payzone/ChariPay, and the real onboarding lead time and pricing. → Direct contact + sandbox contract. Blocks P8 design.
7. **Record-keeping obligations specific to opticians** (register of prescriptions delivered, retention of ordonnances) under the Moroccan dahir on the profession — the primary text was not machine-readable. → Legal / professional association.
8. **What the payment-mode → caisse mapping should be**, validated against how real Moroccan optician shops handle chèque, crédit client, and card. → Interview 2–3 opticians before building P4.

## Sources

**Moroccan legal/fiscal (secondary sources — consulting firms and invoicing vendors; MEDIUM confidence, all flagged for expert confirmation):**
- Facturation électronique Maroc 2026, Upsilon Consulting (art. 145-IX CGI; décret unpublished as of March 2026; UBL 2.1/CII; clearance model) — https://www.upsilon-consulting.com/facturation-electronique-maroc-2026/
- Morocco electronic invoicing, EDICOM — https://edicomgroup.com/blog/morocco-electronic-invoicing
- Mentions obligatoires article 145 CGI, INEO — https://www.ineo.ma/blog/Est-ce-que-votre-facture-contient-les-mentions-obligatoires-prevues-par-l-article-145-du-Code-General-des-Impots
- Mentions obligatoires sur une facture au Maroc, AMDE — https://amde.ma/les-mentions-obligatoires-sur-une-facture-au-maroc/
- Gestion des avoirs / annuler une facture au Maroc, GetQuickBill — https://getquickbill.com/blog/gestion-des-avoirs-maroc
- Réforme TVA Maroc 2024-2026 (convergence to 20%/10%), Upsilon Consulting — https://www.upsilon-consulting.com/reforme-tva-maroc-2024-2026/
- Article 211 CGI, conservation des documents comptables (10 ans), Fiscamaroc — https://www.fiscamaroc.com/dispositions-communes-208/conservation-documents-comptables-316.htm
- Conservation des documents comptables au Maroc (sanctions), Quantis Partners — https://bsauditconseil.com/conservation-documents-comptables/

**Moroccan data protection:**
- CNDP, Loi 09-08 — https://www.cndp.ma/loi-09-08/
- CNDP, Formalités (déclaration vs autorisation) — https://www.cndp.ma/formalites/
- Déclaration ou autorisation CNDP (art. 23, health data = prior authorization, 2–4 month review) — https://avocat-jawhari.com/2025/12/18/declaration-autorisation-cndp/
- Loi 09-08 et données médicales, TabibDoc — https://tabibdoc.ma/blog/reglementation-donnees-medicales-maroc-loi-09-08

**Moroccan optician profession (MEDIUM — primary PDF not machine-readable):**
- Exercice de la profession d'opticien-lunetier au Maroc (dahir), SGG — https://www.sgg.gov.ma/Portals/0/profession_reglementee/dah_opt_fr.pdf
- Droit et devoir de l'opticien marocain (art. 5: <16 ans, acuité ≤6/10, amétropies fortes require a medical ordonnance; méthode subjective otherwise) — https://lopticomaroc.com/droit-et-devoir-de-lopticien-marocain/

**Moroccan payments (LOW–MEDIUM — vendor marketing and blog comparisons; verify contractually):**
- CMI, solution de paiement e-commerce — https://www.cmi.co.ma/fr/solutions-paiement-ecommerce
- Paiement récurrent et abonnements au Maroc, ChariBaaS — https://www.baas.ma/fr/blog/paiement-recurrent-abonnement-maroc
- Payzone SaaS — https://payzone.ma/saas/
- Paiement en ligne au Maroc 2026 : CMI, Payzone, Stripe — https://digitoyou.com/blog/paiement-en-ligne-maroc-cmi-stripe-2026/
- CMI, cession de contrats (Conseil de la concurrence) — https://conseil-concurrence.ma/wp-content/uploads/2024/09/Communique-CMI.pdf

**Offline-first / sync engineering (HIGH — corroborated across independent practitioner sources):**
- The Hidden Problems of Offline-First Sync: Idempotency, Retry Storms, and Dead Letters — https://dev.to/salazarismo/the-hidden-problems-of-offline-first-sync-idempotency-retry-storms-and-dead-letters-1no8
- What We Learned Building Offline-First Software for the Field (duplicate records, clock skew, 4-hour syncs) — https://thefieldco.com/blog/offline-first-field-software/
- Offline-First: Outbox, Idempotency & Conflict Resolution — https://www.educba.com/offline-first/
- Optimizing POS Data Protection and Offline Sync in Odoo — https://bytelegions.com/odoo-pos-offline-sync-data-protection/

**Multi-tenant Postgres (MEDIUM–HIGH):**
- Connection pool exhaustion causes & fixes — https://web-alert.io/blog/database-connection-pool-exhaustion-too-many-connections-guide
- Fixing 'Connection Pool Exhausted' errors — https://oneuptime.com/blog/post/2026-01-24-connection-pool-exhausted-errors/view
- Performance isolation in a multi-tenant database environment, Cloudflare — https://blog.cloudflare.com/performance-isolation-in-a-multi-tenant-database-environment/
- Migrating Millions Of Databases, Scaling Postgres 374 — https://www.scalingpostgres.com/episodes/374-migrating-millions-of-databases/
- Running a safe database migration using Postgres, Retool — https://retool.com/blog/running-safe-database-migrations-using-postgres

**Comparable POS compliance regimes (context, not Moroccan law):**
- NF525 certification of POS software (France: a validated sale cannot be modified, must be secured, retained, producible to the tax administration) — https://infocert.org/en/nf525/
- Sequential invoice numbering compliance guide, Fonoa — https://www.fonoa.com/resources/blog/what-is-sequential-invoice-numbering

---
*Pitfalls research for: multi-tenant SaaS for Moroccan opticians (DB-per-tenant, offline POS, legal facturation)*
*Researched: 2026-09-09*

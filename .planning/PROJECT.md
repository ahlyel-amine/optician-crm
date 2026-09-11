# Optician Management Platform

## What This Is

A multi-tenant SaaS for Moroccan opticians. One platform where an optician business runs its whole day — clients and their ordonnances, stock, fournisseurs and achats, facturation, and a per-magasin caisse — on both web and mobile. Each client business gets its own database, may run one or several magasins, and appears under their own branding.

## Core Value

The counter can complete a sale end to end — find or create the client, attach the ordonnance, take payment (including an acompte), and have it land in that magasin's caisse — producing a facture that is legally valid in Morocco every time.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. -->

**Legal & compliance — calendar time, starts day one**
- [ ] CNDP prior authorization to process ordonnances as health data (law 09-08 art. 23), which is an authorization and not a declaration
- [ ] Hosting jurisdiction chosen early, since the CNDP filing depends on it and it is expensive to reverse
- [ ] Payment merchant contract through a Moroccan acquiring bank — needs a registered company, weeks to months of lead time
- [ ] Client data retained 10 years (art. 211 CGI): churn means archive-then-decommission, never dropping a client's database

**Tenancy & platform**
- [ ] One shared application serving every client, with one database per client business. Onboarding provisions a database — never a new deployment.
- [ ] A client can have several magasins; inside that client's database, stock and caisse are scoped per magasin
- [ ] A control plane that tracks every client database and its schema version, so migrations fan out with a record of who is behind
- [ ] Tenant resolution fails closed — code with no bound client must refuse to run, never fall back to a shared connection
- [ ] Every client database is backed up on a schedule, and restoring one client has been tested rather than assumed
- [ ] The first opticians are onboarded manually, by running the same provisioning the platform uses. Self-serve must not gate the first paying customer.
- [ ] Self-serve signup: an optician creates an account, trials and subscribes with no manual setup from us
- [ ] Subscription billing through Moroccan payment methods (Chari Pay primary, CMI fallback) behind a payment-gateway interface
- [ ] Per-client branding: logo, colors and shop name applied to the UI and to printed documents

**Accounts & permissions**
- [ ] Only the optician (owner) and gérants have logins — floor vendeurs never sign in
- [ ] The owner grants permissions per gérant individually; permissions are data, not fixed role tiers
- [ ] Prix d'achat, margins and business-wide money are owner-only unless the owner explicitly grants them
- [ ] The vendeur who made a sale is recorded as a field on the sale, for tracking rather than access
- [ ] One permission-filtered projection layer shared by the API, exports and printing — so a field hidden in the UI cannot leak through another route

**Clients & ordonnances**
- [ ] Client records with contact details and purchase history
- [ ] Structured ordonnance per client: OD/OG with sphère, cylindre, axe, addition, écart pupillaire
- [ ] Prescripteur and date de prescription recorded on the ordonnance
- [ ] Ordonnance source recorded — ordonnance médicale or réfraction opticien — because Moroccan law does not always require a doctor
- [ ] Ordonnances are versioned append-only, never edited in place
- [ ] The ordonnance feeds lens orders — a commande spéciale carries the prescription to the fournisseur
- [ ] A photo of the paper ordonnance can be attached alongside the structured fields, as evidence for an AMO claim
- [ ] Client and article search is accent-insensitive and tolerant of Arabic transliteration variants — Mohamed, Mohammed and Mhamed find the same person. With no barcode scanning, search *is* the counter UI.

**Stock**
- [ ] Stock per magasin for frames, accessories and stocked lenses
- [ ] Common lens corrections held in stock; unusual corrections ordered specially from the fournisseur/labo
- [ ] Stock is an append-only ledger with derived balances, never a mutable quantity column
- [ ] Stock decrements on sale and increments on réception of a fournisseur delivery
- [ ] A sale warns before it would take stock negative rather than silently overselling; a shortfall the user accepts anyway is recorded as an anomaly for the owner to reconcile
- [ ] Suivi de commande client: statut commandé → prêt → client prévenu → livré
- [ ] Search accepts an exact reference and submits on Enter, so a keyboard-wedge barcode scanner works later without a UI rewrite
- [ ] A physical inventaire can be run: enter counted quantities and post the difference as a stock ajustement
- [ ] Price and reference labels can be printed for articles

**Fournisseurs & achats**
- [ ] Fournisseur directory: contacts, catalogue, negotiated prices, delivery lead times
- [ ] Bon de commande sent to the fournisseur, and réception recorded on arrival
- [ ] Compte fournisseur: running balance owed to each fournisseur, and payments made against it
- [ ] Prix d'achat tracked per item so margin per sale is visible to the owner

**Facturation**
- [ ] Facture in MAD with Moroccan TVA and a sequential legal number
- [ ] The legal number is issued server-side only, from a counter per (client, série, exercice) — never by a device, never from a database sequence, never pre-leased in blocks
- [ ] Submitting the same sale twice — a retried request on a flaky link — never produces two factures; sale creation is idempotent
- [ ] Facture itemisée: monture and verres on separate lines, because AMO reimburses per line
- [ ] Buyer ICE recorded as a first-class field
- [ ] TVA modeled per article and broken out per rate on the facture — never a hardcoded global rate
- [ ] Facture lifecycle status (brouillon → émise → transmise → validée) rather than treating "printed" as final
- [ ] Devis carrying no legal number, printable, and convertible into a facture without re-entering the lines
- [ ] Avoir / retour as the only legal correction path — a facture is never deleted
- [ ] Remise applicable to a line or to the whole sale, with TVA and totals recalculating correctly
- [ ] Print Facture A4, Bon de commande, and an A5 reçu d'acompte so a client leaving a deposit gets printed proof
- [ ] Acompte / paiement partiel: deposit at order, balance on pickup, remainder tracked until settled
- [ ] Payments are an append-only ledger of lines, each carrying its payer, so a future insurer split is a field rather than a migration

**Caisse**
- [ ] One caisse per magasin — a running cash ledger of entries in and out with a current balance
- [ ] Daily and monthly totals read off that ledger
- [ ] A chèque records its date d'échéance and does not count as cash until marked encaissé — a post-dated chèque is not money in the drawer
- [ ] Chèques not yet encaissés are visible with their due dates
- [ ] A non-blocking comptage: enter the cash counted, see attendu versus compté, and store the écart as a note

**Reminders**
- [ ] Stock réappro — item below its threshold, time to reorder
- [ ] Supplier payment due — échéances on achats
- [ ] Client follow-up — renewal nudge for a new ordonnance, new lenses, or a contact lens re-order
- [ ] Relance AMO — a client is reimbursable again 24 months after their last purchase (12 months for children ≤12); remind at month 23

**Tableau de bord**
- [ ] CA du jour and du mois, per magasin and consolidated
- [ ] Marge brute and panier moyen over a chosen period
- [ ] Encours client (restes à payer) and encours fournisseur
- [ ] Owner-facing and permission-filtered — deliberately not a BI tool

**Apps**
- [ ] Web app, French UI
- [ ] Mobile app with full parity — everything the web app does, on phone or tablet

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- **Offline operation** — the application requires a connection. Taken deliberately: it removes the single riskiest phase (a purpose-built sync layer budgeted at 4–8 weeks) and every sync-conflict failure mode with it. The accepted costs are that the counter stops during an outage, and that a competitor advertising local-first sync at 800 DH/year wins that comparison. Reversing this later means retrofitting local storage plus a sync layer, not flipping a flag.
- Mutuelle / tiers payant — in Morocco the patient claims, not the optician, and no local competitor offers a claims module. Kept cheap to add later by modelling payments as lines with a payer.
- Arabic / RTL interface — every local competitor is French-only and sells it as a feature. Arabic *data* must still render (UTF-8 and an Arabic-capable font in the PDF pipeline), since names appear on documents handed to government insurers.
- Logins for floor vendeurs — the optician and gérants operate the system; a vendeur is data recorded on a sale
- A separate deployment per client — one shared application serves everyone; only the database is per client
- A database per magasin — magasins live inside their client's database so the owner sees across all stores without cross-database queries, and a client record is shared between stores
- Full white-label (custom domains, deep theming) — branding only in v1
- An app for the shop's own customers — a 24-month purchase cycle gives no retention loop; a wa.me link covers contact
- Formal clôture Z / certified register (NF525-style) — NF525 is French and Morocco has no equivalent, so building it is pure cost. The caisse stays a ledger, with a non-blocking comptage as the owner's check on a gérant; that is as far as it goes.
- Ticket de caisse on thermal printers — the client needs an itemized A4 original for AMO, and thermal paper fades against a 60-day filing deadline
- Barcode scanning at the counter — no scanner hardware assumed. Search is built scanner-ready at no cost, and printing the labels themselves is in scope.
- Accounting CSV export, part organisme / reste à charge, SAV and retouche tracking, lentilles renewal tracking, inter-magasin stock transfers, advanced statistics — all real, all v2
- DGI e-invoicing integration — not built in v1, but the facture is structured-data-first with a clearance lifecycle and full art. 145 fields, so it stays convertible when the mandate lands

## Context

- **Market**: Morocco. French UI, MAD, Moroccan TVA and facture numbering rules.
- **The market is crowded and cheap, not empty.** Eight live Moroccan competitors, priced between roughly 800 and 4 000 DH/year. That ARPU is why feature bloat is unaffordable and why the exclusions above matter.
- **A competitor advertises local-first offline sync at 800 DH/year**, and that comparison is conceded deliberately (see Out of Scope). The differentiation is depth instead: structured ordonnance, compte fournisseur with échéances, margins hidden from staff, per-gérant permissions.
- **The real local gap is depth**: no competitor advertises a structured ordonnance, compte fournisseur with échéances, per-sale margin hidden from staff, or per-gérant permissions.
- **Buyers**: independent opticians. A client may run a single shop or several magasins; the product must not assume one.
- **Connectivity**: shop internet is not always dependable, and the application requires it. The counter stops during an outage — an accepted trade-off, taken to remove the riskiest work in the project.
- **Domain language is French** — ordonnance, magasin, caisse, fournisseur, facture, acompte, bon de commande, réappro. Keep that vocabulary in the UI and in the domain model.
- **Team**: solo developer, no hard deadline. The scope is ERP-shaped, so sequencing matters more than speed.
- **Trust boundary inside a client**: opticians do not want gérants seeing purchase prices, margins or business-wide revenue. Permissions are a product requirement, not hygiene.

## Constraints

- **Legal — invoicing**: Moroccan TVA and a gapless, chronological, duplicate-free facture series (art. 145 CGI). Gaps are treatable as fraud, and this is the client's tax exposure caused by our software.
- **Legal — health data**: ordonnances require CNDP prior authorization before processing, on a 2–4 month calendar
- **Legal — retention**: 10 years (art. 211 CGI), which constrains offboarding and the cost model
- **Locale**: MAD and French UI — drives formatting and vocabulary
- **Connectivity**: the application requires a connection. Sale submission must still be idempotent, since a retried request on a flaky link must never mint a second facture number.
- **Platforms**: web and mobile at full parity — one shared codebase and API rather than two products
- **Tenancy**: one shared application, one database per client — every request must resolve to the right client database, migrations must fan out across all of them, and a leak across clients is a security failure, not a bug
- **Payments**: Moroccan rails for subscriptions; recurring card-on-file is a vendor claim that must be proven in sandbox before the billing model depends on it
- **Timeline**: no hard deadline — build it right rather than fast

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

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Devis, facture and avoir built as one document model | The research rates devis P1 precisely because the three share a model — cheap together in Phase 6, expensive bolted on later | — Pending |
| Chèque carries a date d'échéance and is not cash until encaissé | Post-dated chèques are heavily used by Moroccan SMEs. Counting one as cash the day it is taken makes the caisse balance lie, which breaks the one thing the caisse is for. | — Pending |
| Non-blocking comptage de caisse | Reverses the earlier exclusion. A pure ledger only records what the gérant chose to record, and gérants now operate the caisse — this is the owner's check, about a day's work, without becoming a formal clôture Z. | — Pending |
| Owner dashboard in v1, not v2 | All eight Moroccan competitors advertise statistics; it is also the screen that shows the owner why they keep paying | — Pending |
| Search tolerant of accents and transliteration variants | With barcode scanning excluded, search is the counter UI. Moroccan names transliterate several ways and an exact-match box would be unusable. | — Pending |
| Django + DRF, not Laravel | Laravel's `stancl/tenancy` would save ~3 weeks of tenancy work, but the developer is fluent in Django and new to Laravel. Django also brings the admin (much of the operator tooling), WeasyPrint, and native `Decimal` for fiscal correctness. | — Pending |
| Tenancy layer hand-built on Django's router | No Django equivalent to `stancl/tenancy` exists, and `django-tenants` is schema-per-client, which contradicts the database-per-client decision. Costed at 2-3 weeks with tests. | — Pending |
| WeasyPrint for A4, not a Chromium sidecar | Pure Python, built for CSS paged media, good accent and Arabic font handling — and it removes a container from the deployment | — Pending |
| React + Vite web SPA now, Expo mobile at Phase 11 | React Native Web is weakest at dense tables, keyboard flows and print CSS, which is exactly the counter UI. Mobile is Phase 11, so a universal app would cost ten phases of friction for a late requirement. | — Pending |
| Typed TS client generated from `drf-spectacular` | Recovers most of the one-language benefit of a TypeScript backend without giving up Django's admin, migrations and `Decimal` | — Pending |
| Money as `Decimal`, never float | TVA per rate, per-line AMO ceilings and MAD rounding are where invoicing software silently goes wrong | — Pending |
| One shared app, one database per client business | Real isolation per paying client without a deployment each; magasins sit inside their client's database so owner-wide views stay ordinary queries. Reconfirmed against a proposal to relax it to schema-per-client. | — Pending |
| Only the optician and gérants log in; permissions granted per gérant | Floor vendeurs never touch the system, so a vendeur is data on a sale rather than an account. Shrinks the permission surface considerably. | — Pending |
| Manual onboarding first; self-serve stays the platform bar | Letting self-serve gate first revenue risks building everything to 80% with zero validation. The manual path calls the same provisioning primitives. | — Pending |
| Server-issued facture numbers, never device-issued | Art. 145 CGI needs a gapless chronological series, so the number must come from a single authority under concurrent creation; a database sequence gaps on rollback | — Pending |
| Stock, caisse and payments as append-only ledgers | Gives full movement history and audit traceability, makes corrections compensating entries rather than edits, and keeps a future insurer split from needing a schema rewrite | — Pending |
| Online only, permanently | Decided after seeing the cost: a purpose-built sync layer was budgeted at 4–8 weeks and rated the project's highest-risk work. Removing it deletes that phase and the whole class of sync-conflict bugs. Accepted costs are recorded in Out of Scope. | — Pending |
| Facture itemisée, per-line TVA, buyer ICE | AMO ceilings are per line, so a lump sum under-reimburses the customer; it also keeps the facture convertible to UBL for the DGI mandate | — Pending |
| Structured ordonnance with prescripteur and source | Prescriptions must feed lens orders and reminders, and Moroccan law distinguishes a medical ordonnance from an optician's refraction | — Pending |
| Morocco first: French UI, MAD, Moroccan TVA | Home market; legal invoicing rules are market-specific and must be right | — Pending |
| Caisse is a running cash ledger, one per magasin | The user was explicit: it should track the actual cash, not act as a formal register with Z closes | — Pending |
| No mutuelle / tiers payant in v1 | The patient claims, not the optician; payments modelled as lines with a payer keep it cheap to add | — Pending |
| Common lenses stocked, unusual ones ordered | Matches how these shops operate, and defines what a commande spéciale is | — Pending |
| All four achats capabilities in v1 | Directory, bon de commande/réception, compte fournisseur and prix d'achat form one flow; a supplier balance needs supplier records to hang off | — Pending |
| Branding-only customization | Covers what clients actually ask for; full white-label is disproportionate for v1 | — Pending |
| Mobile at full parity via one universal codebase | Staff work away from the desk, and two separate products would double the surface for a solo developer | — Pending |
| Local payment rails for subscriptions | Moroccan cards are poorly served by international gateways | — Pending |

## Open Questions

<!-- Need a human — a Moroccan comptable, the DGI, or optician interviews. Not answerable by more search. -->

**Blocking the facturation schema — resolve before that phase:**
- Which TVA rate applies to montures, verres, lentilles and prestations after the 2026 reform
- Whether a facture série per magasin is legal, or a client needs one continuous série per company
- TVA treatment of the acompte (débits vs encaissements), and whether a facture d'acompte needs its own fiscal number
- Whether the facture is issued at commande or at délivrance

**Resolve before the relevant phase, not blocking now:**
- The DGI e-invoicing wave-3 date and threshold — reported January 2027 for businesses of this size, but the implementing décret was reportedly still unpublished as of March 2026
- The CNDP controller/processor split between us and the optician
- Whether Moroccan rails genuinely support recurring card-on-file — a vendor claim, needs sandbox proof
- Payment-mode to caisse mapping, worth an hour with two or three real opticians

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-09 after initialization*

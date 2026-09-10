> **⚠️ DECISIONS TAKEN AFTER THIS RESEARCH — these override what follows**
>
> 1. **Offline operation is OUT OF SCOPE, permanently.** The application requires a connection.
>    Ignore every recommendation below concerning offline sync, local SQLite, sync engines, CRDTs,
>    provisional documents, device-local references, sync conflict handling, and the offline phase in
>    the suggested build order. The facture number is still server-issued from a counter under
>    `FOR UPDATE` (that reasoning holds for concurrent online creation); sale creation must be
>    idempotent so a retried request cannot mint a second number.
> 2. **Tenancy stays one database per client business.** The schema-per-client proposal was
>    considered and declined.
> 3. **Only the optician (owner) and gérants have logins.** Floor vendeurs never sign in — a vendeur
>    is a data field on a sale. Permissions are granted per gérant individually, not by role tier.
> 4. **Manual onboarding comes first**; self-serve remains the platform bar but does not gate the
>    first paying customer.
> 5. **Added to v1:** facture itemisée + buyer ICE, prescripteur + relance AMO, suivi de commande
>    client, avoir/retour.
>
> 6. **The stack is Django + DRF (Python)** — PostgreSQL with one database per client, PgBouncer,
>    Celery + Celery Beat, WeasyPrint for A4 PDF, a React + Vite + TypeScript SPA for web with a typed
>    client generated from `drf-spectacular`, and Expo mobile at Phase 11. **Not Laravel**, not
>    `stancl/tenancy`, not a universal React Native Web app, not `django-tenants` (schema-per-client).
>    The tenancy layer is hand-built on Django's router, costed at 2-3 weeks.
>
> `.planning/PROJECT.md` and `.planning/REQUIREMENTS.md` are authoritative. This file is the research
> record as written, kept for its reasoning and sources.

# Project Research Summary

**Project:** Optician Management Platform (Morocco)
**Domain:** Multi-tenant vertical SaaS — database-per-client, offline-capable POS/caisse, web + mobile parity, Moroccan fiscal invoicing
**Researched:** 2026-09-09
**Confidence:** MEDIUM-HIGH (engineering patterns HIGH; Moroccan fiscal/legal specifics MEDIUM-LOW, dominated by secondary sources)

## Executive Summary

This is an ERP-shaped vertical SaaS wrapped around three hard problems at once: database-per-tenant multi-tenancy, an offline-capable point of sale that must still produce gapless legally-numbered invoices, and a permission model that hides purchase prices and margins from staff. All four researchers converge, independently, on the same core verdict: **do not reach for off-the-shelf sync engines (PowerSync, ElectricSQL) or CRDTs.** Two separate reasons kill them — they assume schema-per-tenant, not database-per-tenant, and they replicate raw rows, which would silently push `prix_achat` onto vendeur devices and defeat the permission model that is this product's actual differentiator. Build instead a purpose-built, server-authoritative command queue: devices push idempotent commands, the server pulls permission-filtered projections down, and every legally- or financially-sensitive value (facture number, stock quantity, caisse balance) is computed server-side from an append-only ledger, never mutated on a device or converged automatically.

The recommended approach is Laravel 13 + stancl/tenancy (database-per-tenant, with real migration fan-out and connection pooling tooling that a solo developer cannot afford to build from scratch) serving a single Expo/React Native Web universal app for web and mobile parity, with PostgreSQL per tenant and a control-plane database holding only tenancy/billing metadata. The facture number is allocated exactly once, server-side, from a per-(tenant, série, exercice) counter row locked with `FOR UPDATE` inside the same transaction that persists the sale — never a Postgres `SEQUENCE` (gaps on rollback), never a pre-leased block to a device (unused numbers are legal gaps under Article 145 CGI). Offline devices print a clearly non-fiscal bon de commande / reçu d'acompte carrying a local reference, and the real facture appears once the device reconnects.

The largest risks are not evenly distributed between code and calendar. Two items — CNDP prior authorization for health-data processing (ordonnances) and the CMI/aggregator merchant-banking paperwork for Moroccan card payments — run on a legal/administrative clock of weeks to months and cannot be compressed by coding faster; they must start on day one, in parallel with everything else. A cluster of open fiscal questions (TVA rate on optical goods, per-magasin vs per-company invoice series, when TVA is due on an acompte) need a Moroccan comptable, not more research, and several of them block schema decisions. Finally, the single biggest structural risk to the project succeeding at all is scope: the declared v1 bar is a full self-serve platform plus a full ERP plus a legally-valid fiscal engine plus a from-scratch offline sync engine plus two client platforms at full parity — a multi-year effort for one developer if built as stated, with the specific failure mode of building everything to 80% with zero paying-customer validation. The recommended mitigation, argued independently by the pitfalls research, is to decouple "first paying customer" (a handful of manually-provisioned tenants) from "self-serve platform" (a later scaling milestone), while still building the tenancy and permission primitives correctly from day one.

## Key Findings

### Recommended Stack

Laravel 13 (PHP 8.4) + `stancl/tenancy` v3.10 gives database-per-tenant provisioning, per-request connection routing, and migration fan-out off the shelf — the two hardest infrastructure capabilities this project needs, and building them solo is estimated at 3-4 weeks plus an ongoing security surface. PostgreSQL 18 per tenant behind PgBouncer (transaction pooling, small per-tenant pools with LRU eviction — pools multiply per (user, database) pair, which is the real connection ceiling with DB-per-tenant, not disk or CPU). A single Expo Router universal app (React Native Web + NativeWind) targets web and mobile from one codebase, backed by Drizzle over `expo-sqlite` (native) and `sqlocal`/OPFS (web) for local storage — chosen specifically because `expo-sqlite`'s web target is alpha-grade and `sqlocal` needs no COOP/COEP headers. Gotenberg (Chromium-in-a-container) renders the legal A4 facture server-side; `expo-print` renders the offline non-fiscal bon de commande on-device. Payments: Chari Pay (ChariBaaS) as primary gateway for recurring subscription billing with CMI as a trust-building fallback, both behind a `PasserelleDePaiement` interface — Stripe/Paddle are ruled out because they poorly serve locally-issued Moroccan cards. Hosting in an EU region (Paris/Marseille), never the US, because of CNDP cross-border transfer rules.

**Core technologies:**
- Laravel 13 + `stancl/tenancy` v3.10: backend + database-per-tenant — the only mainstream framework with battle-tested DB-per-tenant tooling
- PostgreSQL 18 + PgBouncer: per-tenant database engine + connection pooling — sequences, partial indexes, `unaccent`/`pg_trgm` for French name search
- Expo Router (React Native Web) + Drizzle: one universal codebase for web/mobile parity, one local-storage schema for two drivers
- Gotenberg: server-side A4 PDF rendering for the legal facture and bon de commande, with per-tenant branding
- Chari Pay / CMI behind a `PasserelleDePaiement` interface: Moroccan subscription billing, since international gateways don't reliably accept Moroccan cards

### Expected Features

The Moroccan optician software market is crowded, not empty — 8 live competitors at 800-4,000 DH/year. Offline is already claimed by a competitor (OpticWizard, 800 DH/year) so it is a parity requirement, not a moat by itself; the pitch has to rest on depth. The genuine local gap is a structured ordonnance (not free text), a compte fournisseur with échéances, prix d'achat/margin visibility, and owner-customizable permissions — all of which are already in scope. The AMO 24-month reimbursement cycle (CNSS/CNOPS reimburses lunetterie once per 24 months) is an essentially-free, high-value differentiator: a renewal reminder fired off the ordonnance's prescription date is a money-making nudge no competitor advertises, but it only works if the ordonnance captures `prescripteur` and `date de prescription` from day one — retrofitting means backfilling every existing record and the reminder is worthless until backfilled.

**Must have (table stakes), several currently gaps in PROJECT.md:**
- Itemized facture (monture / verres / lentilles as separate lines) — AMO reimbursement ceilings are per-line, so a single bundled line under-reimburses the client and the optician gets blamed
- Suivi de commande / statut du dossier client — the daily "are my glasses ready?" operational loop, currently only implicit as "commande spéciale"
- Devis and Avoir sharing the same document/line-item model as the facture — must be designed together with facturation, not bolted on later, since sequential numbering forbids deleting a facture and an avoir is the only legal correction path
- Prescripteur + date de prescription on the ordonnance — two fields, and a hard dependency of the AMO-renewal reminder and of the fact that AMO only accepts an ophthalmologist's prescription

**Should have (competitive differentiators):**
- AMO 24-month renewal reminder — highest value-to-cost ratio in the product, free rider on the structured ordonnance
- WhatsApp relance via a `wa.me` deep link (zero API cost) for "glasses ready" and renewal nudges — defer the WhatsApp Business API
- Owner-customizable, field-level permissions (hiding prix_achat/margins from vendeurs) — a genuine step up from competitors' fixed "multi-utilisateur" model

**Defer (v2+):**
- Full DGI e-invoicing clearance integration (XML, DGI validation) — wave-3 timing for TPE is reported as Jan 2027 but the implementing décret was reportedly unpublished as of March 2026; model the facture with a lifecycle status and per-rate TVA now, integrate later
- Mutuelle / tiers payant claim management — the patient claims from CNSS/CNOPS directly in Morocco, not the optician, so this is safe to defer provided the facture is itemized and payments are modeled as multi-line/multi-payer from day one
- Arabic/RTL UI, thermal ticket printing, barcode scanning at the counter, end-customer app — all judged safe to defer, each with a specific cheap hedge (Arabic-capable PDF font; A5 acompte receipt; keyboard-wedge-friendly search field; `wa.me` link)

### Architecture Approach

The system is layered as: client apps (web/mobile) writing to a local store + outbox → a shared API that resolves tenant identity (fail-closed, never falling back to a default connection), routes to the tenant's database, and applies a permission gate → domain services (vente, stock, caisse, facturation) that run inside transactions → a control-plane database holding only tenancy/billing/provisioning metadata, never business data. The three load-bearing patterns are: (1) fail-closed tenant context bound by middleware from the first commit, with a permanent two-tenant CI guardrail test; (2) server-allocated legal facture numbers, device-allocated local references, with allocation and document insert sharing one transaction so gaps and duplicates are structurally impossible; (3) append-only ledgers for stock, caisse, and payments, with all balances/quantities derived, never stored as mutable columns — this is what makes an out-of-order offline write a normal append instead of a destructive update.

**Major components:**
1. Control plane (tenant registry, provisioning state machine, migration fan-out runner, subscription state) — infrastructure, never touches optician data
2. Tenant resolver + connection router + permission gate — the request pipeline every tenant-scoped query must pass through
3. Numérotation service — sole allocator of facture/avoir numbers, serialized per (magasin, série, exercice)
4. Stock ledger, caisse ledger, payments ledger — three instances of the same append-only pattern
5. Sync gateway — idempotent batch mutation ingest (push) + permission-filtered cursor-based change feed (pull), built as its own layer beside the domain, not inside it
6. Permission-filtered projection layer — the single serialization surface shared by the API, the sync bundle, exports, and print, so a redacted field cannot leak through a side door

### Critical Pitfalls

1. **Facture number allocated on the device, or via pre-leased blocks/renumbering** — produces duplicates, gaps, and non-chronological sequences, which under Article 145 CGI read as concealed revenue; a facture already handed to a customer can never be renumbered. Avoid by making the server, inside one transaction, the sole and only writer of the legal number.
2. **Off-the-shelf sync engines or CRDTs for stock/caisse/facture** — PowerSync/ElectricSQL assume schema-per-tenant and replicate rows (leaking `prix_achat`); CRDTs converge automatically, which is exactly wrong for money and inventory, which need "reject this" and "server assigns this" semantics they cannot express. Avoid by building a purpose-built idempotent command queue.
3. **Offline sync payload bypassing the permission model** — the highest-probability serious failure in this project, because the API can be carefully permission-checked while the sync bundle, export, and print payload each ship the full row including margins. Avoid with one shared projection/redaction layer used everywhere, verified by a CI test that dumps a vendeur device's local database and greps for purchase prices.
4. **Migration fan-out and tenant provisioning treated as scripts** — a `for` loop over tenant databases fails partway at scale and leaves a split-brain schema fleet with no record of which tenant is where; signup treated as a synchronous function call produces zombie tenants (charged but no database, or vice versa). Avoid with a real tenant registry, resumable/idempotent fan-out, expand/contract migrations, and an explicit signup state machine with a reconciler.
5. **The scope itself** — self-serve platform + full ERP + legal fiscal engine + offline sync engine + customizable permissions + two full-parity clients + Moroccan billing paperwork is, together, a multi-year v1 for one developer if every piece must ship before anything ships. Avoid by decoupling first paying customers (manual provisioning) from the self-serve platform milestone, and by building online-only through a complete, stable sale before starting the offline layer.

## The Open Conflict: Tenancy Model (Do Not Average This)

STACK.md and ARCHITECTURE.md diverge on how much relaxing "one database per client" to "one schema per client" would actually save, and this must be resolved as a business decision, not silently split the difference.

**STACK.md's position:** the single decision that would "halve the work" is relaxing database-per-tenant to schema-per-tenant, because it unlocks PowerSync's wildcard-schema support (v1.24.0+, Postgres-only) and would let you delete most of the custom sync layer — the largest cost line in the project, estimated at 4-8 weeks of solo-dev time to build correctly from scratch.

**ARCHITECTURE.md's position:** this overstates the saving, because PowerSync/ElectricSQL are rejected for a *second, independent* reason that schema-per-tenant does not fix — these engines replicate raw rows, and replicating the `article` table puts `prix_achat` in the vendeur's local SQLite regardless of whether tenants are isolated by schema or by database. The permission-filtered projection layer (Pattern 5 in ARCHITECTURE.md, and the #1-ranked pitfall in PITFALLS.md) still has to be hand-built either way.

**The honest resolution:** relaxing to schema-per-tenant removes one of the two blockers to adopting an off-the-shelf sync engine, not both. It would still simplify the pull/read side of sync (permission-filtered projections could theoretically ride on a PowerSync-managed replication layer with heavier client-side filtering), but it does not eliminate the need for a custom, server-authoritative write path for gapless facture numbers, append-only ledgers, and permission redaction — the actual hardest parts. The realistic saving is meaningfully smaller than "half the project," concentrated in the read/pull mechanics rather than the numbering, ledger, and permission logic. Separately, PROJECT.md records that database-per-tenant was chosen deliberately for isolation, and schema-per-tenant trades that away: harder per-client backup/restore, and one bad `search_path` becomes a cross-tenant leak instead of an impossible query. **This is presented as an open business decision for the person building this, not a recommendation** — if isolation matters as much as PROJECT.md states, stay with database-per-tenant and budget the full custom sync layer; if the sync-layer cost is the dominant constraint, schema-per-tenant is a real, bounded-savings option, but budget the projection layer regardless.

## Calendar-Bound Items — Start Day One, Cannot Be Coded Faster

These are administrative/legal processes running on their own clock, independent of engineering velocity. Both must start in parallel with the first line of code, not scheduled as a "phase."

- **CNDP prior authorization (Law 09-08, Article 23)** — ordonnances are health data about identified individuals, which requires *prior authorization* from Morocco's data protection authority, not the simpler declaration that ordinary business data requires. Reported review time is 2-4 months. This also forces an early, hard-to-reverse decision on hosting jurisdiction (cross-border transfer of Moroccan personal data has its own CNDP regime), and on whether the optician or the platform is the responsable de traitement — which shapes the signup flow. Blocks onboarding the first real external tenant.
- **CMI / payment merchant contract** — accepting Moroccan-issued cards for subscription billing requires a merchant contract in the company's own name with a CMI-partner acquiring bank, which requires a registered Moroccan company (RC, ICE, professional bank account) first. This is weeks-to-months of paperwork that no amount of coding compresses, and aggregator claims of recurring/tokenized billing (Chari Pay, Payzone) are vendor marketing that must be validated in a sandbox before the subscription/billing model is designed around them.

## Consolidated Open Questions Requiring a Human Expert

These recur across all four research files under slightly different framing; deduplicated here with which ones gate schema decisions.

**Blocks schema/architecture decisions — resolve before or during early build:**
1. **Which TVA rate(s) apply** to montures, verres correcteurs, lentilles, produits d'entretien, and optician prestations post-2026 TVA reform (which converged Morocco onto 20%/10%, eliminating 7%/14%). Design mitigation already adopted regardless of the answer: TVA rate is a per-article/per-line field, never a hardcoded constant, and the facture breaks TVA down by rate. → Moroccan expert-comptable.
2. **Is a facture série per magasin legally acceptable**, or must a tenant maintain one continuous série across all its magasins? Determines whether the numbering counter is keyed per (tenant, magasin, série, exercice) or per (tenant, série, exercice) — a schema decision, not a config toggle after the fact, though the design keeps it in a `serie_document` table specifically so it can be changed as data. → Moroccan expert-comptable. Blocks the facturation/numbering phase.
3. **Is the facture issued at commande or at délivrance, and is TVA due on encaissement or on débit (régime des débits vs encaissements)?** Also: does the acompte itself require its own fiscal document/number? Gets every affected client's TVA declaration wrong if answered incorrectly, and changes the acompte/commande/facture document model. → Moroccan expert-comptable. Blocks the sale/facturation phase.
4. **DGI e-invoicing wave-3 date and turnover threshold for TPE/SME opticians** — widely reported as January 2027 above a ~500,000 DH turnover threshold, but the implementing décret was reportedly still unpublished (submitted to the Secrétariat Général du Gouvernement but not in the Bulletin Officiel) as of March 2026, and no official threshold or e-invoicing-specific penalty had been published. Do not build the DGI clearance integration against this rumor; do model the facture as structured data with a lifecycle status now. → Re-check DGI/Bulletin Officiel directly, quarterly.

**Deferrable / validate opportunistically, does not block early schema:**
5. **CNDP controller-vs-processor split** in a multi-tenant health-data SaaS — who files, the platform or each optician client (or both) — and confirmation of permitted hosting jurisdictions. → Privacy counsel, before the first external tenant (see calendar section above).
6. **Whether true card-on-file recurring billing is actually available** to a small Moroccan SaaS via Chari Pay/CMI/Payzone, with real lead times and pricing. → Direct sandbox contract, before designing the billing/dunning model.
7. **Payment-mode-to-caisse mapping** — validated against how real shops handle chèque, crédit client, and card, since putting a card sale into the cash total is reportedly the single most common version of this bug. → Interview 2-3 opticians before building the caisse/sale phase.
8. **Record-keeping obligations specific to the optician profession** (register of prescriptions delivered, retention rules) under the Moroccan dahir governing opticien-lunetiers — the primary text was not machine-readable during research. → Legal counsel or professional association.
9. **Real market share / how many Moroccan opticians use no software at all** — could shift the addressable segment and the feature bar downward; not schema-blocking, useful for prioritization. → Optician interviews.

The single highest-value validation step named across the research is one hour with two working opticians, specifically on the caisse end-of-day count question and on how often they actually encounter bons de prise en charge from private insurers.

## Implications for Roadmap

### Phase 0: Legal & compliance groundwork (parallel track, not a gating phase)
**Rationale:** CNDP authorization and CMI merchant onboarding run on a calendar independent of code; starting late adds a multiplicative delay to launch.
**Delivers:** CNDP authorization filed and hosting jurisdiction decided; Moroccan company registration and CMI/aggregator paperwork underway; expert-comptable engaged on the TVA/numbering/acompte questions above.
**Avoids:** Pitfall — discovering CNDP or CMI lead times the week before the first paying customer.

### Phase 1: Tenancy foundation + control plane
**Rationale:** Nothing built before tenant isolation exists is safe; this is explicitly unretrofittable per all four research files.
**Delivers:** Control-plane DB (tenant registry, schema_version, provisioning state), fail-closed tenant resolver + connection router, resumable/idempotent migration fan-out with canary tenants, a permanent cross-tenant-leak guardrail test in CI, PgBouncer sized correctly from day one.
**Addresses:** Tenancy & platform requirements in PROJECT.md.
**Avoids:** Migration fan-out as a for-loop; provisioning as a synchronous function call; ambient/global tenant context; connection pool exhaustion.

### Phase 2: Domain core — clients, ordonnances, catalogue, money/ledger primitives
**Rationale:** Read-heavy, no sync complexity yet; establishes the French domain model and the ledger/money shapes (stock, payments) that every later phase depends on. This is also where the AMO-renewal-enabling fields (prescripteur, date de prescription) and the itemized-facture-enabling line-item model must be seeded, since retrofitting either means backfilling every record.
**Delivers:** Structured ordonnance (OD/OG, sign convention fixed, append-only versions, prescripteur + date), stock as an append-only ledger with derived quantity, a payments ledger (never `acompte`/`paid` scalar columns), money as integer centimes throughout.
**Addresses:** Structured ordonnance, ordonnance history, stock per magasin from FEATURES.md/PROJECT.md; the AMO renewal differentiator's hard dependency (G5).
**Avoids:** Loose ordonnance fields; stock as a mutable quantity column; money as floats.

### Phase 3: Permissions & roles
**Rationale:** Must precede the feature surface, not follow it — retrofitting field-level redaction across dozens of endpoints later is far more expensive than building the projection layer once, before there is a feature surface to retrofit.
**Delivers:** Permission catalog as code, tenant-owned roles as data, magasin-scoped permission checks, one shared serialization/projection layer for API responses (to be reused unchanged by sync, export, and print in later phases), owner role immutable/undeletable.
**Addresses:** Owner/vendeur roles, owner-customizable permissions, prix d'achat/margin hidden from vendeur.
**Avoids:** Hardcoded role checks; permission checks in the UI only; the offline-sync-leaks-margins failure mode (built here so it structurally cannot happen later).

### Phase 4: Sale, facturation, and caisse — online only
**Rationale:** Get the fiscal core provably correct on a good connection before adding a partition-tolerance problem on top; per ARCHITECTURE.md and PITFALLS.md, the API must already be built for offline (client-generated UUIDs, idempotency keys, nullable facture number with `EN_ATTENTE_NUMEROTATION` status) even though offline sync itself isn't built yet — skipping this turns the offline phase into a rewrite instead of a retrofit.
**Delivers:** Vente + line items + itemized facture (monture/verres/lentilles separated per G4), devis → facture → avoir sharing one document model, the numérotation service (server-side, `FOR UPDATE`-locked counter, one writer, inside the same transaction as the document insert), caisse as an append-only ledger with derived balance and enumerated payment-mode-to-cash mapping, acompte/partial payment via the payments ledger.
**Addresses:** Facturation, caisse, acompte/paiement partiel from PROJECT.md; devis/avoir gaps (G2, G3) from FEATURES.md.
**Avoids:** Facture number on the device; caisse balance as a mutable column; acompte as a scalar column with no refund path.

### Phase 5: Achats & fournisseurs
**Rationale:** Réception is the legitimate stock-increase path (until this phase, stock is seeded by manual ajustement); prix d'achat is the sharpest end-to-end test that the permission model built in Phase 3 actually holds.
**Delivers:** Fournisseur directory, bon de commande, réception (stock+), compte fournisseur with échéances, prix d'achat visible only to owner-permissioned roles.
**Addresses:** Fournisseurs & achats requirements from PROJECT.md.

### Phase 6: Offline sync engine — scoped to the sale path only
**Rationale:** The highest-risk phase in the project; must come after the domain model is stable (Phases 2-5) so schema changes don't ripple through sync twice. Deliberately narrow scope — sell, take payment, record caisse entry, look up client/ordonnance/stock read-only — because every additional offline entity multiplies conflict cases; achats, réception, fournisseur management, role editing, and reporting stay online-only.
**Delivers:** Local store + outbox, idempotent batch mutation ingest with per-item results, permission-filtered pull (reusing the Phase 3 projection layer verbatim), the non-fiscal bon de commande / reçu d'acompte with local reference, oversell-as-append-not-reject for stock, a dead-letter/reconciliation queue, a deterministic simulation test harness (seeded RNG, network partition/delay/reorder/duplicate, per-run invariant assertions) built before the sync engine itself is declared done.
**Addresses:** The offline-capable caisse — this project's Core Value.
**Avoids:** Nearly all of Pitfalls 9, 10, 11, 16, 17 — duplicate sales on retry, trusting device clocks, stock as mutable, data loss on device loss, and untestable sync.

### Phase 7: Mobile parity & hardening
**Rationale:** Real-world validation of Phase 6 under an actual device fleet; comes after web/online is proven so mobile isn't absorbing churn from an unstable domain model.
**Delivers:** Full mobile parity via the shared Expo Router codebase, background sync tuning, offline soak testing on low-end Android, device-token revocation.

### Phase 8: Self-serve signup, subscription billing
**Rationale:** Provisioning mechanics already exist from Phase 1 and can be triggered manually until now — this is explicitly the phase to decouple from "first paying customer." Billing is control-plane work, decoupled from the tenant domain.
**Delivers:** Signup as an explicit, resumable state machine with a reconciler; `CREATE DATABASE ... TEMPLATE` for fast provisioning; gateway-agnostic subscription engine behind `PasserelleDePaiement`; dunning that degrades to read-only, never deletes; billing failures that never block the caisse.
**Addresses:** Self-serve signup, subscription billing via Moroccan payment methods from PROJECT.md.

### Phase 9: Reminders, branding, reporting
**Rationale:** Real value, zero structural risk — deliberately last so it doesn't compete for time with the fiscal/offline core.
**Delivers:** Réappro, échéance fournisseur, and AMO-24-month renewal reminders; WhatsApp `wa.me` relance; per-tenant branding on UI and documents; owner dashboard (CA, marge, panier moyen, encours).
**Addresses:** Reminders from PROJECT.md; the AMO-renewal and WhatsApp differentiators from FEATURES.md.

### Phase Ordering Rationale

- Tenancy (1) → permissions (3) → a complete online-only sale (2, 4) → offline scoped to the sale path only (6) is the sequencing every research file converges on independently; the recommendation to decouple "first paying customer" from "self-serve platform" means Phase 8 can genuinely land late without blocking revenue, provided Phase 1 built provisioning primitives that a human can drive manually in the meantime.
- Devis, facture, and avoir must be designed in one phase (4) because they share one line-item/document model — building the facture alone and retrofitting the other two means rebuilding that model twice.
- Achats (5) and offline sync (6) have a flexible boundary and can swap if early customer signal favors the achats/marges story over the offline story; phases 1, 3, and 4→6 cannot move.
- A real optician should be using the online-only version in their own shop before the offline engine is built — this is the validation checkpoint that prevents paying for a domain-model change twice (once in the domain, once in the sync harness).

### Research Flags

Needs deeper research during planning (`/gsd-research-phase`):
- **Phase 4 (facturation/numbering):** the per-magasin-série legality question and the acompte/TVA-timing question are open and gate the schema; needs either direct expert-comptable engagement or a dedicated research pass synthesizing whatever guidance surfaces before this phase is planned in detail.
- **Phase 6 (offline sync):** flagged by ARCHITECTURE.md as the single highest-risk phase, warranting its own deep research pass on change-feed cursor design, dead-letter handling, and offline soak testing methodology on low-end Android.
- **Phase 8 (billing):** the Chari Pay/CMI recurring-billing capability is vendor-marketing-sourced (LOW confidence) and needs a sandbox-validated pass before the subscription model is finalized.

Standard patterns, likely skip deep research-phase:
- **Phase 1 (tenancy foundation):** stancl/tenancy is a mature, documented reference implementation for exactly this shape of problem.
- **Phase 2 (domain core), Phase 5 (achats):** conventional CRUD/ledger modeling with well-established patterns, no novel technical risk.
- **Phase 9 (reminders/branding/reporting):** standard scheduled-job and templating patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Versions and framework choices HIGH (verified against Packagist/npm registries); Moroccan payment gateway capability claims and fiscal specifics LOW-MEDIUM (vendor marketing, secondary sources) |
| Features | MEDIUM-HIGH | Competitor feature lists HIGH (vendor's own copy); inferences about why Moroccan opticians buy MEDIUM (no direct user interviews); AMO reimbursement rules MEDIUM-HIGH (consistent across secondary sources, not verified against CNSS/CNOPS directly) |
| Architecture | MEDIUM-HIGH | Tenancy mechanics, offline sync patterns, gapless numbering design HIGH (converges with established practitioner patterns and reference implementations); Moroccan fiscal specifics (per-magasin série legality, acompte TVA treatment) explicitly LOW, flagged as open questions |
| Pitfalls | MEDIUM-HIGH | Engineering pitfalls (migration fan-out, connection pooling, sync idempotency, permission leaks) HIGH, corroborated across independent practitioner sources; Moroccan legal specifics (CNDP timelines, DGI décret status, dahir on the optician profession) MEDIUM, sourced from consulting blogs and unofficial texts rather than primary government publication |

**Overall confidence:** MEDIUM-HIGH on engineering approach and architecture; MEDIUM-LOW on Moroccan fiscal/legal specifics, which is a known and explicitly flagged gap rather than an oversight.

### Gaps to Address

- **TVA rate on optical goods, per-magasin série legality, and acompte TVA timing** — all three block schema decisions in the facturation phase and none were resolved by research; must be answered by a Moroccan expert-comptable before or during that phase, not deferred past it.
- **DGI e-invoicing wave-3 date/threshold** — sourced from consulting blogs reporting an unpublished décret as of March 2026; re-verify directly against the DGI/Bulletin Officiel before any DGI integration work is scheduled, and treat all cited dates as provisional.
- **CNDP controller/processor split and hosting jurisdiction** — needs privacy counsel before onboarding the first external tenant; affects both the signup flow design and a highly consequential, hard-to-reverse infrastructure decision (hosting region).
- **Real-world recurring billing capability on Moroccan rails** — Chari Pay/CMI claims are vendor-sourced; requires a sandbox contract to validate before the subscription/billing data model is finalized, with an explicit fallback (invoice + payment link per period) if card-on-file recurring isn't actually available.
- **Payment-mode-to-caisse mapping and general workflow assumptions** — the research explicitly recommends validating with 2-3 real opticians before building the caisse/sale phase, since this is inferred from vendor marketing rather than direct user contact throughout all four research files.
- **The tenancy model conflict itself** (see dedicated section above) is not a research gap so much as an unresolved business decision that the roadmap should surface explicitly rather than silently pick a side on.

## Sources

Aggregated from all four research files; see individual files for full source lists and confidence annotations per source.

### Primary (HIGH confidence)
- Packagist/npm registries — Laravel 13.31, stancl/tenancy 3.10.1, Expo SDK 57, Drizzle, PostgreSQL 18.6, Gotenberg 8.36 (exact versions and compatibility, fetched 2026-09-09)
- PowerSync and ElectricSQL official docs — confirmed one-instance-per-database limitation and replication-slot constraints under database-per-tenant
- Article 145 CGI text (fiscamaroc.com) — sequential/chronological/gap-free numbering requirement, retail ticket-as-invoice substitution
- Practitioner sources on offline-first sync engineering (idempotency, retry storms, dead letters) and multi-tenant Postgres connection pooling — convergent across independent sources

### Secondary (MEDIUM confidence)
- Moroccan competitor marketing pages (OpticWizard, MyOpti, Netoptis, Gestoptic, and others) — feature landscape and pricing
- AMO/CNSS/CNOPS reimbursement rules (ceilings, 24-month cycle, 60-day filing deadline) — consistent across multiple secondary Moroccan health/optician sites
- Moroccan e-invoicing reform coverage (Upsilon Consulting, Hisab, AMDE, EDICOM) — clearance model, UBL 2.1/CII, phased calendar (dates disputed across sources)
- CNDP Law 09-08 authorization requirements and review timelines

### Tertiary (LOW confidence, flagged for validation)
- Chari Pay/ChariBaaS recurring billing, tokenization, and sandbox capability claims (vendor's own marketing pages)
- CMI onboarding timelines and cost figures (blog/comparison sources)
- TVA rate applicable to optical goods specifically (unresolved by any source found)
- Per-magasin invoice série legal acceptability under Article 145 (asserted as common commercial practice, not confirmed against authoritative text)

---
*Research completed: 2026-09-09*
*Ready for roadmap: yes*

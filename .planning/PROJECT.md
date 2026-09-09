# Optician Management Platform

## What This Is

A multi-tenant SaaS for Moroccan opticians. One platform where an optician business runs its whole day — clients and their ordonnances, stock, fournisseurs and achats, facturation, and a per-magasin caisse — on both web and mobile. Each client business gets its own database, may run one or several magasins, and appears under their own branding.

## Core Value

The counter can complete a sale end to end — find or create the client, attach the ordonnance, take payment (including an acompte), and have it land in that magasin's caisse — even when the shop's internet is down, and still produce a legally valid facture afterwards.

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
- [ ] The first opticians are onboarded manually, by running the same provisioning the platform uses. Self-serve must not gate the first paying customer.
- [ ] Self-serve signup: an optician creates an account, trials and subscribes with no manual setup from us
- [ ] Subscription billing through Moroccan payment methods (Chari Pay primary, CMI fallback) behind a payment-gateway interface
- [ ] Per-client branding: logo, colors and shop name applied to the UI and to printed documents

**Accounts & permissions**
- [ ] Only the optician (owner) and gérants have logins — floor vendeurs never sign in
- [ ] The owner grants permissions per gérant individually; permissions are data, not fixed role tiers
- [ ] Prix d'achat, margins and business-wide money are owner-only unless the owner explicitly grants them
- [ ] The vendeur who made a sale is recorded as a field on the sale, for tracking rather than access
- [ ] One permission-filtered projection layer shared by the API, the sync bundle, exports and printing — so a field hidden in the UI cannot leak through another route

**Clients & ordonnances**
- [ ] Client records with contact details and purchase history
- [ ] Structured ordonnance per client: OD/OG with sphère, cylindre, axe, addition, écart pupillaire
- [ ] Prescripteur and date de prescription recorded on the ordonnance
- [ ] Ordonnance source recorded — ordonnance médicale or réfraction opticien — because Moroccan law does not always require a doctor
- [ ] Ordonnances are versioned append-only, never edited in place
- [ ] The ordonnance feeds lens orders — a commande spéciale carries the prescription to the fournisseur

**Stock**
- [ ] Stock per magasin for frames, accessories and stocked lenses
- [ ] Common lens corrections held in stock; unusual corrections ordered specially from the fournisseur/labo
- [ ] Stock is an append-only ledger with derived balances, never a mutable quantity column
- [ ] Stock decrements on sale and increments on réception of a fournisseur delivery
- [ ] Negative stock is permitted and raises an anomaly for the owner to reconcile — an offline oversell is detected, not rejected
- [ ] Suivi de commande client: statut commandé → prêt → client prévenu → livré
- [ ] Search accepts an exact reference and submits on Enter, so a keyboard-wedge barcode scanner works later without a UI rewrite

**Fournisseurs & achats**
- [ ] Fournisseur directory: contacts, catalogue, negotiated prices, delivery lead times
- [ ] Bon de commande sent to the fournisseur, and réception recorded on arrival
- [ ] Compte fournisseur: running balance owed to each fournisseur, and payments made against it
- [ ] Prix d'achat tracked per item so margin per sale is visible to the owner

**Facturation**
- [ ] Facture in MAD with Moroccan TVA and a sequential legal number
- [ ] The legal number is issued server-side only, from a counter per (client, série, exercice) — never by a device, never from a database sequence, never pre-leased in blocks
- [ ] An offline device shows no facture number at all and prints a non-fiscal provisional document with a device-local reference
- [ ] Facture itemisée: monture and verres on separate lines, because AMO reimburses per line
- [ ] Buyer ICE recorded as a first-class field
- [ ] TVA modeled per article and broken out per rate on the facture — never a hardcoded global rate
- [ ] Facture lifecycle status (brouillon → émise → transmise → validée) rather than treating "printed" as final
- [ ] Avoir / retour as the only legal correction path — a facture is never deleted
- [ ] Print Facture A4 and Bon de commande
- [ ] Acompte / paiement partiel: deposit at order, balance on pickup, remainder tracked until settled
- [ ] Payments are an append-only ledger of lines, each carrying its payer, so a future insurer split is a field rather than a migration

**Caisse**
- [ ] One caisse per magasin — a running cash ledger of entries in and out with a current balance
- [ ] Daily and monthly totals read off that ledger
- [ ] The caisse keeps working offline: sales queue locally and sync when the connection returns
- [ ] Offline sync is scoped to the sale path only — achats, réception, reporting and administration stay online

**Reminders**
- [ ] Stock réappro — item below its threshold, time to reorder
- [ ] Supplier payment due — échéances on achats
- [ ] Client follow-up — renewal nudge for a new ordonnance, new lenses, or a contact lens re-order
- [ ] Relance AMO — a client is reimbursable again 24 months after their last purchase (12 months for children ≤12); remind at month 23

**Apps**
- [ ] Web app, French UI
- [ ] Mobile app with full parity — everything the web app does, on phone or tablet

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Mutuelle / tiers payant — in Morocco the patient claims, not the optician, and no local competitor offers a claims module. Kept cheap to add later by modelling payments as lines with a payer.
- Arabic / RTL interface — every local competitor is French-only and sells it as a feature. Arabic *data* must still render (UTF-8 and an Arabic-capable font in the PDF pipeline), since names appear on documents handed to government insurers.
- Logins for floor vendeurs — the optician and gérants operate the system; a vendeur is data recorded on a sale
- A separate deployment per client — one shared application serves everyone; only the database is per client
- A database per magasin — magasins live inside their client's database so the owner sees across all stores without cross-database queries, and a client record is shared between stores
- Full white-label (custom domains, deep theming) — branding only in v1
- An app for the shop's own customers — a 24-month purchase cycle gives no retention loop; a wa.me link covers contact
- Formal clôture Z with écarts de caisse — the caisse stays a pure ledger of the actual cash, as specified. A non-blocking attendu-vs-compté check is the strongest v2 candidate.
- Ticket de caisse on thermal printers — the client needs an itemized A4 original for AMO, and thermal paper fades against a 60-day filing deadline
- Barcode scanning as a feature — no hardware assumed, but search is built scanner-ready at no cost
- Devis / proforma, owner statistics dashboard, physical inventaire screen, accounting CSV export — all real, all v2
- DGI e-invoicing integration — not built in v1, but the facture is structured-data-first with a clearance lifecycle and full art. 145 fields, so it stays convertible when the mandate lands

## Context

- **Market**: Morocco. French UI, MAD, Moroccan TVA and facture numbering rules.
- **The market is crowded and cheap, not empty.** Eight live Moroccan competitors, priced between roughly 800 and 4 000 DH/year. That ARPU is why feature bloat is unaffordable and why the exclusions above matter.
- **Offline is parity, not a moat** — a competitor already advertises local-first sync at 800 DH/year. What nobody advertises solving is gapless legal invoice numbering surviving an offline sale, and that is the defensible part.
- **The real local gap is depth**: no competitor advertises a structured ordonnance, compte fournisseur with échéances, per-sale margin hidden from staff, or per-gérant permissions.
- **Buyers**: independent opticians. A client may run a single shop or several magasins; the product must not assume one.
- **Connectivity**: shop internet is not dependable. The counter cannot stop when it drops.
- **Domain language is French** — ordonnance, magasin, caisse, fournisseur, facture, acompte, bon de commande, réappro. Keep that vocabulary in the UI and in the domain model.
- **Team**: solo developer, no hard deadline. The scope is ERP-shaped, so sequencing matters more than speed.
- **Trust boundary inside a client**: opticians do not want gérants seeing purchase prices, margins or business-wide revenue. Permissions are a product requirement, not hygiene.

## Constraints

- **Legal — invoicing**: Moroccan TVA and a gapless, chronological, duplicate-free facture series (art. 145 CGI). Gaps are treatable as fraud, and this is the client's tax exposure caused by our software.
- **Legal — health data**: ordonnances require CNDP prior authorization before processing, on a 2–4 month calendar
- **Legal — retention**: 10 years (art. 211 CGI), which constrains offboarding and the cost model
- **Locale**: MAD and French UI — drives formatting and vocabulary
- **Offline**: the sale path must work with no connection and sync afterwards — local-first storage, idempotent queued writes, explicit conflict handling. Budget this as its own phase; it is the highest-risk work in the project.
- **Platforms**: web and mobile at full parity — one shared codebase and API rather than two products
- **Tenancy**: one shared application, one database per client — every request must resolve to the right client database, migrations must fan out across all of them, and a leak across clients is a security failure, not a bug
- **Payments**: Moroccan rails for subscriptions; recurring card-on-file is a vendor claim that must be proven in sandbox before the billing model depends on it
- **Timeline**: no hard deadline — build it right rather than fast

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| One shared app, one database per client business | Real isolation per paying client without a deployment each; magasins sit inside their client's database so owner-wide views stay ordinary queries. Reconfirmed against a proposal to relax it to schema-per-client. | — Pending |
| Only the optician and gérants log in; permissions granted per gérant | Floor vendeurs never touch the system, so a vendeur is data on a sale rather than an account. Shrinks the permission surface and removes the largest offline-sync leak risk. | — Pending |
| Manual onboarding first; self-serve stays the platform bar | Letting self-serve gate first revenue risks building everything to 80% with zero validation. The manual path calls the same provisioning primitives. | — Pending |
| Server-issued facture numbers, never device-issued | Art. 145 CGI needs a gapless chronological series; two offline devices cannot both mint the next number, and pre-leased blocks leave legal gaps | — Pending |
| Offline devices print a non-fiscal provisional document | A facture number cannot exist before the server issues one, and showing a fake number would be read aloud to a customer. Matches the real workflow: acompte on visit one, facture at retrait. | — Pending |
| Purpose-built sync — not PowerSync, ElectricSQL or CRDTs | Those engines assume schema-per-tenant and replicate rows, which would leak prix d'achat onto devices; CRDT auto-convergence is precisely the bug for stock, caisse and legal numbering | — Pending |
| Stock, caisse and payments as append-only ledgers | Decides whether late-arriving offline writes are absorbable or corrupting. Oversell can only be detected, never prevented — rejecting a synced sale deletes real money. | — Pending |
| Build online-only through a complete sale, then add offline | The fiscal core must be correct first. The API still uses client-generated UUIDs, idempotency keys and nullable facture numbers from day one, so offline is an addition rather than a rewrite. | — Pending |
| Offline scoped to the sale path only | Every additional offline entity multiplies conflict cases | — Pending |
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

# Optician Management Platform

## What This Is

A multi-tenant SaaS for Moroccan opticians. One platform where an optician business runs its whole day — clients and their ordonnances, stock, fournisseurs and achats, facturation, and a per-magasin caisse — on both web and mobile. Opticians sign up themselves; each client gets their own database, may run one or several magasins, and appears under their own branding.

## Core Value

A vendeur at the counter can complete a sale end to end — find or create the client, attach the ordonnance, take payment (including an acompte), and have it land in that magasin's caisse — even when the shop's internet is down.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. -->

**Tenancy & platform**
- [ ] One shared application serving every client, with one database per client business. Onboarding an optician provisions their database — it never means a new deployment.
- [ ] A client can have several magasins; inside that client's database, stock and caisse are scoped per magasin
- [ ] Provisioning and schema migrations run across every client database automatically, so no client is left on an old schema
- [ ] Self-serve signup: an optician creates an account, trials, and subscribes with no manual setup from us
- [ ] Subscription billing through Moroccan payment methods (CharriPay-style)
- [ ] Per-tenant branding: logo, colors and shop name applied to the UI and to printed documents

**Roles & permissions**
- [ ] Two built-in roles: vendeur (sell, caisse, clients, stock lookup) and owner (everything, across all magasins, including revenue, achats, prix d'achat and margins)
- [ ] The owner can customize permissions per role rather than being locked to the two presets

**Clients & ordonnances**
- [ ] Client records with contact details and purchase history
- [ ] Structured ordonnance per client: OD/OG with sphère, cylindre, axe, addition, écart pupillaire
- [ ] Ordonnance history over time, so renewals and changes are visible
- [ ] The ordonnance feeds lens orders — a commande spéciale carries the prescription to the fournisseur

**Stock**
- [ ] Stock per magasin for frames, accessories and stocked lenses
- [ ] Common lens corrections held in stock; unusual corrections ordered specially from the fournisseur/labo
- [ ] Stock decrements on sale and increments on réception of a fournisseur delivery

**Fournisseurs & achats**
- [ ] Fournisseur directory: contacts, catalogue, negotiated prices, delivery lead times
- [ ] Bon de commande sent to the fournisseur, and réception recorded on arrival
- [ ] Compte fournisseur: running balance of what is owed to each fournisseur, and payments made against it
- [ ] Prix d'achat tracked per item so margin per sale is visible to the owner

**Facturation**
- [ ] Facture in MAD with Moroccan TVA and sequential legal numbering
- [ ] Print Facture A4 and Bon de commande
- [ ] Acompte / paiement partiel: deposit taken at order, balance on pickup, remainder tracked until settled

**Caisse**
- [ ] One caisse per magasin — a running cash ledger of entries in and out with a current balance
- [ ] Daily and monthly totals read off that ledger
- [ ] The caisse keeps working offline: sales queue locally and sync when the connection returns

**Reminders**
- [ ] Stock réappro — item dropped below its threshold, time to reorder
- [ ] Supplier payment due — échéances on achats
- [ ] Client follow-up — renewal nudge for a new ordonnance, new lenses, or a contact lens re-order

**Apps**
- [ ] Web app, French UI
- [ ] Mobile app with full parity — everything the web app does, on phone or tablet

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Mutuelle / tiers payant — client pays in full in v1; splitting invoices and reconciling insurer claims is a large surface for a segment not targeted yet
- Arabic / RTL interface — French only in v1; Arabic can follow once the product is proven
- A separate deployment per client — one shared application serves everyone; only the database is per client
- A database per magasin — magasins live inside their client's database, so the owner can see across all of their stores without cross-database queries, and a client record is shared between the stores
- Full white-label (custom domains, deep theming) — branding only in v1
- An app for the shop's own customers — mobile is a staff tool, not an end-customer product
- Formal clôture Z with écarts de caisse — the caisse is deliberately just a running ledger of the actual cash, with totals read off it
- A separate gérant role preset — owner-customizable permissions cover this for now; add the preset if chains ask
- Ticket de caisse on thermal printers — v1 prints Facture A4 and bon de commande only
- Barcode scanning at the counter — deferred, search is enough for v1

## Context

- **Market**: Morocco. French UI, MAD, Moroccan TVA and facture numbering rules.
- **Buyers**: independent opticians, sold as a subscription. A client may run a single shop or several magasins; the product must not assume one.
- **Connectivity**: shop internet is not dependable. The counter cannot stop when it drops — this is why the caisse is offline-capable rather than online-only.
- **Domain language is French** — ordonnance, magasin, caisse, fournisseur, facture, acompte, bon de commande, réappro. Keep that vocabulary in the UI and in the code's domain model; translating it invites confusion.
- **Team**: solo developer, no hard deadline.
- **Trust boundary inside a client**: opticians do not want their vendeurs seeing purchase prices, margins or business-wide revenue. Permissions are a product requirement, not just hygiene.

## Constraints

- **Legal**: Moroccan TVA and sequential facture numbering — invoices must be legally valid; numbering cannot have gaps or duplicates, including after an offline sync
- **Locale**: MAD and French UI — drives currency/date formatting and the domain vocabulary
- **Offline**: caisse and sales must work with no connection and sync afterwards — pushes toward local-first storage, queued writes, and explicit conflict handling
- **Platforms**: web and mobile at full parity — favors one shared API and as much shared code as possible over two separate products
- **Tenancy**: one shared application, one database per client — every request must resolve to the right client database, and migrations must fan out across all of them; a leak across clients is a security failure, not a bug
- **Payments**: Moroccan payment methods for subscriptions — international gateways do not reliably accept locally issued Moroccan cards
- **Timeline**: no hard deadline — build it right rather than fast

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| One shared app, one database per client business | Gives each paying client real isolation without running a deployment each; magasins sit inside their client's database so owner-wide views stay ordinary queries instead of cross-database aggregation | — Pending |
| Sold as SaaS to many opticians, 1+ magasins each | Target is independent opticians, but chains must not be excluded | — Pending |
| Morocco first: French UI, MAD, Moroccan TVA | Home market; legal invoicing rules are market-specific and must be right | — Pending |
| Caisse is a running cash ledger, one per magasin | User was explicit: it should just track the actual cash, not act as a formal register with Z closes | — Pending |
| Offline-capable caisse with later sync | Shop internet drops; a counter that stops selling is unacceptable, and worth the added complexity | — Pending |
| Structured ordonnance rather than a scan | Prescriptions must feed lens orders and renewal reminders — that needs fields, not an image | — Pending |
| No mutuelle / tiers payant in v1 | Client pays in full; claim handling is a large module for a segment not targeted yet | — Pending |
| Common lenses stocked, unusual ones ordered | Matches how these shops actually operate, and defines what a commande spéciale is | — Pending |
| All four achats capabilities in v1 | Directory, bon de commande/réception, compte fournisseur and prix d'achat form one flow; a supplier balance needs supplier records to hang off | — Pending |
| Owner + vendeur, with owner-customizable permissions | Opticians won't let vendeurs see margins; customization avoids guessing every shop's hierarchy up front | — Pending |
| Branding-only customization | Logo, colors and shop name cover what clients actually ask for; full white-label is disproportionate for v1 | — Pending |
| Mobile at full parity with web | Staff work away from the desk; a reduced companion app would send them back to a computer | — Pending |
| Self-serve platform is the v1 bar | Signup, subscription and onboarding without manual work is what makes this a product rather than a series of installs | — Pending |
| Local payment methods for subscriptions | Moroccan cards are poorly served by Stripe/Paddle | — Pending |

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

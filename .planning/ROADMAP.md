# Roadmap: Optician Management Platform

## Overview

The journey runs from a legal and infrastructural foundation to a self-serve Moroccan SaaS. Two clocks run at once: an administrative one (CNDP prior authorization, hosting jurisdiction, merchant banking) that starts on day one and cannot be compressed by coding, and a build clock that starts with the two unretrofittable primitives — database-per-client tenancy and the per-gérant permission projection layer. On top of those the domain is assembled in dependency order: clients and their versioned ordonnances, then the append-only stock ledger, then the fiscal core (a sale that mints a gapless server-issued facture number and cannot be double-submitted), then payments and the per-magasin caisse, then achats where prix d'achat proves the permission model holds end to end. Branding and printed documents follow once both document types exist, then rappels, then mobile parity across the same codebase and API. Self-serve subscription lands last, deliberately: manual onboarding through the same provisioning path (Phase 2) already put the product in a real optician's hands long before billing exists.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Legal & Compliance Track** - Calendar-driven filings started day one, running in parallel with every build phase
- [ ] **Phase 2: Tenancy Foundation & Control Plane** - Database-per-client provisioning, fail-closed resolution, migration fan-out, manual onboarding
- [ ] **Phase 3: Comptes, Permissions & App Shell** - Owner/gérant logins, per-gérant permissions, and the single projection layer, inside a French web shell
- [ ] **Phase 4: Clients & Ordonnances** - Client records and structured, versioned, validated ordonnances
- [ ] **Phase 5: Stock & Catalogue** - Per-magasin articles with an append-only movement ledger, scanner-ready search, suivi de commande
- [ ] **Phase 6: Vente & Facturation** - The fiscal core: itemised sale, gapless server-issued legal number, idempotent submission, avoir
- [ ] **Phase 7: Paiements & Caisse** - Acompte and payment ledger feeding a per-magasin running cash ledger
- [ ] **Phase 8: Fournisseurs & Achats** - Fournisseur directory, bon de commande, réception, compte fournisseur, prix d'achat and margin
- [ ] **Phase 9: Branding & Documents Imprimés** - Per-client branding in the UI and on printed A4 factures and bons de commande
- [ ] **Phase 10: Rappels & Relances** - Réappro, échéances fournisseur, client follow-up and relance AMO, with a WhatsApp link
- [ ] **Phase 11: Mobile Parity** - The same app on phone and tablet, full feature parity, one codebase and API
- [ ] **Phase 12: Self-Serve Subscription & Opérations Client** - Signup, Moroccan payment rails, lapse handling, operator view, 10-year archival offboarding

## Phase Details

### Phase 1: Legal & Compliance Track
**Goal**: The filings whose lead time is measured in months are in flight from day one, and the hosting decision that gates storing any client data is made and documented
**Depends on**: Nothing (first phase, runs in parallel with Phases 2-12)
**Requirements**: LEGAL-01, LEGAL-02, LEGAL-03
**Success Criteria** (what must be TRUE):
  1. The CNDP prior-authorization dossier for processing ordonnances as health data is filed, and its reference and decision status are tracked in a record the operator can check
  2. The hosting jurisdiction is chosen and its reasoning documented, and infrastructure lives in that jurisdiction before any real client data is stored
  3. A merchant contract application is open with a Moroccan acquiring bank, and its expected lead time is recorded as a tracked project dependency with a date
**Plans**: TBD
**Research needed**: yes — the CNDP controller/processor split between the platform and the optician; also the vehicle for putting the four blocking facturation questions to a Moroccan comptable ahead of Phase 6

Plans:
- [ ] 01-01: TBD

### Phase 2: Tenancy Foundation & Control Plane
**Goal**: A new client business is a provisioning operation, not a deployment, and no code can ever touch data without knowing which client it belongs to
**Depends on**: Phase 1 (LEGAL-02 only — hosting jurisdiction must be settled before real client data is stored)
**Requirements**: TENANT-01, TENANT-02, TENANT-03, TENANT-04, TENANT-05, TENANT-06, TENANT-07, TENANT-08
**Success Criteria** (what must be TRUE):
  1. An operator provisions a new client business with a single repeatable operation and it comes up with its own database at the current schema version; the operator uses that same path to onboard a real optician manually
  2. A provisioning attempt killed halfway leaves no half-created client — rerunning it converges to either a complete client or none
  3. The control plane lists every client database, its host and its schema version, and a migration run across all of them reports per-client succeeded, failed or behind
  4. Code executing with no resolved client context refuses to run rather than falling back to a shared connection, proven by a permanent cross-client-leak guardrail test in CI
  5. A client business with several magasins can be created with stock and caisse scoped per magasin, and provisioning a few hundred clients and touching them all keeps database connections inside budget
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

### Phase 3: Comptes, Permissions & App Shell
**Goal**: The optician and their gérants sign in to a French web application where every field a gérant may not see is filtered in exactly one place
**Depends on**: Phase 2
**Requirements**: PERM-01, PERM-02, PERM-03, PERM-04, PERM-05, PERM-06, APP-01, APP-03
**Success Criteria** (what must be TRUE):
  1. An optician opens the web application in a browser, sees a French interface, signs in, and is still signed in when they return in a new session
  2. The owner creates a gérant account, grants and revokes individual permissions on it without picking a role tier, and deactivates the account later
  3. A signed-in gérant sees only the magasins and data the owner granted, and prix d'achat, margin and business-wide revenue are absent unless explicitly granted
  4. A field hidden from a gérant is equally absent from the API response, an export and a printed document, because all three read through one projection layer
  5. Amounts, dates and numbers render in MAD and French conventions everywhere they appear
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 03-01: TBD

### Phase 4: Clients & Ordonnances
**Goal**: A client's record and their prescription history are captured in structured form, versioned and never overwritten, ready to drive lens orders and reminders
**Depends on**: Phase 3
**Requirements**: CLIENT-01, CLIENT-02, CLIENT-03, CLIENT-04, CLIENT-05, CLIENT-06, CLIENT-07, CLIENT-08
**Success Criteria** (what must be TRUE):
  1. A user creates a client with contact details and finds them again by name or by phone, and the client's page shows their purchase history
  2. A user records an ordonnance with OD and OG values for sphère, cylindre, axe, addition and écart pupillaire, along with the prescripteur, the date de prescription, and whether the source is an ordonnance médicale or a réfraction opticien
  3. Invalid ordonnance values are refused at entry — an axe outside 0-180, an inconsistent cylinder sign convention, or a monocular value entered where a binocular écart pupillaire is expected
  4. Recording a new ordonnance for a client creates a new version, and every earlier ordonnance is still readable exactly as it was entered
  5. A commande spéciale created from an ordonnance carries those prescription values through onto the order that goes to the fournisseur
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 04-01: TBD

### Phase 5: Stock & Catalogue
**Goal**: Each magasin's stock is a derived balance over an append-only ledger, searchable the way a counter actually searches, with a client's special order tracked to pickup
**Depends on**: Phase 3
**Requirements**: STOCK-01, STOCK-02, STOCK-05, STOCK-06, STOCK-07
**Success Criteria** (what must be TRUE):
  1. A user adds montures, accessoires and verres stockés to a magasin's stock with a reference and a price, and sees the current quantity on hand
  2. Every stock change is a ledger movement and the quantity is derived from those movements — there is no mutable quantity column to correct
  3. A user types an exact reference into search and presses Enter to land on the article, so a keyboard-wedge scanner will work later with no UI change
  4. A user sets a réappro threshold on an article
  5. A user moves a client's special order through commandé → prêt → client prévenu → livré and sees its current statut
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 05-01: TBD

### Phase 6: Vente & Facturation
**Goal**: The counter completes an itemised sale that produces a facture legally valid in Morocco every time — gapless, server-numbered, and never duplicated by a retry
**Depends on**: Phase 4, Phase 5
**Requirements**: FACT-01, FACT-02, FACT-03, FACT-04, FACT-05, FACT-06, FACT-08, FACT-11, FACT-12, LEGAL-05, STOCK-03, STOCK-04, PERM-07
**Success Criteria** (what must be TRUE):
  1. A user completes a sale with monture and verres on separate priced lines, records the buyer's ICE and the vendeur who made it, and the facture is issued with a sequential number allocated server-side from a counter per client, série and exercice, carrying every mention obligatoire of art. 145 CGI
  2. Submitting the same sale twice produces one facture and one number; sales created concurrently produce a série with no gap and no duplicate
  3. TVA is configured per article and broken out per rate on the facture, with no global rate anywhere in the system
  4. A facture moves explicitly through brouillon → émise → transmise → validée, a mistake is corrected by issuing an avoir, and no route deletes a facture; the facture is readable as structured data rather than only as a rendered document
  5. Confirming a sale posts a stock movement out automatically; a sale that would take stock negative warns first, and a shortfall the user accepts anyway lands in a réconciliation queue the owner can see and clear
**Plans**: TBD
**UI hint**: yes
**Research needed**: yes — four open questions block this schema and need a Moroccan comptable, not search: the TVA rate on montures/verres/lentilles/prestations after the 2026 reform, whether a série per magasin is legal or one continuous série per company is required, the TVA treatment of an acompte and whether a facture d'acompte needs its own fiscal number, and whether the facture is issued at commande or at délivrance

Plans:
- [ ] 06-01: TBD

### Phase 7: Paiements & Caisse
**Goal**: Money taken at the counter — including a deposit now and the balance at pickup — lands as ledger lines in the right magasin's caisse, with a balance that is always derived
**Depends on**: Phase 6
**Requirements**: FACT-09, FACT-10, CAISSE-01, CAISSE-02, CAISSE-03, CAISSE-04, CAISSE-05
**Success Criteria** (what must be TRUE):
  1. A user takes an acompte when the order is placed and records the balance at retrait, and the outstanding remainder stays visible on the sale until it is settled
  2. Every payment is an append-only ledger line carrying its payer and its payment mode — there is no scalar paid or acompte column anywhere
  3. A payment lands in that magasin's caisse and the current balance updates, and the owner can read the caisse of every magasin in the business
  4. A user reads daily and monthly totals off the caisse ledger, broken down by payment mode
  5. A mistaken caisse entry is corrected by a compensating entry that leaves the original visible; nothing in the caisse can be edited or removed
**Plans**: TBD
**UI hint**: yes
**Research needed**: yes — payment-mode to caisse mapping is worth an hour with two or three real opticians

Plans:
- [ ] 07-01: TBD

### Phase 8: Fournisseurs & Achats
**Goal**: The purchasing side closes the loop — orders go out, deliveries come back into stock, balances owed are tracked, and prix d'achat proves the permission model holds
**Depends on**: Phase 5, Phase 6
**Requirements**: ACHAT-01, ACHAT-02, ACHAT-03, ACHAT-04, ACHAT-05, ACHAT-06, ACHAT-07
**Success Criteria** (what must be TRUE):
  1. A user creates a fournisseur with contacts, a catalogue with negotiated prices, and a delivery lead time
  2. A user issues a bon de commande to a fournisseur and prints it, then records the réception on arrival, which increments stock automatically
  3. A réception that does not match its bon de commande is recorded with the écart visible on both documents
  4. The owner sees the running balance owed to each fournisseur and records payments against it
  5. Prix d'achat is recorded per article and the owner sees the margin on a sale, while a gérant without that permission sees neither in the UI, the API, an export, nor a printed document
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 08-01: TBD

### Phase 9: Branding & Documents Imprimés
**Goal**: Each client's business appears under its own identity, on screen and on the paper it hands to customers and insurers
**Depends on**: Phase 6, Phase 8
**Requirements**: BRAND-01, BRAND-02, BRAND-03, BRAND-04, FACT-07
**Success Criteria** (what must be TRUE):
  1. An owner uploads a logo and sets colors and the shop name, and the application UI for that client shows them
  2. A user prints a Facture A4 and a bon de commande, and both carry that client's branding
  3. A facture for a client whose name or address is in Arabic renders those characters correctly in the printed document
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 09-01: TBD

### Phase 10: Rappels & Relances
**Goal**: The system tells the shop what to do next — reorder this, pay that, call this client back — instead of waiting to be asked
**Depends on**: Phase 7, Phase 8
**Requirements**: RAPPEL-01, RAPPEL-02, RAPPEL-03, RAPPEL-04, RAPPEL-05
**Success Criteria** (what must be TRUE):
  1. An article that drops below its réappro threshold appears in a réappro reminder the user sees without searching for it
  2. The owner sees a reminder when a fournisseur payment échéance falls due
  3. A client due for a new ordonnance, new lenses or a contact lens re-order appears in a follow-up list
  4. A client appears in a relance AMO 23 months after their purchase — 11 months for a child aged 12 or under — noting they are reimbursable again
  5. From any reminder, one action opens a pre-filled WhatsApp message addressed to that client
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 10-01: TBD

### Phase 11: Mobile Parity
**Goal**: Everything the web application does is available on a phone or a tablet, from the same codebase and the same API
**Depends on**: Phase 10
**Requirements**: APP-02
**Success Criteria** (what must be TRUE):
  1. The mobile application installs and runs on both a phone and a tablet, and a user signs in and completes a full sale — client, ordonnance, lines, acompte, caisse entry — on it
  2. Clients, ordonnances, stock, achats, caisse, rappels and branding are all reachable and usable on mobile, with no feature that exists only on web
  3. Layouts adapt between phone and tablet without a second codebase, a second API or a second permission path
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 11-01: TBD

### Phase 12: Self-Serve Subscription & Opérations Client
**Goal**: An optician can find the product, trial it, pay for it and leave it — all without us touching anything, and their data survives their departure for ten years
**Depends on**: Phase 1 (LEGAL-03 — merchant contract), Phase 2, Phase 11
**Requirements**: BILL-01, BILL-02, BILL-03, BILL-04, BILL-05, LEGAL-04
**Success Criteria** (what must be TRUE):
  1. An optician signs up unaided and their trial business is provisioned automatically through the same path an operator uses to onboard manually
  2. An optician subscribes and pays through a Moroccan payment method, with the gateway behind an interface proven by a second implementation that requires no change to billing logic
  3. A subscription that lapses restricts access while leaving the client's data intact, and paying restores access with nothing lost
  4. An operator sees every client business with its subscription status in one view
  5. Offboarding a client archives their data for the 10-year retention period and the archive is demonstrably restorable — no client database is ever dropped
**Plans**: TBD
**UI hint**: yes
**Research needed**: yes — whether Moroccan rails genuinely support recurring card-on-file must be proven in sandbox before the billing model depends on it; if not, the fallback is invoice plus payment link per period, which changes onboarding and dunning

Plans:
- [ ] 12-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12

Phase 1 is a parallel calendar track: it starts first and stays open across later phases. Only LEGAL-02 (hosting jurisdiction) gates Phase 2; the rest runs alongside.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Legal & Compliance Track | 0/TBD | Not started | - |
| 2. Tenancy Foundation & Control Plane | 0/TBD | Not started | - |
| 3. Comptes, Permissions & App Shell | 0/TBD | Not started | - |
| 4. Clients & Ordonnances | 0/TBD | Not started | - |
| 5. Stock & Catalogue | 0/TBD | Not started | - |
| 6. Vente & Facturation | 0/TBD | Not started | - |
| 7. Paiements & Caisse | 0/TBD | Not started | - |
| 8. Fournisseurs & Achats | 0/TBD | Not started | - |
| 9. Branding & Documents Imprimés | 0/TBD | Not started | - |
| 10. Rappels & Relances | 0/TBD | Not started | - |
| 11. Mobile Parity | 0/TBD | Not started | - |
| 12. Self-Serve Subscription & Opérations Client | 0/TBD | Not started | - |

## Coverage

All 76 v1 requirements map to exactly one phase. See the Traceability table in `.planning/REQUIREMENTS.md`.

| Phase | Requirements | Count |
|-------|--------------|-------|
| 1 | LEGAL-01, LEGAL-02, LEGAL-03 | 3 |
| 2 | TENANT-01 … TENANT-08 | 8 |
| 3 | PERM-01 … PERM-06, APP-01, APP-03 | 8 |
| 4 | CLIENT-01 … CLIENT-08 | 8 |
| 5 | STOCK-01, STOCK-02, STOCK-05, STOCK-06, STOCK-07 | 5 |
| 6 | FACT-01 … FACT-06, FACT-08, FACT-11, FACT-12, LEGAL-05, STOCK-03, STOCK-04, PERM-07 | 13 |
| 7 | FACT-09, FACT-10, CAISSE-01 … CAISSE-05 | 7 |
| 8 | ACHAT-01 … ACHAT-07 | 7 |
| 9 | BRAND-01 … BRAND-04, FACT-07 | 5 |
| 10 | RAPPEL-01 … RAPPEL-05 | 5 |
| 11 | APP-02 | 1 |
| 12 | BILL-01 … BILL-05, LEGAL-04 | 6 |
| **Total** | | **76** |

# Requirements — v1

Scope for the first milestone of the Optician Management Platform.
Derived from `.planning/PROJECT.md` and `.planning/research/SUMMARY.md`.

Legend: every requirement is a hypothesis until shipped and validated.

---

## v1 Requirements

### Legal & Compliance (LEGAL)

Calendar-driven work. Starts day one and runs in parallel with build — no amount of coding speed compresses it.

- [ ] **LEGAL-01**: CNDP prior authorization for processing ordonnances as health data is filed, with the dossier tracked to a decision
- [ ] **LEGAL-02**: Hosting jurisdiction is chosen and documented, with the reasoning recorded, before any client data is stored
- [ ] **LEGAL-03**: A payment merchant contract is opened with a Moroccan acquiring bank, and its lead time is tracked as a project dependency
- [ ] **LEGAL-04**: Client offboarding archives the client's data for the 10-year retention period instead of dropping their database
- [ ] **LEGAL-05**: The facture entity carries every mention obligatoire required by art. 145 CGI, including buyer ICE

### Tenancy & Control Plane (TENANT)

- [ ] **TENANT-01**: A new client business is provisioned with its own database by a single repeatable operation
- [ ] **TENANT-02**: A control plane records every client database, its host, and its current schema version
- [ ] **TENANT-03**: A schema migration is applied across every client database, and the operator can see which clients succeeded, failed, or are behind
- [ ] **TENANT-04**: Any code executing without a resolved client context fails immediately rather than falling back to a shared connection
- [ ] **TENANT-05**: A failed provisioning attempt leaves no half-created client — the operation either completes or rolls back cleanly
- [ ] **TENANT-06**: An operator can onboard an optician manually, using the same provisioning path the self-serve flow will call
- [ ] **TENANT-07**: A client business can have several magasins, and stock and caisse are scoped to a magasin within that client's database
- [ ] **TENANT-08**: Database connections are pooled so that adding clients does not exhaust the database server's connection limit
- [ ] **TENANT-09**: Every client database is backed up on a schedule, and restoring a single client has been performed and verified — not assumed

### Accounts & Permissions (PERM)

- [ ] **PERM-01**: An optician (owner) can sign in and stays signed in across sessions
- [ ] **PERM-02**: An owner can create a gérant account for their business and deactivate it later
- [ ] **PERM-03**: An owner can grant or revoke individual permissions for a specific gérant, without those permissions being fixed to a role tier
- [ ] **PERM-04**: A gérant sees only the magasins and data the owner has granted them
- [ ] **PERM-05**: Prix d'achat, margin and business-wide revenue are hidden from a gérant unless the owner explicitly grants access
- [ ] **PERM-06**: A single projection layer enforces field-level permissions for the API, exports and printed documents alike
- [ ] **PERM-07**: A sale records which vendeur made it as a data field, entered by the signed-in user — vendeurs have no login

### Clients & Ordonnances (CLIENT)

- [ ] **CLIENT-01**: A user can create a client record with contact details, and find it again by name or phone
- [ ] **CLIENT-02**: A user can see a client's full purchase history
- [ ] **CLIENT-03**: A user can record a structured ordonnance with OD and OG values for sphère, cylindre, axe, addition and écart pupillaire
- [ ] **CLIENT-04**: The ordonnance records the prescripteur and the date de prescription
- [ ] **CLIENT-05**: The ordonnance records its source — ordonnance médicale or réfraction opticien
- [ ] **CLIENT-06**: A new ordonnance for a client is stored as a new version; earlier ordonnances remain readable and are never overwritten
- [ ] **CLIENT-07**: Ordonnance values are validated on entry (axe within 0–180, cylinder sign convention consistent, monocular and binocular EP distinguished)
- [ ] **CLIENT-08**: A commande spéciale carries its ordonnance values through to the fournisseur order
- [ ] **CLIENT-09**: A user can attach a photo of the paper ordonnance to the structured record, as evidence for an AMO claim
- [ ] **CLIENT-10**: Client and article search is accent-insensitive and tolerant of Arabic transliteration variants, so "Mohamed", "Mohammed" and "Mhamed" find the same person

### Stock (STOCK)

- [ ] **STOCK-01**: A user can add articles (montures, accessoires, verres stockés) to a magasin's stock with a reference and a price
- [ ] **STOCK-02**: Stock movements are recorded in an append-only ledger, and the current quantity is derived from it rather than stored as a mutable column
- [ ] **STOCK-03**: A sale decrements stock and a réception increments it, automatically
- [ ] **STOCK-04**: A sale warns before it would take stock negative; a shortfall the user accepts anyway raises an anomaly in a réconciliation queue the owner can see and clear
- [ ] **STOCK-05**: A user can search stock by exact reference, and the search submits on Enter so a keyboard-wedge scanner works without a UI change
- [ ] **STOCK-06**: A user can see the status of a client's special order as commandé → prêt → client prévenu → livré, and change it
- [ ] **STOCK-07**: A user can set a réappro threshold per article
- [ ] **STOCK-08**: A user can run a physical inventaire — enter counted quantities per article and post the difference as a stock ajustement
- [ ] **STOCK-09**: A user can print price and reference labels for articles

### Fournisseurs & Achats (ACHAT)

- [ ] **ACHAT-01**: A user can create a fournisseur with contacts, negotiated prices and a delivery lead time
- [ ] **ACHAT-02**: A user can create a bon de commande for a fournisseur and print it
- [ ] **ACHAT-03**: A user can record the réception of a fournisseur delivery, which updates stock
- [ ] **ACHAT-04**: A réception that does not match its bon de commande can be recorded with the difference visible
- [ ] **ACHAT-05**: An owner can see the running balance owed to each fournisseur
- [ ] **ACHAT-06**: An owner can record a payment against a fournisseur balance
- [ ] **ACHAT-07**: Prix d'achat is recorded per article, and the owner can see the margin on a sale

### Facturation (FACT)

- [ ] **FACT-01**: A user can create a sale with separate lines for monture and verres, each with its own price
- [ ] **FACT-02**: A facture receives a sequential legal number issued by the server, from a counter scoped per client, série and exercice
- [ ] **FACT-03**: Facture numbers contain no gaps and no duplicates, including under concurrent creation and under retried requests
- [ ] **FACT-04**: TVA is configured per article and broken out per rate on the facture, with no hardcoded global rate
- [ ] **FACT-05**: A facture records the buyer's ICE
- [ ] **FACT-06**: A facture moves through an explicit lifecycle — brouillon, émise, transmise, validée — rather than being considered final once printed
- [ ] **FACT-07**: A user can print a Facture A4 carrying the client's branding
- [ ] **FACT-08**: A user can correct a facture by issuing an avoir; a facture can never be deleted
- [ ] **FACT-09**: A user can take an acompte at order time and record the balance paid at retrait, with the remainder visible until settled
- [ ] **FACT-10**: Payments are recorded as an append-only ledger of lines, each line carrying its payer and payment mode
- [ ] **FACT-11**: The facture is stored as structured data (not as a rendered PDF record), so it stays convertible to UBL for the DGI mandate
- [ ] **FACT-12**: Submitting the same sale twice — a retried request on a flaky link — never produces two factures; sale creation is idempotent
- [ ] **FACT-13**: A user can create a devis that carries no legal number, print it, and convert it into a facture without re-entering the lines
- [ ] **FACT-14**: A user can apply a remise to a sale line or to the whole sale, and TVA and totals recalculate correctly

### Caisse (CAISSE)

- [ ] **CAISSE-01**: Each magasin has its own caisse, holding a running ledger of cash entries in and out
- [ ] **CAISSE-02**: A user can see the current caisse balance for their magasin
- [ ] **CAISSE-03**: A user can read daily and monthly totals off the caisse ledger, broken down by payment mode
- [ ] **CAISSE-04**: An owner can see the caisse of every magasin in their business
- [ ] **CAISSE-05**: Caisse entries are append-only; a mistake is corrected by a compensating entry, never by editing history
- [ ] **CAISSE-06**: A payment by chèque records its date d'échéance and does not count toward the caisse cash balance until it is marked encaissé
- [ ] **CAISSE-07**: A user can see every chèque not yet encaissé with its due date
- [ ] **CAISSE-08**: A user can record a physical cash count; the system shows attendu versus compté and stores the écart as a note, without blocking anything

### Reminders (RAPPEL)

- [ ] **RAPPEL-01**: A user sees a reminder when an article drops below its réappro threshold
- [ ] **RAPPEL-02**: An owner sees a reminder when a fournisseur payment échéance is due
- [ ] **RAPPEL-03**: A user sees a reminder to follow up a client for a new ordonnance, new lenses or a contact lens re-order
- [ ] **RAPPEL-04**: A user sees a relance AMO 23 months after a client's purchase (11 months for children aged 12 or under), noting the client is reimbursable again
- [ ] **RAPPEL-05**: A user can contact a client about a reminder via a pre-filled WhatsApp link

### Tableau de Bord (DASH)

Owner-facing reporting. Deliberately not a BI tool.

- [ ] **DASH-01**: An owner sees CA du jour and CA du mois, per magasin and consolidated
- [ ] **DASH-02**: An owner sees marge brute and panier moyen over a chosen period
- [ ] **DASH-03**: An owner sees encours client (restes à payer) and encours fournisseur

### Branding & Documents (BRAND)

- [ ] **BRAND-01**: An owner can upload a logo and set colors and shop name for their business
- [ ] **BRAND-02**: The branding appears in the application UI for that client
- [ ] **BRAND-03**: The branding appears on printed factures and bons de commande
- [ ] **BRAND-04**: Printed documents render Arabic characters correctly in client names and addresses
- [ ] **BRAND-05**: A user can print an A5 reçu d'acompte carrying the client's branding, so a client leaving a deposit gets printed proof

### Applications (APP)

- [ ] **APP-01**: The web application runs in a browser with a French interface
- [ ] **APP-02**: The mobile application runs on phone and tablet with the same features as the web application
- [ ] **APP-03**: Amounts, dates and numbers are formatted for Morocco (MAD, French conventions)

### Subscription & Self-Serve (BILL)

- [ ] **BILL-01**: An optician can sign up, and a trial of their business is provisioned automatically
- [ ] **BILL-02**: An optician can subscribe and pay through a Moroccan payment method
- [ ] **BILL-03**: Payment gateway integration sits behind an interface, so a second gateway can be added without touching billing logic
- [ ] **BILL-04**: A subscription that lapses restricts access without destroying the client's data
- [ ] **BILL-05**: An operator can see the status of every client business and its subscription

---

## v2 — Deferred

Real requirements, deliberately not in v1.

- Accounting export (CSV) of ventes, achats and TVA collectée/déductible — cheap insurance against "add full accounting" pressure
- Split "part organisme / reste à charge" — trigger: the third prospect mentions bons de prise en charge
- SAV / retouche / garantie — trigger: shops asking how to track a frame sent back to the supplier
- Lentilles renewal tracking — a 1–3 month cadence, a richer relance loop than glasses
- Transfert de stock entre magasins — trigger: the first genuine multi-shop customer
- Advanced statistics (taux de transformation, top verriers, rotation du stock) beyond the DASH basics
- WhatsApp Business API for automated relances (v1 uses a pre-filled wa.me link)
- Gérant role presets, if chains ask for them
- DGI e-invoicing transmission, when the mandate and its décret are published

---

## Out of Scope

With reasoning, to prevent re-adding.

- **Mutuelle / tiers payant** — in Morocco the patient claims, not the optician, and no local competitor offers a claims module. Kept cheap to add later by modelling payments as lines with a payer.
- **Arabic / RTL interface** — every local competitor is French-only. Arabic *data* still renders (BRAND-04); only the RTL interface is excluded.
- **Logins for floor vendeurs** — the optician and gérants operate the system; a vendeur is data on a sale.
- **A separate deployment per client** — one shared application serves everyone; only the database is per client.
- **A database per magasin** — magasins live inside their client's database, so owner-wide views stay ordinary queries.
- **Full white-label** (custom domains, deep theming) — branding only in v1.
- **An app for the shop's own customers** — a 24-month purchase cycle gives no retention loop.
- **Formal clôture Z / certified register (NF525-style)** — NF525 is French and Morocco has no equivalent, so building it is pure cost. The caisse stays a ledger, with a *non-blocking* comptage (CAISSE-08) as the owner's check on a gérant — that is as far as it goes.
- **Ticket de caisse on thermal printers** — the client needs an itemized A4 original for AMO, and thermal paper fades against a 60-day filing deadline. A printed acompte receipt is covered by BRAND-05 on A5 instead.
- **Barcode scanning at the counter** — no scanner hardware assumed. STOCK-05 keeps it free to add later, and STOCK-09 covers printing the labels themselves.
- **Offline operation** — the application requires a connection. Taken deliberately: it removes the single riskiest phase (a purpose-built sync layer budgeted at 4–8 weeks) and every sync-conflict failure mode with it. Accepted costs: the counter stops during an outage, and a competitor advertising local-first sync at 800 DH/year wins that comparison. Reversing it later means retrofitting local storage plus a sync layer, not flipping a flag.

---

## Open Questions

These block schema decisions and need a Moroccan comptable, the DGI, or optician interviews — not more search.

**Blocking facturation (FACT-02, FACT-04, FACT-09):**
1. Which TVA rate applies to montures, verres, lentilles and prestations after the 2026 reform
2. Whether a facture série per magasin is legal, or a client needs one continuous série per company
3. TVA treatment of the acompte (débits vs encaissements), and whether a facture d'acompte needs its own fiscal number
4. Whether the facture is issued at commande or at délivrance

**Needed before their phase, not blocking now:**
5. DGI e-invoicing wave-3 date and threshold — reported January 2027, but the implementing décret was reportedly unpublished as of March 2026
6. The CNDP controller/processor split between the platform and the optician
7. Whether Moroccan rails genuinely support recurring card-on-file — a vendor claim needing sandbox proof (blocks BILL-02)
8. Payment-mode to caisse mapping, worth an hour with two or three real opticians (informs CAISSE-03)

---

## Traceability

Every v1 requirement maps to exactly one phase. Source of truth for phase structure: `.planning/ROADMAP.md`.

**Coverage: 90/90 requirements mapped — no orphans, no duplicates.**

| Requirement | Phase |
|-------------|-------|
| LEGAL-01 | Phase 1 — Legal & Compliance Track |
| LEGAL-02 | Phase 1 — Legal & Compliance Track |
| LEGAL-03 | Phase 1 — Legal & Compliance Track |
| LEGAL-04 | Phase 12 — Self-Serve Subscription & Opérations Client |
| LEGAL-05 | Phase 6 — Vente & Facturation |
| TENANT-01 | Phase 2 — Tenancy Foundation & Control Plane |
| TENANT-02 | Phase 2 — Tenancy Foundation & Control Plane |
| TENANT-03 | Phase 2 — Tenancy Foundation & Control Plane |
| TENANT-04 | Phase 2 — Tenancy Foundation & Control Plane |
| TENANT-05 | Phase 2 — Tenancy Foundation & Control Plane |
| TENANT-06 | Phase 2 — Tenancy Foundation & Control Plane |
| TENANT-07 | Phase 2 — Tenancy Foundation & Control Plane |
| TENANT-08 | Phase 2 — Tenancy Foundation & Control Plane |
| TENANT-09 | Phase 2 — Tenancy Foundation & Control Plane |
| PERM-01 | Phase 3 — Comptes, Permissions & App Shell |
| PERM-02 | Phase 3 — Comptes, Permissions & App Shell |
| PERM-03 | Phase 3 — Comptes, Permissions & App Shell |
| PERM-04 | Phase 3 — Comptes, Permissions & App Shell |
| PERM-05 | Phase 3 — Comptes, Permissions & App Shell |
| PERM-06 | Phase 3 — Comptes, Permissions & App Shell |
| PERM-07 | Phase 6 — Vente & Facturation |
| CLIENT-01 | Phase 4 — Clients & Ordonnances |
| CLIENT-02 | Phase 4 — Clients & Ordonnances |
| CLIENT-03 | Phase 4 — Clients & Ordonnances |
| CLIENT-04 | Phase 4 — Clients & Ordonnances |
| CLIENT-05 | Phase 4 — Clients & Ordonnances |
| CLIENT-06 | Phase 4 — Clients & Ordonnances |
| CLIENT-07 | Phase 4 — Clients & Ordonnances |
| CLIENT-08 | Phase 4 — Clients & Ordonnances |
| CLIENT-09 | Phase 4 — Clients & Ordonnances |
| CLIENT-10 | Phase 4 — Clients & Ordonnances |
| STOCK-01 | Phase 5 — Stock & Catalogue |
| STOCK-02 | Phase 5 — Stock & Catalogue |
| STOCK-03 | Phase 6 — Vente & Facturation |
| STOCK-04 | Phase 6 — Vente & Facturation |
| STOCK-05 | Phase 5 — Stock & Catalogue |
| STOCK-06 | Phase 5 — Stock & Catalogue |
| STOCK-07 | Phase 5 — Stock & Catalogue |
| STOCK-08 | Phase 5 — Stock & Catalogue |
| STOCK-09 | Phase 9 — Branding & Documents Imprimés |
| ACHAT-01 | Phase 8 — Fournisseurs & Achats |
| ACHAT-02 | Phase 8 — Fournisseurs & Achats |
| ACHAT-03 | Phase 8 — Fournisseurs & Achats |
| ACHAT-04 | Phase 8 — Fournisseurs & Achats |
| ACHAT-05 | Phase 8 — Fournisseurs & Achats |
| ACHAT-06 | Phase 8 — Fournisseurs & Achats |
| ACHAT-07 | Phase 8 — Fournisseurs & Achats |
| FACT-01 | Phase 6 — Vente & Facturation |
| FACT-02 | Phase 6 — Vente & Facturation |
| FACT-03 | Phase 6 — Vente & Facturation |
| FACT-04 | Phase 6 — Vente & Facturation |
| FACT-05 | Phase 6 — Vente & Facturation |
| FACT-06 | Phase 6 — Vente & Facturation |
| FACT-07 | Phase 9 — Branding & Documents Imprimés |
| FACT-08 | Phase 6 — Vente & Facturation |
| FACT-09 | Phase 7 — Paiements & Caisse |
| FACT-10 | Phase 7 — Paiements & Caisse |
| FACT-11 | Phase 6 — Vente & Facturation |
| FACT-12 | Phase 6 — Vente & Facturation |
| FACT-13 | Phase 6 — Vente & Facturation |
| FACT-14 | Phase 6 — Vente & Facturation |
| CAISSE-01 | Phase 7 — Paiements & Caisse |
| CAISSE-02 | Phase 7 — Paiements & Caisse |
| CAISSE-03 | Phase 7 — Paiements & Caisse |
| CAISSE-04 | Phase 7 — Paiements & Caisse |
| CAISSE-05 | Phase 7 — Paiements & Caisse |
| CAISSE-06 | Phase 7 — Paiements & Caisse |
| CAISSE-07 | Phase 7 — Paiements & Caisse |
| CAISSE-08 | Phase 7 — Paiements & Caisse |
| RAPPEL-01 | Phase 10 — Rappels, Relances & Tableau de Bord |
| RAPPEL-02 | Phase 10 — Rappels, Relances & Tableau de Bord |
| RAPPEL-03 | Phase 10 — Rappels, Relances & Tableau de Bord |
| RAPPEL-04 | Phase 10 — Rappels, Relances & Tableau de Bord |
| RAPPEL-05 | Phase 10 — Rappels, Relances & Tableau de Bord |
| DASH-01 | Phase 10 — Rappels, Relances & Tableau de Bord |
| DASH-02 | Phase 10 — Rappels, Relances & Tableau de Bord |
| DASH-03 | Phase 10 — Rappels, Relances & Tableau de Bord |
| BRAND-01 | Phase 9 — Branding & Documents Imprimés |
| BRAND-02 | Phase 9 — Branding & Documents Imprimés |
| BRAND-03 | Phase 9 — Branding & Documents Imprimés |
| BRAND-04 | Phase 9 — Branding & Documents Imprimés |
| BRAND-05 | Phase 9 — Branding & Documents Imprimés |
| APP-01 | Phase 3 — Comptes, Permissions & App Shell |
| APP-02 | Phase 11 — Mobile Parity |
| APP-03 | Phase 3 — Comptes, Permissions & App Shell |
| BILL-01 | Phase 12 — Self-Serve Subscription & Opérations Client |
| BILL-02 | Phase 12 — Self-Serve Subscription & Opérations Client |
| BILL-03 | Phase 12 — Self-Serve Subscription & Opérations Client |
| BILL-04 | Phase 12 — Self-Serve Subscription & Opérations Client |
| BILL-05 | Phase 12 — Self-Serve Subscription & Opérations Client |

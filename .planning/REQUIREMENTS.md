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

### Stock (STOCK)

- [ ] **STOCK-01**: A user can add articles (montures, accessoires, verres stockés) to a magasin's stock with a reference and a price
- [ ] **STOCK-02**: Stock movements are recorded in an append-only ledger, and the current quantity is derived from it rather than stored as a mutable column
- [ ] **STOCK-03**: A sale decrements stock and a réception increments it, automatically
- [ ] **STOCK-04**: A sale warns before it would take stock negative; a shortfall the user accepts anyway raises an anomaly in a réconciliation queue the owner can see and clear
- [ ] **STOCK-05**: A user can search stock by exact reference, and the search submits on Enter so a keyboard-wedge scanner works without a UI change
- [ ] **STOCK-06**: A user can see the status of a client's special order as commandé → prêt → client prévenu → livré, and change it
- [ ] **STOCK-07**: A user can set a réappro threshold per article

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

### Caisse (CAISSE)

- [ ] **CAISSE-01**: Each magasin has its own caisse, holding a running ledger of cash entries in and out
- [ ] **CAISSE-02**: A user can see the current caisse balance for their magasin
- [ ] **CAISSE-03**: A user can read daily and monthly totals off the caisse ledger, broken down by payment mode
- [ ] **CAISSE-04**: An owner can see the caisse of every magasin in their business
- [ ] **CAISSE-05**: Caisse entries are append-only; a mistake is corrected by a compensating entry, never by editing history

### Reminders (RAPPEL)

- [ ] **RAPPEL-01**: A user sees a reminder when an article drops below its réappro threshold
- [ ] **RAPPEL-02**: An owner sees a reminder when a fournisseur payment échéance is due
- [ ] **RAPPEL-03**: A user sees a reminder to follow up a client for a new ordonnance, new lenses or a contact lens re-order
- [ ] **RAPPEL-04**: A user sees a relance AMO 23 months after a client's purchase (11 months for children aged 12 or under), noting the client is reimbursable again
- [ ] **RAPPEL-05**: A user can contact a client about a reminder via a pre-filled WhatsApp link

### Branding & Documents (BRAND)

- [ ] **BRAND-01**: An owner can upload a logo and set colors and shop name for their business
- [ ] **BRAND-02**: The branding appears in the application UI for that client
- [ ] **BRAND-03**: The branding appears on printed factures and bons de commande
- [ ] **BRAND-04**: Printed documents render Arabic characters correctly in client names and addresses

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

- Non-blocking comptage de caisse — the vendeur or gérant enters counted cash, the system shows attendu vs compté and stores the difference as a note. The strongest v2 candidate; roughly a day's work.
- Devis / proforma, used for insurer prise en charge pre-approval
- Owner statistics dashboard
- Physical inventaire screen with a single focused input
- Accounting export (CSV)
- Label printing for articles
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
- **Formal clôture Z with écarts de caisse** — the caisse stays a pure ledger of the actual cash, as specified.
- **Ticket de caisse on thermal printers** — the client needs an itemized A4 original for AMO, and thermal paper fades against a 60-day filing deadline.
- **Barcode scanning as a feature** — no hardware assumed; STOCK-05 keeps it free to add.
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

Filled in by the roadmapper: every v1 requirement maps to exactly one phase.

| Requirement | Phase |
|-------------|-------|
| _(pending roadmap)_ | |

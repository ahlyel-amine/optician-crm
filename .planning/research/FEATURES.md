> **⚠️ DISPOSITIONS TAKEN AFTER THIS RESEARCH — read before acting on anything below.**
>
> **Adopted into v1:** G1 suivi de commande (STOCK-06) · G2 devis (FACT-13) · G3 avoir (FACT-08) ·
> G4 facture itemisée (FACT-01, LEGAL-05) · G5 prescripteur + date (CLIENT-04/05) and the relance AMO
> 24 mois (RAPPEL-04) · G6 tableau de bord owner (DASH-01…03) · G7 inventaire physique (STOCK-08).
> Also adopted beyond the G-list: étiquettes prix (STOCK-09), remise sur ligne (FACT-14), chèque avec
> date d'échéance (CAISSE-06/07), reçu d'acompte A5 (BRAND-05), photo de l'ordonnance (CLIENT-09),
> recherche tolérante aux variantes de translittération (CLIENT-10), sauvegarde et restauration par
> client (TENANT-09).
>
> **Deferred to v2:** G8 export comptable.
>
> **Exclusion verdicts acted on:** the comptage de caisse reversal was accepted — a *non-blocking*
> attendu-vs-compté check is in v1 (CAISSE-08); formal clôture Z / NF525 stays out. Label printing is
> in v1; barcode *scanning* stays out, with search built scanner-ready.
>
> **Two things below no longer apply.** Offline is **out of scope permanently** — ignore the
> offline rows, the "Offline-first" differentiator and the OpticWizard parity argument that rests on
> it. And only the optician and gérants log in; floor vendeurs have no account, so "vendeur-scoped
> permissions" means per-gérant grants.
>
> v1 is **90 requirements**. `.planning/PROJECT.md` and `.planning/REQUIREMENTS.md` are authoritative.

# Feature Research

**Domain:** Optician shop management SaaS (logiciel de gestion pour opticiens), Morocco
**Researched:** 2026-09-09
**Confidence:** MEDIUM-HIGH

Sources are marketing pages of live Moroccan and French competitors plus Moroccan tax and
AMO reimbursement rules. Competitor feature lists are HIGH confidence (vendor's own copy);
inferences about *why* Moroccan opticians buy are MEDIUM (no direct user interviews were
possible). Every claim about Moroccan law is flagged with its confidence inline.

---

## Market Reality Check (read this before the tables)

**The Moroccan optician software market is not empty — it is crowded and cheap.**

| Product | Origin | Model | Price | Notes |
|---------|--------|-------|-------|-------|
| OpticWizard | Moroccan | Cloud + local app, **offline-first with sync** | **800 DH/year** (500 DH/6mo) | Windows/Linux/macOS/iOS/Android. Clients, ordonnances, stock, ventes, **paiements partiels**, facturation, offline. Advertises "factures mutuelle". Closest competitor to this project. |
| MyOpti | Moroccan | Cloud, responsive | 1 500 / 3 000 / 4 000 DH/year | "Suivi des ordonnances", point de vente, caisse, multi-magasins, multi-utilisateurs, BL/devis/factures, **impression ticket code à barres**, soldes/promos, rapports |
| Netoptis | Moroccan | 100% online | 1 month free trial | Multi-magasin, multi-agent, référentiel articles (montures, verres, lentilles), fournisseurs et achats, clients et ventes, tableaux de bord |
| Gestoptic | Moroccan | 4 tiers (Light→Platinum) | not published | Portefeuille client + fournisseur, avoirs, **journal de caisse**, échéanciers, statistiques marge/CA/charges, **marketing direct SMS** |
| Optix System, PLANET SOFT, OpticManager, optiques.ma | Moroccan | mix desktop/cloud | not published | PLANET SOFT claims 500+ Moroccan opticians, 20+ years — the incumbent installed base. Generic retail with optical flavour. |
| Osmose / MyEasyOptic / Cosium / Optimum | French | Cloud | — | Full French vertical: EDI verriers, carte Vitale, SCOR, NF525, tiers payeurs. **Most of this is legally French and irrelevant here.** |

**Three consequences that constrain the whole feature set:**

1. **ARPU is ~800–4 000 DH/year (roughly 80–400 USD).** Feature bloat is not affordable.
   Every feature must be cheap to build and cheap to support. This is the single strongest
   argument for the declared exclusions.
2. **Offline is already claimed by a competitor at 800 DH/year.** The Core Value in
   PROJECT.md ("the counter keeps working when internet drops") is a *parity requirement*,
   not a moat. It must be there, and it must be genuinely better than OpticWizard's, but the
   pitch cannot rest on it alone.
3. **The real gap in the local field is depth, not breadth.** Every local competitor sells
   "clients + stock + ventes + caisse". Almost none advertise a *structured* ordonnance
   (OD/OG sphère/cylindre/axe/addition/EP), a compte fournisseur with échéances, prix
   d'achat and margin visibility, or vendeur-scoped permissions. That is where this project
   is genuinely differentiated — and it happens to be exactly what PROJECT.md already picked.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features Moroccan opticians assume exist. Missing these = the product feels incomplete
against a 800 DH/year competitor.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Fiche client + historique d'achats | Universal across all 8 local competitors | LOW | In PROJECT.md ✅ |
| **Ordonnance structurée OD/OG** (sphère, cylindre, axe, addition, EP) | It is the domain. Feeds lens order and renewal | MEDIUM | In PROJECT.md ✅. **Add prescriber fields** — see gap G5 below |
| Historique des ordonnances | Renewals and evolution of correction | LOW | In PROJECT.md ✅ |
| **Suivi de commande / statut du dossier client** | The single most operational optician workflow. MyOpti sells it as "Suivi des ordonnances (en cours / prêt / livré)". LensPro sells statuses + notification | MEDIUM | **GAP — only implicit in PROJECT.md as "commande spéciale".** See G1 |
| Stock montures / verres / lentilles / accessoires, par magasin | Universal | MEDIUM | In PROJECT.md ✅ |
| Décrémentation stock à la vente, incrément à la réception | Universal | MEDIUM | In PROJECT.md ✅. Hard part is offline ordering |
| Fournisseurs: fiche, catalogue, prix négociés | Universal (Netoptis, Gestoptic) | LOW | In PROJECT.md ✅ |
| Bon de commande fournisseur + réception | Universal | MEDIUM | In PROJECT.md ✅ |
| Compte fournisseur / échéancier / règlements | Gestoptic sells it explicitly | MEDIUM | In PROJECT.md ✅ |
| Prix d'achat + marge | Owner-facing, why the owner buys the software | LOW | In PROJECT.md ✅ |
| **Facture A4 conforme art. 145 CGI** (ICE, IF, RC, TP, n° séquentiel, HT/TVA/TTC) | Legal. A non-conforming invoice can trigger a DGI procedure. Fine of ~500 DH/facture, capped 50 000 DH/yr | MEDIUM | In PROJECT.md ✅. **12 mandatory mentions** — HIGH confidence |
| **Facture détaillée ligne par ligne (monture séparée des verres)** | AMO ceilings are per-line: monture 400 DH, verres 400 DH, progressifs 800 DH. A single "ensemble 1 800 DH" line gets the client under-reimbursed | LOW | **GAP — this is the hidden requirement that makes "no mutuelle module" survivable.** See G4 |
| **Devis / facture proforma** | MyOpti ("BL, Devis et factures"), Gestoptic, OpticManager all sell it. Used for insurer *prise en charge* pre-approval and for a 2 000 DH purchase decision | LOW | **GAP — absent from PROJECT.md.** See G2 |
| **Avoir / retour / annulation** | Gestoptic and MyOpti sell it. Also a *legal consequence*: with gapless sequential numbering you may not delete a facture — an avoir is the only correction mechanism | MEDIUM | **GAP — absent from PROJECT.md.** See G3 |
| Acompte / paiement partiel / reste à payer | Universal in this vertical (glasses are ordered, then collected). OpticWizard sells it by name | MEDIUM | In PROJECT.md ✅ |
| Modes de paiement multiples (espèces, chèque, carte, virement) | Chèque is still heavily used by Moroccan SMEs | LOW | Partially implied. Chèque needs a due date field |
| Caisse / journal de caisse par magasin, totaux jour/mois | Universal. Gestoptic sells "journal de caisse" | MEDIUM | In PROJECT.md ✅ |
| **Tableau de bord / statistiques (CA, marge, panier moyen)** | Advertised by literally every competitor found | MEDIUM | **GAP — implied by "owner sees revenue" but not scoped.** See G6 |
| Multi-magasin + multi-utilisateur | MyOpti and Netoptis both sell it | MEDIUM | In PROJECT.md ✅ |
| Recherche client / article rapide | With no barcode scanning, search *is* the UI. Must be accent-insensitive, tolerant of Arabic-name transliteration variants (Mohamed/Mohammed/Mhamed), and work offline | MEDIUM | **Raise priority — this is load-bearing because of the barcode exclusion** |
| Inventaire physique | Counting 500–2 000 frames. Every competitor sells "gestion d'inventaire" | MEDIUM | **GAP — not in PROJECT.md.** See G7 |
| Impression étiquettes prix / référence | optiques.ma sells "impression de code-barres articles"; MyOpti sells "impression ticket code à barre" | LOW | See the barcode exclusion assessment |
| Sauvegarde automatique | Every local competitor leads with it — the incumbents are desktop apps that lose data | LOW | Free consequence of SaaS; **say it loudly in marketing** |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Relance renouvellement calée sur le cycle AMO 24 mois** | AMO (CNSS/CNOPS) reimburses lunetterie **once per 24 months** (12 months for children ≤12). A reminder at month 23 saying "M. X est de nouveau remboursable" is a *money-making* reminder, not a nag. **No competitor found advertises this.** The structured ordonnance + its date is exactly the data needed | LOW | **Highest value-to-cost ratio in the entire product.** Free rider on features already planned. Make it the headline |
| Relance client via **WhatsApp** ("vos lunettes sont prêtes") | WhatsApp dominates Moroccan consumer messaging. Gestoptic still sells SMS. Utility WhatsApp msg ≈ 0.08 MAD vs structurally expensive Moroccan SMS | **LOW if done right** | **v1: generate a pre-filled `wa.me` deep link the vendeur taps.** Zero API, zero cost, zero Meta approval, works on the mobile app today. WhatsApp Business API (BSP, ~25–75 EUR/mo + per-tenant WABA) is HIGH complexity — defer it |
| **Marge par vente et par article, invisible au vendeur** | PROJECT.md states the trust boundary explicitly. Local competitors show statistics but not role-scoped ones | MEDIUM | Depends on prix d'achat + permissions |
| **Permissions personnalisables par l'owner** | Competitors offer fixed "multi-utilisateurs". Fine-grained is a genuine step up | MEDIUM-HIGH | Do not over-build: a checklist of ~20 permissions beats an RBAC engine |
| Vue consolidée multi-magasin pour l'owner | Netoptis/MyOpti support multi-magasin but the consolidated-margin view is the owner's actual question | MEDIUM | Free given one DB per client (magasin is a column, not a database) |
| **Offline-first sur mobile ET web, avec numérotation de facture sans trou** | Parity vs OpticWizard, but the *gapless numbering after offline sync* is the hard part nobody advertises solving | **HIGH** | See PITFALLS — this is the riskiest single requirement in the project |
| Self-serve signup + abonnement par moyen de paiement marocain | Local competitors mostly sell by phone call and install. Netoptis offers a free month — closest to self-serve | MEDIUM-HIGH | Real differentiator on *distribution*, not on features |
| Branding par client sur la facture imprimée | Opticians are brand-proud; a facture with their logo is what the client hands to CNSS | LOW | In PROJECT.md ✅ |
| Réappro par seuil, par magasin | Standard elsewhere, weakly advertised locally | LOW | In PROJECT.md ✅ |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Moteur de tiers payant / gestion des remboursements** | "My insurer clients" | In Morocco the *patient* claims, not the optician. Building claim files, organism grids, écarts de remboursement and relances is the largest module in French software (Osmose ships an entire "Tiers Payeurs" module) for a flow that mostly does not exist here | Itemized facture + a generic multi-payer payment model so a split can be added later (see G4) |
| **Commande EDI verriers** (Essilor OpsysWeb, Hoya iLog, BBGR) | "Order lenses in one click" | The EDI infrastructure French software plugs into does not exist for the Moroccan market at SME scale. Would require per-supplier integrations you cannot get access to | Bon de commande PDF + WhatsApp/email to the labo. This is how Moroccan shops already order |
| **Caisse certifiée / conformité NF525** | Copied from French vendor marketing | NF525 is a **French** legal requirement. Morocco has no equivalent certification. Building it is pure cost | Running ledger, as decided. See exclusion assessment #4 |
| Carte Vitale, SCOR, devis normalisé, réseaux de soins, grilles mutuelles | Appear in every French competitor's catalogue | 100% French regulatory artefacts | Ignore entirely |
| **Comptabilité générale (grand livre, bilan, liasse)** | "So my accountant doesn't need anything else" | Unbounded scope, requires accounting expertise and per-client chart of accounts, kills a 1 500 DH/year product | **Export CSV/Excel of ventes, achats and TVA collectée/déductible for the comptable.** This is 2 days of work and satisfies 95% of the request |
| Agenda / prise de rendez-vous / module optométrie-réfraction | "I do refractions in the shop" | Drags the product toward medical practice management, a different product with different buyers. Also: AMO only accepts an **ophthalmologist's** prescription, so an in-shop refraction is not the reimbursable document | A free-text "mesures magasin" block on the ordonnance, clearly distinct from the ordonnance médicale |
| Programme de fidélité à points | Retail reflex; MyOpti sells "soldes et promos" | Purchase cycle is **once every 24 months**. A points balance that takes 6 years to be worth anything creates data with no behaviour change | The AMO-renewal relance *is* the retention mechanism. Ship "remise" on a line and stop |
| OCR / scan de l'ordonnance | "Faster than typing 10 numbers" | Osmose ships prescription OCR, but handwritten Moroccan ophthalmologist prescriptions are the worst possible OCR input, and a mis-read axis produces unusable lenses. PROJECT.md already decided structured entry | Structured fields + optional photo attachment of the paper ordonnance for evidence |
| Boutique en ligne / catalogue public / essayage virtuel | "Also sell online" | Different business, different buyer, different competitor set (glasse.ma) | Out of scope permanently |
| Application pour le client final | "Modern" | See exclusion assessment #6 — no retention loop at a 24-month cadence | wa.me link |
| Full white-label / domaine personnalisé | Chains ask | Disproportionate for v1; PROJECT.md already excluded it | Branding only ✅ |

---

## Gaps Found in PROJECT.md (recommended additions)

These are features the research says are **table stakes in this vertical** but are absent or
only implicit in the Active requirements. Listed in priority order.

**G1 — Suivi de commande / statut du dossier client (HIGH priority, MEDIUM complexity)**
The core optician loop is: client orders → verres commandés au labo → verres reçus →
montage → client prévenu → livré + solde encaissé. MyOpti sells this as its ordonnance
feature. Without it, a shop cannot answer "are M. Bennani's glasses ready?" — which is the
question they get on the phone all day. PROJECT.md covers commande spéciale (outbound to
supplier) but not the *client-facing status* of that order. **Recommend: an explicit status
field on the client order, with `client prévenu le` timestamp, and a "commandes en attente"
worklist screen.** This also becomes the trigger for the WhatsApp "vos lunettes sont prêtes"
message — the highest-frequency, highest-goodwill use of the reminder system.

**G2 — Devis / facture proforma (MEDIUM priority, LOW complexity)**
Advertised by MyOpti, Gestoptic and OpticManager. Two Moroccan uses: (a) the client takes a
devis to their private insurer to request a *prise en charge* before buying; (b) a 2 000 DH
purchase decision usually involves going home to think. A devis is a facture without a legal
number that converts into one — cheap if designed alongside facturation, expensive if bolted
on afterwards.

**G3 — Avoir / retour / annulation (MEDIUM priority, MEDIUM complexity)**
Not optional given the sequential-numbering constraint: once a facture is numbered you cannot
delete it, so the *only* legal way to fix "wrong correction, wrong price, client cancelled"
is an avoir. Combined with the offline requirement, "vendeur invoiced the wrong thing while
offline" is a certainty, not an edge case. Also needs a stock re-entry and a caisse
counter-entry. **Design this at the same time as facturation, not later.**

**G4 — Facture itemisée monture / verres / lentilles (HIGH priority, LOW complexity)**
AMO reimbursement is capped per component: monture 400 DH, verres standard 400 DH, verres
progressifs 800 DH, ceilings ~800 DH standard / ~1 200 DH progressif, and the complementary
mutuelle then works off the AMO décompte (MEDIUM-HIGH confidence — figures widely cited by
Moroccan optician and health sites, worth confirming with one optician). The submitted
document must be the **original itemized invoice**. If the software prints "Équipement
optique complet — 1 800 DH" as one line, the optician's client gets less money back and
blames the optician. **This is the requirement that makes deferring the entire mutuelle
module survivable — treat it as a hard constraint on the facture model, not a nice-to-have.**

**G5 — Prescripteur et date sur l'ordonnance (HIGH priority, LOW complexity)**
AMO accepts only a prescription signed by an **ophtalmologiste** (optometrist prescriptions
are ineligible), and the claim must be filed within **60 days of the prescription date**.
So the ordonnance record needs: `prescripteur` (name), `type` (ophtalmologiste / mesure
magasin), `date de prescription`. The 24-month renewal clock also runs from the prescription
date, not the sale date — so G5 is a hard dependency of the AMO-renewal relance
differentiator. Two extra fields, very large payoff.

**G6 — Tableau de bord owner (MEDIUM priority, MEDIUM complexity)**
Every competitor advertises statistics. Minimum viable: CA du jour/mois par magasin, marge
brute, panier moyen, top montures, valeur du stock, encours client (restes à payer),
encours fournisseur. Owner-only by permission. Do not build a BI tool.

**G7 — Inventaire physique (MEDIUM priority, MEDIUM complexity)**
Needed at least annually and it is where the no-barcode decision actually bites. See the
barcode exclusion assessment for the cheap mitigation.

**G8 — Export comptable (LOW priority, LOW complexity)**
CSV/Excel of ventes, achats, TVA collectée and déductible per period. Cheap insurance
against the "add full accounting" pressure.

---

## Assessment of the Declared v1 Exclusions

Each exclusion is judged **SAFE TO DEFER** / **SAFE WITH CONDITIONS** / **ADOPTION-BLOCKING**.

### 1. Mutuelle / tiers payant — **SAFE WITH CONDITIONS** ✅

**Why it is safe.** Morocco's AMO reimburses the *insured person*, not the optician. The
documented flow is: patient pays the optician in full → submits ophthalmologist's
prescription + **original itemized facture** + feuille de soins + copy of the insurance card
to CNSS/CNOPS → receives a décompte → optionally forwards it to a complementary mutuelle.
Deadline 60 days from the prescription, processing 45–60 days. The optician is never in the
payment chain in the standard case. Not one of the eight Moroccan competitors examined
advertises a claims/tiers-payant module; the closest is OpticWizard's "**factures mutuelle**",
which is a *printed invoice suitable for a claim*, not claim management. Confidence: HIGH on
the patient-pays flow, MEDIUM on the absence of any local demand.

**The conditions (do these in v1, they are cheap):**
1. **The facture must be itemized** — monture, verres (with the correction), lentilles,
   accessoires as separate priced lines. Non-negotiable (G4).
2. **The facture must carry the ordonnance details and the ophthalmologist's name/date** (G5),
   since the claim file ties the invoice to the prescription.
3. **Model payments as N payment lines each with a payer**, not as a single
   `montant_paye` scalar. If a payment line can say "payer = organisme X, ref prise en
   charge = Y", then the day a client says "AtlantaSanad covers 70% directly for this
   corporate account", you add a payer type and a field — not a schema migration.

**The residual risk.** "Conventionné" opticians with CNSS/CNOPS exist, and private insurers
(AtlantaSanad, Saham/Sanlam, AXA, RMA, Wafa) issue *bons de prise en charge* to corporate
employees. A shop with a big corporate contract nearby genuinely does split invoices. If
condition 3 is honoured that shop is served by a small v1.x feature ("part organisme /
reste à charge"), not by a rewrite. **If condition 3 is skipped, this exclusion becomes
expensive later.** That is the whole risk.

### 2. Arabic / RTL interface — **SAFE WITH ONE CHEAP CONDITION** ✅

**Why it is safe.** Every Moroccan optician product examined is French-only, and several use
"interface 100% en français" as a *selling point*. Opticians are diplômés with
post-baccalaureate training in a French-language curriculum; the entire trade vocabulary
(ordonnance, monture, verres progressifs, écart pupillaire) is French with no established
Darija equivalent. Building an RTL layout is not a translation task — it is a mirrored UI, a
second PDF pipeline, and a permanent double maintenance cost, for zero observed competitive
pressure. Confidence: HIGH for the UI language, MEDIUM for the long-run trajectory.

**The condition.** Distinguish *RTL UI* (defer) from *Arabic data* (do now). Client names,
shop names and addresses will sometimes be typed in Arabic script. Ensure UTF-8 end to end
and — critically — that the **PDF/facture generator embeds an Arabic-capable font**. A
facture that renders a client's name as boxes is an embarrassing, hard-to-retrofit bug in a
document the client hands to a government insurer. Cost: one font file and one test case.

### 3. Impression ticket thermique — **SAFE TO DEFER, and probably correct on the merits** ✅

**Why it is safe.** Three reinforcing reasons.
(a) *Legally unnecessary.* Moroccan CGI art. 145 permits a ticket de caisse to serve as the
invoice for retail sales to individuals (quantity, price, TVA where applicable) — but it is
permissive, not mandatory. An A4 facture always satisfies it and more.
(b) *The A4 facture is the more useful document anyway.* The client needs an original itemized
invoice for AMO. A thermal ticket is a *worse* output for the customer's actual need, and
thermal paper fades — a poor fate for a document with a 60-day filing deadline.
(c) *Ticket size matches ticket value.* Moroccan complete pairs run roughly 1 000–1 800 DH
entry, 1 800–2 800 DH standard, 3 500 DH+ premium. Nobody hands out a 5 cm receipt for a
2 500 DH purchase.

**Residual friction.** Low-value side sales — solutions d'entretien, étuis, cordons, piles —
where printing an A4 for 40 DH feels absurd, and the deposit receipt at order time. Mitigate
with an **A5 / half-page "reçu d'acompte" layout** off the same PDF pipeline. Cost: one
template. Do not buy a thermal printer driver stack for this.

### 4. Clôture Z formelle avec écarts de caisse — **SAFE ON THE LAW, PARTIALLY RISKY ON THE BUSINESS** ⚠️

**On the law: unambiguously safe.** "Caisse certifiée NF525" and the certified Z close are a
**French** obligation. Morocco has no equivalent cash-register certification requirement.
Building NF525-style sealing, chaining and inalterability would be pure imported cost.
Confidence: HIGH.

**On the business: this is the one exclusion worth re-examining.** PROJECT.md itself states
the trust boundary — "opticians do not want their vendeurs seeing purchase prices, margins or
business-wide revenue. Permissions are a product requirement, not just hygiene." That anxiety
is about *not fully trusting the staff*. A pure running ledger with no end-of-day count gives
an owner **no mechanism to detect cash going missing**: the ledger only records what the
vendeur chose to record. For a single owner-operator shop, irrelevant. For the multi-magasin
owner — precisely the higher-value customer PROJECT.md says must not be excluded — it is the
first question they will ask, and Gestoptic already sells "suivi de la caisse" and
"statistiques trésorerie" to that buyer.

**Recommendation (small, does not violate the decision).** Do not build a certified Z. Do add
a **"comptage / arrêté de caisse"**: at end of day the vendeur enters the counted cash, the
system shows *attendu* (from the ledger) vs *compté*, stores the difference as a dated note,
and moves on. Non-blocking, no sealing, no fiscal semantics, no reopening rules — roughly a
day of work on top of a ledger that already computes daily totals. It converts the caisse
from a record into a control, which is what the owner is paying for. **Verdict: the stated
exclusion (formal Z, écarts as a fiscal artefact) is safe; excluding *any* end-of-day count
is the most likely of the six exclusions to cost a multi-magasin deal.**

### 5. Barcode scanning at the counter — **SAFE FOR SELLING, RISKY FOR INVENTAIRE** ⚠️

**Safe at the counter.** An optician sells perhaps 5–15 items a day, each a several-minute
consultative sale involving face shape, correction and price negotiation. The seconds saved
by scanning are irrelevant. Nothing in the Moroccan competitor set treats counter scanning as
a headline feature — what two of them advertise is barcode **label printing** ("impression de
code-barres articles", "impression ticket code à barre"), i.e. tagging frames, which is a
different and cheaper feature.

**Risky at inventaire.** A shop holds roughly 500–2 000 frames. An annual physical count
performed by typing references is genuinely painful, and it is the moment an optician most
notices whether the software respects their time.

**Three cheap mitigations that get ~80% of barcode for ~5% of the cost — do all three in v1:**
1. **Print price/reference labels** (référence + prix, optionally a Code128 of the internal
   reference). Two competitors already sell this; it is a PDF template plus a barcode
   rendering library.
2. **Do not architecturally block scanning.** USB and Bluetooth barcode scanners are
   keyboard-wedge devices — they emit keystrokes plus Enter. If the article-search field
   accepts a reference exactly and submits on Enter, an optician who buys a 200 DH scanner
   finds it already works. **The cost of this is zero if the search field is designed for it,
   and a rewrite if it is not.** Make it an explicit design note, not an accident.
3. **A dedicated inventaire screen** with a single always-focused input and a running count,
   so counting is type-Enter-type-Enter rather than navigating a grid.

With those, deferring scanning is safe. Without mitigation 2, "add barcode" later means
reworking the search and sale-entry UI.

### 6. End-customer app — **SAFE TO DEFER, permanently** ✅

Purchase frequency is once per 24 months (AMO cadence, and the real replacement cadence too).
There is no retention loop that justifies a consumer app install: the customer would open it
twice in two years. None of the Moroccan competitors offer one. The two genuine
customer-facing moments — "your glasses are ready" and "you're eligible for reimbursement
again" — are both served better by a WhatsApp message than by an app the customer would have
to install and remember. **Confidence: HIGH. Do not revisit.**

### Summary table

| Exclusion | Verdict | Cheap condition to attach |
|-----------|---------|---------------------------|
| Mutuelle / tiers payant | SAFE with conditions | Itemized facture (G4) + prescriber fields (G5) + **multi-payer payment lines** |
| Arabic / RTL UI | SAFE with condition | UTF-8 + Arabic-capable font in the PDF pipeline |
| Ticket thermique | SAFE — arguably correct | Add an A5 "reçu d'acompte" template |
| Clôture Z formelle | SAFE on law, **partially risky on business** | Add a non-blocking "comptage de caisse" (attendu vs compté) |
| Barcode scanning | SAFE at counter, **risky at inventaire** | Label printing + keyboard-wedge-friendly search + inventaire screen |
| End-customer app | SAFE permanently | wa.me link instead |

**Nothing in the declared exclusion list is outright adoption-blocking.** Two of them
(clôture Z, barcode) carry a real but bounded cost that a small, cheap addition removes.

---

## Feature Dependencies

```
Fiche client
    └──requires──> (nothing)

Ordonnance structurée OD/OG
    └──requires──> Fiche client
    └──requires──> Prescripteur + date de prescription (G5)

Relance renouvellement AMO 24 mois          [KEY DIFFERENTIATOR]
    └──requires──> Ordonnance structurée
                       └──requires──> date de prescription (G5)
    └──requires──> Moteur de rappels

Commande spéciale (verres) vers fournisseur
    └──requires──> Ordonnance structurée
    └──requires──> Fournisseur
    └──requires──> Bon de commande

Suivi de commande client / statut (G1)      [TABLE STAKES, currently a gap]
    └──requires──> Commande spéciale
    └──requires──> Vente / facture (to link the acompte)
    └──enables───> Relance WhatsApp "vos lunettes sont prêtes"

Vente / Facture
    └──requires──> Fiche client
    └──requires──> Article en stock (ou commande spéciale)
    └──requires──> Numérotation séquentielle légale
    └──requires──> Itemisation monture/verres (G4)

Avoir (G3)
    └──requires──> Facture
    └──requires──> Mouvement de stock inverse
    └──requires──> Écriture de caisse inverse

Devis (G2)
    └──requires──> the same line-item model as Facture
    └──converts-to──> Facture     [design together, or pay twice]

Acompte / paiement partiel
    └──requires──> Facture
    └──requires──> Caisse
    └──requires──> Modèle de paiement multi-lignes  [see mutuelle condition 3]

Caisse (journal par magasin)
    └──requires──> Magasin
    └──requires──> Vente, Acompte, Règlement fournisseur, Dépense

Comptage de caisse (recommended)
    └──requires──> Caisse + totaux journaliers

Marge / statistiques owner (G6)
    └──requires──> Prix d'achat
    └──requires──> Vente
    └──requires──> Permissions (to hide from vendeur)

Compte fournisseur / échéancier
    └──requires──> Fournisseur, Réception, Règlements
    └──enables───> Relance "échéance fournisseur"

Réappro par seuil
    └──requires──> Stock par magasin + seuil par article
    └──enables───> Relance "réappro"

Inventaire physique (G7)
    └──requires──> Stock par magasin
    └──enhanced-by──> Étiquettes + champ de recherche compatible douchette

Offline / sync
    └──CONFLICTS WITH──> Numérotation séquentielle sans trou
    └──CONFLICTS WITH──> Décrémentation de stock partagée entre postes
    └──CONFLICTS WITH──> Facturation électronique DGI (clearance model, see below)
```

### Dependency notes that change the roadmap

- **Devis, Facture and Avoir share one line-item + document model.** Building the facture
  alone and adding the other two later means rebuilding the document model twice. Put all
  three in the same phase.
- **The AMO renewal relance is nearly free but only if G5 ships with the ordonnance.** Adding
  `date de prescription` and `prescripteur` later means backfilling every existing ordonnance,
  and the reminder is worthless until backfilled. Ship G5 in the ordonnance phase.
- **Offline vs sequential numbering is the project's central conflict**, and avoirs make it
  worse (an offline avoir referencing an offline facture). This belongs in PITFALLS, but the
  feature-level consequence is: **decide the numbering strategy before building facturation,
  not before building sync.** Per-magasin number ranges/prefixes is the usual escape hatch and
  is legally defensible under art. 145 as long as each series is itself gapless and
  chronological (MEDIUM confidence — verify with a Moroccan comptable).
- **The multi-payer payment model is a dependency of the mutuelle exclusion being safe.** It
  is not a feature; it is a shape decision made once in the facturation phase.

---

## The DGI e-invoicing clock (not a v1 feature, but it dates the roadmap)

Morocco is rolling out **mandatory electronic invoicing** under art. 145 CGI, launched by the
Loi de Finances 2024, using a **clearance model**: each invoice is transmitted to the DGI
platform for validation *before* being sent to the client, in UBL 2.1 or UN/CEFACT CII XML
with an electronic signature and validated ICE. Phasing widely reported as: large IS-liable
companies 1 Jan 2026, medium 1 Jul 2026, **PME/TPE and auto-entrepreneurs with turnover above
500 000 DH on 1 Jan 2027**. Penalty around 500 DH per non-conforming invoice, capped
50 000 DH/year. Confidence: MEDIUM-HIGH — consistent across many Moroccan advisory sources,
but these are commercial blogs with an interest in urgency; **confirm the wave-3 date and
threshold against the DGI's own publication before committing anything.**

**Why it matters to features, not just compliance:**
- A single optician shop turning over ~500 000 DH/year is entirely ordinary — a meaningful
  share of the target market falls into wave 3.
- Clearance-before-send **collides head-on with the offline caisse**. An invoice created
  offline cannot be pre-cleared. The eventual answer is a two-document model: an internal
  sale/receipt issued immediately offline, and a cleared facture emitted on reconnection.
- **Feature-level implication for v1:** do not model the facture as "printed = final". Model
  it with a status (`brouillon` → `émise` → later `transmise` / `validée DGI`) and keep the
  document data structured enough to serialise to UBL later. That is a modelling choice worth
  ~zero cost now and a rewrite later.
- **Positioning implication:** "conforme DGI" will be the dominant Moroccan software sales
  pitch through 2026–2027. Competitors like Fawatir and Facture Go already lead with it. Being
  visibly on that path is a sales asset even before the feature exists.

---

## MVP Definition

### Launch With (v1)

- [ ] **Fiche client + historique** — the spine of everything
- [ ] **Ordonnance structurée OD/OG + prescripteur + date (G5)** — the domain, and the
      dependency of the best differentiator
- [ ] **Stock par magasin** (montures, verres stockés, lentilles, accessoires) with seuils
- [ ] **Vente + facture A4 conforme art. 145, itemisée (G4)** — legal floor and AMO-usable
- [ ] **Devis → Facture → Avoir (G2, G3)** — one document model, built once
- [ ] **Acompte / paiement partiel, paiements multi-lignes multi-modes** — the vertical's
      defining money flow, and the hook for later tiers payant
- [ ] **Caisse par magasin, journal + totaux jour/mois** — plus a non-blocking comptage
- [ ] **Suivi de commande client avec statut (G1)** — the daily operational loop
- [ ] **Fournisseurs, bon de commande, réception, compte fournisseur, prix d'achat** — one
      coherent flow; PROJECT.md is right that splitting it is worse
- [ ] **Rôles owner/vendeur + permissions personnalisables** — margins hidden from vendeur
- [ ] **Offline caisse + ventes, avec numérotation sans trou** — parity requirement, hardest
      requirement
- [ ] **Rappels: réappro, échéance fournisseur, renouvellement client (AMO 24 mois)**
- [ ] **Relance WhatsApp par lien `wa.me`** — "vos lunettes sont prêtes" and the renewal nudge
- [ ] **Tableau de bord owner minimal (G6)** — CA, marge, panier moyen, encours
- [ ] **Recherche client/article rapide, offline, tolérante aux variantes de nom**
- [ ] **Impression étiquettes prix/référence + écran d'inventaire** (barcode mitigation)
- [ ] **Facture A4 + bon de commande + reçu d'acompte A5, avec branding du client**
- [ ] Self-serve signup, essai, abonnement par moyen de paiement marocain
- [ ] Multi-magasin dans un même tenant

### Add After Validation (v1.x)

- [ ] **Split "part organisme / reste à charge"** — trigger: the third prospect mentions
      bons de prise en charge
- [ ] **Export comptable CSV/Excel (G8)** — trigger: first accountant complaint (will be fast)
- [ ] **SAV / retouche / garantie** (casse, adaptation, réparation) — trigger: shops asking
      how to track a frame sent back to the supplier
- [ ] **Lentilles: suivi de renouvellement et re-commande** — trigger: shops with real contact
      lens volume; the 1–3 month cadence is a different, richer relance loop than glasses
- [ ] **Transfert de stock entre magasins** — trigger: first genuine 2+ shop customer
- [ ] **Statistiques avancées** (taux de transformation, top verriers, rotation du stock)
- [ ] **WhatsApp Business API via BSP** — trigger: manual `wa.me` tapping becomes the
      complaint; requires solving per-tenant WABA/sender identity
- [ ] **Comptage de caisse renforcé** (historique des écarts par vendeur) — trigger:
      multi-magasin owners
- [ ] **Préparation e-facturation DGI** (statut de document, sérialisation UBL 2.1) —
      trigger: confirmed wave-3 date approaching

### Future Consideration (v2+)

- [ ] **Facturation électronique DGI complète** (clearance, signature, XML) — defer until the
      DGI platform, its sandbox and the wave-3 rules are concrete; building against rumour is
      the classic way to build the wrong thing
- [ ] **Tiers payant / gestion des remboursements** — only if the market shifts toward
      conventionnement, or if the product moves upmarket to chains with corporate contracts
- [ ] **Interface arabe / RTL** — defer until a prospect refuses to buy without it. This has
      not happened to any competitor
- [ ] **Fidélité, parrainage** — weak fit with a 24-month cycle
- [ ] **Intégrations fournisseurs / catalogues verriers** — only if a Moroccan distributor
      offers a real feed
- [ ] Full white-label, custom domains
- [ ] Application client final — **not planned**

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Fiche client + historique | HIGH | LOW | P1 |
| Ordonnance structurée OD/OG | HIGH | MEDIUM | P1 |
| Prescripteur + date de prescription (G5) | HIGH | LOW | P1 |
| Facture conforme art. 145, itemisée (G4) | HIGH | MEDIUM | P1 |
| Numérotation séquentielle sans trou (offline-safe) | HIGH (legal) | HIGH | P1 |
| Acompte / paiement partiel, paiements multi-lignes | HIGH | MEDIUM | P1 |
| Caisse par magasin + totaux | HIGH | MEDIUM | P1 |
| Suivi de commande client / statut (G1) | HIGH | MEDIUM | P1 |
| Stock par magasin + mouvements | HIGH | MEDIUM | P1 |
| Fournisseur + BC + réception + compte + prix d'achat | HIGH | HIGH | P1 |
| Rôles + permissions personnalisables | HIGH | MEDIUM | P1 |
| Offline + sync | HIGH | HIGH | P1 |
| Relance renouvellement AMO 24 mois | **HIGH** | **LOW** | **P1 — best ratio in the product** |
| Relance WhatsApp par lien wa.me | HIGH | LOW | P1 |
| Devis (G2) | MEDIUM | LOW | P1 (same model as facture) |
| Avoir / retour (G3) | MEDIUM | MEDIUM | P1 (legally required corrective path) |
| Recherche rapide offline | HIGH | MEDIUM | P1 |
| Tableau de bord owner (G6) | HIGH | MEDIUM | P1 (minimal) / P2 (rich) |
| Branding sur documents imprimés | MEDIUM | LOW | P1 |
| Self-serve signup + paiement marocain | HIGH (business) | HIGH | P1 |
| Étiquettes prix / référence | MEDIUM | LOW | P1 |
| Écran d'inventaire (G7) | MEDIUM | MEDIUM | P2 |
| Comptage de caisse (attendu vs compté) | MEDIUM-HIGH | LOW | **P2 — recommended reversal** |
| Reçu d'acompte A5 | MEDIUM | LOW | P2 |
| Export comptable (G8) | MEDIUM | LOW | P2 |
| Part organisme / reste à charge | MEDIUM | LOW (if model is right) | P2 |
| SAV / retouche / garantie | MEDIUM | MEDIUM | P2 |
| Suivi renouvellement lentilles | MEDIUM | MEDIUM | P2 |
| Transfert de stock inter-magasins | MEDIUM | MEDIUM | P2 |
| WhatsApp Business API (BSP) | MEDIUM | HIGH | P3 |
| Facturation électronique DGI | HIGH (2027) | HIGH | P3 (design for it now) |
| Tiers payant complet | LOW (today) | HIGH | P3 |
| Interface arabe / RTL | LOW | HIGH | P3 |
| Fidélité à points | LOW | MEDIUM | P3 — recommend never |
| EDI verriers | LOW (Morocco) | HIGH | P3 — recommend never |
| App client final | LOW | HIGH | Never |

---

## Competitor Feature Analysis

| Feature | OpticWizard (MA, 800 DH/yr) | MyOpti (MA, 1 500–4 000 DH/yr) | Gestoptic / Netoptis (MA) | Osmose (FR) | Our Approach |
|---------|------------------------------|-------------------------------|---------------------------|-------------|--------------|
| Ordonnance | "ordonnances optiques" on the client file; fields not specified | "Suivi des ordonnances" (en cours / prêt / livré) | Not advertised | OCR + audiométrie NOAH + mesures ACEP | **Fully structured OD/OG + prescripteur + date — deeper than any local competitor, and it powers the relance** |
| Suivi de commande client | Not advertised | Yes, as ordonnance status | Not advertised | Vue pilotage atelier type Trello | Explicit statut + "client prévenu le" + worklist |
| Offline | **Yes — local app, auto-sync** | No (cloud) | No (100% en ligne) | n/a | Parity required; win on gapless numbering after sync |
| Facturation | "factures officielles conformes aux standards marocains" | BL, devis et factures (personnalisables sur les tiers hauts) | Devis, factures, avoirs | SCOR, AMC | Art. 145 conforme + **itemisation AMO** + branding on all tiers |
| Acompte / paiement partiel | **Yes, by name** | "Gestion des paiements" | Suivi des paiements | Complet | Multi-ligne, multi-mode, multi-payeur-ready |
| Caisse | POS complet | "Gestion de la Caisse", dépenses, cartes cadeaux | "Journal de caisse", trésorerie | Caisse NF525, Z, audit espèces | Ledger + **comptage non bloquant** (no NF525) |
| Fournisseurs / achats | Not advertised | "Fournisseurs et clients" | Portefeuille fournisseur, avoirs, échéanciers | EDI tous fabricants | **Full chain incl. compte fournisseur and prix d'achat — a genuine local gap** |
| Marge / prix d'achat | Not advertised | "Rapports et statistiques" | Statistiques bénéfice, CA, charges | Complet | **Per-sale margin, hidden from vendeur** |
| Permissions | Not advertised | "Multi utilisateurs" | Agents par magasin | Complet | **Owner-customizable — clear local differentiator** |
| Multi-magasin | Not advertised | Yes | Yes (Netoptis) | Supervision multi-établissements | Yes, consolidated owner view |
| Barcode | Not advertised | "Impression ticket code à bar" | "Impression de code-barres articles" (optiques.ma) | Douchette + RFID | **Label printing yes; scanning deferred but not blocked** |
| Relances client | Not advertised | Suivi des promos | **SMS marketing** (Gestoptic) | Relances tiers payeurs | **WhatsApp + AMO 24-month renewal trigger** |
| Mutuelle | "factures mutuelle" (= printable claim invoice) | Not advertised | Not advertised | Full Tiers Payeurs module | Itemized facture only; payment model kept open |
| Arabic | Not advertised | Not advertised | Not advertised | n/a | French UI, Arabic-capable data + fonts |
| Mobile | iOS/Android/iPad | Responsive (tablette, smartphone) | Web | Web | **Full-parity native/mobile app** |
| Distribution | Self-serve-ish, 800 DH/yr | Tiered annual | Sales-led, 1 free month (Netoptis) | Sales-led | **Self-serve + local payment** |

---

## Sources

**Moroccan competitors (vendor marketing copy — HIGH confidence on advertised features, no confidence on quality):**
- OpticWizard — https://opticwizard.com/ and https://www.appvizer.fr/sante/optometrie/opticwizard
- MyOpti — https://myopti.ma/
- Netoptis — https://www.netoptis.com/
- Gestoptic — https://www.gestoptic.ma/
- Optix System — https://optixsystem.com/
- PLANET SOFT — https://planetsoftmaroc.com/logiciel-de-gestion-pour-magasin-optique/
- OpticManager — https://opticmanager.com/
- optiques.ma — https://www.optiques.ma/
- OPTIKOS (NSE) — https://www.nse-ma.com/fr/logiciel-de-gestion-optikos/

**French vertical (for the full feature superset and to identify France-only artefacts):**
- Osmose, catalogue des fonctionnalités — https://www.osmose-solutions.com/a-propos/catalogue-des-fonctionnalites
- MyEasyOptic — https://www.myeasyoptic.com/ ; EDI manual — https://www.myeasyoptic.com/wp-content/uploads/2019/03/MEO-Commande-EDI.pdf
- Cosium — https://www.cosium.com/fr/logiciel-optique/
- LensPro (WhatsApp notifications, order statuses) — https://lenspro.fr/

**Moroccan AMO / reimbursement (MEDIUM-HIGH confidence — consistent across sources, but all secondary; confirm figures with an optician or CNSS directly):**
- https://ophtalmologue.co.ma/remboursement-lunettes-au-maroc/ — ceilings (monture 400, verres 400 / progressifs 800; cap 800 / 1 200), required documents, 60-day deadline, 24-month cadence
- https://www.lopticomaroc.com/remboursement-lunettes-verres-par-cnss-et-cnops/
- https://www.cnops.org.ma/fr/dispositifs-medicaux
- https://sahha.ma/tools/remboursement-cnss
- https://www.astucesoptique.com/posts/combien-rembourse-la-mutuelle-pour-les-lunettes

**Moroccan invoicing law (HIGH confidence on art. 145 mentions; MEDIUM-HIGH on the e-invoicing calendar):**
- Article 145 CGI — https://www.fiscamaroc.com/dispositions-communes-208/article-145-tenue-de-la-comptabilite-214.htm
- Mentions obligatoires — https://amde.ma/les-mentions-obligatoires-sur-une-facture-au-maroc/ and https://fatouraplus.com/en/guide-auto-entrepreneur/mentions-obligatoires-facture-maroc-art-145/
- Facturation électronique 2026 — https://www.sage.com/fr-ma/blog/facturation-electronique-maroc-2026/ , https://www.upsilon-consulting.com/facturation-electronique-maroc-2026/ , https://hisab.ma/fr/docs/mandate-2026
- Ticket de caisse as invoice for B2C — https://clicpaie.ma/blogs/modele-facture-maroc/

**Moroccan messaging economics (MEDIUM confidence):**
- WhatsApp Business API pricing Morocco — https://eho.ma/34617/whatsapp-business-api-prix-maroc/ , https://tourakdigital.ma/blog/whatsapp-business-api-maroc-strategie-2026

**Moroccan optical market pricing:**
- https://kto.ma/prix-lunettes-maroc.html (1 000–1 800 DH entry, 1 800–2 800 standard, 3 500+ premium)

---

## Known Gaps in This Research

1. **No direct optician interviews.** Everything about *why* Moroccan opticians buy is
   inferred from vendor marketing. The single highest-value validation step is one hour with
   two opticians — specifically on the caisse-count question and on how often they see bons
   de prise en charge.
2. **TVA rate on optical goods in Morocco is unresolved.** Searches did not settle whether
   montures and verres correcteurs carry 20%, a reduced rate, or an exemption as dispositifs
   médicaux. **Design consequence: TVA rate must be per-article configurable, never hardcoded,
   and the facture must break TVA down by rate.** Confirm with a Moroccan comptable.
3. **Sequential numbering across multiple magasins** — whether per-magasin series with
   distinct prefixes are acceptable under art. 145 is asserted here at MEDIUM confidence only.
   This determines the offline numbering strategy and must be resolved before facturation is
   built.
4. **The DGI e-invoicing wave-3 date and 500 000 DH threshold** come from commercial advisory
   blogs, not from the DGI. Verify before planning around it.
5. **Actual market share of the incumbents** (PLANET SOFT's "500+ opticians" is a vendor
   claim) and how many Moroccan opticians use no software at all — the latter may be the real
   target segment and would change the feature bar downward.

---
*Feature research for: optician shop management SaaS, Morocco*
*Researched: 2026-09-09*

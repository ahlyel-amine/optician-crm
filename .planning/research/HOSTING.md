# Hosting Research — Morocco vs EU

**Question**: where to host a multi-tenant Django SaaS for Moroccan opticians that stores health data
(ordonnances), with **one PostgreSQL database per client business**.

**Researched**: 2026-09-11. **Status**: decision-ready, with three items that only a sales contact can close.

---

## Bottom line

**Host in an EU region (Paris or Marseille), on a managed PostgreSQL service that can restore a single
logical database — Scaleway Paris is the closest fit found.** Then file the CNDP paperwork for the
processing *and* the transfer before the first real client record exists.

The operational reality in Morocco is the crux, and it resolves cleanly:

- **No Moroccan provider was found selling managed PostgreSQL** with automated backups, PITR and a
  provisioning API. Every Moroccan offer located is colocation, VPS/VDC, or Microsoft-365-style
  resale. (HIGH confidence that none is *advertised*; MEDIUM that none exists — see the caveat in §1.)
- **One hyperscaler is now genuinely live in Morocco**: Oracle's `af-casablanca-1`, launched
  February–April 2026. This is a real region, not an announcement. It is the only in-country path to a
  managed database, and whether it carries *OCI Database with PostgreSQL* could not be verified.
- **Latency does not decide this.** The last-mile in Morocco (~30–50 ms) dominates the ~10–25 ms of
  Morocco→EU transit. Moving the server from Casablanca to Paris changes a page interaction by a few
  tens of milliseconds, on top of a last-mile the user already has.
- **The law does not prohibit EU hosting.** Law 09-08 art. 43 permits transfer to states the CNDP has
  recognised as adequate; EU member states are on that list. It is a *formality*, not a ban — but the
  formality is real and the article citation in PROJECT.md is probably wrong (see §6).

**The single condition that flips this**: Oracle confirming that OCI Database with PostgreSQL runs in
`af-casablanca-1` at a price a solo developer can carry. That would remove the cross-border transfer
question entirely for the same operational quality — a strictly better position. **Ask Oracle before
committing.**

---

## 1. Does any Moroccan provider offer managed PostgreSQL?

**Answer: none found. Not one.** — **HIGH** confidence that no Moroccan provider *advertises* managed
PostgreSQL with automated backups, PITR and programmatic database creation; **MEDIUM** confidence that
none exists, because Moroccan provider documentation is thin and several sell only through quotation.

| Provider | What they actually sell | Managed Postgres? | Confidence |
|---|---|---|---|
| **Maroc Telecom / MT Cloud** (`mtcloud.ma`) | Microsoft 365, Google Workspace, Exchange Online, Kaspersky/Fortinet security, Veritas/Dropsuite backup, SD-WAN, Meraki WiFi, SSL certs, domains, Red Hat servers. IaaS sold separately as VPS / VDS / Virtual Datacenter since 2016. | **No.** The catalogue page contains no database, no PostgreSQL, no DBaaS entry at all. No prices published; sales-contact only; datacenter locations not disclosed. | **HIGH** (read the catalogue directly) |
| **Inwi** (Inwi Cloud / VDC) | IaaS as Virtual Datacenter, colocation and dedicated space, ISO 27001 + PCI-DSS certified datacenters (Rabat Technopolis, 1 000 m² white space extensible to 2 000 m²). Signed a "cloud souverain" deal with SAP. | **No evidence of a DBaaS.** Marketing describes VDC and hosting only. | **MEDIUM** (marketing pages only) |
| **N+ONE Datacenters** | Carrier-neutral Tier-III datacenters at Nouaceur and Settat. Colocation → managed hosting → IaaS/hybrid/private cloud. **Hosts the Oracle Casablanca region.** AWS partner. | **Not found.** Their own cloud products are described as IaaS and hybrid cloud; no database service is documented. | **MEDIUM** |
| **Omnidata** | 30+ years of infrastructure integration and managed services around Oracle / IBM / Microsoft. 24/7 maintenance with SLAs. | This is an **integrator / MSP**, not a cloud with a self-service database product. They would *run* Postgres for you as a managed service contract — a different commercial shape (people, retainer) from a per-hour DBaaS. | **MEDIUM** |
| **Dataprotect** | Cybersecurity / MSSP. Cloud *security* monitoring, audit, SOC, ISO 27001 alignment. | **No.** Not a hosting provider. | **HIGH** |
| **Hostino, Nindohost, cloudvps.ma** | Moroccan VPS and shared hosting, "sovereign datacenter on Moroccan territory" framing. cloudvps.ma from ~620 MAD/year. Hostino Cloud VPS is **quote-only with a 12-month minimum commitment**. | **No.** VPS only. | **MEDIUM–HIGH** |
| **Azul Cloud (UM6P)** | Moroccan sovereign-cloud initiative from UM6P's College of Computing — compute, storage, AI services. **Entered beta in June 2026.** | Unknown; beta. Not a basis for a production commitment in 2026. | **MEDIUM** |

### What this means for the architecture

The requirement is not merely "a Postgres." It is:

1. `CREATE DATABASE` / `DROP DATABASE` driven by the provisioning state machine, from code;
2. automated scheduled backups;
3. point-in-time recovery;
4. **restore of one customer's database without disturbing the other customers on the same instance.**

(4) is the sharp one and it is where most managed services are weakest — see §4. No Moroccan provider
was found that documents any of the four.

### Could not be verified — say so plainly

- Whether MT Cloud, Inwi or N+ONE will sell a *managed Postgres under contract* (an MSP arrangement
  rather than a product). Several of these firms plainly could; none publishes it. This is a
  sales-conversation answer, not a documentation answer.
- Whether Oracle's `af-casablanca-1` carries OCI Database with PostgreSQL (see §2).
- Azul Cloud's service catalogue and GA date.

---

## 2. Hyperscalers and European providers in Morocco

**Separate the launched from the announced. Only one is launched.**

### LAUNCHED — Oracle Cloud Infrastructure, `af-casablanca-1`

**HIGH confidence.** This is real and documented in Oracle's own release notes.

- Region identifier `af-casablanca-1`, region key `LEJ`, **one availability domain**.
- Oracle's release-notes page gives a launch date of **20 February 2026**; press coverage reports the
  region "up and running" on **7 April 2026** with the public launch announced 13 April 2026. Treat
  Q1–Q2 2026 as the launch window.
- **Physically hosted by N+ONE Datacenters**, across Nouaceur and Settat.
- First hyperscaler public cloud region in North Africa.
- Second Moroccan region planned at **Settat** — *announced, not launched*.
- Services reported available: Autonomous Database, MySQL HeatWave, OKE (Kubernetes), OCI VMware
  Solution, OCI Generative AI, AI Infrastructure.

**The unresolved question**: *Is `OCI Database with PostgreSQL` available in `af-casablanca-1`?*
**Could not be verified — LOW confidence either way.** Oracle's per-region service-availability pages
returned HTTP 403 to automated fetching, the Casablanca release note does not enumerate services, and
the press service lists name Autonomous Database and MySQL HeatWave but **not** PostgreSQL. Oracle's
stated *strategy* is to offer all 200+ services in every region, but a single-AD region commonly lags.
**This is question #1 to put to Oracle sales.**

What OCI Database with PostgreSQL does offer where it exists (**MEDIUM–HIGH**, from Oracle docs):
scheduled daily/weekly/monthly automated backups, retention up to **35 days**, manual backups for
longer retention, HA across nodes with near-instant failover, read replicas on shared storage,
cross-region backup copy. **Limit: 10 backups per tenancy per region.** PITR is *not* documented on
the overview page — **unverified**.

### NOT A REGION — AWS Wavelength Zone, Casablanca

**HIGH confidence.** AWS and Orange Morocco launched an **AWS Wavelength Zone** in Casablanca
(announced May 2024, live by ~February 2025), inside Orange's Moroccan datacenters. Morocco and Senegal
were the first countries to get Wavelength Zones **without** an existing AWS Region or Local Zone.

**Do not mistake this for an AWS region.** Wavelength is a 5G-edge product: a constrained subset of EC2
and EBS for low-latency mobile edge workloads. **No RDS. No managed Postgres.** It does not give AWS
data residency in Morocco for this architecture.

### NO PRESENCE

- **Microsoft Azure** — no Morocco region, no announcement found. Microsoft's active MEA build-out is
  **Saudi Arabia East, confirmed for Q4/November 2026** — not Morocco. **HIGH**.
- **Google Cloud** — no Morocco region. Nearest African region is **Johannesburg**. Nearest useful
  regions are Paris (`europe-west9`) and Madrid (`europe-southwest1`). A Maroc Telecom / Google Cloud
  partnership for a renewable-powered regional data hub has been reported — **an announcement, with no
  launched region**. **MEDIUM–HIGH**.
- **OVHcloud** — sells *to* Morocco (localised `ovhcloud.com/fr-ma/` storefront) but has **no Moroccan
  datacenter**. Buying from the Moroccan storefront still places data in Gravelines / Strasbourg /
  Roubaix. **HIGH**. Do not let the `fr-ma` domain be mistaken for local hosting.
- **Scaleway** — France (Paris), Amsterdam, Warsaw. No African presence. **HIGH**.
- **Hetzner** — Germany, Finland, USA, Singapore. No African presence, **and no managed database
  product at all** (third parties like Ubicloud build managed Postgres on top of Hetzner). **HIGH**.

### Summary

> In 2026, **Oracle is the only hyperscaler with a full public cloud region on Moroccan soil.** AWS has
> an edge zone, not a region. Azure and Google have nothing, launched or announced-with-a-date.

---

## 3. If only IaaS is available locally — what a solo developer must operate

This is the honest cost of choosing a Moroccan VPS/VDC (MT Cloud, Inwi VDC, N+ONE, Hostino). All of the
following stops being a line item and becomes *your evenings*. **Confidence: HIGH on the list of
responsibilities; MEDIUM on the hour estimates, which are judgement.**

| Responsibility | What it means with DB-per-tenant | Setup | Ongoing |
|---|---|---|---|
| **PostgreSQL install + tuning** | shared_buffers, work_mem, max_connections. With N tenant databases behind PgBouncer the connection maths is per (user, database) pool pair — the real ceiling. | 1–2 d | low, until it isn't |
| **PgBouncer** | Already mandatory in this architecture (PROJECT.md). Self-hosting means *you* own its config, its restarts, and the transaction-pooling-vs-prepared-statements interaction. | 2–3 d | ~2 h/mo |
| **Automated backups** | pgBackRest or barman. Must cover **every** tenant database and handle databases appearing and disappearing as clients are provisioned and churn. Off-box storage required. | 2–3 d | ~2 h/mo |
| **PITR** | WAL archiving to object storage, retention policy, and a rehearsed restore. **Not optional** — a 10-year retention obligation (art. 211 CGI) with no tested restore is a liability, not a backup. | 2–4 d | ~2 h/mo |
| **Single-tenant restore** | The hard one. Restore a whole cluster to a scratch host at time T, pg_dump the one client's database, reload it. Must be scripted and **rehearsed**, or it does not exist. | 2–3 d | 1 rehearsal/quarter |
| **Replication / failover** | Streaming replica + promotion runbook, or accept that a host failure is a full-outage restore-from-backup event. The product is **online-only** — an outage stops the counter in every shop. | 3–5 d | ~2 h/mo |
| **Monitoring & alerting** | Prometheus + postgres_exporter + Grafana + Alertmanager, plus disk-full alerts. Disk-full on a Postgres host is the classic solo-dev outage. | 2–3 d | ~3 h/mo |
| **Patching** | OS and Postgres CVEs, minor-version upgrades, and a major-version upgrade path across N databases. | — | ~4 h/mo |
| **Security hardening** | TLS, pg_hba, network isolation, encrypted backups, key management — with **health data** on the box. | 2–3 d | ~2 h/mo |

**Realistic total: roughly 3–5 weeks of setup, then ~15–20 hours a month forever.**

Put that against the project's own numbers: the hand-built tenancy layer is already budgeted at 2–3
weeks, on a 12-phase solo ERP-shaped build with no deadline. Self-operating Postgres adds a *second*
project of comparable size that produces no customer-visible feature, and it adds it in the one area
where a mistake is unrecoverable rather than inconvenient. **This is the strongest argument in the whole
document**, and it points away from Moroccan IaaS more forcefully than any latency or price number.

A softening note, for fairness: Ubicloud demonstrates that managed Postgres can be layered onto raw
VMs, and Omnidata-style MSP contracts exist in Morocco. Neither is a self-service API you can call from
a provisioning state machine, which is what this architecture needs.

---

## 4. Indicative pricing

All figures **indicative**, for a small production setup. EUR to MAD at roughly **1 EUR = 11 MAD**.
**Confidence: MEDIUM** — list prices from vendor and third-party pricing pages, most verified in 2026
but some via secondary sources. Re-check before committing.

### The structural point that dominates every number

**Do not provision one managed database *instance* per client.** At EUR 11–80/month per instance
against an ARPU of 800–4 000 MAD/year (roughly EUR 73–365 per **year**), one instance per client is
instantly and permanently loss-making — a single EUR 11/month DEV instance costs EUR 132/year, which
exceeds the entire revenue of an 800 MAD customer.

The architecture must be **many logical databases inside one managed Postgres instance**, scaled up as
tenant count grows. That is compatible with database-per-client isolation (CREATE DATABASE inside a
shared cluster) and it is how the per-tenant cost stays in the tens of dirhams.

**This makes "can I restore ONE logical database?" the single most important procurement question**,
because the whole cost model depends on co-tenanting databases in one instance.

### European options

| Option | Spec | Price | Notes |
|---|---|---|---|
| **Scaleway Managed PostgreSQL** DEV-S | 1 vCPU / 2 GB / 10 GB | **~EUR 11/mo** | Dev/proto tier. Paris, Amsterdam, Warsaw — identical pricing. |
| **Scaleway** PRO2-XXS | 2 vCPU / 8 GB / 20 GB | **~EUR 80/mo** (no HA) / **~EUR 123/mo** (HA) | Realistic first production tier. |
| **Scaleway** PRO2-XS | 4 vCPU / 16 GB / 50 GB | **~EUR 158/mo** | Where you land at scale. |
| Scaleway backups | — | 100 GB included, then **EUR 0.025/GB/mo** | Egress EUR 0.01/GB beyond quota. |
| **Hetzner** CX23 (app server) | shared vCPU | **EUR 5.49/mo** | Post-June-2026 pricing. |
| **Hetzner** CPX22 | dedicated AMD vCPU | **EUR 19.99/mo** | CPX/CCX rose 113–176 % in June 2026 — older blog numbers are stale. |
| **Hetzner** CX33 | — | **EUR 25.47/mo** (was 19.47) | |
| **Hetzner managed Postgres** | — | **does not exist** | Self-host, or Ubicloud on top. |
| **AWS RDS** db.t4g.small | 2 vCPU / 2 GB | **~USD 0.032/hr = ~USD 23/mo** base | **Not** verified for eu-west-3 Paris specifically; Paris runs above the base rate. Storage, backups beyond the free allowance, and egress are extra. |
| **OVHcloud Public Cloud Databases** | — | **Could not verify** | The pricing page defeated automated fetch and secondary sources returned a figure (EUR 0.088) that is not credible as a monthly price. **Check ovhcloud.com/fr/public-cloud/prices/ by hand.** |

### Moroccan options

| Option | Price | Notes |
|---|---|---|
| **cloudvps.ma** VPS | **from 620 MAD/year** (~EUR 56/yr) | Cheap. Raw VPS — everything in section 3 is yours. |
| **Hostino** Cloud VPS | **quote only, 12-month minimum commitment** | Opaque pricing is itself a finding. |
| **MT Cloud** VPS/VDS/VDC | **no published prices** | Sales contact required. |
| **Inwi** VDC | **no published prices** | Sales contact required. |
| **Oracle af-casablanca-1** | OCI list pricing, region-uniform in principle | OCI Database with PostgreSQL bills per **OCPU-hour** + per **GB-month** storage + Object Storage for backups. One secondary source cites ~AUD 330/mo for 2 OCPU / 32 GB / 64 GB — **LOW confidence**, and larger than needed. **Price the actual small shape with Oracle.** |

### Two sketched monthly bills

**EU, Scaleway Paris — the recommended shape**

- App server (Scaleway or Hetzner, Django + Celery): ~EUR 12–25
- Managed PostgreSQL PRO2-XXS, all tenant databases inside it: ~EUR 80
- Redis (Celery broker): ~EUR 8–15
- Object storage (ordonnance photos, PDFs, backup overflow): ~EUR 5
- Sentry (free or team tier): EUR 0–26
- **Total: ~EUR 105–150/month = roughly 1 155–1 650 MAD/month**

At 30 clients paying the 800 MAD floor (24 000 MAD/yr = 2 000 MAD/mo), infrastructure eats **55–80 %**
of revenue. At 30 clients at a 2 000 MAD midpoint (5 000 MAD/mo) it is **25–35 %** — workable but not
comfortable. **The infra bill is not negligible against this ARPU. It is a real constraint on pricing,
and it argues for pricing above the 800 MAD floor.**

**Morocco, self-operated VPS**

- Two VPS (app + db): ~EUR 30–60/month, or as low as 620 MAD/year each at the very bottom of the market
- Object storage for backups: ~EUR 5
- Your time: ~15–20 h/month — unpriced, and the real number

Cheaper in cash, dramatically more expensive in the only resource a solo developer cannot buy more of.

---

## 5. Latency from Moroccan cities to the nearest EU regions

**Confidence: MEDIUM.** No single authoritative Casablanca-to-Paris RTT measurement was located. The
picture below is assembled from several measurements and is directionally solid, not precise.

**What was actually measured:**

- **Casablanca / Rabat to Lisbon: 11 ms** — best-path minimum, RIPE-style measurement to last-mile IPs
  of African operators, 164 validated IPs, April 2026 (africloud African Latency Report). **MEDIUM–HIGH**
- **Lisbon to France ~29 ms**, Lisbon to UK ~28 ms, Lisbon to Netherlands ~36 ms — same report, as
  European reference points, **not** Morocco-routed. **MEDIUM**
- **Casablanca in-country averages: ~40 ms broadband, ~50 ms mobile.** Best broadband ping recorded on
  Orange at ~37 ms, best mobile on Inwi ~45 ms. National fixed-line average ~54 ms (Q3 2024). **MEDIUM**
- A Moroccan consumer-tech source claims **15–25 ms to European servers on good fibre**. **LOW** — blog-grade.

**Physical plausibility.** Morocco to Europe runs on short, direct submarine cables: **Atlas Offshore**
(Asilah to Marseille, ~1 630 km) and **Loukkos** (Asilah to Rota, Spain). At ~1 630 km of fibre the
one-way propagation floor is ~8 ms, so ~16–20 ms RTT Casablanca to Marseille is physically reasonable,
and Paris adds only a few ms over Marseille. Madrid should be closest of the three, then Marseille,
then Paris — and the spread between them is too small to drive the choice.

**Working estimate — state it as an estimate, not a measurement:**

| Route | Estimated RTT | Confidence |
|---|---|---|
| Casablanca to Madrid | ~15–25 ms | MEDIUM |
| Casablanca to Marseille | ~18–30 ms | MEDIUM |
| Casablanca to Paris | ~22–35 ms | MEDIUM |
| Rabat / Marrakech to Paris | add ~2–8 ms over Casablanca | LOW |
| Casablanca to in-country (Oracle Casablanca) | ~5–15 ms | LOW |

### The judgement

**Latency does not decide this, and it should not be allowed to.**

A Moroccan shop's *last mile* already costs ~37–50 ms before any packet reaches an international link.
Moving the server from Casablanca to Paris adds roughly **20–30 ms of RTT on top of a ~40 ms floor** —
a large relative increase on a number the user cannot perceive as a step change. A browser interaction
needing 5 sequential round trips goes from ~200 ms to ~350 ms. That is the difference between "instant"
and "fast", not between "fast" and "broken".

Two caveats that matter more than the raw number:

1. **Chattiness beats distance.** A React SPA firing 12 sequential API calls to render the counter
   screen will feel worse from Paris than a well-designed one will. The fix is batching the API, not
   moving the datacenter. Design the counter screen to need one or two round trips.
2. **Morocco's variance is the real problem, and hosting location does not fix it.** PROJECT.md already
   records that shop internet is undependable and that the counter stops during an outage. An in-country
   server does not rescue a shop whose fibre is down. That is an argument about *availability*, already
   decided, not about *latency*.

---

## 6. The CNDP cross-border transfer regime under law 09-08

### Resolving the contradiction in the existing research files

The two files disagree, and **both are partly wrong**:

- `research/STACK.md` says **"art. 43 declaration"**. The article is right for *transfer*, but
  "declaration" is the wrong characterisation, and it conflates two separate formalities.
- `PROJECT.md` and `research/PITFALLS.md` say **"art. 23 prior authorization"** for health data. The
  *substance* is right — health data does require prior authorisation — but **the article number
  appears to be wrong**.

**On the article number for sensitive/health data, the sources genuinely disagree:**

| Source | Article cited for sensitive/health-data authorisation |
|---|---|
| CNDP's own "Formalités" page | *"en application de l'article 12, paragraphes 1-a et 1-c, et l'article 21, paragraphe 1"* |
| CMS Law (international firm, Morocco flash-info) | **Art. 12** for autorisation préalable; **art. 4** for déclaration préalable |
| Moroccan practitioner blogs (avocat-jawhari, TabibDoc) | **Art. 23** — yet the same sources elsewhere say art. 23 concerns *security and confidentiality of data*, a different subject |
| Secondary compliance guides | **Art. 21** — the obligation on the responsable de traitement to seek authorisation for sensitive data |

**Assessment (MEDIUM confidence):** the cluster is **art. 12 + art. 21** — art. 12 defining the
sensitive-data categories and the authorisation regime, art. 21 placing the obligation on the
controller. **Art. 23 more likely concerns security and confidentiality obligations, not the
authorisation regime.**

**The full text of law 09-08 could not be retrieved.** Every host attempted (droit-afrique.com,
media.casablanca-bourse.com, WIPO Lex) returned 403, 404 or refused the connection. **Confirm the
citation against the Bulletin Officiel text or with counsel before it goes into a filing. Do not cite
"art. 23" in a CNDP dossier on the strength of a blog.**

**What does not depend on the citation, and is not in doubt (HIGH confidence):** processing health data
requires **prior authorisation** from the CNDP, not a simple declaration. This is stated directly on the
CNDP's own formalities page and operationalised by a dedicated form.

### The operative facts — these are what matter

There are **two separate formalities**, and the existing research collapses them into one.

**(a) The processing itself — autorisation préalable**

- Health data is a sensitive category requiring **prior authorisation**, not declaration. **HIGH**
- **Form F112** (standard prior-authorisation request); **F113** is the simplified form. **HIGH**
- Health-specific supporting documents required: identity and qualifications of those processing the
  data; a research protocol where applicable; prior scientific or ethical opinions if any; **a
  commitment to code the data**, or a request for derogation from coding; and a request for extended
  retention if needed. **HIGH** — note the **data-coding commitment**, which has architectural
  implications and should be raised with counsel before the ordonnance schema is fixed.
- **Stated statutory decision time: 2 months, extendable once**, with the clock restarting if the file
  is incomplete. **HIGH** — this is the CNDP's own published figure and is *shorter* than the "2-4
  months" recorded in PITFALLS.md. Plan 2-4 months of real elapsed time; cite 2 months as statutory.

**(b) The transfer abroad — articles 43 and 44**

- **Art. 43 (HIGH)**: personal data may be transferred to a foreign state only if that state ensures a
  **sufficient level of protection** of privacy and fundamental rights. Adequacy is assessed by the
  CNDP, which **publishes and maintains a list** of adequate countries.
- **The list exists: Délibération n° 236-2015.** Reported to include **France, Spain, Germany, Belgium,
  the Netherlands, Portugal, Italy, the UK, Switzerland, Canada, Sweden, Norway, Finland, Ireland**.
  **MEDIUM** — the CNDP page references the deliberation without reproducing it, and every country list
  found is secondary. **Verify the current deliberation text before filing.**
- **Art. 44 (HIGH)**: derogations permitting transfer *even to a non-adequate country* — explicit
  consent of the data subject; necessity for protection of life, public interest, legal proceedings,
  **medical treatment**, or international judicial cooperation; international agreements Morocco is
  party to; or CNDP authorisation where the processing ensures sufficient protection.
- **Form F118** — "demande de transfert à l'étranger". **HIGH**
- **Critical procedural dependency (HIGH, from the CNDP's own transfer page)**: authorisation for
  transfer is granted only when the underlying treatment has already received CNDP approval, as a
  declaration or an authorisation. **The F112 processing authorisation must land before the F118
  transfer request can succeed. These are sequential, not parallel.** This is the single most
  schedule-relevant fact in this document and **it is not reflected anywhere in the current roadmap** —
  Phase 1 treats the CNDP filing as one item on a 2-4 month clock, when it is two filings on
  consecutive clocks.
- CNDP transfer decisions also carry a **2-month** stated delay, extendable once. **HIGH**

### Declaration, authorisation, or prohibition?

**Answer: authorisation — for the processing, and on the balance of sources for the transfer too.**
Not a declaration. Not a prohibition.

**Sources disagree on one point, and it should be flagged rather than resolved by assertion**: whether
a transfer to a country *already on the adequacy list* still needs an F118 authorisation, or whether
adequacy reduces it to a lighter formality.

- The CNDP's transfer page reads as: adequate-list countries are one of the permitted cases, and
  **F118 is the authorisation route**, with a 2-month decision.
- One secondary source says F118 is required **except** where the destination is on the adequacy list
  or the transfer is covered by sufficient contractual guarantees.
- STACK.md's existing note — the adequacy list applies **but preliminary formalities must still be
  respected** — is consistent with the CNDP's framing and is probably the safe reading.

**Operating assumption: file the F118 regardless.** It costs a form and two months you are already
spending on the F112. Getting it wrong is criminally sanctioned.

### Sanctions

**3 months to 1 year imprisonment and 20 000 to 200 000 MAD** for unauthorised transfer.
**MEDIUM-HIGH** — consistent across the existing STACK.md note and Upsilon Consulting, both secondary.

### The other regime — DGSSI cloud décrets, and why they probably do not apply

A separate and much stricter Moroccan regime exists, and it must not be confused with law 09-08.

- **Décret n° 2-24-921** on cloud service providers, with a qualification framework published in 2025.
  Reported to establish two levels: **level 1 (systèmes d'information sensibles)** — hosting and
  operation by a **100 % Moroccan-owned, Moroccan-directed, Moroccan-staffed company**; **level 2
  (données sensibles)** — **physical storage on Moroccan territory**, no application of foreign law,
  no unsupervised outsourcing or remote access.
- **Décret n° 2-23-1047**, reported as requiring sensitive data to remain under Moroccan jurisdiction.

**Scope — and this is the crux (MEDIUM confidence).** These are **DGSSI / national-security
instruments**. Their scope is repeatedly described as **public bodies, administrations, and
infrastructures d'importance vitale (OIV)**. "Données sensibles" in the DGSSI sense means
**nationally-sensitive information systems**, which is *not* the same concept as "données sensibles"
under the CNDP and law 09-08 (health, race, politics, religion, union membership). **A private
optician's SaaS is very unlikely to be an OIV.**

Two independent sources were checked (the Village-Justice analysis of décret 2-24-921, and the FutureRoc
compliance guide) and **both declined to state that the décrets reach private-sector SaaS** — one said
private-sector coverage "remains unspecified", the other said DGSSI obligations attach to "public
bodies and infrastructures of vital importance".

**Could not be verified — and it is the one legal item that could invalidate the recommendation.** If
these décrets were read to cover any processing of health data by a private company, EU hosting would
become unlawful rather than merely a formality. **Put this exact question to Moroccan privacy counsel.**
It is a cheap question with a very expensive wrong answer.

### One further point, recorded for completeness

**Morocco is not on the European Commission's adequacy list.** This does not affect hosting Moroccan
data in the EU — the flow is Morocco to EU, governed by Moroccan law. It would matter only if EU
personal data ever flowed *into* a Moroccan-hosted system. **MEDIUM**

---

## 7. Does hosting location affect DGI e-invoicing readiness?

**Answer: no — not materially. HIGH confidence on the reasoning, MEDIUM on the mandate details.**

What was established about the mandate:

- Morocco has adopted a **clearance / CTC model**: each invoice is transmitted to the DGI platform for
  validation **before** being sent to the customer, and is not legally valid until validated. **MEDIUM-HIGH**
- Format: **UBL 2.1** (or UN/CEFACT CII), structured XML/JSON, electronically signed. **MEDIUM-HIGH**
- The national platform runs under the DGI's **SIMPL** infrastructure; the build was contracted to
  Moroccan firm **xHub** (~6.3 M MAD). **MEDIUM**
- **10-year archiving** minimum, with integrity, permanent accessibility and readability, secure
  time-stamping, and restoration in an exploitable format on inspection. **MEDIUM-HIGH** — consistent
  with the art. 211 CGI retention already recorded in PROJECT.md.
- Archiving may be on the company's own servers, **a certified cloud solution**, or the DGI's national
  platform. **MEDIUM**
- A **PDP** route exists (plateforme de dématérialisation partenaire) — a DGI-certified partner handling
  emission, signature, clearance transmission and 10-year archiving. **MEDIUM**
- **The implementing décret was transmitted to the Secretary General of the Government in April 2026**
  and, on the sources found, **was still not published**. **MEDIUM** — this updates the PROJECT.md open
  question, which recorded "unpublished as of March 2026". Still unpublished five months later.

**Why hosting location is not the deciding factor:**

1. Clearance is an **outbound HTTPS call** from your application to the DGI platform. It works from
   Paris exactly as it works from Casablanca, over a link measured in section 5 in tens of milliseconds.
2. **No requirement was found that the issuing software be hosted in Morocco.** Archiving is explicitly
   permitted on "the company's own servers", and a Moroccan business using French-hosted accounting
   software is already the norm rather than the exception.
3. The readiness that matters is **structural, and PROJECT.md already has it**: structured-data-first
   factures, full art. 145 fields, buyer ICE as a first-class field, per-line TVA, and a facture
   lifecycle (brouillon, émise, **transmise**, **validée**) that already models clearance states. That
   work is hosting-agnostic and is the actual moat.

**Two caveats, stated honestly:**

- **If** DGI certification as a **PDP** is later pursued, the certification criteria *might* include
  hosting or archiving requirements. **Unverified — the criteria are not published, because the décret
  is not published.** But PDP status is explicitly excluded from v1.
- A Moroccan-hosted *archive* may be a lighter compliance story if the décret, when published, imposes
  residency on the 10-year fiscal archive. **Re-check when the décret lands.** It is cheap to satisfy
  later by replicating the archive to Moroccan object storage without moving the application — record
  that as a designed escape hatch, not as a reason to host in Morocco now.

**Verdict: this question does not constrain the hosting decision. Re-open it when the décret is published.**

---

## 8. Recommendation

### Host in the EU — Scaleway Paris (or OVH / AWS Paris), with the CNDP formalities filed first.

**The reasoning, in order of weight:**

1. **The operational argument is decisive and one-sided.** No Moroccan provider sells managed
   PostgreSQL. Choosing Morocco today means self-operating Postgres — 3-5 weeks of setup and 15-20
   hours a month forever (section 3), on a solo project that already carries a 2-3 week hand-built
   tenancy layer. That is a second infrastructure project delivering no customer-visible value, in the
   one area where errors are unrecoverable rather than inconvenient.
2. **The regulatory argument is weaker than it looks.** EU hosting is **not prohibited**. EU member
   states are on the CNDP adequacy list. It is a filing (F118) running on the same calendar as the F112
   you must file anyway for health data. A formality with a known form and a 2-month statutory clock is
   not a reason to take on a permanent operational burden.
3. **Latency is a non-issue** (section 5) — roughly 20-30 ms added to a ~40 ms last-mile floor.
4. **DGI readiness is unaffected** (section 7).
5. **Cost favours the EU too**, once the per-tenant model is right — many logical databases inside one
   managed instance.

**Pick Scaleway Paris specifically, for one concrete reason.** Scaleway documents that **each logical
database in a Database Instance is backed up and can be restored separately** — to the original
database, or to a **new named database**. That is a direct, documented match for *"restoring one client
has been tested rather than assumed"* (TENANT-05) combined with *"never dropping a client's database"*
(the 10-year retention requirement). Autobackups default to daily with 7-day retention, configurable.
Logical databases are creatable via console and API. **MEDIUM-HIGH confidence.**

Contrast **AWS RDS**: PITR restores an entire *instance* to a new instance. Restoring one tenant means
restore-whole-cluster, then pg_dump the one database, then reload. Workable and scriptable, but a
materially worse fit for exactly the operation this product must perform routinely.

**Unverified on Scaleway, and worth confirming before committing**: whether **PITR** (as distinct from
daily snapshots) is offered for PostgreSQL, and the **maximum number of logical databases per
instance**. Both matter. OVHcloud explicitly advertises PITR for PostgreSQL via control panel and API —
**if Scaleway has only daily snapshots and OVH has true PITR, that reverses the pick between them.**

### Conditions that flip this decision

| Condition | Flips to | Likelihood |
|---|---|---|
| **Oracle confirms OCI Database with PostgreSQL is live in af-casablanca-1** at a viable price | **Morocco (OCI Casablanca)** — strictly better: managed Postgres *and* no cross-border transfer. **Ask this first.** | Unknown — the single most valuable open question |
| Counsel finds **décret 2-24-921 / 2-23-1047 reaches private-sector health-data processors** | **Morocco, mandatory** — EU hosting becomes unlawful, not merely a formality | Low, but catastrophic if missed |
| CNDP **refuses or stalls the F118** transfer authorisation | **Morocco** — and having built on managed Postgres makes a migration to a self-run instance painful rather than impossible | Low-medium |
| A Moroccan provider launches real managed Postgres with per-database restore (Azul Cloud GA, Inwi, N+ONE) | **Morocco** — revisit at that point | Medium over 2-3 years |
| Scaleway caps logical databases per instance too low | Another EU provider (OVH, AWS Paris), **not** Morocco | Medium |
| Opticians' purchasing behaviour shows data sovereignty is a **sales objection** | Reconsider on commercial, not technical, grounds — and note Oracle Casablanca now makes "hosted in Morocco" answerable | Medium |

### Do this in Phase 1, in this order

1. **Email Oracle Morocco today** and ask the PostgreSQL question (section 9). It is one email and it
   could change the answer. Do not architect around it, but do not skip it.
2. **File the F112** health-data prior authorisation. Nothing else can start until this is in.
   2 months statutory; plan 2-4.
3. **File the F118** transfer request once F112 is approved — **it cannot succeed before then**.
4. **Ask counsel the DGSSI scope question** — one question, expensive if wrong.
5. **Prove the per-database restore in a sandbox** before the first client database exists. Provision
   two logical databases on the chosen provider, back them up, restore *one*, and confirm the other is
   untouched. This is TENANT-05, and it is the acceptance test for the whole hosting choice.
6. **Record the decision and its reasoning** — LEGAL-02 is satisfied by the documented reasoning, not
   by the choice alone.

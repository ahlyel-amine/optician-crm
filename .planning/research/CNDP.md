# CNDP / loi 09-08 — controller vs processor for a multi-tenant optician SaaS

**Status:** research to inform a professional consultation. **Not legal advice.**
**Date:** 2026-09-11

**Primary sources:** the text of loi 09-08 itself (extracted from the CNDP's own PDF,
`https://www.cndp.ma/images/lois/Loi-09-08-Fr.pdf` — all article quotes below are verbatim from it),
CNDP procedural pages on `cndp.ma`, and the CNDP's **public national register** at
`https://rn-pdp.cndp.ma` (22 963 entries, last updated 07/09/2026), queried directly.

---

## 0. Bottom line

1. **Two article numbers in PROJECT.md are wrong and must be corrected.** Prior authorisation for
   sensitive data is **art. 21**, routed by **art. 12-1-a** — not art. 23. **Art. 23 is the
   security-and-subcontracting article**, which is separately the most important article for this
   platform. Art. 43 for cross-border transfer is **correct as cited**. (HIGH)
2. **There is an article the earlier research missed entirely: art. 22.** It is an express derogation
   putting health-data processing under **déclaration** rather than authorisation, when the processing
   has as its *sole purpose* care / diagnosis / health-service management **and** is carried out by a
   health practitioner bound by professional secrecy. A déclaration gets a **récépissé within 24
   hours** (art. 19). Whether an optician's mixed clinical-and-commercial file fits "seule finalité"
   is **genuinely arguable**. (HIGH that the article says this; LOW that it applies here.)
3. **On the decisive question the statute points one way and the register points the other.**
   - The *text* makes each optician the **responsable du traitement** and the platform a
     **sous-traitant** (art. 1-5 / 1-6). On that reading the optician files, not us.
   - But the register holds a direct precedent the other way: **DabaDoc**, a Moroccan software
     vendor, holds **autorisation préalable A-436/2021 → décision A-S-436/2021, granted 12/12/2021**,
     in its own name, for *"Service en ligne de gestion du cabinet médical www.dabadoc.com"*. A
     platform vendor filed once, for the platform, with a health-scoped instrument. (HIGH that the
     entry exists and reads this way; MEDIUM-LOW on what it proves, since the register does not
     publish scope or reasoning.)
   - **This is not settled. It is question 1 for the lawyer.**
4. **Self-serve signup is not obviously dead.** Three independent escape routes exist — art. 22
   déclaration (24-hour récépissé), a DabaDoc-style single platform authorisation, and the CNDP's
   **simplified/model regime** (form F113 against a published *modèle*, including the brand-new
   **D-941-2025 model for "traitements de suivi des patients"**). None is confirmed for this exact
   use case. **Do not redesign onboarding before a lawyer rules.** (MEDIUM)
5. **Observed market practice is that essentially nobody in this market has filed for the patient or
   prescription file.** One vendor of ten publishes a CNDP number at all, and that number is
   mischaracterised. Reported as observation — see the warning in §7.

---

## 1. Responsable du traitement vs sous-traitant (Q1)

**Verbatim, art. 1 of loi 09-08:**

> **5- « responsable du traitement »** : la personne physique ou morale, l'autorité publique, le
> service ou tout autre organisme qui, **seul ou conjointement avec d'autres, détermine les finalités
> et les moyens du traitement** de données à caractère personnel. […]
>
> **6- « sous-traitant »** : la personne physique ou morale, l'autorité publique, le service ou tout
> autre organisme qui **traite des données à caractère personnel pour le compte du responsable du
> traitement** ;

Materially identical to Directive 95/46 and to GDPR art. 4(7)/(8). (HIGH)

**Mapping onto this product.** Each optician decides *why* prescriptions are recorded (serve their
customer, order lenses, support an AMO claim) and whose customers they are. The platform decides the
technical means but not the purpose, and holds the data "pour le compte" of the optician. On a plain
reading of art. 1-5 / 1-6, **the optician is the responsable du traitement and the platform is the
sous-traitant.** (HIGH on the reading; the *consequence for who files* is where certainty drops — §3, §6.)

Two caveats a lawyer should test, because they cut against the clean answer:

- **"seul ou conjointement avec d'autres"** — art. 1-5 expressly contemplates **joint controllers**.
  A platform that defines the ordonnance schema, sets retention, runs relance/reminder campaigns and
  derives analytics is making purpose-level decisions. Joint controllership is available on the face
  of the text. (MEDIUM)
- The platform is unambiguously a **controller in its own right** for the subscription relationship —
  optician accounts, billing, support, telemetry. Separate traitement, platform as responsable. (HIGH)

**Art. 23 governs the relationship** (verbatim):

> 2- Le responsable du traitement, lorsque le traitement est effectué pour son compte, doit **choisir
> un sous-traitant qui apporte des garanties suffisantes** au regard des mesures de sécurité technique
> et d'organisation […]
>
> 3- La réalisation du traitement en sous-traitance doit être **régie par un contrat ou un acte
> juridique** qui lie le sous-traitant au responsable du traitement et qui prévoit notamment que le
> **sous-traitant n'agit que sous la seule instruction du responsable du traitement** et que les
> obligations [de sécurité] lui incombent également ;
>
> 4- Aux fins de la conservation des preuves, les éléments du contrat […] sont **consignés par écrit**
> ou sous une autre forme équivalente.

And **art. 25**:

> Toute personne agissant sous l'autorité du responsable du traitement ou de celle du sous-traitant,
> ainsi que **le sous-traitant lui-même** qui accède à des données à caractère personnel **ne peut les
> traiter que sur instruction du responsable du traitement**, sauf en vertu d'obligations légales.

So Morocco **has a written-DPA requirement**, it is **art. 23-3 and 23-4**, and it binds this platform
directly. Not optional, and independent of how the controller question resolves. (HIGH)

Also **art. 15-i**: the controller's declaration must disclose "leur cession, **sous-traitance**, sous
toute forme, à des tiers". Each optician's filing is meant to name us. (HIGH)

---

## 2. Is an optical prescription "données sensibles"? (Q2)

**Verbatim, art. 1-3:**

> **3- « données sensibles »** : données à caractère personnel qui révèlent l'origine raciale ou
> ethnique, les opinions politiques, les convictions religieuses ou philosophiques ou l'appartenance
> syndicale de la personne concernée ou **qui sont relatives à sa santé y compris ses données
> génétiques** ;

Health data is **explicitly** sensitive. (HIGH)

**Does an optical prescription qualify?** Almost certainly. Sphère / cylindre / axe / addition are a
measured refractive error of a named individual — a physiological condition. "Relatives à sa santé" is
broad with no de-minimis carve-out. Assume yes. (HIGH that the risk assessment must assume yes;
MEDIUM that a Moroccan court or the CNDP would so hold — no published Moroccan decision on point was
found.)

**Does it matter that an optician is not a doctor?** Enormously — but for **art. 22**, not for
sensitivity. Sensitivity attaches to the *data* (art. 1-3 is drafted around the data, not the
profession). Profession determines whether the art. 22 derogation is open. See §3. (HIGH)

Relevant: **loi 45-13** brought *opticien-lunetier* into the regulated health professions and repealed
the 1954 dahir governing the profession. Its art. 6 defines the role (delivering corrective optical
articles; performing adaptation and adjustment with control instruments) and restricts delivery
without a medical prescription in defined cases — under 16, acuity ≤ 6/10 after correction, strong
refractive errors, presbyopia mismatched with age. This supports, but does not prove, that a Moroccan
optician is a "praticien de la santé" for art. 22. **I did not verify a secret-professionnel clause in
45-13 itself** — and that is the part art. 22 actually turns on. (MEDIUM on professional status; LOW
on the secrecy duty.)

PROJECT.md already records an ordonnance `source` field (*ordonnance médicale* vs *réfraction
opticien*). **That field may turn out to be legally load-bearing, not merely informational**: a
doctor-issued prescription transcribed by the optician and a refraction performed by the optician sit
differently against art. 22.

---

## 3. Which regime, and which article? (Q3) — corrections to existing research

### The routing article is art. 12

**Verbatim, art. 12:**

> Sauf dispositions législatives particulières, le traitement de données à caractère personnel doit
> faire l'objet :
> **1- D'une autorisation préalable lorsque les traitements concernent :**
> a) **Les données sensibles visées à l'alinéa 3 de l'article premier** ci-dessus. Toutefois, sont
> dispensés de ladite autorisation les traitements mis en œuvre par **une association ou tout autre
> groupement à but non lucratif** [religieux, philosophique, politique, syndical, culturel ou sportif] […]
> b) **l'utilisation de données à caractère personnel à d'autres fins que celles pour lesquelles elles
> ont été collectées** ;
> c) des données génétiques, à l'exception de ceux mis en œuvre par des personnels de santé et qui
> répondent à des fins médicales […] ;
> d) des données portant sur les infractions, condamnations ou mesures de sûreté […] ;
> e) des données comportant le **numéro de la carte d'identité nationale** de la personne concernée ;
> f) L'interconnexion de fichiers […]
> **2- D'une déclaration préalable dans les autres cas**

Two triggers here that nobody has flagged and that bear directly on the schema:

- **art. 12-1-e — the CIN.** Storing a customer's carte d'identité nationale number triggers
  authorisation **on its own**, independently of health data. Plausible for AMO paperwork.
  **Flag this for the data model.** (HIGH)
- **art. 12-1-b — secondary use.** The reminders/relance module (AMO 23-month nudge,
  prescription-renewal follow-up) is arguably use "à d'autres fins que celles pour lesquelles elles ont
  été collectées". **The reminders feature is the most likely part of the product to create a filing
  obligation nobody expected.** (MEDIUM)

The only exemption in art. 12-1-a is for non-profit associations. It helps neither a SaaS nor an
optician. (HIGH)

### The authorisation article is art. 21

**Verbatim, art. 21:**

> 1- Le traitement des données sensibles est subordonné à une autorisation de la loi qui en fixe les
> conditions. **A défaut, il doit être autorisé par la Commission nationale** ;
> 2- Cette autorisation est accordée au vu du **consentement exprès de la personne concernée** ou
> lorsque le traitement des données est **indispensable à l'exercice des fonctions légales ou
> statutaires du responsable du traitement** ; […]

Confirmed by **art. 28-9**, listing among the CNDP's powers "délivrer les autorisations prévues à
**l'article 21**". (HIGH)

> **Correction to PROJECT.md:** it cites *"law 09-08 art. 23"* for the authorisation requirement, in
> both the Requirements list and Constraints. **Art. 23 is confidentiality and security.** The correct
> citation is **art. 12-1-a + art. 21**. Art. 23 still belongs in the document — as the DPA and
> security obligation (§8).
>
> Note that at least one Moroccan vendor guide repeats the same art. 23 error, so it is probably the
> source of the original claim. (MEDIUM)

### Art. 22 — the derogation that could change the business model

**Verbatim, art. 22:**

> **Par dérogation aux dispositions de l'article 21** ci-dessus, le traitement des données relatives à
> la santé est **subordonné à une déclaration** à la Commission nationale, **lorsqu'il a pour seule
> finalité** :
> - la médecine préventive, les diagnostics médicaux, l'administration de soins ou de traitements ou
>   **la gestion des services de santé** et qu'il est effectué par **un praticien de la santé soumis au
>   secret professionnel ou par toute autre personne également soumise à une obligation de secret** ;
> - de sélectionner les personnes susceptibles de bénéficier d'un droit, d'une prestation ou d'un
>   contrat […]

Two **cumulative** conditions: (a) **sole purpose** among those listed, and (b) carried out by a health
practitioner bound by professional secrecy, or another person equally bound by a secrecy obligation.

**Why this matters enormously.** If an optician's ordonnance processing falls under art. 22, the regime
is **déclaration**, and **art. 19** gives a **récépissé within 24 hours**, with processing permitted on
receipt:

> La Commission nationale délivre, **dans un délai de 24 heures** courant à compter de la date du dépôt
> de la déclaration un récépissé […] Le responsable du traitement peut mettre ledit traitement en œuvre
> **dès réception dudit récépissé**.

A 24-hour formality is compatible with self-serve signup. A 2-4 month authorisation is not. **The whole
business-model question may turn on art. 22 rather than on the controller/processor split.** (HIGH that
this is the right question to ask; LOW that art. 22 applies as the product is currently scoped.)

**Why it probably does not apply cleanly.** "Seule finalité" is restrictive. Here the ordonnance sits
inside a commercial system — it feeds a sale, an invoice, stock, a supplier order and a 23-month relance.
That is not a *sole* care purpose. A lawyer may be able to structure the ordonnance as a **separate
traitement with its own declared finalité**, distinct from the commercial traitement — but that is a
design decision with schema consequences and must be advised, not assumed.

Note too that the **CNDP's own published formalités page lists health data flatly under autorisation
préalable and does not surface the art. 22 derogation at all.** Regulator practice may be narrower than
the statute. (MEDIUM)

**Art. 20 is a further hazard.** Even a validly filed déclaration can be converted to the authorisation
regime by the CNDP, by reasoned decision **notified within 8 days** of filing, where the processing
"présente des dangers manifestes". The declaration route is fast but **not final**. (HIGH)

### Arts. 43 / 44 — cross-border transfer: **verified correct as cited**

**Art. 43:** transfer abroad only to a state ensuring "un niveau de protection suffisant"; the CNDP
"établit la liste des Etats répondant aux critères".

**Art. 44** gives derogations: express consent of the data subject, or necessity (life, public interest,
legal claims, **performance of a contract between the controller and the data subject**, contract in the
data subject's interest, judicial mutual assistance, or **"la prévention, le diagnostic ou le traitement
d'affections médicales"**), or a bilateral/multilateral agreement, or **express reasoned CNDP
authorisation** where contractual clauses or internal rules give sufficient protection. (HIGH)

**Penalty — art. 60:** 3 months to 1 year imprisonment and 20 000-200 000 DH. (HIGH)

**Practical consequence for the hosting decision** (PROJECT.md flags hosting jurisdiction as early and
expensive to reverse): the register shows **EU hosting is workable via the adequacy route**. DabaDoc
holds **T-220/2021 → T-HB-220/2021** for transfer to **IRELAND**, legal basis recorded as *"Pays assurant
une protection suffisante de la vie privée"*. Other Moroccan companies hold transfer filings to
**FRANCE, ALLEMAGNE, LUXEMBOURG** on the same basis and to the **ETATS-UNIS** on other bases. A transfer
filing (**form F118**, régime "Demande de Transfert de Donnée à l'Etranger", numbered `T-nnn/YYYY`) is a
**separate formality, required in addition** to the declaration or authorisation. Morocco-only hosting
avoids the formality entirely. (HIGH)

---

## 4. CNDP guidance and precedent for SaaS / medical software (Q4)

### The strongest precedent found: DabaDoc

Read directly from the CNDP public register. Six entries for **DABADOC** (Casablanca):

| Régime | N° | Nature | Dénomination / finalité | Décision |
|---|---|---|---|---|
| **Autorisation Préalable** | **A-436/2021** | Normale | **"Service en ligne de gestion du cabinet médical www.dabadoc.com"** | **Accordée — A-S-436/2021, 12/12/2021** |
| Autorisation Préalable | A-382/2021 | Simplifiée | Gestion des ressources humaines | A-RH-382/2021 |
| Autorisation Préalable | A-353/2017 | Normale | Formulaire en ligne | Accordée, 02/02/2018 |
| Transfert | T-220/2021 | Simplifiée | www.dabadoc.ma → **IRLANDE** ("pays assurant une protection suffisante") | Accordée — T-HB-220/2021 |
| Déclaration | D-256/2024 | Normale | Prise de contact visiteurs plate-forme | Accordée, 04/04/2024 |
| Déclaration | D-257/2024 | Normale | Gestion des cookies | Accordée |

**Why this matters:** a **software vendor** — not a doctor, not a clinic — obtained a **prior
authorisation in its own name** whose declared subject is **the online practice-management service
itself**, under a **health-scoped decision code (`A-S-`)**. It is the only health-scoped instrument found
anywhere in a ten-vendor sweep. (HIGH that the entry exists and reads as described; **MEDIUM-LOW on what
it proves** — the register publishes no scope or reasoning, so it is not visible whether DabaDoc filed
for its own controller-side processing or in a way that covers practitioners' patient data.)

**This is the single most useful item to put in front of a lawyer.** It is a concrete, named, granted
Moroccan precedent for exactly the shape of company this project is.

### The CNDP decision-number format, decoded from register data

The CNDP publishes no numbering legend. The format was reconstructed empirically from register rows.
The register has **two distinct columns**: `N°` (case number) and `Récépissé / Autorisation` (the issued
instrument), and the instrument inserts an activity/norm code the case number lacks:

**`<régime>-<norme/activité>-<séquence>/<année>`**

| Code | Meaning | Confidence |
|---|---|---|
| `D-` | Déclaration de traitement | HIGH |
| `A-` | Demande d'Autorisation Préalable | HIGH |
| `T-` | Demande de Transfert de Donnée à l'Étranger | HIGH |
| `-GC-` | **Gestion des Clients** (a *norme simplifiée*; appears verbatim in the register's own dropdown) | HIGH |
| `-RH-` | Gestion des Ressources Humaines | HIGH |
| `-S-` | **Santé** | MEDIUM-HIGH (inferred from A-436/2021's subject) |
| `-HB-` | Hébergement | MEDIUM-HIGH |

No `AU-` (autorisation unique) prefix was found in the register. A separate **"Nature"** column qualifies
every entry as **Normale** or **Simplifiée**, matching CNDP forms **F211** (déclaration normale), **F214**
(déclaration simplifiée), **F112** (autorisation normale), **F113** (autorisation simplifiée). (HIGH)

**Verification trap worth recording:** a vendor-published *récépissé* number will never match a direct
register search — you must strip the activity code to get the case number (`D-GC-908/2025` → search
`D-908/2025`). Further, the register's global search box **only indexes the responsable-de-traitement
name**; the `N°` column is searchable only via its column filter, and the `Récépissé / Autorisation`
column has **no filter at all**. So absence-by-name is meaningful; absence-by-number is not. (HIGH)

### The CNDP model / simplified regime — it exists, and is the likely practical route

- **Form F113, "Demande d'autorisation préalable"** (CNDP, Sept 2025). Its **Section III is headed
  "MODÈLE D'AUTORISATION DE TRAITEMENT"** and asks for "Catégorie de l'activité", "**Le modèle
  d'autorisation qui correspond à votre traitement**", "Dénomination du traitement" and a "Numéro de
  décision". Header cites "Loi N° 09-08 […] **Art 12**". (HIGH — read from the form.)
- Mechanism: the CNDP publishes a **délibération** defining a model for a recurring processing type; a
  controller then files the **simplified F113** referencing that model instead of a bespoke F112.
- **Directly relevant and very recent:** on **28/11/2025** the CNDP adopted **Délibération n° D-941-2025,
  "relative au modèle type de demande d'autorisation des traitements de suivi des patients"** — a
  standard authorisation model for **patient-monitoring processing**. Adopted alongside **D-942-2025**
  (vidéosurveillance in health establishments), **D-943-2025** (access control — notably *converted from
  declaration to authorisation*), **D-939-2025** (cookies, simplified declaration) and **D-940-2025**
  (newsletters, simplified declaration). (HIGH that these exist and are titled as stated; **the body text
  of D-941-2025 could not be retrieved** — the PDF fetch returned an error page.)
- **D-941-2025 is a live lead.** If a published model exists for patient monitoring, an ordonnance file
  may map onto it, converting a bespoke multi-month filing into a simplified one.
- Older evidence that the *autorisation unique* concept exists in Moroccan practice: **Délibération
  n° 30-AU-2012 du 09/11/2012**, a *modèle de demande d'autorisation unique* for **insurance
  organisations** managing subscriptions. (MEDIUM — secondary source, not read in original.)
- **Délibération n° D-03-2023 du 17/03/2023** simplifies notification for **bioequivalence studies** — the
  only clearly health-sector deliberation on the CNDP's public deliberations index.

### What could NOT be found

- **No CNDP deliberation, FAQ entry or guidance addressing cloud/SaaS providers as such.** The CNDP FAQ
  covers none of: controller vs processor, cloud hosting, SaaS, or whether a provider may file on behalf
  of clients. (HIGH — page checked.)
- **No published CNDP decision explaining the controller/processor split for multi-tenant software.**
- **No published legend for the register's decision-code prefixes.**

---

## 5. Timelines and what a filing requires (Q5)

| | Déclaration | Autorisation préalable | Transfert |
|---|---|---|---|
| Form | **F211** (normale) / **F214** (simplifiée) | **F112** (normale) / **F113** (simplifiée, per modèle) | **F118** |
| Register prefix | `D-nnn/YYYY` | `A-nnn/YYYY` | `T-nnn/YYYY` |
| Legal basis | art. 12-2, arts. 13-20 | art. 12-1, art. 21 | arts. 43-44 |
| Timeline | **récépissé in 24 h** (art. 19); may start on receipt | CNDP states **2 months, extendable once**; clock **pauses** while the file is incomplete | separate filing; must be granted before transferring |
| Risk | CNDP may convert to authorisation, notified **within 8 days** (art. 20) | *"Tout dossier incomplet fera l'objet d'un rejet"* | — |

(HIGH on forms, prefixes and the art. 19 / art. 20 statutory deadlines; MEDIUM on the 2-month figure — the
CNDP states it on its own site but the statute does not set it, and "extendable once" plus pause-on-
incomplete mean **the 2-4 month planning assumption in PROJECT.md is reasonable and should stand**.)

**Documents the CNDP lists for a prior authorisation:**
- authorisation letter for the signatory;
- **justificatifs de l'information des personnes concernées** (proof data subjects were informed);
- **evidence of consent**, where consent is the basis;
- **sub-processing contracts** setting out technical and organisational security measures — i.e. **our
  DPA becomes an exhibit to our customers' filings**;
- for health data specifically: researcher credentials, medical protocol, **ethics-committee opinion**,
  and a data-coding commitment.

That last line is telling: the CNDP's health-authorisation document set is written for **research**, not
routine care. Circumstantial support for the reading that routine care was meant to travel the art. 22
declaration route. (MEDIUM — inference.)

**Language:** forms are French; F113 is a French-language PDF. The register has French and Arabic
interfaces. **Fees:** none mentioned on any CNDP formalités, procedures or authorisation page (MEDIUM —
absence of evidence; confirm with the CNDP). **Filing channel:** could not confirm whether filing is an
online portal or paper/email; CNDP publishes PDF forms and a helpline (3020). (LOW — unresolved.)

---

## 6. Can one authorisation cover the platform and all its customers? (Q6)

**On the text and the register's structure: no.** Every register entry is keyed to a single named
**responsable du traitement** with its own RC number, address and city. The register's filter fields are
`RT_NOM`, `ACTIVITE`, `REGIME`, `NUM_ADTR`, `DECISION` — there is no field for "covered third parties" and
no visible construct for one filing covering many independent controllers. Form F113 has exactly one
"IDENTIFICATION DU RESPONSABLE DE TRAITEMENT" block. (HIGH on the structure; MEDIUM on the conclusion.)

**Three qualifications:**

1. **The DabaDoc precedent (A-436/2021 → A-S-436/2021)** shows a vendor holding a health-scoped
   authorisation whose declared subject is *the service*. If that covers the practitioners' patient data,
   it is functionally the thing this project needs. **Unverified — scope is not published.** Lawyer
   question 1.
2. **The "modèle" regime is the CNDP's intended answer to "many small controllers doing the same thing".**
   It does not remove the per-controller filing, but converts a bespoke filing into a simplified one
   (F113 + décision number). If **D-941-2025** or a successor fits, each optician's filing could become a
   short form rather than a months-long dossier. **Whether a simplified authorisation is materially
   faster than a normale one is not published.** (MEDIUM)
3. **Art. 22**, if it applies, sidesteps the issue entirely — déclaration, 24-hour récépissé. (LOW)

**Net:** a single platform-wide authorisation covering all customers *as controllers* is **not
established** and must not be assumed. A single platform authorisation for the platform's **own**
processing is clearly available — DabaDoc has one. The gap between those two is the business-model risk.

---

## 7. What Moroccan health-adjacent software vendors actually do (Q7)

> **Read this as observed practice, not as guidance.** That a market operates without visible filings is
> evidence about enforcement reality and competitive norms. It is **not** a basis for deciding not to
> comply. **Art. 52** (10 000-100 000 DH for operating a file without the required declaration or
> authorisation) and **art. 57** (3 months-1 year **imprisonment** and 50 000-300 000 DH for processing
> health data without express consent) apply regardless of what competitors do.

### Register evidence — opticians and clinics

**Not one Moroccan optician entity in the register has filed anything about customer, prescription or
health data.** Everything filed is peripheral:

| Entity | Activité | Filing | Subject |
|---|---|---|---|
| ATLAS OPTIQUE SARL (Casablanca) | "lunettier opticien" | D-13/2019 *Simplifiée* | **vidéosurveillance** |
| COMPAGNIE INDUSTRIELLE D'OPTIQUE DU MAROC (CIOM) | "opticien" | A-447/2021, D-481/2021, T-40/2022, T-41/2022, T-232/2021, T-267/2024 | **RH, actionnariat salarié (Essilor), hébergement cloud RH → France** |
| LN OPTIC (Tanger) | "Fabrication et Commerce Optique" | A-444/2021, D-478/2021, D-187/2013, T-44/2022, T-45/2022, T-229/2021, T-61/2013 | **RH, actionnariat, contact box → France** |
| LIVING OPTIC (Fès) | — | D-447/2025 *Simplifiée* (délib. 350/2013) | — |

Same pattern sector-wide — even large clinics file for everything *except* the patient file:

| Entity | Filing | Subject |
|---|---|---|
| CLINIQUE AIN BORJA (Casablanca) | A-232/2024 *Normale* | recording satisfaction calls with **patients and doctors** |
| CLINIQUE AIN BORJA | A-233/2024 *Normale* | use of **patient/staff photos and video** for communications |
| CLINIQUE AIN BORJA | A-975/2023, D-912/2023, D-706/2026 | RH, vidéosurveillance, courriers |
| CENTRE D'HEMODIALYSE CLINIQUE DU REIN | A-26/2025, A-1612/2024, D-1307/2024 | RH, fournisseurs, vidéosurveillance |
| CENTRE DE RECHERCHES CLINIQUES (Marrakech) | D-252/2022 | vidéosurveillance |

**Interpretation.** Either (a) the core clinical file is handled as an art. 22 déclaration that the
register's limited search did not surface, or (b) it is not being filed. These could not be
distinguished — **absence from a result set is not proof of absence from the register**, given the search
limitations noted in §4. (MEDIUM on the pattern; LOW on the explanation.)

### Vendor evidence — ten vendors examined

Legend: **(a)** CNDP number published · **(b)** privacy policy citing 09-08/CNDP · **(c)** DPA offered ·
**(d)** hosting disclosed · **(e)** controller/processor allocation · **(R)** found in register by name

**Optician software**

| Vendor | a | b | c | d | e | R |
|---|---|---|---|---|---|---|
| **MyOpti** (MJTECH SARL AU, Rabat) | No | **No privacy policy at all** | **Yes** (in CGU) | Unnamed "ISO 27001 certified" provider | **Yes, explicit** | No |
| **Netoptis** (PRIMASYS) | No | Yes, cites 09-08, no number | No | **"Centres de Données… en Europe"** | No | No |
| **Gestoptic** (OmegaUpdate, Agadir) | No | **Nothing published** | No | N/A (desktop app) | No | No |
| **OpticWizard** (Rotunda Tech Ltd, **UK**) | No | Mentions 09-08 once, in passing | No | Not specified | **Yes, explicit** | No |
| **OpticienPro** | No | Policy exists, **zero Moroccan anchoring** | No | No | No | No |
| **LopticoMaroc** | No | **Nothing published** | No | — | No | No |

- **OpticWizard (~800 DH/yr) takes exactly the processor position**, in English:
  > "In most cases, we act as a **processor** on behalf of our professional clients (opticians) regarding
  > data they record about their own customers. For data linked to OpticWizard user accounts, we act as
  > the **data controller**."
  No CNDP number, CNDP not named at all, no hosting location, no DPA. Controller entity is **Rotunda Tech
  Ltd, a UK company** — a UK-GDPR frame applied to a Moroccan market. (HIGH)
- **MyOpti has the market's best-drafted DPA while publishing nothing about CNDP.** Its CGU contains a
  real processor clause — *"MJTECH n'agit qu'en qualité de sous-traitant vis-à-vis de ses Clients"*, client
  determines *"les finalités et les moyens du traitement"*, sub-processor authorisation with a 10-day
  objection window, delete-or-return on termination. But **no privacy policy, no mentions légales, no
  CNDP/09-08 reference** on the site. (HIGH)
- **Netoptis has an unremediated cross-border exposure**: it advertises European hosting yet appears
  nowhere in the register, including under the `T-` transfert regime such hosting requires. Its privacy
  policy was **last updated 1 December 2018**. (HIGH on what is published; HIGH on register absence by
  name.)
- **Gestoptic and LopticoMaroc publish no legal documentation whatsoever.** Gestoptic is a **desktop
  application**, which materially reduces its own processor exposure. LopticoMaroc is a directory/blog,
  not a vendor. (HIGH)

**Medical / dental / teleconsultation**

| Vendor | a | b | c | d | e | R |
|---|---|---|---|---|---|---|
| **Cabidoc** (POCKETDOC SARL) | **Yes — D-GC-908/2025**, mischaracterised | Marketing yes; **privacy policy no** | No | Claims Morocco, ISO 27001 | No | **Yes** |
| **TabibDoc Pro** (Wustack) | No | Yes — "Conforme à la Loi 09-08 (CNDP)" | No | **Not disclosed** | **Yes, explicit** | No |
| **DabaDoc** | **No** — holds A-S-436/2021 but does not publish it | Claims "autorisé par la CNDP" | Not seen | Not on site; **register shows transfer to Ireland** | No | **Yes — 6 entries** |

**The Cabidoc claim, verified against the register — this is the most instructive finding in the sweep.**
Cabidoc markets *"Certification CNDP Officielle N° D-GC-908/2025"*. The register entry is:

> **POCKETDOC SARL** | Casablanca | Activité: **"Application de gestion des cabinets medicaux"** |
> Régime: **Déclaration de Traitement** | N° **D-908/2025** | Nature: **Simplifiée** | Dénomination &
> Finalité: **"Gestion des clients"** | Décision: **Accordée** | Récépissé: **D-GC-908/2025** |
> **28/05/2025**

Three material discrepancies (HIGH confidence, verified in the register):
1. **"Certification" is wrong.** It is a *déclaration* — a self-notification receipted within 24 hours —
   not a certification and not an authorisation. Cabidoc's own Instagram post is more accurate:
   *"déclarée à la CNDP"*.
2. **The scope is customer management, not health data.** Finalité is "Gestion des clients" under the
   `-GC-` *norme simplifiée* — managing its own client base (the doctors). **It does not cover patient
   health data.**
3. **The claim appears only in marketing.** Cabidoc's privacy policy mentions **neither CNDP nor loi 09-08
   nor the number**, discloses no hosting location, allocates no roles and lists no sub-processors.

**DabaDoc is the exact inverse: real substance, nothing published.** It holds the only health-scoped
instrument found in the sweep (`A-S-436/2021`) plus a declared transfer to Ireland — and publishes no
number, no hosting location, no controller/processor split. (Its "HIPAA compliant" marketing claim is
noise; HIPAA is a US statute with no Moroccan application.)

**TabibDoc Pro has the clearest role allocation of any medical vendor** — Wustack as *responsable du
traitement* for portal/support data, as *sous-traitant* for health data inside the product, with the
treating physician as controller. No CNDP number, no hosting location, no DPA template. Its own guide
tells doctors that health data needs *autorisation préalable* and offers a technical sheet *"to attach to
your CNDP authorisation request"* — i.e. **it positions the doctor as the filer and does not claim its own
registration.** (HIGH)

### What this means

- **Published CNDP compliance is close to non-existent**: 1 vendor of 10 publishes a number, and that one
  overstates what it is.
- **Publication and substance are uncorrelated.** The vendor with the strongest register position
  (DabaDoc) publishes nothing; the vendor with the loudest claim (Cabidoc) holds the weakest instrument.
  **A published number proves nothing until resolved against the register's Régime and Finalité columns.**
- **The structural gap across the whole sector is health-data scope.** These vendors are mostly
  sous-traitants processing patient data, but the registrations that exist are for "Gestion des clients"
  or HR. `A-S-436/2021` is the only health-scoped instrument found.
- **Cross-border hosting is largely undeclared.** DabaDoc is the only vendor that appears to have filed a
  transfer.
- **For this project:** no competitor has solved this publicly, so there is no template to copy; doing it
  properly is a genuine differentiator when selling to multi-store opticians; but **you will be the one
  explaining an unfamiliar obligation to your own customers at signup.**

---

## 8. Platform obligations regardless of how the controller question resolves (Q8)

All bind the platform whether it is sous-traitant, joint controller or controller. (HIGH unless noted.)

1. **A written data processing agreement with every optician — art. 23-3 and 23-4.** Must state the
   sous-traitant acts **only on the controller's instructions** (art. 23-3, reinforced by art. 25) and
   that art. 23-1 security obligations apply to it too. Must be **in writing or equivalent** for
   evidentiary purposes (art. 23-4).
   *Design consequence:* the DPA must be part of the **self-serve signup flow** — clickwrap terms
   incorporating a DPA, accepted before provisioning, with the acceptance recorded. Cheap now, expensive
   to retrofit.
2. **Security measures — art. 23-1.** Appropriate technical and organisational measures against
   accidental or unlawful destruction, loss, alteration, unauthorised disclosure or access, *"notamment
   lorsque le traitement comporte des transmissions de données dans un réseau"*, proportionate to risk and
   data nature, judged against the state of the art and cost.
3. **The art. 24 health-data control set — a concrete engineering checklist, not a principle.** For
   sensitive or health data the controller must implement eight named controls: entry control to
   facilities (a), data-media control (b), insertion control (c), usage control (d), **access control —
   only authorised persons may access data covered by the authorisation (e)**, transmission-recipient
   verification (f), **introduction control — ability to verify after the fact, within an appropriate
   period, which personal data were entered, when and by whom (g)**, and transport control (h).
   **(g) is an audit-log requirement in all but name**; (e) maps onto the per-gérant permission model
   already in PROJECT.md. Build both into the ordonnance module.
   **Penalty — art. 58:** 3 months to 1 year and 20 000-200 000 DH.
4. **Professional secrecy — art. 26.** Binds the controller and everyone who learns of processed personal
   data in the course of their duties, **including after leaving the role**, under the criminal law. Put a
   secrecy clause in staff and contractor agreements.
5. **Express consent for health data — art. 57.** Criminal liability (3 months-1 year and
   **50 000-300 000 DH**) for processing health data **without the express consent of the data subject**.
   This is framed as a **consent** offence, not a filing offence — **express consent capture is required
   independently of which filing regime applies**. Art. 21-2 also makes express consent one of only two
   grounds on which an authorisation is granted.
   *Design consequence:* the ordonnance record should carry an explicit consent artefact — who consented,
   when, to what.
6. **Data subject rights — arts. 7, 8, 9** (access, rectification, opposition). **Art. 53:** a
   20 000-200 000 DH fine **per infraction** for refusing them. The platform must give each optician the
   tooling to honour requests — export, correct, suppress — and the DPA should commit us to assist.
   Append-only ordonnance versioning (already a PROJECT.md requirement) **must not make rectification
   impossible**; a correction must be expressible.
7. **Retention — art. 55.** 3 months-1 year and 20 000-200 000 DH for retaining data beyond the period set
   by law or **beyond the period stated in the declaration or authorisation**. **This collides head-on
   with the 10-year art. 211 CGI retention in PROJECT.md.** They are reconcilable — art. 55's first limb
   defers to "la durée prévue par la législation en vigueur" — but the declared retention in the CNDP
   filing must be stated to match the fiscal obligation, and health data may warrant a shorter period than
   invoices. **Do not declare one blanket retention period for the whole database.** Take advice.
8. **Purpose limitation — art. 54.** 3 months-1 year and 20 000-200 000 DH for processing *"à des fins
   autres que celles déclarées ou autorisées"*. Combined with **art. 12-1-b**, this makes the
   reminders/relance module the sharpest unflagged risk in the product — see §3.
9. **Cross-border transfer — arts. 43-44, penalty art. 60.** Separate F118 filing per destination. Drives
   the hosting decision; see §3.
10. **Breach handling.** Loi 09-08 as read contains **no general breach-notification duty** — no such
    article was found. A real gap versus GDPR, and one that should not be assumed either way on this
    reading alone. (MEDIUM) Contractual breach-notification to the optician belongs in the DPA regardless.
11. **Being named in customers' filings — art. 15-i.** Each optician's declaration must disclose
    sub-processing "sous toute forme". Expect to supply customers with a standard paragraph and a
    security-measures annex. **Prepare this once, as a document, and ship it with onboarding.**

---

## 9. What is genuinely unsettled

Stated plainly, so this is not searched again — these need a lawyer, not more searching:

- **Whether the platform can file once and cover its customers.** Not established either way. The DabaDoc
  precedent suggests something like it is possible; the register structure and the F113 form suggest
  per-controller filing.
- **Whether art. 22 puts an optician's ordonnance file on déclaration rather than authorisation.** Turns
  on "seule finalité" and on whether a Moroccan opticien-lunetier is a *"praticien de la santé soumis au
  secret professionnel"*. Neither is resolved by available online material.
- **What D-941-2025 (modèle for "traitements de suivi des patients") actually contains**, and whether an
  optical prescription file maps onto it. PDF body could not be retrieved.
- **Whether a simplified (F113) authorisation is materially faster than a normale one.** Not published.
- **Whether filing is online or paper, and whether any fee applies.** Not published.
- **Whether loi 09-08 is being replaced or amended.** Reform has been publicly discussed in Moroccan
  press; **the status of any draft was not verified** — this check was cut short. Unresolved, and it
  matters for a project starting now.
- **Whether the register's apparent absence of patient-file filings is real** or an artefact of its
  limited search (the global search box indexes only the responsable's name).
- **Whether Medicalink / DrData / Sanidoc / Clinicalink are live Moroccan vendors at all** — absent from
  the register by name, but their websites were not verified. Treat as not investigated, not as a negative.

---

## 10. Questions for a Moroccan data-protection lawyer / CNDP pre-filing consultation

Ordered by business impact. **Q1-Q3 decide whether self-serve signup survives. Ask those first.**

1. **Can the platform obtain a single CNDP prior authorisation, in its own name, covering the processing
   of optical prescription data belonging to all of its optician customers — so a new optician can be
   provisioned and start recording ordonnances immediately, without their own filing?** Please review
   **DabaDoc's autorisation A-436/2021 (décision A-S-436/2021, 12/12/2021, "Service en ligne de gestion du
   cabinet médical www.dabadoc.com")** as the closest known precedent and tell us what its scope actually
   is — does it cover the practitioners' patient data, or only DabaDoc's own processing? If it covers the
   practitioners, how was the filing structured?
2. **Does art. 22 apply to a Moroccan optician's prescription file, putting it under *déclaration*
   (24-hour récépissé, art. 19) instead of art. 21 authorisation?** Specifically: (a) is an
   *opticien-lunetier* under loi 45-13 a *"praticien de la santé soumis au secret professionnel"*, and is
   there an express secrecy duty in 45-13 or its implementing texts? (b) can the ordonnance be structured
   as a **separate traitement with a "seule finalité"** of care / health-service management, distinct from
   the commercial sale, invoicing and stock traitement — and what schema separation would that require of
   us? (c) does it change the answer whether the prescription came from a doctor (*ordonnance médicale*)
   or from the optician's own refraction (*réfraction opticien*)?
3. **If neither 1 nor 2 works and each optician must file their own authorisation: how long does it
   actually take in practice** for a simplified (F113) filing against a published model, for a small
   independent business? Is there **any** mechanism — a *modèle*, an *autorisation unique*, a sectoral
   deliberation — under which a new optician could lawfully begin processing before the decision issues,
   or must they wait? This single answer determines whether we redesign onboarding.
4. **Does Délibération n° D-941-2025 du 28/11/2025 ("modèle type de demande d'autorisation des traitements
   de suivi des patients") cover an optical prescription file?** If yes, what does the model require, and
   can we prepare a pre-filled F113 for customers to submit at signup? If no, is the CNDP open to adopting
   a model for opticians, and what would proposing one involve?
5. **Is the platform a sous-traitant, a joint controller, or a controller in its own right**, given that
   we define the ordonnance schema, set retention, run the reminder/relance campaigns (AMO 23-month nudge,
   prescription-renewal follow-up) and derive analytics? Do the relance features push us into joint
   controllership, and do they independently trigger **art. 12-1-b** (authorisation for use *"à d'autres
   fins que celles pour lesquelles elles ont été collectées"*)?
6. **Please review our draft DPA against art. 23-3 and 23-4**, and tell us what the CNDP expects in the
   *"contrats de sous-traitance"* exhibit our customers must attach to their own filings. Can we give
   customers a **standard annex** (security measures, sub-processors, the art. 15-i sub-processing
   disclosure) that the CNDP will accept as-is?
7. **Hosting: Morocco or EU?** The register shows Moroccan companies transferring to Ireland, France,
   Germany and Luxembourg on the *"pays assurant une protection suffisante"* basis, with a separate **F118**
   filing per destination (e.g. DabaDoc's **T-220/2021 → T-HB-220/2021** to Ireland). **For sensitive
   health data specifically**, is EU hosting accepted in current CNDP practice, or is Morocco-resident
   hosting effectively expected? Does the answer change if we are sous-traitant rather than controller?
   **Who files the F118 — us, or each optician?**
8. **Retention.** How do we reconcile the **10-year fiscal retention (art. 211 CGI)** with **art. 55**
   (criminal liability for retaining beyond the period stated in the declaration/authorisation)? Should
   health data carry a shorter declared retention than invoices, and what period should we declare? What
   does compliant **offboarding of a churned optician** look like — archive, restrict, anonymise, or delete
   health data while retaining fiscal records?
9. **Express consent (art. 57 — imprisonment and up to 300 000 DH).** What form of express consent must the
   optician capture from their customer before a prescription is recorded, what evidence must be retained,
   and what should the product capture and store to make it provable? Do art. 21-2 consent (for the
   authorisation) and art. 57 consent (for the processing) require separate artefacts?
10. **Art. 24 controls.** Is there a CNDP-expected standard (ISO 27001, a CNDP référentiel, a sectoral
    guide) for the eight controls in art. 24 — in particular **24-1-g**, after-the-fact verification of
    which data were entered, when and by whom? Will our audit-log and per-gérant permission design satisfy
    it, and would the CNDP grant any **art. 24-2 dispensation** given our size?
11. **CIN / carte d'identité nationale (art. 12-1-e).** Storing a customer's CIN triggers authorisation
    independently of health data. Should we design the schema to **avoid storing CIN entirely**, and is
    that feasible given AMO claim paperwork?
12. **Breach.** Does any Moroccan instrument impose a breach-notification duty on a controller or a
    sous-traitant — statutory, sectoral, or CNDP practice? If not, what should the DPA commit us to?
13. **Enforcement posture.** What is the CNDP's actual stance toward a small SaaS vendor operating before
    its filing is granted? Is there a safe way to onboard early customers during the filing period — and
    does the **manual-onboarding-first** sequencing already in the roadmap change the analysis versus
    self-serve?
14. **Is loi 09-08 being replaced or amended?** What is the status of any draft, what would change for the
    controller/processor relationship, and should we design to the current law or to the draft?
15. **Filing mechanics.** Online portal or paper/email; any fee; French only or Arabic accepted; who must
    sign; and a realistic end-to-end calendar if we start today.

---

## 11. Recommended edits to PROJECT.md (no changes made)

- **Requirements → Legal & compliance:** change *"law 09-08 art. 23"* to **"art. 12-1-a and art. 21"**;
  add separate lines for **art. 23 (written DPA with each optician + security measures)** and **art. 24
  (the eight health-data controls, incl. the 24-1-g audit log)**.
- **Constraints → Legal — health data:** note that **art. 22 may put this under déclaration instead**, and
  that the question is open pending advice. Keep the 2-4 month calendar as the planning assumption.
- **Open Questions:** promote *"The CNDP controller/processor split between us and the optician"* out of
  "resolve before the relevant phase" — **it gates both the self-serve signup requirement and the hosting
  decision, which are early and expensive to reverse.**
- **Add to Open Questions:** whether the reminders/relance module is a secondary use triggering
  art. 12-1-b; whether CIN is stored anywhere (art. 12-1-e); how art. 211 CGI 10-year retention reconciles
  with art. 55.
- **Add to Active requirements:** a clickwrap DPA accepted at signup **before provisioning**, with the
  acceptance recorded — this must be in the self-serve flow from the start.
- **Context (competitive):** no Moroccan optician-software competitor publishes any CNDP registration; the
  best-drafted processor clause in the market (MyOpti's CGU) sits behind a site with no privacy policy at
  all. Verifiable compliance is an available differentiator for multi-store buyers.

---

## Sources

**Primary**
- Loi n° 09-08, Dahir n° 1-09-15 du 18 février 2009, B.O. n° 5714 — https://www.cndp.ma/images/lois/Loi-09-08-Fr.pdf (text extracted; all article quotes above are verbatim from it)
- CNDP public national register (RN-PDP), 22 963 entries, updated 07/09/2026 — https://rn-pdp.cndp.ma/fr/list/1.html (queried directly; all DabaDoc, Cabidoc/POCKETDOC, optician and clinic entries above read from it)
- CNDP form F113, "Demande d'autorisation préalable", Sept 2025 — https://www.cndp.ma/wp-content/uploads/2025/09/CNDP-Autorisation-Prealable-Conformement-Decision-F113-20250910.pdf
- CNDP — Formalités — https://www.cndp.ma/formalites/
- CNDP — Notifier une demande d'autorisation préalable — https://www.cndp.ma/notifier-une-demande-dautorisation-prealable/
- CNDP — Notifier un traitement — https://www.cndp.ma/notifier-un-traitement/
- CNDP — Procédures de notification — https://www.cndp.ma/procedures-de-notification-process/
- CNDP — Délibérations — https://www.cndp.ma/deliberation/
- CNDP — Nouvelles délibérations (D-939 à D-943-2025, 28/11/2025) — https://www.cndp.ma/la-cndp-publie-de-nouvelles-deliberations/
- CNDP — Registre National PDP — https://www.cndp.ma/registre-nationale-pdp/
- CNDP — FAQ — https://www.cndp.ma/faq/
- Décret n° 2-09-165 du 21 mai 2009 (implementing decree) — https://www.cndp.ma/wp-content/uploads/2023/06/Decret-2-09-165-FR.pdf — **scanned image, no extractable text; not read**

**Secondary / market**
- Cabidoc — https://cabidoc.com/ · https://cabidoc.com/gestion-cabinet-medical-maroc · https://cabidoc.com/privacy · https://cabidoc.com/terms
- TabibDoc Pro — https://tabibdoc.ma · https://tabibdoc.ma/legal/confidentialite · https://tabibdoc.ma/blog/guide-complet-conformite-cndp-cabinet-medical
- DabaDoc — https://www.dabadoc.com/
- MyOpti — https://myopti.ma · CGU: https://myopti.ma/site/terms_condition
- Netoptis — https://netoptis.com · https://netoptis.com/site/privacy · https://netoptis.com/site/terms
- OpticWizard privacy policy — https://opticwizard.com/politique-de-confidentialite
- Gestoptic — https://www.gestoptic.ma/ · OpticienPro — https://opticienpro.ma/politique-de-confidentialite/ · LopticoMaroc — https://www.lopticomaroc.com/logiciels-pour-opticiens/
- Netoptis on loi 45-13 and opticians — https://www.netoptis.com/blog/projet-loi45_13-opticiens
- Note de présentation, projet de loi 45-13, SGG — https://www.sgg.gov.ma/portals/0/AvantProjet/56/Avp_loi_45.13_Fr.pdf
- CMS, Etat des lieux de la protection des données au Maroc — https://cms.law/fr/mar/legal-updates/flash-info-maroc-etat-des-lieux-de-la-protection-des-donnees-a-caractere-personnel-au-maroc-loi-n-09-08

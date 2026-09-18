---
phase: 04-clients-ordonnances
type: research
created: 2026-09-18
consumed_by: gsd-planner
---

# Phase 4: Clients & Ordonnances — Research

**Researched:** 2026-09-18
**Domain:** PostgreSQL extensions across a database-per-client fleet, trigram/phonetic name search,
immutable versioned clinical records, tenant-scoped file storage, French/Moroccan prescription conventions
**Confidence:** HIGH where labelled `[mesuré]` (run against the live Compose stack, PostgreSQL 18.6)
and `[paquet]` (read from installed source). MEDIUM on the clinical conventions — the sign convention
and the transposition rule are corroborated by French *and* Moroccan trade sources, but the numeric
bounds have no normative source and are marked as such.

## How to read the labels

| Label | Means |
|---|---|
| `[mesuré]` | I ran it, in this repo's Compose stack or its venv, and report what happened |
| `[paquet]` | Read from the installed package source under `.venv/` |
| `[repo]` | Read from this repository's own code or planning documents |
| `[CITED: url]` | From a named external source |
| `[raisonné]` | Inference. No tool confirmed it. Treat as a proposal, not a fact |

---

<user_constraints>
## User Constraints (from 04-CONTEXT.md)

**Status carried forward verbatim: ACCEPTED BY DEFAULT, NOT RATIFIED.** The four grey areas were put
to the owner on 2026-09-17; he did not answer them and then said « continue ». A plan applies them by
**naming** them, so that disagreement costs one word. This research disputes three of the four — see
the verdict table below — and a disputed recommendation is *more* in need of naming, not less.

### Acquis — inherited, not reopened

- `domaine/` already carries `magasins`, `stock`, `caisse`. Phase 4 adds its business apps and
  **each must enter `BUSINESS_APPS` in `plateforme/tenancy/router.py` in the same commit** — an
  unclassified app fails `manage.py check` with `tenancy.E001`, which is intended (Pitfall 12).
- The projection layer exists and **`CHAMPS_PROTEGES` is still empty.** Plan 03-06 designated phase 8
  as the one that would fill it. **That is probably wrong: the ordonnances arrive now.** See grey area 5.
- The rights `ordonnance.voir` and `ordonnance.saisir` already exist in the catalogue since phase 3.
- Every new `APIView` carries its `@extend_schema` in the plan that creates it, and any change to a
  view, serializer or route regenerates `web/src/api/schema.yml` **and** the TypeScript client in the
  same commit.
- Every new query parameter enters `PARAMETRES_RESERVES` in the same commit.
- `MagasinScopedViewSet` is inherited **first**; the guard checks MRO order.

### Locked decisions (grey areas 1–4, accepted by default)

1. **Clinical rules** — minus-cylinder convention, refused if positive; axe integer 0–180; sphère
   −30.00..+30.00; cylindre −10.00..0; addition +0.50..+4.00; all in 0.25 steps; both EP forms stored
   and explicitly distinguished, never derived one from the other in silence.
2. **CLIENT-08 cannot be satisfied in this phase.** Phase 4 builds the commande spéciale attached to
   an ordonnance and carrying its values; phase 8 connects the bon de commande. **Do not tick
   CLIENT-08 in phase 4.**
3. **Ordonnance photo** — a named Django `Storage` injected by setting, never a hard-coded path; no
   image in the database; the path carries the client and a read never resolves a client-supplied
   path; local filesystem in development; **the production choice is a Phase 1 output**; access to the
   image goes through the **same right** as the structured record (`ordonnance.voir`).
4. **Transliteration-tolerant search** — `unaccent` + `pg_trgm` with a GIN index on the normalised
   name, plus a curated equivalence table as data. **Refuse** generic phonetic normalisation of the
   Soundex / Metaphone family.

### Claude's discretion (grey area 5, an engineering decision, logged not asked)

Whether an ordonnance is a protected **field** or a protected **row**, and therefore whether Phase 4
is the first real user of `CHAMPS_PROTEGES`. The rule from 03-06 applies: a new renderer is added to
the `RENDUS` list in `tests/test_projection.py` **in the plan that creates it**.

### Deferred / out of scope

- The fournisseur half of CLIENT-08 — phase 8.
- Any real patient data reaching production: the legal lock is on **storing real data**, not on
  writing the code. Phase 1 has not started.
- The backlog of **18 manual browser verifications** from phase 3 is open. Phase 4 must not add to it
  without someone intending to do them.
</user_constraints>

---

## 1. Verdict on the four accepted-by-default recommendations

Lead finding first, because three of the four move.

| # | CONTEXT recommendation | Verdict | Why |
|---|---|---|---|
| 4a | `CREATE EXTENSION` must be proven to work on a non-superuser role | **CONFIRMED, and stronger than hoped** | The per-client role — no `SUPERUSER`, no `CREATEDB`, no `CREATEROLE` — created `unaccent`, `pg_trgm`, `fuzzystrmatch` and `btree_gin` in its own database. `[mesuré]` §2 |
| 4b | `unaccent` + `pg_trgm`, GIN on the normalised name, is layer 1 | **PARTLY INVALIDATED** | `unaccent` **cannot be indexed at all** (it is `STABLE`) — proven, §5.3. And the default `%` operator at threshold 0.3 **misses "Mohammed" when searching "Mhamed"** — it fails CLIENT-10's own example. The `<%` operator passes. The operator choice is load-bearing and the CONTEXT does not name it. `[mesuré]` §5 |
| 4c | Refuse Soundex **and** Metaphone | **HALF REFUTED** | Soundex is genuinely bad here — it merges Abdelkader with Abdelkrim and Mohamed with Mahmoud. But `metaphone(nom, 8)` produces `MHMT` for **Mhamed, Mohamed, Mohammed and Mouhamed** — exactly CLIENT-10 — while keeping Abdelkader and Abdelkrim apart, which trigrams do *not* do. On the measured corpus it is strictly better than both soundex and dmetaphone. `[mesuré]` §5.5 |
| 1 | Minus-cylinder, refused if positive | **CONFIRMED for the ordonnance, INCOMPLETE for the product** | Ophthalmologists in France *and in Morocco* prescribe in minus-cyl. But **the optician and the lab work in plus-cyl**, and transposition is a daily counter operation. CLIENT-08 sends these values to the fournisseur. A model that only refuses plus-cyl leaves the optician doing the arithmetic in their head. `[CITED]` §6.1 |
| 1 | Axe integer 0–180 inclusive | **MINOR FLAW** | The prescription convention is **1 to 180**; 0 and 180 are the same axis and 0 is not written. `0–180 inclusive` admits two encodings of one axis. `[CITED]` §6.2 |
| 1 | Sphère ±30.00 | **CONTRADICTS THIS PROJECT'S OWN RESEARCH** | `.planning/research/PITFALLS.md` Pitfall 18 already says −20.00..+20.00. Neither has a normative source. The plan must pick one and say which document it is overruling. `[repo]` §6.3 |
| 1 | Addition +0.50..+4.00 | **HARMLESS BUT USELESS** | Observed clinical range is +0.75..+3.50. The proposed bound is a superset, so it rejects nothing real and therefore protects nothing. The check that *would* catch a typo — addition is normally identical in both eyes — is missing. `[CITED]` §6.4 |
| 1 | Both EP forms, never derived | **CONFIRMED, with one refinement and one internal contradiction to resolve** | Monocular EP is nose-bridge-to-each-eye and is **not** half the binocular value, which is exactly why it cannot be split out. But bino ≈ mono_OD + mono_OG *is* a valid cross-check, and `PITFALLS.md` says "binocular derived — not the reverse". Pick one sentence. Also: half-millimetre precision, so `Decimal`, not integer. `[CITED]` §6.5 |
| 2 | CLIENT-08 stays open until phase 8 | **CONFIRMED, and the missing half is already specified** | `.planning/research/ARCHITECTURE.md` line 290 already decided the hard part: the prescription is **copied (snapshotted), not referenced**, onto the supplier order line. `[repo]` §3.4 |
| 3 | Named Storage, path carries the client, same permission as the record | **CONFIRMED, but the mechanism the CONTEXT implies does not exist in Django** | `FileField(storage=<callable>)` evaluates the callable **once, at field construction** — a per-tenant storage instance is impossible that way. `[paquet]` §4.1 |

**Two findings with no home in the CONTEXT at all:**

- **A bare `SET pg_trgm.*` leaks across requests through PgBouncer.** Proven: a threshold set outside a
  transaction survived onto a subsequently opened Django connection. This is threat T-02-02, and
  Phase 4 is the first feature in the product that would trip it. §2.4
- **`date de naissance` is load-bearing in Phase 4 and no CLIENT requirement names it.** Moroccan
  regulation requires a doctor's ordonnance for under-16s, and RAPPEL-04 needs an age to apply the
  11-month child rule. `[repo: PITFALLS.md Pitfall 18]` §6.6

---

## 2. Question 1 — extensions across the fleet

### 2.1 The privilege, proven in the running stack

`[mesuré]` Against `optique-db-1` (PostgreSQL 18.6), connected through the tenancy registry as client
`anfa`'s own role:

```
WHOAMI:                                  optique_u000001 / optique_c000001
ROLE ATTRS (super, createdb, createrole): (False, False, False)
PRIVS (db CREATE, public CREATE, public owner): (True, True, pg_database_owner)
CREATE EXTENSION unaccent:       OK
CREATE EXTENSION pg_trgm:        OK
CREATE EXTENSION fuzzystrmatch:  OK
CREATE EXTENSION btree_gin:      OK
CREATE EXTENSION postgis:        FAILED — not available on this server
INSTALLED: unaccent 1.1, pg_trgm 1.6, fuzzystrmatch 1.2, btree_gin 1.3 — all owned by optique_u000001, in schema public
```

*(The dev database was restored afterwards: extensions dropped, probe table dropped, `ALTER ROLE
… RESET ALL`. `select extname from pg_extension` → `plpgsql` only.)*

**Why it works, so the plan knows what it depends on:**

1. `[mesuré]` All four are **trusted extensions** on 18.6 —
   `SELECT name, trusted FROM pg_available_extension_versions` returns `t` for `unaccent`, `pg_trgm`,
   `fuzzystrmatch`, `btree_gin` and `citext`. A trusted extension needs `CREATE` on the database and
   `CREATE` on the target schema, not `SUPERUSER`.
2. `[repo]` `SqlProvisioner.create_database` issues `CREATE DATABASE {name} OWNER {owner}` where the
   owner is the client's own role. The role therefore has `CREATE` on the database.
3. `[mesuré]` On PostgreSQL 15+ the `public` schema is owned by `pg_database_owner`; the probe
   confirmed `has_schema_privilege(current_user,'public','CREATE') = true`.

**The exact privilege required is therefore: ownership of the database.** Not a grant, not a role
attribute. Our own provisioning path already guarantees it.

> **The single condition that invalidates this.** If a managed provider ever hands out a *non-owner*
> application role — the scenario `DatabaseProvisioner` exists as an interface to absorb
> (`02-RESEARCH.md` Open Question 2, still open) — this finding does not carry. The plan should record
> the dependency in one sentence rather than assume it away.

### 2.2 Migration, not provisioning — and the reason is decisive

The CONTEXT asks whether the extension belongs at provisioning time. **It does not, and this is not a
close call.**

`[repo]` `provision_client()` returns early:

```python
if client.status == Client.ACTIVE:
    # Idempotent no-op. The operator ran it twice, or self-serve retried.
    return client
```

There is no path that re-runs provisioning over an already-ACTIVE client. An extension created only at
provisioning time would exist on clients provisioned *after* the change and on nobody else — including
the two clients in this development cluster today. `migrate_all` is the only mechanism in the product
that reaches every existing client and *reports* who failed and who is behind.

**Recommendation:** a `CreateExtension` operation in a **business app** migration.

- `[paquet]` `django.contrib.postgres.operations.CreateExtension.database_forwards` calls
  `router.allow_migrate(schema_editor.connection.alias, app_label, **self.hints)` with no
  `model_name`. `TenantRouter.allow_migrate` handles that signature and returns
  `is_tenant_alias(db)` for a business app — so the extension is created on tenant aliases and never
  on `default`. Verified against the installed Django 6.1.1.
- `[repo]` `migrate_all` migrates each client with `client.connection_params(direct=True)`, which
  swaps in `PG_ADMIN_HOST/PORT`. **DDL never goes through PgBouncer.** Nothing to do here.
- `[raisonné]` Put the extension migration in the **lowest** business app in the dependency graph that
  needs it, and make the index migration depend on it explicitly. Django applies migrations per app in
  dependency order, so an index using `gin_trgm_ops` in app X and an extension in app Y needs
  `dependencies = [("Y", "000N_extensions")]` or it will race on a fresh database.

### 2.3 Test-suite path

`[repo]` Two distinct paths, both satisfied:

| Path | Database | Created as | Owner | Extension creatable |
|---|---|---|---|---|
| `tenant_a` / `tenant_b` static aliases | `test_optique_test_a/b` | pytest-django, as `optique_app` (has `CREATEDB`) | `optique_app` | yes |
| Provisioning tests | `test_client_c00000N` | `SqlProvisioner`, `OWNER test_client_u00000N` | the client role | yes — this is the shape proven in §2.1 |

### 2.4 PgBouncer — the real interaction, and it is not the one the CONTEXT expected

DDL bypasses the pooler entirely (§2.2). The hazard is at **runtime**, and it is serious.

`[mesuré]` Through PgBouncer (`pool_mode = transaction`, `CONN_MAX_AGE = 0`), as the client role:

```
default word_sim threshold:      0.6
after bare SET … = 0.91:         0.91
--- Django connection closed, new connection opened ---
fresh client conn sees:          0.91      <-- LEAKED across the pool
inside atomic + SET LOCAL 0.42:  0.42
after commit:                    0.91      <-- SET LOCAL reverted correctly
```

A bare `SET pg_trgm.word_similarity_threshold` — which is what `set_limit()` and every blog post about
pg_trgm tuning tell you to do — **rode a pooled server connection into the next request.** This is
exactly threat T-02-02, the one `docker-compose.yml` sets `log_statement = all` to detect. It has not
bitten yet because nothing in Phases 2–3 issues session SQL. Phase 4's search is the first thing that
would.

**Two safe ways to set the threshold. The plan must use one and forbid the other in a grep-able way.**

| Option | Shape | Verdict |
|---|---|---|
| **A — role default** | `ALTER ROLE <client role> SET pg_trgm.word_similarity_threshold = 0.3`, once, in the same migration as the extension | `[mesuré]` Works: `rolconfig` carries it, and a newly opened connection starts at `0.3`. Applied by the server at connection startup, so it is pooling-safe by construction and costs zero statements per request. **Recommended.** |
| **B — `SET LOCAL`** | inside an explicit `transaction.atomic(using=alias)` around the query | `[mesuré]` Correctly reverted at commit. Safe, but adds a transaction to a read path and one more thing to remember at every call site. |
| **C — bare `SET` / `set_limit()`** | anywhere | **Forbidden.** Proven to leak. |

> `[mesuré]` **Gotcha with option A:** `ALTER ROLE … SET pg_trgm.*` fails in a session where the
> pg_trgm module has not yet been loaded — `unrecognized configuration parameter`, or
> `permission denied to set parameter` once a placeholder exists. Call any pg_trgm function first in
> the same session (`SELECT similarity('a','b')`) and it succeeds for a non-superuser. The migration
> must do those two statements in that order, and the reason must be in a comment or someone will
> "tidy" the first one away.

### 2.5 `django.contrib.postgres` in `INSTALLED_APPS` — a decision with a `tenancy.E001` consequence

`[mesuré]` `django.contrib.postgres` is **not** currently in `INSTALLED_APPS`, and
`from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension, CreateExtension`,
`…search import TrigramWordSimilarity`, `…indexes import GinIndex` all import fine without it.

`[paquet]` **But the ORM *lookups* are registered only in `PostgresConfig.ready()`:**

```python
CharField.register_lookup(TrigramWordSimilar)
TextField.register_lookup(TrigramWordSimilar)   # and Unaccent, TrigramSimilar, TrigramStrictWordSimilar
```

So without the app installed, `.filter(nom_recherche__trigram_word_similar="mhamed")` — the only ORM
form that compiles to the `%>` operator and therefore the only one that **uses the GIN index** — does
not exist. The `TrigramWordSimilarity()` *annotation* is importable but produces a
`word_similarity(a,b) >= x` predicate, which is a sequential scan.

**Recommendation: add `django.contrib.postgres` to `INSTALLED_APPS`, and add its label `postgres` to
`CONTROL_PLANE_APPS` in `plateforme/tenancy/router.py` in the same commit.** It owns no models, exactly
like `projection` and `drf_spectacular` which are already listed there for the same reason. Omitting
the classification fails `manage.py check` with `tenancy.E001` on the next run — which is the system
working, but it will be a confusing five minutes if the plan does not say it up front.

`[paquet]` One side effect to record rather than fear: `PostgresConfig.ready()` connects
`register_type_handlers` to `connection_created`, which runs
`SELECT oid, typarray FROM pg_type WHERE typname = %s` for `hstore` and `citext`. It is wrapped in
`@functools.lru_cache` **keyed by connection alias**, so it is two queries per alias per process, not
per request, and it is a query rather than a session-state `SET` — it does not pollute a pooled server
connection. `[repo]` No test in `tests/test_connection_budget.py` asserts "zero statements at connect"
(the five tests there are configuration invariants plus two live connection-count probes), so nothing
turns red. The `log_statement = all` proof in `docker-compose.yml` is a manual claim and will now show
two extra lines per alias; update the comment rather than removing the app.

### 2.6 Which extensions Phase 4 actually needs

| Extension | Needed? | Why |
|---|---|---|
| `pg_trgm` | **Yes** | The only way to get an indexed fuzzy match. |
| `fuzzystrmatch` | **Yes, if metaphone is adopted** (§5.5) | `metaphone()` is `IMMUTABLE` and indexable on a plain btree. |
| `unaccent` | **Probably not** — see §5.3 | It is `STABLE`, cannot be indexed, and Python-side normalisation does the same job with no extension and no volatility lie. |
| `btree_gin` | Only if a single GIN index must combine the trigram column with a scalar (e.g. `actif`). Not needed for the shape recommended here. |
| `citext` | No. `lower()` on a normalised column is clearer and already indexable. |

---

## 3. Question 2 — the ordonnance data model

### 3.1 Does the stock ledger pattern transfer? No — and copying it would be a mistake

`[repo]` `domaine/stock/models.py` is a ledger of **signed deltas** with an aggregated derivation:

```python
#: Signed. +10 received, -1 sold, and a correction is another row, never an edit.
quantite_delta = models.IntegerField()
```

Quantity on hand = `SUM(quantite_delta)`. A correction is a compensating row of the opposite sign.

**An ordonnance is not that shape.** There is no "compensating ordonnance"; you cannot add a
−0.25 sphère row to a +2.00 sphère row and call the result a correction. The clinically meaningful
object is one complete prescription at one moment.

The right characterisation, and the sentence the plan should carry:

> Stock and caisse derive their truth by **aggregation** over deltas. Ordonnances derive theirs by
> **selection** over immutable snapshots. What the two share — and it is the part CLAUDE.md #4 is
> actually about — is that **no mutable column carries the truth and a correction is an append.**
> What they do not share is the arithmetic.

`[raisonné]` Concretely: transferring the delta pattern would produce an `OrdonnanceDelta` table that
nobody can read at the counter and that makes "print this client's current prescription" a fold. The
misleading part of the analogy is the word "ledger"; the transferable part is "append-only".

### 3.2 Recommended shape

`[raisonné]` One table, one complete immutable row per version.

```
Ordonnance
  client            FK -> Client, PROTECT
  magasin           FK -> Magasin (via MagasinScopedModel)      # see the open question in §3.3
  version           PositiveSmallInteger                        # 1, 2, 3 … per client
  supersede         FK -> self, null, PROTECT                   # the row this one replaces
  type_revision     {renouvellement, correction}                # null on version 1
  motif_revision    CharField(blank)                            # free text, why
  source            {ordonnance_medicale, refraction_opticien}  # CLIENT-05
  prescripteur      CharField(blank)                            # CLIENT-04; blank iff source=opticien
  date_prescription DateField                                   # CLIENT-04
  sphere_od / sphere_og      Decimal(4,2), null
  cylindre_od / cylindre_og  Decimal(4,2), null
  axe_od / axe_og            PositiveSmallInteger, null
  addition_od / addition_og  Decimal(3,2), null
  ep_binoculaire             Decimal(4,1), null                 # mm, half-mm steps
  ep_mono_od / ep_mono_og    Decimal(4,1), null
  ep_saisi          {binoculaire, monoculaire, les_deux}        # which one the user actually entered
  photo             FileField, blank                            # CLIENT-09, §4
  created_at / created_by
```

Three shape decisions worth defending explicitly in the plan:

1. **Flat `_od` / `_og` columns, not two rows per ordonnance.** A two-row shape makes "axe OD present,
   sphère OD absent" representable, turns every read into an aggregation, and turns the cross-eye
   checks (§6.4) into a self-join. Ten columns is not a modelling failure; it is the domain.
2. **`supersede` points forward-to-back, on the new row.** The alternative — an `erronee` flag set on
   the old row — is an `UPDATE` on an immutable record, which is the thing CLIENT-06 forbids. With the
   pointer on the new row, "was version 2 a mistake?" is answered by
   `exists(version 3 where supersede=2 and type_revision='correction')` — derived, never written.
3. **`ep_saisi` is stored, not inferred from which columns are null.** Null is ambiguous between
   "not measured" and "not applicable"; the CONTEXT's requirement that the system record *which form
   was entered* needs its own column.

### 3.3 What a "typo correction" means in this model — and the open question it exposes

A correction is **a new version** with `type_revision = correction` and `supersede` pointing at the
mistaken row. The old row stays readable exactly as entered, which is CLIENT-06's literal wording, and
the mistake stays visible, which is what makes the "plausible typo" failure mode (axe 90 typed for 9)
recoverable at all.

**What it is *not*:** an annotation on the old row. An annotation is an `UPDATE`, and once one `UPDATE`
path exists on this table someone will reach for it for a second reason.

> **OPEN QUESTION FOR THE OWNER — magasin scope on an ordonnance.**
> A client belongs to the business; an ordonnance is captured at one magasin. If `Ordonnance` inherits
> `MagasinScopedModel` then `MagasinScopedViewSet` filters it, and **a gérant granted only magasin B
> will not see an ordonnance recorded at magasin A for the same client — and will then record a
> duplicate.** That is a clinical hazard, not a permissions nicety. The alternatives are: (a) scope it
> and accept the duplication, (b) record the capturing magasin as a plain column with no queryset
> filter, so any authorised gérant sees the full prescription history. This research recommends (b)
> and flags that the storage shape is identical either way — only the viewset changes — so it is
> cheap to defer the *filtering* decision but **not** cheap to omit the column. Put the column in
> version 1 of the migration regardless.

### 3.4 CLIENT-08 — the half that Phase 4 can build is already specified

`[repo]` `.planning/research/ARCHITECTURE.md` line 290:

> "**Ordonnance → commande spéciale:** the structured prescription is copied (snapshotted, not
> referenced) onto the supplier order line, so a later prescription edit cannot silently change what
> was ordered."

That settles the design question the CONTEXT leaves open. Phase 4 builds the `CommandeSpeciale` with
**copied** prescription values plus a `source_ordonnance` FK kept for traceability only. Phase 8 reads
the copy. The CONTEXT is right that the tick does not move in Phase 4.

`[CITED]` One thing to build now because it is cheap now and a remake later: the copied block must
render the values in the **plus-cylinder** form the lab works in (§6.1), with the convention stated on
the page. `PITFALLS.md` Pitfall 18 already says "have a real optician review that output before
shipping" — that is a phase-8 verification item, not a phase-4 one, but the *function* that transposes
belongs here, next to the model, with its own test.

### 3.5 Grey area 5 — the projection registre

`[repo]` `CHAMPS_PROTEGES` is `{}` and `CHAMPS_PUBLICS` has 11 entries.

`[raisonné]` The answer to the CONTEXT's own question:

| Thing | Row or field? | Mechanism |
|---|---|---|
| The ordonnance itself | **Row** | `ordonnance.voir` gates access to whole objects — that is `MagasinScopedViewSet` and queryset filtering (03-07), not the field registre |
| A "dernière ordonnance" summary on the client record | **Field** | A protected field on an object the caller *is* allowed to see. This is `CHAMPS_PROTEGES`'s first real entry |

So: **Phase 4 is the first real user of the registre if and only if the client detail screen shows a
prescription summary.** The UI-SPEC decides that, and the plan that writes the UI-SPEC must decide it
consciously rather than discovering it in a serializer.

`[repo]` **The chore that will otherwise turn CI red:** `test_perm06_tout_champ_de_modele_expose_est_classe`
requires that **every model field exposed by a `ModelSerializer` is in `CHAMPS_PROTEGES` or
`CHAMPS_PUBLICS`.** Phase 4 exposes roughly 25 new fields across `Client` and `Ordonnance`. Each one
needs a line in `CHAMPS_PUBLICS` in the same commit as its serializer. That is the single most
mechanical and most forgettable task in this phase; put it in the acceptance criteria of every plan
that adds a serializer, not in one clean-up plan at the end.

`[repo]` No new **renderer** is created by Phase 4, so the `RENDUS` list in `tests/test_projection.py`
(JSON, CSV, HTML, catalogue) stays at four — *unless* the ordonnance photo is served through a fifth
path, in which case it joins the list. See §4.4.

---

## 4. Question 3 — storing the ordonnance photo (CLIENT-09)

### 4.1 The mechanism the CONTEXT implies does not exist

`[repo]` There is **no** `MEDIA_ROOT`, no `MEDIA_URL`, no `STORAGES`, no `FileField` and no
`ImageField` anywhere in `config/`, `plateforme/` or `domaine/`. Phase 4 is the first file in the
product.

`[paquet]` `django/db/models/fields/files.py`, `FileField.__init__`:

```python
self.storage = storage if storage is not None else default_storage
if callable(self.storage):
    self._storage_callable = self.storage
    self.storage = self.storage()          # <-- called ONCE, at field construction
```

**A callable `storage=` is evaluated exactly once, at import time.** The tenant alias only exists in a
`contextvar` at request time. So the obvious shape — `storage=lambda: TenantStorage(current_alias())` —
silently binds whichever tenant happened to be bound when the module was imported, which in practice is
none, and in the worst case is one. This is precisely the class of bug CLAUDE.md #12 describes:
invisible to code review, because the guarantee it breaks is written one layer up.

`[paquet]` `upload_to=` **is** per-instance — `FileField.generate_filename(instance, filename)` runs at
save time — but it only controls the name, not the storage root, and the name it produces is then
persisted in the row.

### 4.2 Recommended shape

`[raisonné]` **One `Storage` subclass, a module-level singleton, that resolves the tenant prefix inside
every method from `current_alias()`.**

```
class StockageOrdonnances(Storage):
    def _prefixe(self) -> str:
        return current_alias()        # raises NoTenantBound — fails closed, like the router
    def _open(self, name, mode):  ...   # joins self._prefixe() with name, then validates
    def _save(self, name, content): ...
    def exists / delete / size / url ...
```

The property that makes this safe, and the one sentence to put in the docstring:

> **The stored name is tenant-relative and the prefix is re-derived from the live context on every
> access. A row carrying another tenant's path cannot resolve, because the prefix never comes from
> the row.**

That is the same discipline as `TenantRouter`: the caller does not get to name the boundary.

`[paquet]` Classic path traversal is *already* blocked by the framework —
`django/core/files/utils.py::validate_file_name(name, allow_relative_path=True)` raises
`SuspiciousFileOperation` on an absolute path or any `..` component, and `Storage.save/open/delete` all
call it. So the residual risk is **not** `../../`; it is a perfectly valid relative path that belongs
to a different optician. Only re-deriving the prefix closes that.

`[repo]` **Follow the existing precedent, which is already in this repo:**
`plateforme/control_plane/storage.py` is an abstract two-method interface, a
`LocalFilesystemStorage` that is honest about being development-only, an `is_relative_to(root)` escape
check, `chmod(0o600)` on every artifact, and `import_string(settings.BACKUP_STORAGE)` to swap the
backend. Phase 4 should copy that shape exactly — with one difference the plan must not miss: Django's
`FileField` needs a **`django.core.files.storage.Storage` subclass**, not the two-method ABC. Do not
try to reuse `BackupStorage`; mirror it.

### 4.3 What the tenancy layer does and does not give you here

`[repo]` `plateforme/tenancy/` constrains **connections and rows** and nothing else. There is no file
handling in it at all. State that plainly in the plan, because it changes the honest security claim:

> Isolation between clients for *rows* rests on `REVOKE CONNECT` and a separate database — a boundary
> below the application. Isolation for *files* rests on Python and this one class. There is no
> `REVOKE` underneath it.

That is the same admission `plateforme/projection/registre.py` already makes for field visibility, and
the same compensating control applies: **a test that binds tenant B and attempts to read tenant A's
stored path, and is refused.** That test is not optional; it is the whole guarantee.

### 4.4 Serving the image

`[raisonné]` The CONTEXT is right and the reasoning should be preserved verbatim in the plan: a signed
URL that bypasses the permission check makes the projection layer theatre.

- **No `MEDIA_URL`, no static serving, no pre-signed object-storage URL.** The bytes leave through a
  DRF view that has already resolved `ordonnance.voir` **and** the magasin scope for that row.
- If streaming through Python becomes a cost, the escape hatch is `X-Accel-Redirect` / `X-Sendfile` —
  but issued *after* the permission check, from an internal-only location. Record it as the escape
  hatch, do not build it.
- `[repo]` If that view is implemented as a new **renderer**, it joins the `RENDUS` list in
  `tests/test_projection.py` per the 03-06 rule. If it is an ordinary `APIView` returning
  `FileResponse`, it does not — but it still needs its own permission test.

### 4.5 Production — a Phase 1 output, and two Phase 2 guarantees it touches

`[repo]` Mark in the plan, as the CONTEXT asks:

> **The production storage backend is an output of Phase 1 (LEGAL-02, hosting jurisdiction), not of
> Phase 4.** Development is local filesystem. `backups/` and the dev media root must both be
> gitignored — a committed ordonnance photo is a health-data leak in git history, which is not
> revocable.

Two further consequences the CONTEXT does not draw, and both are real:

1. `[raisonné]` **TENANT-09 (per-client backup, verified single-client restore) currently backs up a
   *database*.** An ordonnance photo that lives outside the database is outside that guarantee. Either
   the Phase 4 plan extends the backup artifact to include the client's file prefix, or Phase 2's
   promise quietly becomes false. Flag it; do not silently pick.
2. `[raisonné]` The **10-year retention (art. 211 CGI)** and the offboarding archive in Phase 12 have
   the same gap.

### 4.6 One concrete one-line gap found while reading

`[repo]` `plateforme/tenancy/telemetry.py`'s `SENSITIVE_KEY` regex covers `ordonnance`, `prescription`,
`sphere`, `cylindre`, `axe`, `addition`, `nom`, `telephone` and so on — but **not** `photo`, `image`,
`fichier`, `scan`, `piece_jointe` or `upload`. An uploaded filename routinely contains the patient's
name (`ordonnance_benali_ahmed.jpg`), and a `ValidationError` traceback through an upload serializer
would carry it to Sentry unredacted. One regex alternation, in the plan that adds the upload.

---

## 5. Question 4 — transliteration-tolerant search (CLIENT-10)

All numbers in this section were produced against `optique-db-1`, PostgreSQL 18.6, `pg_trgm` 1.6,
`fuzzystrmatch` 1.2, on a 20 400-row table of Moroccan first-name × surname combinations. `[mesuré]`

### 5.1 The measurement that changes the plan

Searching the full-name column for `mhamed`, at the default `pg_trgm.similarity_threshold = 0.3`:

| Operator | Returns | Verdict against CLIENT-10 |
|---|---|---|
| `%` (similarity) | Mhamed (0.583), Mohamed (0.333), Mouhamed (0.313) | **FAILS** — "Mohammed" is missing |
| `<%` (word_similarity) | Mhamed (1.000), Mohamed (0.571), Mouhamed (0.571), **Mohammed (0.333)** | **PASSES** |
| `metaphone(…,8)` equality | Mhamed, Mouhamed, Mohamed, Mohammed | **PASSES** |

The reason `%` fails is dilution: `similarity('mohammed alaoui', 'mhamed')` is dragged down by the
surname the user did not type. `word_similarity` scores the query against the best-matching *extent*
of the target, so a one-token query is not punished for the tokens it omits.

**The CONTEXT's layer 1 is therefore salvageable but under-specified: it names the extensions and the
index and not the operator, and the default operator is the one that fails.**

`[mesuré]` The GIN `gin_trgm_ops` index **does** serve `<%` — forced with `enable_seqscan = off`:

```
Bitmap Heap Scan on bench_client   Filter: ('mhamed' <% nom_recherche)
  -> Bitmap Index Scan on idx_bench_trgm
       Index Cond: (nom_recherche %> 'mhamed'::text)
Execution Time: 4.3 ms   (20 400 rows)
```

### 5.2 No scalar threshold separates truth from error

This is the finding that determines the *shape* of the feature, not just its parameters.

| Pair | `similarity` | Should match? |
|---|---|---|
| mohamed / mohammed | 0.700 | **yes** |
| youssef / yousef | 0.667 | yes |
| elhassan / el hassan | 0.583 | yes |
| mohamed / mhamed | 0.500 | **yes** |
| khadija / khdija | 0.500 | yes |
| fatima / fatma | 0.444 | yes |
| **fatima / fatiha** | **0.400** | **NO — different people** |
| **abdelkader / abdelkrim** | **0.400** | **NO — different people** |
| **mohamed / hamed** | 0.400 | no |
| **mohammed / mhamed** | **0.333** | **YES — CLIENT-10's own example** |
| mohamed / mohcine | 0.231 | no |
| mohamed / ahmed | 0.167 | no |

The required true positive at 0.333 sits **below** two required true negatives at 0.400. **The ranking
is inverted.** No threshold exists that admits "Mhamed ↔ Mohammed" and excludes "Fatima ↔ Fatiha".

**Consequence for the plan, and it is a UX decision as much as a technical one:**

> Trigram similarity is a **recall and ranking** device, never a precision filter. The search endpoint
> returns a *ranked candidate list* that the person at the counter chooses from. Nothing in Phase 4
> may auto-select, auto-merge, or treat a single high-scoring hit as "the client". A false positive at
> the counter is the neighbour's record — and with ordonnances on it, that is a health-data disclosure,
> not a UX annoyance.

### 5.3 `unaccent` cannot be indexed — proven, and it changes the recommendation

`[mesuré]` `SELECT proname, provolatile FROM pg_proc`:

| Function | Volatility | Indexable |
|---|---|---|
| `unaccent` | **`s` (STABLE)** | **no** |
| `lower`, `similarity`, `soundex`, `metaphone`, `dmetaphone` | `i` (IMMUTABLE) | yes |

`[mesuré]` Both routes fail identically:

```
CREATE INDEX ON t USING gin (unaccent(nom) gin_trgm_ops)
  -> 42P17: functions in index expression must be marked IMMUTABLE
ALTER TABLE t ADD COLUMN g text GENERATED ALWAYS AS (unaccent(nom)) STORED
  -> 42P17: generation expression is not immutable
ALTER TABLE t ADD COLUMN g text GENERATED ALWAYS AS (lower(nom)) STORED  +  GIN gin_trgm_ops
  -> OK
CREATE INDEX ON t (metaphone(nom,8))
  -> OK
```

Two ways out, and they are not equivalent:

| Option | Shape | Assessment |
|---|---|---|
| **A — `IMMUTABLE` wrapper** | `CREATE FUNCTION f_unaccent(text) RETURNS text IMMUTABLE AS $$ SELECT unaccent('unaccent', $1) $$` | The community standard, and it is a lie: the function is not immutable, it depends on a dictionary that can change, and the index silently goes wrong if it does. **And** CLAUDE.md #12 requires `REVOKE EXECUTE … FROM PUBLIC` on it in the same migration, plus a test that the wrong principal is refused. Cost and risk for no gain. |
| **B — normalise in Python on write** | a plain `nom_recherche` column, filled by the model's `save()` / a service, indexed `GIN gin_trgm_ops` | `[raisonné]` Immutable by construction. `unicodedata.normalize('NFKD', …)` + strip combining marks + casefold + collapse whitespace does the accent folding with **no extension at all**. **Recommended.** |

**Consequence: `unaccent` is probably not needed by this phase.** The extension surface shrinks to
`pg_trgm` (+ `fuzzystrmatch` if §5.5 is adopted). That is a smaller thing to prove across 300 client
databases, which is the whole point of question 1.

`[raisonné]` The honest cost of option B: changing the normalisation rule later needs a backfill
migration over `nom_recherche`. Write the normaliser as one named function with its own unit tests so
the backfill is a `RunPython` that calls it, not a rewrite.

`[repo]` One related note: `SqlProvisioner.create_database`'s docstring says the ICU `fr-FR` locale
matters because "Phase 4's `test_client10_search_finds_mohamed_mohammed_and_mhamed` depends on it."
`[raisonné]` That is mildly misattributed — ICU collation governs `ORDER BY` and `lower()` on accented
uppercase; trigram matching does not consult it. The collation is still the right decision for sorting
a French client list; it just is not what makes CLIENT-10 pass. Worth correcting the docstring in
passing so the next reader does not chase it.

### 5.4 Soundex — the CONTEXT is right

`[mesuré]` Collision groups across 30 distinct Moroccan first names:

```
M530 = {Mhamed, Mohamed, Mohammed, Mouhamed}     (also Mahmoud in the pairwise test)
A134 = {Abdelkader, Abdelkrim}                    <-- wrong merge
F350 = {Fatima, Fatma}
R230 = {Rachid, Rachida}                          <-- wrong merge
```

Soundex keys on the first letter and four consonant classes. It merges Abdelkader with Abdelkrim, and
in the pairwise test Mohamed with Mahmoud. **Confirmed: do not use it.**

### 5.5 Metaphone — the CONTEXT's blanket rejection is refuted by measurement

`[mesuré]` `metaphone(nom, 8)`, same corpus, **three** collision groups:

```
MHMT = {Mhamed, Mohamed, Mohammed, Mouhamed}      <-- exactly CLIENT-10, and trigrams cannot do this
FTM  = {Fatima, Fatma}                            <-- correct; two spellings of one name
RXT  = {Rachid, Rachida}                          <-- one genuine false positive
```

And, decisively, `metaphone(…,8)` **keeps `Abdelkader` (`ABTLKTR`) and `Abdelkrim` (`ABTLKRM`) apart** —
which soundex, dmetaphone **and trigram similarity at 0.400** all fail to do.

Other measured behaviour:

- `[mesuré]` **Code length ≥ 6 is load-bearing.** `metaphone('abdelkader',4)` and
  `metaphone('abdelkrim',4)` are both `ABTL`. At 6 and 8 they separate. Write the `8` as a named
  constant with this sentence next to it.
- `[mesuré]` Accented Latin is handled gracefully: `Aïcha` and `Aicha` both give `AX`; `Naïma`/`Naima`
  both `NM`; `Zoubaïr`/`Zoubair` both `SBR`.
- `[mesuré]` The English-tuning failure the CONTEXT warned about is real but narrow:
  `metaphone('ghali',8)` = `FL` (the "-gh-" of *laugh*). `dmetaphone` gets `KL`. It is one name class,
  not a systemic collapse.
- `[mesuré]` **Arabic script produces an empty key for all three functions** — `soundex('محمد')`,
  `metaphone('محمد',8)` and `dmetaphone('محمد')` all return `''`. An empty key would match every other
  Arabic-script name in the table. BRAND-05 already anticipates Arabic client names. **Any phonetic
  index must carry `WHERE key <> ''` and the query must skip the phonetic branch when the query's own
  key is empty.** This is a one-line guard and a silent cross-client-visible bug if omitted.
- `[mesuré]` `dmetaphone` is worse than `metaphone` here: it merges Abdelkader with Abdelkrim (`APTL`)
  and splits Khadija from Khdija the other way round. Do not reach for it because the name sounds more
  modern.

**Recommendation to the planner:** raise the CONTEXT's grey area 4 rejection as a *named* disagreement.
The measured position is:

> Soundex: rejected, confirmed. Double Metaphone: rejected, confirmed. **`metaphone(nom, 8)`: adopt as
> one recall source among three**, indexed on a plain btree, guarded against the empty Arabic key,
> and never used as a filter on its own.

### 5.6 The shape to build

`[raisonné]` Three recall sources, unioned, ranked, capped:

| Layer | Mechanism | Catches |
|---|---|---|
| 1 | exact / prefix on `nom_recherche` and on `telephone` | the 90% case, and CLIENT-01's "find by phone" |
| 2 | `nom_recherche` `<%` query-token, GIN `gin_trgm_ops` | spelling drift, accents, one-letter variants |
| 3 | `metaphone(nom_recherche,8) = metaphone(query,8)`, btree, `<> ''` | Mhamed ↔ Mohammed, which layer 2 misses at any safe threshold |
| 4 | curated equivalence table (§5.7) | everything the first three still miss |

Rank by `GREATEST(similarity, word_similarity)` descending with an exact-match and phone-match boost,
`LIMIT 20`, and return the score so the UI can show *why* a row is there.

`[repo]` `PARAMETRES_RESERVES` already contains `"search"`, so a `?search=` parameter needs no new
entry. Any other name (`?q=`, `?telephone=`) does, in the same commit.

### 5.7 The curated equivalence layer, as data

`[raisonné]` The CONTEXT is right that this is data, not code. Concrete shape:

```
EquivalenceNom
  forme_normalisee   CharField, indexed      # 'mhamed'
  groupe             CharField, indexed      # 'mohamed'  — the canonical key
  source             {amorce, opticien}      # seeded, or added by a user
```

- Symmetric by construction: membership of a `groupe`, not a pair. `mhamed → mohamed`,
  `mohammed → mohamed`, `mouhamed → mohamed`; the query joins its own normalised token to `groupe` and
  then matches any member.
- **Seeded per client database**, in `seed_new_client`'s extension point (`plateforme/control_plane/seeding.py`
  already has the marked block, and its rule holds: `get_or_create` only, never a blind `create`).
  `[raisonné]` Per-client rather than in the control plane, because the control plane holds identity
  and the client database holds business data (CLAUDE.md #11), and because an optician who adds a local
  variant should not affect the fleet.
- The seed list is small — the twenty or thirty first-name families that actually recur. Do not try to
  be complete; layers 2 and 3 cover the tail.

---

## 6. Question 5 — verifying the clinical recommendations

### 6.1 Cylinder sign — confirmed for the ordonnance, incomplete for the product

`[CITED: atol.fr, cof.fr, optique-sergent.com, jl-optique.fr]` French ophthalmologists prescribe in
**negative cylinder** in the large majority of cases. `[CITED: lopticomaroc.com/transposition]` The same
is stated for Morocco. **The CONTEXT's core choice is correct and now has sources.**

**But the same sources say the other half, which the CONTEXT omits entirely:**

> "L'ophtalmologiste prescrit en cylindre négatif […] l'opticien et le verrier travaillent en cylindre
> positif, mieux adapté au surfaçage et à la commande des verres." — and transposition "is performed
> daily by every optician." `[CITED: jl-optique.fr]`

This product is *for opticians*, and CLIENT-08 sends these values to the fournisseur. So:

| Rule | Recommendation |
|---|---|
| Canonical storage | **minus-cyl, one convention, one place.** Confirmed. |
| Entry | Offer a **"saisir en cylindre positif"** toggle that transposes on the spot and **echoes the transposed minus-cyl result back before saving.** Forcing the optician to do the arithmetic mentally is how a wrong lens gets ordered, and a transposition error passes every bound. |
| Output to the fournisseur | The commande spéciale block renders the **plus-cyl** form, with the convention printed on the page (§3.4). |
| Implementation | One pure function, one test file, no second stored column. A second column is a second source of truth. |

`[CITED]` **The transposition rule**, verified against a worked Moroccan example
(`+1.50 (−0.50 à 20°)` → `+1.00 (+0.50 à 110°)`):

```
sphere'   = sphere + cylindre
cylindre' = −cylindre
axe'      = (axe + 90) mod 180,  with 0 mapped to 180
```

### 6.2 Axe — 1 to 180, not 0 to 180

`[CITED: gatinel.com, opticonex.fr, orthoptiste.relais-vision.fr]` The TABO scheme runs 0–180, read
anticlockwise. **On a prescription the axis is written between 1 and 180**; 0° and 180° are the same
axis, and an axis of 200° is an error to be folded to 20°.

`[raisonné]` `0–180 inclusive` therefore admits **two encodings of one axis**, which means two client
records can hold the same prescription and compare unequal. CLIENT-07's own wording says "0–180", so
do not contradict the requirement — **accept 0 at entry and canonicalise it to 180**, store `1 ≤ axe ≤ 180`,
and put the normalisation in the same named place as the sign convention.

**Two rules the CONTEXT omits and that catch real errors:**

- `[raisonné]` **`axe` is required if and only if `cylindre` is non-null and non-zero, and must be
  absent otherwise.** An axis with no cylinder is meaningless; a cylinder with no axis is unorderable.
  This is a cross-field constraint, not a range check, and it catches a whole error class that no bound
  does.
- `[raisonné]` A cylinder of exactly `0` should be stored as `NULL`, not `0`. "No astigmatism" and
  "astigmatism of zero dioptres" are the same fact with two encodings again.

### 6.3 Sphère — the project contradicts itself and neither side has a source

| Document | Range |
|---|---|
| `04-CONTEXT.md` grey area 1 | −30.00 .. +30.00 |
| `.planning/research/PITFALLS.md` Pitfall 18 `[repo]` | −20.00 .. +20.00 |

`[raisonné]` I could not find a normative source for either. **Report honestly: this bound is
judgement, in both documents.** What matters more than the number:

- The plan must **name which document it is overruling.** Two ranges written down in one repository is
  how a validator and a test end up disagreeing.
- `[raisonné]` A hard refusal at ±20 (PITFALLS' number, already written down, and the one a lens
  catalogue actually reaches) plus a **soft warning band beyond ±10** is worth more than either bound
  alone, because the warning catches the plausible typo — `+2.50` typed `+25.0` — that both hard
  bounds admit.

### 6.4 Addition — the bound is safe and useless; the missing check is the valuable one

`[CITED: visiondirect.fr, visio-net.fr, cahiers-ophtalmologie.fr]` The prescribed addition range in
practice is **+0.75 to +3.50** dioptres; first prescriptions sit near +0.75 and reach +2.75/+3.00 by the
late fifties.

The CONTEXT's +0.50..+4.00 is a strict superset. It will never reject a valid prescription — and it
will therefore never reject anything. That is fine as a guard-rail; it is not a control.

`[CITED: visiondirect.fr]` **"L'addition varie de +0,75 à +3,50 dioptries. Elle est la même pour les
deux yeux."**

`[raisonné]` That last sentence is the highest-value validation in this whole section and it is absent
from the CONTEXT: **warn — do not refuse — when `addition_od ≠ addition_og`.** It is a cross-field
check against a *plausible* value, which is precisely the failure mode the CONTEXT itself names as the
one bounds cannot catch. It must warn rather than refuse, because unequal additions do occur and a
refusal would make the software wrong about a real prescription.

`[raisonné]` 0.25-dioptre steps for sphère, cylindre and addition: correct for spectacle lenses, no
contradicting source found. Enforce as a modulo check, not as a choices list.

### 6.5 Écart pupillaire — confirmed, with a refinement and a contradiction to settle

`[CITED: conseil-optique.com, krys.com, orbitech-ai-academy.fr]`

- **Binocular EP** is pupil-to-pupil. **Monocular EP** is measured **from the nose bridge to each
  eye** — two independent half-distances that are routinely asymmetric.
- Monocular EPs are **indispensable** for progressives and strong corrections; shortcuts are
  inappropriate and the optician must take them on the client.
- Measured **to the half-millimetre** for progressives.
- Since September 2014 (France) the ophthalmologist is required to measure the pupillary distance.

**Three consequences for the model:**

1. `[raisonné]` The asymmetry is the point: **`bino ≈ mono_OD + mono_OG` is a valid cross-check, but
   splitting a binocular value into two monoculars is not valid** — it assumes a symmetry that is the
   exact thing progressives are sensitive to. The CONTEXT's "never derive one from the other" and
   PITFALLS' "binocular derived — not the reverse" are reconcilable, but **the plan must write the one
   sentence it means**, because they read as contradictory. Recommended wording: *store what was
   entered; compute the binocular sum as a displayed check when both monoculars exist; never compute a
   monocular.*
2. `[raisonné]` **`Decimal(4,1)` in millimetres, step 0.5 — not an integer.** The CONTEXT does not say
   this and an integer column is a silent loss of the precision progressives need.
3. `[raisonné]` The `ep_saisi` discriminator (§3.2) is what makes "a monocular value entered where a
   binocular was expected" — CLIENT-07's literal wording and roadmap criterion 3 — detectable at all.
   Without it, the two forms are just numbers in the same plausible range (a binocular of 62 and a
   monocular of 31 are both plausible, and a monocular of 62 is not detectable as wrong without knowing
   which was meant).

### 6.6 A field no CLIENT requirement names, and Phase 4 needs it

`[repo: PITFALLS.md Pitfall 18]`

> "Moroccan regulation (dahir on the profession d'opticien-lunetier, per secondary sources) requires a
> doctor's ordonnance for subjects under 16, for acuity ≤6/10 after correction, and for strong
> ametropia or presbyopia inconsistent with age; otherwise the optician may determine correction by the
> subjective method. […] Client date of birth is therefore a meaningful field, and a warning for
> under-16 without a medical ordonnance is a genuinely useful, differentiating feature."

`[raisonné]` And **RAPPEL-04** (phase 10) needs an age to apply the 11-month AMO rule to children aged
12 and under. Two independent requirements depend on a field that CLIENT-01 does not mention.

**Add `date_naissance` to `Client` in Phase 4.** Adding it later is a migration plus a data-collection
campaign across every existing client record — which is the expensive kind. The under-16 warning itself
can wait; the column cannot.

`[raisonné]` Flagged as `[ASSUMED]` on the legal side: PITFALLS itself says "per secondary sources". The
*column* is justified by RAPPEL-04 alone, so it does not depend on the legal claim being right.

---

## 7. Runtime state inventory

Phase 4 is additive — new tables, new files, new extensions. It renames nothing. The categories are
answered anyway, because two of them are non-empty.

| Category | Found | Action |
|---|---|---|
| Stored data | Nothing to migrate — no existing table holds a client or ordonnance. **But** the `nom_recherche` normalised column is derived data; if the normaliser ever changes, a backfill `RunPython` is required (§5.3). | none now; write the normaliser as a named callable so the future backfill is trivial |
| Live service config | **Two existing dev client databases** (`optique_c000001` anfa, `optique_c000002`) are ACTIVE and will receive the extension only via `migrate_all` — not via provisioning (§2.2). | ensure the extension is a migration, then run `migrate_all` |
| OS-registered state | None — no scheduler entries, no pm2, no systemd in this project. Verified by `docker ps` (three containers) and the absence of any such file in the repo. | none |
| Secrets / env vars | New settings only: the media storage backend and its root. `.env.example` must gain them in the same commit, following the `BACKUP_STORAGE` / `BACKUP_LOCAL_ROOT` precedent. | add to `.env.example` |
| Build artifacts | The generated TypeScript client and `web/src/api/schema.yml` are regenerated in the same commit as any view change — already the standing rule `[repo: CONTEXT acquis]`. | follow the existing rule |
| **PgBouncer pool state** | `[mesuré]` A session GUC set outside a transaction survives on a pooled server connection (§2.4). The dev cluster currently carries a leaked `0.91` from this research's probe; `server_idle_timeout = 60` reaps it. | none; the finding is the deliverable |

---

## 8. Environment availability

| Dependency | Required by | Available | Version | Fallback |
|---|---|---|---|---|
| PostgreSQL | everything | ✓ | 18.6 (`optique-db-1`) | — |
| `pg_trgm` | CLIENT-10 | ✓ | 1.6, trusted | none — CLIENT-10 has no non-index answer |
| `unaccent` | CLIENT-10 (per CONTEXT) | ✓ | 1.1, trusted | **Python NFKD normalisation — recommended over the extension** (§5.3) |
| `fuzzystrmatch` | CLIENT-10 layer 3 | ✓ | 1.2, trusted | drop layer 3; accept that Mhamed↔Mohammed rests on `<%` at 0.3 with 4.7 points of headroom |
| `btree_gin` | not needed | ✓ | 1.3 | — |
| PgBouncer | runtime | ✓ | 1.25.2, transaction mode | — |
| Redis | Celery | ✓ | 8 | — |
| Django | — | ✓ | 6.1.1 `[repo: pyproject.toml]` | — |
| `django.contrib.postgres` | the `<%` ORM lookup | ✓ (ships with Django) | — | hand-written `Lookup`; worse |
| Pillow | `ImageField` validation | **✗ not in `pyproject.toml`** | — | use `FileField` + explicit content-type/magic-byte validation, which is what a plain `ImageField` does not give you anyway |

**Missing with no fallback:** none.
**Missing with fallback:** Pillow. `[raisonné]` Recommend **not** adding it: `ImageField` only proves
the bytes are decodable, and the check that matters for an upload endpoint is size, declared type and
magic bytes. Adding an image library to handle untrusted uploads enlarges the attack surface for a
guarantee we do not need.

---

## 9. Validation architecture

### Test framework

| Property | Value |
|---|---|
| Framework | pytest 9.1.1 + pytest-django 4.14.0 + pytest-xdist 3.8.0 `[repo]` |
| Config | `pyproject.toml` `[tool.pytest.ini_options]`, `DJANGO_SETTINGS_MODULE = config.settings.test` |
| Quick run | `.venv/bin/pytest -q -m "not slow"` |
| Full suite | `.venv/bin/pytest` (Compose must be up) |
| Tenant fixtures | `tenant_a`, `tenant_b`, `deux_magasins`, `magasins_du_client_b` in `conftest.py`. **Two tenants, never one.** |
| Frontend | vitest, `web/` |

### Phase requirements → tests

`[raisonné]` Names follow the project convention `test_<req>_<what>`.

| Req | Behaviour | Type | Command | Exists? |
|---|---|---|---|---|
| CLIENT-01 | create + find by name and by phone | integration | `pytest tests/test_clients.py::test_client01_trouve_par_nom_et_par_telephone` | ❌ Wave 0 |
| CLIENT-02 | purchase history on the client page | integration | `…::test_client02_historique_achats_visible` | ❌ Wave 0 (stub until Phase 6) |
| CLIENT-03 | OD/OG structured capture | unit | `tests/test_ordonnances.py::test_client03_od_og_structures` | ❌ Wave 0 |
| CLIENT-04/05 | prescripteur, date, source | unit | `…::test_client04_prescripteur_et_date`, `…::test_client05_source_medicale_ou_opticien` | ❌ Wave 0 |
| CLIENT-06 | new version, earlier ones unchanged | integration | `…::test_client06_nouvelle_version_ne_modifie_jamais_la_precedente` | ❌ Wave 0 |
| CLIENT-06 | **no UPDATE path exists** | guard | `…::test_client06_aucune_route_ne_modifie_une_ordonnance` (grep + viewset introspection) | ❌ Wave 0 |
| CLIENT-07 | axe out of range refused; axe required iff cylindre | unit | `…::test_client07_axe_hors_bornes_refuse` | ❌ Wave 0 |
| CLIENT-07 | positive cylinder refused at storage; transposition offered at entry | unit | `…::test_client07_cylindre_positif_refuse_en_stockage` | ❌ Wave 0 |
| CLIENT-07 | EP mono/bino distinguished, never derived | unit | `…::test_client07_ep_mono_et_bino_distingues` | ❌ Wave 0 |
| CLIENT-07 | transposition round-trips | unit | `…::test_client07_transposition_aller_retour_est_identite` | ❌ Wave 0 |
| CLIENT-09 | photo stored under the bound tenant | integration | `tests/test_ordonnance_photo.py::test_client09_photo_rangee_sous_le_client_lie` | ❌ Wave 0 |
| CLIENT-09 | **tenant B cannot read tenant A's path** | security | `…::test_client09_un_chemin_dun_autre_client_est_refuse` | ❌ Wave 0 — **the whole guarantee (§4.3)** |
| CLIENT-09 | image requires `ordonnance.voir` | security | `…::test_client09_image_exige_le_droit_ordonnance_voir` | ❌ Wave 0 |
| CLIENT-10 | the three named names find one person | integration | `tests/test_recherche_clients.py::test_client10_mohamed_mohammed_mhamed_trouvent_la_meme_personne` | ❌ Wave 0 — **already named in `provisioner.py`'s docstring `[repo]`** |
| CLIENT-10 | search uses the index, not a seq scan | performance | `…::test_client10_la_recherche_utilise_lindex_gin` (EXPLAIN assertion) | ❌ Wave 0 |
| CLIENT-10 | Fatima and Fatiha are **not** merged | integration | `…::test_client10_deux_prenoms_distincts_ne_fusionnent_pas` | ❌ Wave 0 |
| CLIENT-10 | an Arabic-script name does not match every other one | security | `…::test_client10_cle_phonetique_vide_ne_rapproche_rien` | ❌ Wave 0 (§5.5) |
| — | **no bare `SET pg_trgm.` anywhere** | guard | grep over `plateforme/` and `domaine/` (§2.4) | ❌ Wave 0 |
| — | extension present on **both** tenant aliases after migrate | integration | `tests/test_extensions.py::test_extensions_presentes_sur_chaque_base_client` | ❌ Wave 0 |
| — | every new model field is classified | conformity | `tests/test_projection.py::test_perm06_tout_champ_de_modele_expose_est_classe` | ✅ exists — will go **red** until §3.5 is done |

### Sampling rate

- Per task commit: `pytest -q -m "not slow" tests/test_ordonnances.py tests/test_recherche_clients.py`
- Per wave merge: `pytest -q -m "not slow"` + `cd web && npm test`
- Phase gate: full suite, `spectacular --fail-on-warn`, `migrate_all --check` exits 0, `npm run build`

### Wave 0 gaps

- [ ] `tests/test_clients.py`, `tests/test_ordonnances.py`, `tests/test_recherche_clients.py`,
      `tests/test_ordonnance_photo.py`, `tests/test_extensions.py` — all new
- [ ] `tests/factories.py` — `ClientFactory`, `OrdonnanceFactory`; the latter must be able to produce
      a **deliberately invalid** instance so the validation tests have something to reject
- [ ] A seeded corpus of Moroccan names for the CLIENT-10 tests. Use the 30 first names × 20 surnames
      in this research's probe; the measured numbers in §5 are reproducible against it
- [ ] No framework installation needed

---

## 10. Security domain

### Applicable ASVS categories

| Category | Applies | Control |
|---|---|---|
| V2 Authentication | no (Phase 3) | session auth, unchanged |
| V3 Session management | no (Phase 3) | unchanged |
| V4 Access control | **yes — the phase's main risk** | `ordonnance.voir` / `ordonnance.saisir` via `MagasinScopedViewSet` (inherited **first**, MRO-checked) and the projection registre. The IDOR shape named in `vues.py` — filtering in `list()` instead of `get_queryset()` — applies directly to `/ordonnances/42/` |
| V5 Input validation | **yes** | DRF serializers + model `CheckConstraint`. Ranges belong in **both**: a `clean()` is bypassed by `bulk_create`, exactly as `control_plane/models.py` already argues for `active_client_has_db_name` |
| V6 Cryptography | no new use | the photo's encryption at rest is a property of the production backend — Phase 1 |
| V12 File upload | **yes — new to this project** | size cap, allow-list of content types, magic-byte check, filename never taken from the client, tenant prefix re-derived (§4.2) |
| V13 API | yes | `@extend_schema` on every new view, schema + TS client regenerated in the same commit |

### Threat patterns for this phase

| Pattern | STRIDE | Mitigation |
|---|---|---|
| Cross-client file read via a stored path | Information disclosure | prefix re-derived from `current_alias()`, never from the row (§4.2); named test |
| IDOR on `/ordonnances/<id>/` | Elevation | filter in `get_queryset()`; `MagasinScopedViewSet` first in the MRO; the existing MRO check covers it |
| Health data in a Sentry event | Information disclosure | `telemetry.SENSITIVE_KEY` already covers the clinical fields — **extend it to `photo`/`image`/`fichier`/`scan`/`upload`** (§4.6) |
| Session GUC leaking across tenants via PgBouncer | Information disclosure / Tampering | never a bare `SET`; role default or `SET LOCAL` (§2.4); grep guard |
| Empty phonetic key matching every Arabic-script name | Information disclosure | `key <> ''` on both sides (§5.5) |
| False positive at the counter opening a neighbour's ordonnances | Information disclosure | ranked candidate list, never auto-select (§5.2) |
| Upload used as a storage-exhaustion vector | DoS | size cap + per-ordonnance count cap |
| SQL injection through the search term | Tampering | ORM lookups only; if raw SQL is needed for the ranking, bound parameters — the `psycopg.sql` discipline in `provisioner.py` is the house style |

---

## 11. What I could NOT verify, and why

Listed so the planner knows exactly where it is standing on reasoning rather than evidence.

| # | Claim | Why unverified | Risk if wrong |
|---|---|---|---|
| 1 | **Sphère range** (±20 or ±30) | No normative standard found for prescribable sphere range. Both numbers in this repository are judgement. | Low — a wrong bound rejects a rare real prescription, which is visible and fixable. But the two documents must be reconciled or a validator and a test will disagree. |
| 2 | **0.25-dioptre step** universally | Corroborated by every consumer-facing source; no standards document read. | Low |
| 3 | **Under-16 medical-ordonnance rule** in Morocco | `PITFALLS.md` itself sources it to "secondary sources"; I did not reach the dahir. | Medium *if built as a refusal*. Build it as a warning, or not at all in Phase 4. The `date_naissance` column is justified by RAPPEL-04 independently. |
| 4 | **Non-owner app role in production** | The hosting provider is not chosen (Phase 1 / `02-RESEARCH.md` OQ2). §2.1 proves the *owner* case only. | High if it happens — the extension migration would fail on every client at once. Mitigation: `migrate_all` already reports per-client failure, so it fails loudly, not silently. |
| 5 | **Metaphone behaviour on a real Moroccan client list** | Measured on a 30-name synthetic corpus of my own construction. Representative-looking, not sampled from real data. | Medium — the collision groups could be worse on real names. The mitigation is structural, not statistical: metaphone is one recall source in a ranked list, never a filter. |
| 6 | **The `<%` threshold of 0.3** has 4.7 points of headroom | `word_similarity('mhamed','mohammed') = 0.333` versus `('mhamed','ahmed') = 0.286`. Measured, but on the same synthetic corpus. | Medium — a real corpus could put a false positive inside that gap. This is precisely why §5.2 says rank, do not filter. |
| 7 | **Whether the ordonnance should be magasin-scoped** | A product decision, not a technical one. Raised as an open question in §3.3. | High if guessed wrong — a gérant who cannot see an ordonnance from another magasin records a duplicate, and duplicate prescriptions for one patient is a clinical problem. Put it to the owner. |
| 8 | **Whether TENANT-09's backup covers the file store** | Read `backup.py`'s existence; did not read its artifact composition end to end. | Medium — an uncovered photo store quietly falsifies a Phase 2 guarantee. Cheap to check during planning. |
| 9 | **Pillow / image validation library choice** | Recommended against adding one; did not evaluate alternatives (`python-magic`, `filetype`). | Low |
| 10 | **CNDP position on storing an ordonnance photograph** specifically | Out of scope for this phase; `.planning/research/CNDP.md` holds the open questions and they need a lawyer. | High at deployment, zero while building. The CONTEXT already states this correctly. |

---

## 12. Sources

### Primary — measured in this session (HIGHEST confidence)

- Live Compose stack: `optique-db-1` PostgreSQL 18.6, `optique-pgbouncer-1` 1.25.2 transaction mode.
  `CREATE EXTENSION` privilege probe, trigram/metaphone/soundex measurements over a 20 400-row corpus,
  `EXPLAIN (ANALYZE)` plans, function volatility, expression-index and generated-column failures,
  PgBouncer session-GUC leak, `ALTER ROLE … SET` role default.
- Installed source under `.venv/lib/python3.13/site-packages/django/` (6.1.1):
  `contrib/postgres/operations.py`, `contrib/postgres/apps.py`, `contrib/postgres/signals.py`,
  `db/models/fields/files.py`, `core/files/utils.py`, `core/files/storage/base.py`.

### Primary — this repository

`plateforme/tenancy/{router,context,middleware,provisioner,registry}.py`,
`plateforme/control_plane/{provisioning,seeding,models,storage,backup}.py`,
`plateforme/control_plane/management/commands/migrate_all.py`,
`plateforme/projection/{registre,vues,filtres}.py`, `plateforme/comptes/permissions_catalogue.py`,
`domaine/{magasins,stock,caisse}/models.py`, `config/settings/{base,test}.py`, `conftest.py`,
`docker-compose.yml`, `docker/pgbouncer/pgbouncer.ini`, `docker/postgres/init/00-databases.sql`,
`.planning/research/{PITFALLS,ARCHITECTURE}.md`, `.planning/{ROADMAP,REQUIREMENTS}.md`, `CLAUDE.md`.

### Secondary — external, cited

- Cylinder convention and transposition (France):
  [atol.fr](https://www.atol.fr/conseils/ordonnance-lunettes-prescription) ·
  [cof.fr](https://www.cof.fr/les-conseils-de-votre-ophtalmo/comment-lire-votre-ordonnance-de-lunettes) ·
  [optique-sergent.com](https://www.optique-sergent.com/conseils/lire-une-ordonnance.html) ·
  [jl-optique.fr](https://jl-optique.fr/sante-visuelle/conversion-ordonnance-ophtalmo-opticien/) ·
  [thomassinclairlabs.com](https://www.thomassinclairlabs.com/vue/transposition.html)
- Cylinder convention and transposition (**Morocco**):
  [lopticomaroc.com](https://lopticomaroc.com/transposition/)
- Axis / TABO 1–180: [gatinel.com](https://www.gatinel.com/recherche-formation/astigmatisme/astigmatisme-et-erreur-daxe/) ·
  [opticonex.fr](https://opticonex.fr/schema-tabo-axes) ·
  [orthoptiste.relais-vision.fr](https://orthoptiste.relais-vision.fr/schema-tabo)
- Addition range and both-eyes equality:
  [visiondirect.fr](https://www.visiondirect.fr/info/comprendre-votre-ordonnance) ·
  [visio-net.fr](https://www.visio-net.fr/services/choisir-ses-lunettes/guide-verre-progressif-comprendre-ordonnance) ·
  [cahiers-ophtalmologie.fr](https://www.cahiers-ophtalmologie.fr/media/e39208994c029c378ecbb0a2f1c54c9e.pdf)
- Écart pupillaire monoculaire vs binoculaire:
  [conseil-optique.com](https://www.conseil-optique.com/conseil-optique/les-ecarts-pupillaires/) ·
  [krys.com](https://www.krys.com/sante/la-vision/controler-sa-vue/qu-est-ce-que-la-distance-pupillaire-) ·
  [orbitech-ai-academy.fr](https://orbitech-ai-academy.fr/blog/superieur/centrage-et-montage-des-verres-precision-opticienne)

---

## 13. Metadata

| Area | Confidence | Reason |
|---|---|---|
| Extension privilege and placement | **HIGH** | Run against the live stack as the real client role; the early-return in `provision_client` is read from the repo |
| PgBouncer GUC leak | **HIGH** | Reproduced end to end, including the `SET LOCAL` control |
| Search measurements | **HIGH** on the numbers, **MEDIUM** on generalisation | Real `similarity()` / `word_similarity()` / `metaphone()` on a synthetic but plausible corpus |
| `unaccent` non-indexability | **HIGH** | Two failure modes reproduced with their SQLSTATEs |
| `FileField` storage semantics | **HIGH** | Read from the installed source |
| Ordonnance model shape | **MEDIUM** | Reasoned from the existing patterns and requirements; one product question (magasin scope) is open |
| Cylinder convention and transposition | **MEDIUM-HIGH** | Multiple French sources plus one Moroccan source agreeing, with a worked example |
| Numeric clinical bounds | **LOW** | No normative source found for any of them; the project already contradicts itself |

**Researched:** 2026-09-18
**Valid until:** ~2026-10-18 for the package and PostgreSQL findings (pinned versions, so stable).
The clinical section does not expire; the hosting-dependent parts expire when Phase 1 decides.
</content>
</invoke>

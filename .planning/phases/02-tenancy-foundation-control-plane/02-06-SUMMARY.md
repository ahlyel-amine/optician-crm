---
phase: 02-tenancy-foundation-control-plane
plan: 06
subsystem: magasin-scoping
tags: [tenancy, TENANT-07, magasins, stock, caisse, append-only-ledger, decimal]
requires:
  - 02-02 (Magasin, MagasinScopedModel, MagasinScopedQuerySet)
  - 02-03 (router, BUSINESS_APPS, tenancy.E001)
  - 02-04 (provision_client, seed_new_client, the --magasin argument)
provides:
  - domaine/stock/models.py — MouvementStock
  - domaine/caisse/models.py — EcritureCaisse
  - BUSINESS_APPS extended to {magasins, stock, caisse}
affects:
  - Phase 3 (supplies the magasin list to for_magasins; there is no implicit filter)
  - Phase 5 (extends MouvementStock — article, fournisseur, achat)
  - Phase 6 (facture série; CLAUDE.md open question #2 is deliberately not pre-empted)
  - Phase 7 (extends EcritureCaisse — session, mode de règlement, chèque lifecycle)
tech-stack:
  added: []
  patterns:
    - append-only ledgers with derived balances, asserted by field-name introspection
    - composite indexes leading with magasin
    - explicit queryset projection, never an implicit default-manager filter
    - a system check that makes forgetting to classify an app impossible
key-files:
  created:
    - domaine/stock/apps.py
    - domaine/stock/models.py
    - domaine/stock/migrations/0001_initial.py
    - domaine/caisse/apps.py
    - domaine/caisse/models.py
    - domaine/caisse/migrations/0001_initial.py
  modified:
    - plateforme/tenancy/router.py
    - config/settings/base.py
    - tests/test_magasin_scoping.py
decisions:
  - "effet_sur_solde lands in the Phase 2 core, because CLAUDE.md #5 cannot be retrofitted"
  - "montant is always positive; direction is `sens`, so a sign error is not a refund"
  - "quantite_delta is a signed delta, never a running total"
  - "no implicit magasin filter and no magasin contextvar — the asymmetry with client scoping is the design"
metrics:
  tasks: 2
  commits: 2
  tests-added: 11
  completed: 2026-09-13
---

# Phase 2 Plan 06: Multi-Magasin & Scoped Ledgers Summary

TENANT-07 in both halves: `--magasin` repeated on the operator command seeds every
requested magasin and a client with none is refused, and the stock and caisse ledgers are
scoped to a magasin by an **explicit** queryset projection inside that client's database.

The design decision that matters is an asymmetry, and it is deliberate: **a client is a
connection and fails closed; a magasin is a column and is explicit.**

## The Phase 2 core, which Phases 5 and 7 extend rather than replace

These are real models, not placeholders and not test fixtures. They carry only what
TENANT-07 needs; article references, fournisseur links, sessions de caisse and the chèque
lifecycle belong to phases that have their own requirements and their own open questions.

### `domaine/stock/models.py` — `MouvementStock(MagasinScopedModel)`

| Field | Type | Note |
|---|---|---|
| `magasin` | FK PROTECT | inherited, never overridden |
| `reference_article` | `CharField(64, db_index)` | Phase 5 replaces with a real FK |
| `type_mouvement` | `CharField(16, choices)` | `entree` / `sortie` / `ajustement` / `inventaire` |
| `quantite_delta` | `IntegerField` | **signed delta, never a running total** |
| `motif` | `CharField(200, blank)` | |
| `created_at` | `DateTimeField(auto_now_add, db_index)` | |

`Meta`: `Index(["magasin", "reference_article", "created_at"])`,
`CheckConstraint(~Q(quantite_delta=0))`.

Quantity on hand is **derived** by summing `quantite_delta` for an article in a magasin.

### `domaine/caisse/models.py` — `EcritureCaisse(MagasinScopedModel)`

| Field | Type | Note |
|---|---|---|
| `magasin` | FK PROTECT | inherited |
| `sens` | `CharField(8, choices)` | `entree` / `sortie` |
| `montant` | `DecimalField(12, 2)` | **always positive**; MAD; never float |
| `libelle` | `CharField(200)` | |
| `effet_sur_solde` | `BooleanField(default=True)` | see below |
| `created_at` | `DateTimeField(auto_now_add, db_index)` | |

`Meta`: `Index(["magasin", "created_at"])`, `CheckConstraint(Q(montant__gt=0))`.

**`montant` is positive and direction is `sens`.** A signed amount would make "is this a
refund or a sign error?" unanswerable, and a sign error would pass the constraint.

**`effet_sur_solde` is in the Phase 2 core rather than Phase 7 on purpose.** CLAUDE.md
non-negotiable #5 — *a chèque is not cash until `encaissé`* — cannot be retrofitted onto a
ledger whose rows are assumed to move the balance on their creation date. Post-dated
chèques are normal in Morocco. Phase 7 adds the échéance, the encaissement date and the
lifecycle that flips the flag; the flag itself has to exist first.

## The magasin code derivation rule

`plateforme/control_plane/seeding.py`, `_magasin_specs`:

1. A dict entry may carry an explicit `code`; it is upper-cased and used as given.
2. Otherwise `slugify(nom).upper()` with hyphens removed, truncated to 20 characters
   (the column width), falling back to `"MAG"` if nothing survives.
3. A collision is resolved with a numeric suffix: `base[:18] + "2"`, then `3`, …

`"Centre Ville"` → `CENTREVILLE`; a later `"Centre-Ville"` → `CENTREVILLE2`.

**Determinism is the mechanism idempotency rests on**, which is why it has its own test
rather than being inferred from the idempotency test: the same input list must always
produce the same codes, or a rerun after a kill inserts a second set of magasins instead
of matching with `get_or_create` (threat T-02-42).

`code` is unique **inside the client's database**, deliberately — two different opticians
may each have a magasin called `CENTRE`, and a globally unique code would make the second
one unprovisionable.

## Final `BUSINESS_APPS` membership

```python
BUSINESS_APPS = frozenset({"magasins", "stock", "caisse"})
```

Both labels were added in the **same commit** as `INSTALLED_APPS`. The `tenancy.E001`
system check makes forgetting impossible rather than merely unlikely (Pitfall 12), and
`test_tenant04_new_business_apps_are_classified` carries a **negative control**: it removes
`caisse` from the set and asserts `manage.py check` then fails with `tenancy.E001`. Without
that, "no E001" is evidence of nothing.

Phases 6 (`facturation`) and 8 (`branding`) extend this set the same way.

The backstop strengthened automatically, as designed: it derives the table list from
`BUSINESS_APPS` rather than hardcoding it, so
`test_tenant04_business_models_never_migrate_to_default` now asserts the absence of
**three** tables from the control-plane database instead of one —
`magasins_magasin`, `stock_mouvementstock`, `caisse_ecriturecaisse`.

## For the Phase 3 planner: there is no implicit magasin filter, and that is the design

Phase 2 supplies `for_magasin(m)` and `for_magasins([...])`. **Phase 3 supplies the list.**

```python
MouvementStock.objects.for_magasins(request.user.magasins_autorises)
```

Do not add a magasin contextvar, and do not make the default manager filter. The asymmetry
with client scoping is deliberate:

| | Client | Magasin |
|---|---|---|
| Isolation boundary | the database connection | a column |
| Legitimate cross-scope reads | **never** | **constantly** — the owner's dashboard, réappro across magasins |
| Right default | fail closed | explicit |

An implicit filter would silently return **partial data to the owner's dashboard**: a wrong
number with no error, which is worse than a crash. And CLAUDE.md open question #2 — *is a
facture série per magasin legal, or is one continuous série per company required?* — is
unresolved, so the model must not assume either answer.

`test_tenant07_stock_and_caisse_are_scoped_per_magasin` asserts **both** halves for this
reason: `for_magasin(centre)` returns exactly one row, *and* the plain manager still
returns both. A filter-only assertion would pass against an implicit filter.

## Deviations from Plan

### 1. Task 2 required no production change

`seed_new_client`, written in plan 02-04, already refused an empty magasin list, derived
codes deterministically, accepted dicts with an explicit code and used `get_or_create`
exclusively; `provision_client` the command already required `--magasin`; `Magasin.__str__`
already returned `f"{self.code} — {self.nom}"`. Task 2 is therefore the six tests that pin
those properties, plus the end-to-end verification. Every acceptance criterion was still
run.

### 2. One acceptance criterion is not met as literally written

`grep -nE "(solde|montant_paye|quantite_stock)" domaine/stock/models.py
domaine/caisse/models.py` is required to return nothing. It returns three lines, and it
cannot do otherwise: the plan's own `<action>` block specifies a field named
**`effet_sur_solde`**, and the docstring explaining that there is deliberately no `solde`
column matches too.

The criterion's intent — no mutable running-total column — holds and is checked two ways:

- `grep -nE "^\s+(solde|montant_paye|quantite_stock|quantite|total|balance)\s*=" domaine/*/models.py`
  returns nothing (no such field assignment exists);
- `test_tenant07_ledgers_have_no_mutable_balance_column` introspects both models' field
  names against a ten-name forbidden list, so it also covers names the grep never
  anticipated and turns red when someone adds one in Phase 5 or 7.

## Verification

| Check | Result |
|---|---|
| `uv run pytest tests/test_magasin_scoping.py -q --create-db` | **0** — 12 passed (criterion: ≥6), 0 pending |
| `uv run pytest tests/test_provisioning.py -q --create-db` | **0** — 10 passed, incl. `test_tenant06_command_module_contains_no_provisioning_logic` |
| `uv run pytest -q -m "not slow and not pending"` | **0** — 68 passed, 1.26s |
| `manage.py check --settings=config.settings.test` | **0** — no `tenancy.E001` |
| `manage.py makemigrations --check --dry-run --settings=config.settings.test` | **0** |
| `test_tenant04_business_models_never_migrate_to_default` | **0** — now covers 3 tables |
| `grep -n '"stock"' / '"caisse"' router.py` | both in `BUSINESS_APPS` |
| `grep -rn "FloatField" domaine/` | no match |
| `grep -n "DecimalField" domaine/caisse/models.py` | `max_digits=12, decimal_places=2` |
| `grep -n 'fields=\["magasin"' domaine/*/models.py` | one index line per file |
| `grep -n "on_delete" domaine/stock/models.py domaine/caisse/models.py` | no match — PROTECT is inherited |
| `grep -cE "\.create\(" plateforme/control_plane/seeding.py` | **0** |
| `grep -n "ValueError" plateforme/control_plane/seeding.py` | `class SeedError(ValueError)` |
| `grep -n "mark.pending" tests/test_magasin_scoping.py` | no match |

### End to end from a real shell, against Compose

| Step | Exit | Result |
|---|---|---|
| `provision_client --code MULTI01 ... --magasin Centre --magasin Maarif --magasin Gueliz` | **0** | ACTIVE |
| count magasins inside MULTI01's tenant context | — | **3** — `CENTRE`, `GUELIZ`, `MAARIF` |
| `provision_client --code NOMAG --raison-sociale X` (no `--magasin`) | **1** | message names the rule; **no `Client` row created at all** |
| `deprovision_client --code MULTI01 --yes-i-am-sure` | **0** | `pg_database` restored |

## Known Stubs

| Stub | File | Reason |
|---|---|---|
| 2 tests fail with `pytest.fail("pending: ...")` | `tests/test_backup_restore.py` | Owned by plan 02-07 |
| `reference_article` is a `CharField`, not an FK | `domaine/stock/models.py` | Phase 5 owns the article catalogue. Documented in the module docstring as the Phase 2 core |
| The TVA / facture-série seed | `plateforme/control_plane/seeding.py` | Marked extension point, blocked on CLAUDE.md open questions #1 and #2 — guessing the série shape is the client's tax exposure |

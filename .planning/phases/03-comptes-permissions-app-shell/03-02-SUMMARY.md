---
phase: 03-comptes-permissions-app-shell
plan: 02
subsystem: test-scaffold
tags: [tests, pending, factories, fixtures, PERM-01, PERM-02, PERM-03, PERM-04, PERM-05, PERM-06, APP-01, APP-03]
requires:
  - 03-01 (comptes.Utilisateur as AUTH_USER_MODEL, the pending marker, formats_mad.json)
  - 02-03 (conftest TENANT_DBS, tenant_a / tenant_b, the collection-time django_db marker)
provides:
  - 38 collected pending tests — one named function per name in 03-VALIDATION.md, plus the two CLAUDE.md #13 additions
  - UtilisateurFactory / ProprietaireFactory / GerantFactory, all pinned to the control plane
  - deux_magasins and magasins_du_client_b — two magasins per tenant, as there are already two tenants
  - the parametrized PERM-06 conformance scaffold, registry x renderers, with a collection-safe fallback
affects:
  - 03-04 (removes the markers on the four storage-shape tests; adds AccesMagasinFactory / DroitAccordeFactory here)
  - 03-05 (Acces resolution — four tests)
  - 03-06 (registry and its four consumers — nine tests)
  - 03-07 (magasin scope and aggregates — four tests)
  - 03-08 (session auth — five tests)
  - 03-09 (write surface — four tests)
  - 03-10 (locale, formatter, committed schema — six tests)
tech-stack:
  added: []
  patterns:
    - a named test exists before its implementation, marked pending, so every later plan starts from a named red
    - every import of code under construction lives inside the function, never at module scope
    - a parametrization over a registry that does not exist yet needs a constant fallback, or collection breaks
    - a fallback case is also what stops a parametrized-over-nothing test from being green and worthless
key-files:
  created:
    - tests/test_comptes_auth.py
    - tests/test_comptes_droits.py
    - tests/test_magasin_acces.py
    - tests/test_locale.py
    - tests/test_projection.py
    - tests/test_schema_contrat.py
  modified:
    - tests/factories.py
    - conftest.py
decisions:
  - AccesMagasinFactory and DroitAccordeFactory deferred to 03-04, as the plan's own task text resolves — a factory cannot defer Meta.model, so writing one before its model breaks collection
  - both tenants get the same magasin codes (ANFA / MAARIF) on purpose, so resolving a magasin by code outside the tenant connection is visible
  - the twelfth PERM-06 name is not duplicated here; it is already green in tests/test_comptes_socle.py
metrics:
  tasks: 3
  commits: 3
  tests-added: 38 (all pending)
  suite: 114 passed, 38 deselected (114 passed, 0 deselected before)
  duration: ~35 min
  completed: 2026-09-14
---

# Phase 3 Plan 02: Test Scaffold Summary

Thirty-eight named pending tests now stand where the phase's eight requirements will be
implemented, so no later plan starts from a blank page — each starts from a named red with
a docstring saying what its red would prove. The quick loop is untouched at 84 passed and
the full non-pending suite is unchanged at **114 passed**, which is the point: this plan
adds proof obligations, not behaviour.

## What each later plan owes, by name

| Plan | Tests it turns green | File |
|---|---|---|
| **03-04** | `test_perm03_un_droit_est_une_ligne_pas_un_palier` · `..._un_droit_est_stocke_par_gerant_magasin_et_permission` · `..._le_journal_enregistre_qui_a_accorde_quoi_et_quand` · `test_perm05_le_catalogue_declare_prix_achat_marge_et_ca_global` | `test_comptes_droits.py`, `test_magasin_acces.py` |
| **03-05** | `test_perm03_un_droit_accorde_dans_un_magasin_ne_fuit_pas_vers_un_autre` · `..._la_revocation_prend_effet_sans_reconnexion` · `test_perm04_un_droit_obsolete_sur_un_magasin_inactif_n_accorde_rien` · `..._lacces_du_proprietaire_est_lensemble_complet_et_non_un_filtre_saute` | `test_comptes_droits.py`, `test_magasin_acces.py` |
| **03-06** | `test_perm06_champ_protege_absent_de_lapi_de_lexport_et_du_document` (×3 renderers) · `..._tout_champ_de_modele_expose_est_classe` · `..._le_schema_est_identique_pour_le_proprietaire_et_le_gerant` · `..._un_champ_protege_est_optionnel_dans_le_schema` · `..._un_champ_protege_ne_peut_pas_etre_ecrit_par_un_gerant` · `..._aucune_vue_ne_renvoie_un_values_queryset` · `..._le_renderer_html_est_absent_hors_developpement` · `..._toute_tache_de_rendu_exige_acting_utilisateur_id` · `..._lacces_absent_vaut_aucun_droit` | `test_projection.py` |
| **03-07** | `test_perm04_un_gerant_ne_voit_que_les_magasins_accordes_en_liste_et_en_detail` · `..._ne_peut_pas_ecrire_dans_un_magasin_non_accorde` · `test_perm05_un_agregat_est_calcule_sur_le_queryset_deja_filtre` · `test_perm06_un_champ_protege_ne_peut_ni_trier_ni_filtrer` | `test_magasin_acces.py`, `test_projection.py` |
| **03-08** | the five `test_perm01_*` | `test_comptes_auth.py` |
| **03-09** | `test_perm02_un_proprietaire_ne_cree_un_compte_que_dans_son_propre_client` · `..._un_compte_desactive_est_refuse_des_la_requete_suivante` · `test_perm03_un_proprietaire_ne_peut_pas_accorder_a_un_utilisateur_dun_autre_client` · `test_perm06_le_catalogue_servi_a_un_gerant_manager_est_deja_intersecte` | `test_comptes_droits.py`, `test_projection.py` |
| **03-10** | the five `test_app01_*` / `test_app03_*` · `test_perm06_le_schema_committe_correspond_au_schema_genere` | `test_locale.py`, `test_schema_contrat.py` |

Each plan removes **only its own** markers, and removing one must produce a red before the
code goes in. That is the only thing that distinguishes these from tests written to pass.

## The two names that are not in `03-VALIDATION.md`

`test_perm03_un_droit_est_stocke_par_gerant_magasin_et_permission` and
`test_perm03_un_droit_accorde_dans_un_magasin_ne_fuit_pas_vers_un_autre` were added
because CLAUDE.md **#13** requires them and the validation table omitted them —
`03-RESEARCH.md` §4 designs `DroitAccorde(utilisateur, code)`, with no magasin dimension,
and its own correction banner plus `03-UI-SPEC.md` 0.1 say that shape is superseded.
Without these two, a model matching the research would pass the entire phase and the fix
would be a data migration on live permission grants.

They are deliberately a pair. The first asserts the **constraint** is
`(utilisateur, magasin_code, code)`; the second asserts the **behaviour**, because a
three-column constraint sitting above an `acces.peut(code)` that ignores the magasin stores
a distinction the code does not make — and the database looks right while the gérant who
may discount at Anfa may discount at Maârif.

## Why the load-bearing test is already parametrized, and why it has a fallback

```python
@pytest.mark.parametrize("rendu", RENDUS)
@pytest.mark.parametrize("cle,code", champs_proteges_parametres())
def test_perm06_champ_protege_absent_de_lapi_de_lexport_et_du_document(...):
```

Two separate problems are solved here, and both would be easy to get wrong:

1. **Collection.** `parametrize` arguments are evaluated when the module is imported, so
   `from plateforme.projection.registre import CHAMPS_PROTEGES` at module scope would turn
   the registry's absence into a collection error for the *whole suite* — every unrelated
   test red for the wrong reason, and the quick loop unusable for waves 3 through 14. The
   import lives inside `champs_proteges_parametres()`, guarded by `except ImportError`.
2. **Meaning.** `CHAMPS_PROTEGES` is deliberately empty in phase 3 — `prix_achat`, `marge`
   and business-wide revenue do not exist as columns until phases 8 and 10. A test
   parametrized over zero cases collects zero tests and is *green*. The constant fallback
   `("tests.RessourceFixture.valeur_protegee", "article.voir_prix_achat")` is what keeps
   the phase's most important test from being green and worthless; plan 03-06 creates the
   fixture resource it names.

The function body imports **without** a guard, so the day 03-06 removes the marker the test
goes frankly red rather than quietly passing over a fallback.

## Why the fixtures now provide two magasins

Same argument as `tenant_b`, one level down (`03-RESEARCH.md` P16). With a single magasin,
a view that ignores scope entirely returns exactly what a correct view returns — the right
answer and the wrong answer are the same object, and every assertion passes over the bug.

`deux_magasins` (client A) and `magasins_du_client_b` (client B) create **the same two
codes**, `ANFA` and `MAARIF`, in both tenants on purpose. Two Moroccan opticians may
genuinely both have an "Anfa" branch, so a lookup that resolves a magasin by code without
going through the tenant connection would serve the other business's rows — and distinct
per-tenant codes would hide that behind a collision that never happens in test.

Both were exercised end to end against Compose before the commit (scratch test, since
removed): the factories write to `default`, the password is a real `argon2` hash that
`check_password` accepts, and both tenants hold their own `ANFA` / `MAARIF`.

## Acceptance criteria, as run

### Task 1

| Criterion | Result |
|---|---|
| `grep -cE 'class (ProprietaireFactory\|GerantFactory\|UtilisateurFactory)' tests/factories.py` | **3** |
| `grep -c 'database = "default"' tests/factories.py` | **5** (≥ 2) |
| `grep -c 'set_password' tests/factories.py` | **2** (≥ 1) |
| `grep -c 'def deux_magasins' conftest.py` | **1** |
| `grep -c 'django_db_setup\|django_db_modify_db_settings' conftest.py` | **1** — see deviation 1 |
| `uv run pytest -x -q -m "not slow and not pending"` | **84 passed**, unchanged |

### Task 2

| Criterion | Result |
|---|---|
| distinct `def test_*` across the four files | **24** |
| each of the 24 names appears exactly once | verified by loop over the name list — no misses, no duplicates |
| `pytest --collect-only -q` on the four files | exit **0**, 24 collected, no collection error |
| `pytest -q -m pending tests/ --collect-only` | **24** at that point (≥ 24) |
| `uv run pytest -x -q -m "not slow and not pending"` | **84 passed**, 54 deselected |
| `grep -c '^from plateforme.comptes' tests/test_comptes_droits.py` | **0** |

### Task 3

| Criterion | Result |
|---|---|
| `grep -c 'def test_perm06_' tests/test_projection.py` | **11** |
| `grep -c 'parametrize' tests/test_projection.py` | **3** (≥ 2 — the load-bearing test is doubly parametrized) |
| `grep -c 'def test_perm06_le_schema_committe_correspond_au_schema_genere' tests/test_schema_contrat.py` | **1** |
| `pytest --collect-only -q tests/test_projection.py tests/test_schema_contrat.py` | exit **0**, 14 collected |
| `uv run pytest -x -q -m "not slow and not pending"` | **84 passed**, 68 deselected |
| `grep -c '^from plateforme.projection' tests/test_projection.py` | **0** |

### Plan-level verification

| Check | Result |
|---|---|
| `uv run pytest --collect-only -q tests/` | exit **0**, **152 collected**, no collection error |
| distinct collected `test_perm0*` / `test_app0*` names | **43**, against ~36 named in `03-VALIDATION.md` |
| `grep -rn 'django_db_setup' conftest.py tests/` | no result (exit 1) |
| `uv run pytest -q -m "not pending"` | **114 passed, 38 deselected** |

## Deviations from Plan

### 1. One acceptance criterion is unsatisfiable as literally written, and correctly so

`grep -c 'django_db_setup\|django_db_modify_db_settings' conftest.py` is specified to
return 0. It returns **1**, and it returned 1 before this plan ran. The single match is
line 9 of the file's own module docstring:

```
`django_db_modify_db_settings_xdist_suffix` runs *first*, so aliases introduced inside an
```

That is the prose explaining **why overriding those fixtures is forbidden** — the
`interfaces` section of this plan points at that exact docstring. Deleting the sentence to
satisfy a grep would remove the warning the criterion exists to protect.

The criterion's intent was verified instead, two ways, both exact:

| Check | Result |
|---|---|
| `grep -c 'django_db_setup' conftest.py` | **0** |
| `grep -cE '^\s*def (django_db_setup\|django_db_modify_db_settings)' conftest.py` | **0** |
| the plan's own `<verification>` form, `grep -rn 'django_db_setup' conftest.py tests/` | no result |

No pytest-django fixture is overridden, and `pytest_sessionstart` /
`pytest_collection_modifyitems` were not touched. **Raised rather than relaxed** — the
criterion should be reworded to the `^\s*def` form in any future plan that reuses it.

### 2. [plan-directed] The two grant factories are not in this plan

`must_haves.artifacts` lists `DroitAccordeFactory` and `AccesMagasinFactory` as provided by
`tests/factories.py`, but Task 1's action text resolves the tension itself
(*« Choix retenu : les déclarer au plan 03-04 »*) and the acceptance criteria count only
three classes. The technical reason is real and worth recording: `Meta.model` is read when
the factory *class* is created, so a factory written before its model raises at import and
breaks collection for the whole suite — the exact failure mode threat T-03-08 describes and
that every other file in this plan avoids. A named comment sits at the bottom of
`tests/factories.py` saying where they land and that they too write to `default`.
Plan 03-04's own file list already includes `tests/factories.py`.

### 3. The twelfth PERM-06 name is not duplicated

`test_perm06_aucun_modele_metier_n_est_enregistre_dans_ladmin` is already implemented, green
and carrying a positive control in `tests/test_comptes_socle.py` since plan 03-01. Writing a
pending stub of the same name would put two functions with one name in the suite, one of
them maintained. The plan directs this explicitly; recorded because `grep -c 'def
test_perm06_' tests/test_projection.py` returns 11 rather than 12 as a result.

### 4. `requirements mark-complete` was deliberately **not** run

The plan's frontmatter lists all eight requirements, and its objective states why in the
same breath: *« Ce plan n'implémente aucune exigence ; il en écrit les tests nommés. […]
La propriété d'implémentation appartient aux plans 03-04 à 03-14. »* Every one of the
eight checkboxes in `.planning/REQUIREMENTS.md` reads as a working feature
(*"An optician (owner) can sign in and stays signed in across sessions"*), not as a test
that exists.

Ticking them here would assert that eight requirements are done while every test proving
them fails on `pytest.fail("non implémenté")` — which is threat **T-03-07** verbatim, the
very repudiation this plan exists to close. `REQUIREMENTS.md` is therefore untouched. Each
of 03-04 through 03-14 marks its own requirement when the last of its named tests goes
green.

## Notes for later plans

- **Remove your own markers, and confirm the red first.** A `pending` left behind after
  implementation is a test that exists, never runs, and fools the phase gate (threat
  T-03-10). Plan 03-10 checks the count is zero for every requirement declared done.
- `uv run pytest -q -m pending tests/ --collect-only | tail -1` is the running count: **38**
  today. It must only ever go down.
- The stubs that take `db_all` or `deux_magasins` already receive the collection-time
  `django_db(databases=TENANT_DBS)` marker, because `deux_magasins` pulls `tenant_a` into
  the fixture closure and `conftest.pytest_collection_modifyitems` matches on that.
- `MOT_DE_PASSE_DE_TEST` in `tests/factories.py` is the shared login literal; 03-08's
  session tests should import it rather than retype it.
- `magasins_du_client_b` exists and is currently used by no test. It is the cross-tenant
  control for the isolation tests of 03-05 and 03-07; if those land without it, the
  same-code collision it sets up goes untested.

## Known Stubs

**All 38 tests added by this plan are stubs, by design** — that is the plan's entire
deliverable, declared in its objective (*« Ce plan n'implémente aucune exigence »*). Each
carries `@pytest.mark.pending`, a body of `pytest.fail("non implémenté : plan 03-XX")`
naming its owner, and a docstring stating what its red would prove. None is on a
user-facing path; nothing renders through any of them. The table at the top of this summary
is the resolution schedule, and `03-02` therefore closes **none** of the eight requirements
in its frontmatter — it creates the named test of each. Ownership of implementation stays
with plans 03-04 through 03-14.

`tests/factories.py` has a second, narrower stub: the named comment where
`AccesMagasinFactory` and `DroitAccordeFactory` will go (deviation 2), resolved by 03-04.

## Self-Check: PASSED

All six created test files verified present on disk. Both modified files verified changed.
All three commits verified in `git log`: `c629d4d`, `94e9b53`, `446ba0d`. Suite re-run
after the last commit: **114 passed, 38 deselected**.

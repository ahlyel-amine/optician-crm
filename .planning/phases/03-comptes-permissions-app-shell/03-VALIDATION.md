---
phase: 3
slug: comptes-permissions-app-shell
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-14
---

# Phase 3 — Validation Strategy

> Derived from `03-RESEARCH.md` § Validation Architecture and `03-UI-SPEC.md`.
> Project-wide conventions: `.planning/TESTING.md`. Test names are French, matching the domain language.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend** | pytest + pytest-django (exists, 107 tests green) |
| **Frontend** | **vitest — Wave 0 gap, does not exist yet**, alongside `web/` itself |
| **Config** | `pyproject.toml [tool.pytest.ini_options]` (exists); `web/vitest.config.ts` (new) |
| **Quick run** | `uv run pytest -x -q -m "not slow and not pending"` **and** `npm --prefix web test -- --run` |
| **Full suite** | `uv run pytest --create-db` + `npm --prefix web test -- --run` + the OpenAPI schema diff gate |
| **New markers** | none — the projection tests are ordinary integration tests |

---

## Sampling Rate

- **After every task commit:** the quick run for whichever side changed; both if the change crosses the boundary
- **After every plan wave:** full suite including the schema diff gate
- **Before `/gsd-verify-work`:** full suite green, `spectacular --fail-on-warn` clean, committed schema matches generated
- **Max feedback latency:** 30 seconds per side

---

## Per-Requirement Verification Map

Task IDs filled in by the planner; every task cites one of these.

| Requirement | Named tests | Automated |
|---|---|---|
| **PERM-01** | `test_perm01_la_connexion_etablit_une_session_et_lie_le_client` · `..._le_cookie_de_session_survit_a_la_fermeture_du_navigateur` · `..._la_deconnexion_invalide_la_session_immediatement` · `..._la_connexion_est_limitee_en_debit` · `..._une_requete_api_sans_jeton_csrf_est_refusee` | yes |
| **PERM-02** | `test_perm02_un_proprietaire_ne_cree_un_compte_que_dans_son_propre_client` · `..._un_compte_desactive_est_refuse_des_la_requete_suivante` · `..._un_utilisateur_client_ne_peut_jamais_etre_operateur` (via `queryset.update`, proving a DB constraint not `clean()`) | yes |
| **PERM-03** | `test_perm03_un_droit_est_une_ligne_pas_un_palier` · `..._la_revocation_prend_effet_sans_reconnexion` · `..._un_proprietaire_ne_peut_pas_accorder_a_un_utilisateur_dun_autre_client` · `..._le_journal_enregistre_qui_a_accorde_quoi_et_quand` | yes |
| **PERM-04** | `test_perm04_un_gerant_ne_voit_que_les_magasins_accordes_en_liste_et_en_detail` · `..._ne_peut_pas_ecrire_dans_un_magasin_non_accorde` · `..._un_droit_obsolete_sur_un_magasin_inactif_n_accorde_rien` · `..._lacces_du_proprietaire_est_lensemble_complet_et_non_un_filtre_saute` | yes |
| **PERM-05** | `test_perm05_un_agregat_est_calcule_sur_le_queryset_deja_filtre` · `..._le_catalogue_declare_prix_achat_marge_et_ca_global` | partly — live verification belongs to Phase 8, see below |
| **PERM-06** | 12 tests, led by `test_perm06_champ_protege_absent_de_lapi_de_lexport_et_du_document` (**parametrized over `CHAMPS_PROTEGES` × {api, export, document}**) · `..._tout_champ_de_modele_expose_est_classe` · `..._le_schema_est_identique_pour_le_proprietaire_et_le_gerant` · `..._un_champ_protege_ne_peut_ni_trier_ni_filtrer` · `..._lacces_absent_vaut_aucun_droit` | yes |
| **APP-01** | `test_app01_les_erreurs_de_lapi_sont_en_francais` | yes |
| **APP-03** | `test_app03_un_montant_traverse_le_json_en_chaine_pas_en_flottant` · `..._le_formatage_serveur_respecte_la_fixture_partagee` (pytest) · `format.test.ts` (vitest, **same JSON fixture**) · `..._la_date_courte_est_au_format_jj_mm_aaaa` · `..._aucun_montant_n_est_un_flottant_dans_une_reponse` | yes |

**The load-bearing test of the phase** is the PERM-06 parametrization: one registry × three renderers. It is what stops the API, the export and the printed document from agreeing today and drifting by Phase 9.

**The client-side half** (`03-UI-SPEC.md` §8.3, §7.7): a named vitest test mirroring the server's conformance test, asserting an omitted JSON key produces no column header, no `—`, no tooltip and no zeroed total — and that the permission catalogue is served pre-intersected, so a hidden code is absent from the wire rather than filtered in the browser.

---

## Wave 0 Requirements

- [ ] `web/` — Vite + React + TypeScript, shadcn/ui init (`new-york`, neutral, CSS variables)
- [ ] `web/vitest.config.ts` + the first failing frontend tests
- [ ] The shared money/date format fixture — **one JSON file read by both pytest and vitest**, so server and client cannot disagree
- [ ] `tests/test_comptes_auth.py`, `test_comptes_droits.py`, `test_projection.py`, `test_locale.py` — named tests as stubs
- [ ] OpenAPI schema committed, plus the CI diff gate
- [ ] Test factories for `Utilisateur`, `DroitAccorde`, `AccesMagasin`

---

## Manual-Only Verifications

| Behavior | Requirement | Why manual | Instructions |
|---|---|---|---|
| Keyboard traversal of the permission screen with a screen reader | PERM-03 | Assistive-technology behaviour is not meaningfully simulated in vitest | Tab through §7 with VoiceOver; every switch announces its label, state and magasin scope |
| The interface reads as French, not as translated English | APP-01 | Judgement, not assertion | A French speaker reads the §12 lexicon against the built screens |

---

## Known Deferral

Roadmap criterion 3 names prix d'achat, marge and CA — **fields that do not exist until Phases 8 and 10**. Phase 3 delivers and tests the *mechanism* (the catalogue declares the codes; the projection layer enforces absence) but cannot verify those specific fields. Live verification is Phase 8's. Recorded here so the phase is not marked complete on a criterion it structurally cannot meet.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags (`vitest --run`, never bare `vitest`)
- [ ] Feedback latency < 30s per side
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

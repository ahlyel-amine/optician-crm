---
phase: 03-comptes-permissions-app-shell
plan: 04
subsystem: droits-catalogue-et-stockage
tags: [comptes, permissions, PERM-03, PERM-04, PERM-05, claude-md-6, claude-md-13, T-03-16, T-03-17, T-03-18, T-03-19]
requires:
  - 03-01 (comptes.Utilisateur, AUTH_USER_MODEL, comptes dans CONTROL_PLANE_APPS)
  - 03-02 (les stubs pending nommés, UtilisateurFactory / GerantFactory / ProprietaireFactory, deux_magasins)
  - 02-03 (TenantRouter.allow_relation — la frontière qui impose une valeur plutôt qu'une FK)
provides:
  - plateforme/comptes/permissions_catalogue.py — 21 codes, 7 sections, 21 explications, PREREQUIS et ses deux sens
  - DroitAccorde unique par (utilisateur, magasin_code, code) — CLAUDE.md #13
  - AccesMagasin (PERM-04) et JournalDroit append-only (T-03-19)
  - AccesMagasinFactory / DroitAccordeFactory, sur `default`
affects:
  - 03-05 (Acces / acces_pour — consomme les trois tables ; étend le test `..._ne_fuit_pas_vers_un_autre` à la résolution)
  - 03-06 (registre de projection — itère Permission à l'import)
  - 03-09 (service d'octroi — applique PREREQUIS et la règle accès-avant-droit une seconde fois)
  - 03-11 (SPA — reçoit sections, libellés et explications du serveur, n'en code aucun en dur)
  - phases 8 et 10 (article.voir_prix_achat, vente.voir_marge, dashboard.voir_ca_global existent déjà)
tech-stack:
  added: []
  patterns:
    - le catalogue est du code énumérable à l'import ; les octrois sont des données
    - une valeur plutôt qu'une clé étrangère quand la relation franchirait la frontière plan de contrôle / base client
    - une garantie que la base ne peut pas exprimer est écrite en Python, dite franchement dans la docstring, et testée
    - un test négatif ne vaut que doublé de son contrôle positif
key-files:
  created:
    - plateforme/comptes/permissions_catalogue.py
    - plateforme/comptes/migrations/0002_droits.py
  modified:
    - plateforme/comptes/models.py
    - tests/factories.py
    - tests/test_comptes_droits.py
    - tests/test_magasin_acces.py
decisions:
  - la forme retenue est celle de CLAUDE.md #13 et 03-UI-SPEC 0.1 — (utilisateur, magasin_code, code) — et NON celle de 03-RESEARCH section 4
  - magasin_code est le code métier, une valeur, jamais une FK ni une clé primaire
  - la règle « un droit ne vise qu'un magasin accordé » est une règle Python assumée, pas une contrainte de base
  - JournalDroit ne porte aucune relation vers DroitAccorde, sinon il disparaîtrait avec lui
  - aucun preset, aucun bundle, aucune fonction « droits standard » ; la raison est dans la docstring du module
metrics:
  tasks: 2
  commits: 2 (dont un absorbé par un exécuteur parallèle — voir Déviations)
  tests-added: 3
  tests-unpended: 5
  suite: 122 passed, 33 pending (114 passed, 38 pending avant)
  duration: ~45 min
  completed: 2026-09-14
---

# Phase 3 Plan 04 : le catalogue des droits et la forme des octrois — Summary

Vingt-et-un codes de permission existent maintenant comme **code Python énumérable à
l'import**, répartis en sept sections alignées sur la navigation et pourvus chacun d'une
phrase d'explication en français ; et un droit accordé est **une ligne
`(utilisateur, magasin_code, code)`**, unique sur les trois colonnes, avec le test qui
prouve qu'un droit donné à Anfa ne vaut rien à Maârif.

## La décision, écrite ici pour que les phases 8 et 10 ne retombent pas sur la mauvaise référence

**La forme retenue est celle de CLAUDE.md #13 et de `03-UI-SPEC.md` 0.1.**
**Ce n'est pas celle de `03-RESEARCH.md` §4.**

| Source | Forme | Statut |
|---|---|---|
| `03-RESEARCH.md` §4 | `DroitAccorde(utilisateur, code)`, `UniqueConstraint(utilisateur, code)` | **superseded** par son propre bandeau de correction |
| CLAUDE.md #13 · `03-UI-SPEC.md` 0.1 | `DroitAccorde(utilisateur, magasin_code, code)`, `UniqueConstraint` sur les trois | **construit** |

La recherche elle-même en doutait — sa question ouverte n° 5 appelle cela « la seule
décision genuinement chère à inverser » — puis a conçu contre. Le coût de l'inversion, s'il
fallait la faire plus tard : une migration de données sur des droits en production, plus un
changement de signature de `peut()`, donc de chacun de ses sites d'appel, dans chaque
module de chaque phase suivante.

Ce que l'interface montre n'est pas ce que le stockage porte, et c'est délibéré
(`03-UI-SPEC.md` 7.5) : une case à cocher par droit, une ligne écrite par magasin accordé,
et la dimension magasin n'apparaît à l'écran que si le propriétaire demande « Par
magasin ». **C'est le stockage qui doit pouvoir, pas l'écran qui doit montrer.**

## Pourquoi `magasin_code` est une valeur, et pas seulement par commodité

`Utilisateur` vit sur `default`. `Magasin` vit dans la base de l'opticien.
`TenantRouter.allow_relation` :

```python
return obj1._state.db == obj2._state.db
```

Une clé étrangère entre les deux n'est pas indésirable, elle est **inconstructible**. C'est
la même frontière qui rend `django-guardian` structurellement impossible sur ce projet, et
non simplement inutile — un détail que la recherche mentionne et qu'il valait la peine de
rendre visible dans le code plutôt que dans un document.

Deuxième raison, celle qui décide entre le code métier et la clé primaire : `pg_restore`
réattribue les `id` dans une base neuve, `ANFA` non. Stocker le code fait survivre l'octroi
à une restauration et à une bascule (TENANT-09). Le prix admis est qu'un code peut devenir
obsolète ; il est intersecté avec les magasins **actifs** à la résolution (plan 03-05,
menace T-03-20), et aucune ligne d'octroi n'affirme à elle seule qu'un magasin existe.

Vérifié plutôt que supposé — les trois tables sont épinglées au plan de contrôle :

```
AccesMagasin default= True tenant_a= False
DroitAccorde default= True tenant_a= False
JournalDroit default= True tenant_a= False
```

## La garantie que la base ne peut pas tenir, dite franchement

`DroitAccorde.save()` refuse un droit visant un magasin sans `AccesMagasin` correspondant
(menace T-03-18 : la ligne est inerte aujourd'hui et devient active le jour où le magasin
est accordé — un droit que personne n'a décidé d'accorder, apparu à l'occasion d'une action
sans rapport).

Une `CheckConstraint` porte sur une ligne, pas sur l'existence d'une ligne dans une autre
table. Une clé étrangère composite vers `AccesMagasin` ferait de `(utilisateur, magasin)` la
clé de la table des droits, donc interdirait de révoquer un accès sans détruire l'historique
des droits. **Contrairement à la garantie opérateur du plan 03-01, la base ne peut pas nous
sauver ici.** C'est donc une règle Python : posée dans `save()`, appliquée une seconde fois
par le service d'octroi (plan 03-09), testée par
`test_perm03_un_droit_ne_peut_viser_un_magasin_non_accorde`. `queryset.update()` la
contourne toujours, et la docstring le dit plutôt que de le laisser découvrir.

## Trois tests qui auraient pu passer pour la mauvaise raison

1. **`..._ne_fuit_pas_vers_un_autre` donne au gérant l'accès aux *deux* magasins** avant de
   n'accorder le droit qu'à Anfa. Sans cela, il passerait parce que Maârif est inaccessible,
   ce qui ne prouve rien sur CLAUDE.md #13 — la fuite qu'il surveille est celle du *droit*,
   pas celle de l'*accès*.
2. **Chaque assertion négative est doublée de son contrôle positif.** « Aucun droit à
   Maârif » est vrai d'un stockage qui n'accorde jamais rien ; l'assertion « le droit existe
   à Anfa » est ce qui lui donne un sens. Même construction dans le test du magasin non
   accordé, où le chemin nominal est réaffirmé après le refus.
3. **`..._est_stocke_par_gerant_magasin_et_permission` interdit toute unicité plus étroite**,
   et pas seulement exige la bonne. Une `UniqueConstraint(utilisateur, code)` ajoutée à côté
   de la nôtre reverserait CLAUDE.md #13 en laissant verte l'assertion qui ne regarde que la
   contrainte nommée.

## Ce que le catalogue interdit, et pourquoi c'est écrit dans le module

Aucun preset, aucun bundle, aucune fonction « droits standard ». La docstring du module
écrit la raison — CLAUDE.md #6, plus l'argument commercial de `research/FEATURES.md` : les
droits par gérant sont le seul différenciateur trouvé sur ce marché, et un « Gérant
standard » le supprime en une migration — pour que le prochain lecteur tente de la
contester plutôt que de l'ignorer.

`test_perm03_un_droit_est_une_ligne_pas_un_palier` refuse **trois** formes de retour du
palier : un champ de modèle nommé `role` / `tier` / `palier` / `niveau` / `profil` /
`groupe` n'importe où dans `comptes` ; un attribut du module dont le *nom* annonce un
paquet ; et un attribut dont la *valeur* est une collection de codes du catalogue. La
moitié stockage ajoute la quatrième : accorder `stock.voir` ne rend aucun des vingt autres
codes vrai.

## Le vingt-et-unième code

`vente.voir` — « Consulter les ventes et les factures » — vient de `03-UI-SPEC.md` 0.2, pas
de la recherche. Sans lui, un gérant qui peut consulter une facture passée sans enregistrer
de vente est inexprimable, et l'entrée de navigation `Ventes` n'a aucun code auquel se
conditionner. `vente.creer` et `vente.remise` en dépendent dans `PREREQUIS`.

## Critères d'acceptation, tels qu'exécutés

### Tâche 1

| Critère | Résultat |
|---|---|
| `grep -c '= "' permissions_catalogue.py` → 21 codes | **21** |
| `grep -c 'vente.voir"' …` ≥ 1 | **1** |
| `grep -cE 'role\|palier\|tier\|niveau\|preset' …` → 0 hors commentaires d'interdiction | **4**, lignes 17, 18, 22, 24 — toutes dans le paragraphe de la docstring qui énonce l'interdiction. Voir déviation 2 |
| `python -c` : union des sections = `set(Permission.values)` | **exit 0** — 21 codes, 7 sections |
| `python -c` : chaque clé et valeur de `PREREQUIS` ∈ `Permission.values` | **exit 0** — 9 entrées |
| `pytest tests/test_comptes_droits.py -q -k "catalogue or palier"` | **3 passed** |
| `<verify>` : `-k "catalogue or palier or prerequis"` | **3 passed** (4 avec le PERM-05 de `test_magasin_acces.py`) |

### Tâche 2

| Critère | Résultat |
|---|---|
| `grep -c 'uniq_droit_par_utilisateur_magasin_code' models.py` → 1 | **1** |
| `grep -c 'magasin_code' models.py` ≥ 3 | **14** |
| `grep -c 'ForeignKey("magasins' models.py` → 0 | **0** |
| `grep -cE 'class (AccesMagasin\|DroitAccorde\|JournalDroit)' models.py` → 3 | **3** |
| `test -f plateforme/comptes/migrations/0002_droits.py` | **exit 0** |
| `manage.py makemigrations --check --dry-run` | **exit 0**, « No changes detected » |
| `pytest -q -k "stocke or fuit or palier or journal"` | **5 passed** |
| `grep -c 'pytest.mark.pending' test_comptes_droits.py` a baissé d'au moins 5 | **8 → 4**, soit 4 dans ce fichier ; **36 → 31** dans `tests/`, soit 5. Voir déviation 1 |
| `<verify>` : `-x -k "stocke or fuit or palier or journal or magasin_non_accorde"` | **5 passed** |

### Vérification du plan

| Critère | Résultat |
|---|---|
| `manage.py check` | **no issues (0 silenced)** |
| `manage.py makemigrations --check --dry-run` | **exit 0** |
| `pytest tests/test_comptes_droits.py -q -m "not pending"` | **7 passed**, 4 restent `pending` (ceux qui attendent l'API, plans 03-05 et 03-09) |
| `pytest -x -q -m "not slow and not pending"` | **92 passed** (84 avant) |
| `pytest -q -m "not pending"` | **122 passed, 33 deselected** (114 / 38 avant) |
| `grep -rn 'DroitAccorde' plateforme/ \| grep -v magasin_code` | 4 lignes, toutes inoffensives : la ligne `class DroitAccorde(models.Model):`, deux phrases de docstring (dont celle qui déclare la forme de la recherche abandonnée) et le `name='DroitAccorde'` du `CreateModel`, dont la liste de champs contient `magasin_code`. **Aucune définition de droit sans dimension magasin** |

## Rouge → vert

| Test | Rouge, pour quelle raison | Vert |
|---|---|---|
| `..._pas_un_palier` (moitié catalogue) | `ImportError: cannot import name 'permissions_catalogue'` | après le catalogue |
| `..._les_sept_sections_couvrent_exactement_le_catalogue` (neuf) | `ModuleNotFoundError` | après `SECTIONS` + `EXPLICATIONS` |
| `..._la_carte_des_prerequis_est_acyclique_et_close…` (neuf) | `ModuleNotFoundError` | après `PREREQUIS`, `fermeture_prerequis`, `dependants` |
| `test_perm05_le_catalogue_declare_prix_achat_marge_et_ca_global` | `ModuleNotFoundError` | après les trois codes différés |
| `..._pas_un_palier` (moitié stockage) | `ImportError: cannot import name 'DroitAccorde'` | après les modèles |
| `..._est_stocke_par_gerant_magasin_et_permission` | `LookupError: App 'comptes' doesn't have a 'AccesMagasin' model` | après les modèles + `0002_droits` |
| `..._ne_fuit_pas_vers_un_autre` | idem | idem |
| `..._un_droit_ne_peut_viser_un_magasin_non_accorde` (neuf) | `ImportError` | après `valider_acces_magasin` |
| `..._le_journal_enregistre_qui_a_accorde_quoi_et_quand` | `ImportError` | après `JournalDroit` |

Compte des `pending` : **38 → 33**. Cinq marqueurs retirés, aucun ajouté, aucun marqueur
appartenant à un autre plan touché.

## Déviations du plan

### 1. [Rule 3 — bloquant] Un critère d'acceptation est insatisfaisable dans le fichier qu'il nomme

`grep -c 'pytest.mark.pending' tests/test_comptes_droits.py` est spécifié comme devant
baisser **d'au moins 5**. Il baisse de **4** : 8 → 4.

Le plan 03-04 possède cinq stubs (table de `03-02-SUMMARY.md`), mais l'un des cinq —
`test_perm05_le_catalogue_declare_prix_achat_marge_et_ca_global` — vit dans
`tests/test_magasin_acces.py`, pas dans `tests/test_comptes_droits.py`. Les quatre autres
sont bien dans le fichier nommé, et ce sont les quatre retirés.

L'**intention** — « ce plan retire au moins cinq marqueurs » — est vérifiée exactement, à
l'échelle où elle est vraie :

| Mesure | Avant | Après |
|---|---|---|
| `grep -c … tests/test_comptes_droits.py` | 8 | **4** |
| `grep -c … tests/test_magasin_acces.py` | 6 | **5** |
| somme sur `tests/*.py` | 36 | **31** |
| `pytest -q -m pending --collect-only` | 38 | **33** |

Le marqueur n'a pas été relaxé et aucun stub appartenant à un autre plan n'a été touché
pour faire le compte. **Signalé plutôt qu'assoupli** : un plan futur qui réutilise ce
critère devrait le formuler sur `tests/`, pas sur un fichier.

### 2. [signalé] Le critère « grep des paliers = 0 » retourne 4, et il le doit

`grep -cE 'role|palier|tier|niveau|preset' plateforme/comptes/permissions_catalogue.py`
retourne **4**. Le critère lui-même prévoit l'exception (« hors commentaires expliquant
leur interdiction ») ; les quatre lignes sont les lignes 17, 18, 22 et 24 de la docstring du
module, c'est-à-dire exactement le paragraphe qui énonce pourquoi un preset est interdit et
qui nomme le test qui le refuse. Supprimer ces mots pour satisfaire un `grep` retirerait
l'avertissement que le critère existe pour protéger. Aucune autre occurrence dans le
fichier — vérifié ligne par ligne, pas au compteur.

### 3. [Rule 3 — bloquant] `tests/test_magasin_acces.py` n'est pas dans `files_modified`

Le stub PERM-05 que ce plan doit mettre au vert y vit (plan 03-02), et un test ne peut pas
être mis au vert depuis un autre fichier sans le dupliquer — ce qui mettrait deux fonctions
du même nom dans la suite, dont une seule maintenue. Le fichier a donc été modifié : un
marqueur `pending` retiré, un corps écrit. **Aucune autre ligne** de ce fichier n'a changé,
et aucun des cinq stubs restants (plans 03-05 et 03-07) n'a été touché. Le fichier
n'appartient à aucun autre plan de la vague 3.

### 4. [Rule 2 — fonctionnalité critique manquante] Deux garanties ajoutées au-delà du texte du plan

- **`JournalDroit.save()` refuse la réécriture et `delete()` la suppression.** Le plan dit
  « append-only » ; sans ces deux refus, l'append-only est une intention. Un journal
  modifiable répond toujours à la question « qui a donné les marges à Karim ? », mais pas
  forcément la vérité (menace T-03-19). Testé dans
  `..._le_journal_enregistre_qui_a_accorde_quoi_et_quand`.
- **`_valider()` refuse tout code hors catalogue** dans `fermeture_prerequis` et
  `dependants`, plutôt que de l'ignorer. Un code ignoré produit un octroi sans effet que
  personne ne remarque avant l'appel du gérant.

### 5. Un exécuteur parallèle a absorbé le commit de la tâche 2

Les quatre fichiers de la tâche 2 étaient indexés (`git add` nommant chaque fichier, jamais
`git add .`) quand l'exécuteur du plan **03-11**, qui travaille dans le même worktree, a
committé. Son commit `e3ff242` (« feat(03-11): task 3 — Valeur, du contenu arabe… »)
contient donc, en plus de ses trois fichiers `web/`, mes quatre fichiers backend :

```
plateforme/comptes/migrations/0002_droits.py |  65 ++
plateforme/comptes/models.py                 | 256 ++
tests/factories.py                           |  55 +-
tests/test_comptes_droits.py                 | 233 +-
```

**Rien n'est perdu et rien n'est modifié** : `git diff e3ff242 -- <mes quatre fichiers>` est
vide, et `permissions_catalogue.py` était déjà dans mon propre commit `4f0b11c`. Ce qui est
perdu est l'**atomicité** du commit de la tâche 2 et l'exactitude de son message.

**L'historique n'a pas été réécrit**, délibérément : `e3ff242` est HEAD, l'exécuteur 03-11
est en cours de plan et construira dessus, et un `reset --soft` suivi de deux commits
pendant qu'un autre agent écrit dans le même dépôt risque de perdre son travail — un coût
sans commune mesure avec celui d'un message de commit inexact. La correspondance est donc
enregistrée ici :

| Tâche | Commit | Message |
|---|---|---|
| Tâche 1 | `4f0b11c` | `feat(03-04): task 1 - le catalogue des 21 droits, ses sections et ses prerequis` |
| Tâche 2 | `e3ff242` (partiel) | absorbé dans un commit du plan 03-11 — voir ci-dessus |

Pour les plans suivants qui s'exécutent en parallèle dans un worktree partagé : `git commit`
sans pathspec valide **tout l'index**, y compris ce qu'un autre agent vient d'indexer. La
forme sûre est `git commit -F - -- <chemins>`, qui ne committe que les chemins nommés.

## Notes pour les plans suivants

- **03-05** étend `test_perm03_un_droit_accorde_dans_un_magasin_ne_fuit_pas_vers_un_autre`
  à la résolution : la moitié stockage est verte ici, la moitié `acces.peut(code, magasin)`
  lui appartient, et la docstring du test le dit. Le test n'est plus `pending` ; sa moitié
  manquante est nommée dans son propre corps, pas dans un marqueur.
- **03-09** consomme `fermeture_prerequis` (sens octroi) et `dependants` (sens révocation),
  et doit appliquer une seconde fois la règle accès-avant-droit — `save()` la tient, mais
  `queryset.update()` la contourne, et une API qui écrit en masse passerait à côté.
- **03-06 / 03-11** : les libellés et les explications sont servis par le serveur. Le
  catalogue servi à un gérant-manager doit être **déjà intersecté** avec ses propres droits
  (`03-UI-SPEC.md` 7.7) — c'est une garantie au fil, pas une règle de rendu.
- **Phases 8 et 10** : `article.voir_prix_achat`, `vente.voir_marge` et
  `dashboard.voir_ca_global` existent déjà ; il n'y aura qu'une ligne de registre de
  projection à écrire. Et la référence pour la forme du stockage est **CLAUDE.md #13**, pas
  `03-RESEARCH.md` §4.
- `REQUIREMENTS.md` n'a **pas** été modifié : PERM-03 et PERM-05 sont réclamées par
  plusieurs plans de cette phase, et cocher après l'un d'eux dirait au verrou de phase que
  l'exigence est faite alors que sa surface d'API et sa résolution n'existent pas encore.

## Known Stubs

Aucun. Les trois modèles sont complets et migrés, le catalogue est complet à 21 codes, et
rien dans ce plan ne rend une valeur vide ou un texte d'attente vers une interface. Les
quatre `pending` restants de `tests/test_comptes_droits.py` appartiennent nommément aux
plans 03-05 (`..._la_revocation_prend_effet_sans_reconnexion`) et 03-09 (les deux PERM-02 de
création de compte et `..._ne_peut_pas_accorder_a_un_utilisateur_dun_autre_client`).

## Self-Check: PASSED

Les deux fichiers créés sont présents sur le disque
(`plateforme/comptes/permissions_catalogue.py`,
`plateforme/comptes/migrations/0002_droits.py`), les quatre fichiers modifiés portent bien
les changements, et les deux commits existent dans `git log` : `4f0b11c` (tâche 1) et
`e3ff242` (tâche 2, absorbé — déviation 5). Suite re-passée après le dernier commit :
**122 passed, 33 deselected**.

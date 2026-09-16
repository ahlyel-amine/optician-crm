---
phase: 03-comptes-permissions-app-shell
plan: 06
subsystem: projection-un-registre-quatre-consommateurs
tags: [projection, PERM-05, PERM-06, openapi, drf-spectacular, csv, document, T-03-29, T-03-30, T-03-31, T-03-32, T-03-33, T-03-34, T-03-35, T-03-36, T-03-37, A-03-06]
requires:
  - 03-05 (Acces, Acces.ANONYME, Acces.SCHEMA, _PorteurAcces, AccesMiddleware)
  - 03-04 (permissions_catalogue.Permission — les 21 codes, dont les trois de phases 8 et 10)
  - 03-02 (les stubs pending nommés de tests/test_projection.py et leur paramétrisation à repli)
  - 02-03 (TenantRouter et sa branche fail-closed sur une application non classée)
provides:
  - plateforme/projection/registre.py — CHAMPS_PROTEGES, CHAMPS_PUBLICS, cle_de_champ, est_classe, champs_interdits, codes_proteges_de
  - plateforme/projection/serializers.py — SerializerProjete et acces_du_contexte (consommateur 1)
  - plateforme/projection/export.py — exporter_csv, BOM_UTF8, SEPARATEUR (consommateur 2)
  - plateforme/projection/documents.py — contexte_document, rendre_html (consommateur 3)
  - plateforme/projection/templates/projection/document.html — le gabarit qui itère et ne nomme pas
  - plateforme/projection/schema.py — requete_mock_schema, marquer_champs_proteges_optionnels (consommateur 4)
  - config/settings/base.py — REST_FRAMEWORK et SPECTACULAR_SETTINGS
  - tests/ressources_fixture.py — la ressource test-only qui prouve la machinerie
affects:
  - 03-07 (portée des lignes et des agrégats — consomme champs_interdits(magasin_id=...) et le registre pour les allowlists de tri/filtre)
  - 03-10 (le schéma commité et sa porte de diff — lit le document que ce plan rend déterministe)
  - phases 4 à 8 (tout ModelSerializer hérite de SerializerProjete et classe ses champs)
  - phase 8 (une ligne de registre + une entrée dans _sujet_pour = trois assertions)
  - phase 9 (tout nouveau rendu rejoint la liste RENDUS du test de conformité, dans son propre plan)
tech-stack:
  added: []
  patterns:
    - un lien énumérable plus un test qui l'itère, plutôt qu'une classe de base qui n'empêche rien
    - la clé est le champ de modèle, jamais la classe de sérialiseur — un champ imbriqué reste protégé
    - l'en-tête d'un export se dérive des champs déjà projetés ; une liste écrite à la main rend une colonne vide
    - un gabarit de document itère une liste déclarée et ne nomme aucun champ
    - un réglage dangereux n'est pas seulement laissé à son défaut, son nom est absent du fichier
    - chaque assertion d'absence porte son contrôle positif, sinon une panne la satisfait
key-files:
  created:
    - plateforme/projection/registre.py
    - plateforme/projection/serializers.py
    - plateforme/projection/export.py
    - plateforme/projection/documents.py
    - plateforme/projection/schema.py
    - plateforme/projection/templates/projection/document.html
    - tests/ressources_fixture.py
  modified:
    - config/settings/base.py
    - config/settings/local.py
    - tests/test_projection.py
decisions:
  - "CHAMPS_PROTEGES reste vide en phase 3 ; la preuve de bout en bout passe par une ressource test-only, injectée au registre par monkeypatch — la ligne exacte que la phase 8 écrira à demeure"
  - "L'export CSV utilise `;` et un BOM UTF-8 — révisable, non vérifié contre un vrai Excel"
  - "Le gabarit de document reçoit des paires (nom, valeur) et n'a aucune variable pointée ; string_if_invalid reste inchangé"
  - "Le post-traitement du schéma lit `registry._components` (privé) pour rester chirurgical, avec un repli par nom de champ plus large mais jamais plus permissif"
  - "COMPONENT_NO_READ_ONLY_REQUIRED n'est pas seulement laissé à False : son nom est absent de config/settings/, et un test l'exige"
  - "DEFAULT_RENDERER_CLASSES est JSON seul en base ; le renderer HTML navigable n'existe que dans local.py (A-03-06)"
  - "test_perm06_aucune_vue_ne_renvoie_un_values_queryset est réattribué au plan 03-07, conformément au registre de menaces de ce plan (T-03-38)"
  - "REQUIREMENTS.md n'est pas coché : PERM-05 et PERM-06 sont réclamées par plusieurs plans, et la vérification vivante appartient à la phase 8"
metrics:
  tasks: 3
  commits: 3
  tests-added: 14 (0 vert dans ce fichier auparavant)
  markers-pending-retires: 8 (11 -> 3 dans tests/test_projection.py)
  suite: 149 passed, 20 deselected (135 / 30 avant)
  duration: ~70 min
  completed: 2026-09-16
---

# Phase 3 Plan 06 : un registre, quatre consommateurs, un test paramétré — Summary

`plateforme/projection/` existe et **rien ne peut plus diverger en silence**. Un champ
inscrit au registre est absent de la charge utile JSON, n'a aucune colonne dans le CSV,
aucune valeur dans le HTML, et n'est jamais `required` dans le schéma OpenAPI — le tout
vérifié par un seul test paramétré registre × rendus, qui grandit tout seul.

---

## La règle que la phase 9 doit connaître, et elle est la seule chose qui empêche la dérive

> **Tout nouveau rendu est ajouté à la liste `RENDUS` de
> `tests/test_projection.py`, et reçoit sa branche dans le corps du test de conformité,
> DANS LE PLAN QUI LE CRÉE.**

Ce n'est pas une recommandation de style. C'est la garantie elle-même, et elle dépend
d'un souvenir à moins d'être écrite ici.

Le mode de défaillance contre lequel tout ce plan est construit : la phase 9 écrit un
gabarit de facture contenant une variable pointée sur un champ protégé, Django rend une
chaîne vide, et **rien ne le signale** — ni exception, ni avertissement, ni test rouge. Une
classe de base partagée n'y peut rien : le gabarit n'en hérite pas. Une revue de code n'y
peut rien : le rendu *a l'air* correct.

Deux conséquences pratiques, et elles se tiennent ensemble :

| Ce que la phase ajoute | Ce qu'elle doit écrire, en plus du code |
|---|---|
| un **rendu** (PDF A4, e-mail, export XLSX…) | son nom dans `RENDUS` **et** sa branche d'assertions |
| un **champ protégé** (`achats.Article.prix_achat`…) | sa ligne dans `CHAMPS_PROTEGES` **et** son entrée dans `_sujet_pour` |

La seconde est mécanique : le test paramétré prend la nouvelle clé tout seul, et
`_sujet_pour` échoue en disant exactement quoi écrire. La première ne l'est pas — un rendu
qui n'est pas dans la liste n'est vérifié par rien, et personne ne s'en apercevra avant un
audit. **Le garde du garde, c'est ce paragraphe.**

Une limite du même ordre, nommée plutôt que cachée : le test des tâches Celery détecte une
« tâche de rendu » par le fait qu'elle appelle `exporter_csv`, `contexte_document` ou
`rendre_html`. Une tâche de phase 9 qui appellerait directement le moteur PDF lui
échapperait. C'est la même règle qui la rattrape : passer par `rendre_html`, donc rejoindre
`RENDUS`.

---

## Ce que le registre est, et ce qu'il n'est pas

`CHAMPS_PROTEGES` est **vide**, et doit le rester jusqu'à la phase 8. `prix_achat` et
`marge` n'existent pas encore (ACHAT-04/07), le chiffre d'affaires global non plus
(DASH-01) ; les inventer ici préempterait le schéma de la phase 8, ce que
`03-RESEARCH.md` correction 3 nomme comme l'erreur à ne pas commettre et ce que la
docstring de `domaine/stock/models.py` interdit déjà.

Mais **un test paramétré sur zéro cas est vert et ne vaut rien**. D'où
`tests/ressources_fixture.py` : un modèle, son sérialiseur, sa vue, sa route et sa tâche
Celery, tous test-only, injectés au registre par `monkeypatch.setitem` le temps d'un test.
L'injection est littéralement la ligne que la phase 8 écrira à demeure, donc ce qui est
vérifié est bien le mécanisme qu'elle utilisera.

Trois décisions de forme sur cette ressource, parce qu'elles paraissent arbitraires :

| Décision | Pourquoi |
|---|---|
| `app_label = "tests"` | imposé par la clé que le plan 03-02 avait écrite, et correct par ailleurs : `tests` n'est pas installée, donc `makemigrations` ne la voit jamais et `tenancy.E001` ne la contrôle jamais |
| l'alias `default` est nommé par le gestionnaire et par `save()` | `tests` n'est ni dans `CONTROL_PLANE_APPS` ni dans `BUSINESS_APPS`, donc `TenantRouter._route` **lève** — et c'est voulu. Classer `tests` dans le routeur mettrait une étiquette de test dans le fichier le plus sensible du dépôt, pour le confort d'un modèle fictif |
| la table est créée par une fixture de **session**, par `schema_editor` | il n'y a pas de migration possible pour une application non installée, et une table créée dans un test disparaîtrait avec la transaction que pytest-django annule |

`grep -rn 'ressources_fixture' domaine/ plateforme/` ne retourne rien.

Et `CHAMPS_PUBLICS` n'est pas de la paperasse : `test_perm06_tout_champ_de_modele_expose_est_classe`
parcourt les sous-classes de `ModelSerializer` sous `Acces.SCHEMA` — sous un accès
ordinaire il n'examinerait que la moitié publique, vert et aveugle — et refuse tout champ
de modèle exposé qui n'est ni protégé ni déclaré public. « Public » devient une décision
écrite plutôt qu'un silence, et la phase 6 ne peut pas ressusciter un champ en l'imbriquant.

---

## Ce qui a été vérifié plutôt que constaté

**1. Chaque assertion d'absence porte son contrôle positif.** « Le champ est absent » est
vrai d'un rendu en panne. Les trois branches du test de conformité affirment donc aussi
que le propriétaire, lui, le reçoit — dans le JSON, dans l'en-tête CSV, dans le HTML — et
la branche `document` vérifie en plus que le prix public **est** imprimé, pour que
« absent » ne puisse pas vouloir dire « vide ».

**2. Le test du schéma a deux contraires, pas zéro.** « Les deux documents sont
identiques » est satisfait par un générateur cassé. Deux contrôles le ferment :

- avec le `build_mock_request` d'origine, la requête mock ne porte aucun `acces`, la
  projection retombe fail-closed sur `Acces.ANONYME`, et le champ protégé disparaît du
  schéma **pour tout le monde** — deux documents égaux, tous deux faux, et le `schema.yml`
  commité cesserait de décrire l'API ;
- avec l'épinglage **naïf** — résoudre `acces_pour(requete.user)`, ce que la recopie de
  `request.user` invite à écrire — les deux documents **diffèrent**. C'est exactement la
  fuite de A-03-09, reproduite dans le test pour que l'assertion d'égalité ait un sens.

**3. Le crochet de `required` a son contraire aussi.** Sans lui (`patched_settings` ne
laissant que le hook d'enums), le champ protégé **est** dans `required`. Et `id`, en
lecture seule, y reste dans les deux cas — ce qui distingue le crochet chirurgical de
l'interrupteur global qui rendrait `id` optionnel sur chaque ressource du produit.

**4. Le détecteur de tâches de rendu a son contrôle négatif.** Une fonction fautive
définie dans le test — elle appelle `exporter_csv` et n'a pas `acting_utilisateur_id` —
doit être reconnue ; sinon la boucle ne détecterait rien et le test serait vert pour
toujours. Il y a aussi une assertion « au moins une tâche trouvée », qui rougirait le jour
où `tests.exporter_ressources_fixture` disparaîtrait du registre Celery.

**5. Le gabarit est vérifié deux fois, parce qu'une fois ne suffit pas.** Le test source
refuse toute variable pointée entre doubles accolades dans `plateforme/projection/templates/`
— un gabarit ajouté en phase 9 y tombe du seul fait de vivre dans ce dossier. Mais un
gabarit peut parfaitement itérer la **mauvaise** liste : le second test compte les cellules
rendues contre les champs projetés.

---

## Une découverte qui vaut d'être connue : `Request.user` de DRF réécrit la requête sous-jacente

Le setter `user` de `rest_framework.request.Request` fait `self._request.user = value`.
Une vue sans classe d'authentification y pose donc `AnonymousUser` — **après** que
`AccesMiddleware` a installé son `SimpleLazyObject`. Comme celui-ci se résout plus tard, au
premier `get_fields()`, il voit cet `AnonymousUser` et rend `Acces.ANONYME`.

Trois conséquences :

1. **En production, rien ne bouge.** `SessionAuthentication` repose le même compte, donc
   la valeur lue est la même.
2. **Le sens de l'erreur est fail-closed.** Si DRF refusait d'authentifier là où le
   middleware avait résolu, la projection se resserre au lieu de s'ouvrir. C'est la bonne
   direction, et elle est notée ici pour que personne ne « corrige » la paresse en
   résolvant l'accès à l'entrée du middleware — ce qui coûterait deux requêtes SQL à chaque
   sonde de santé (T-03-27) et perdrait cette propriété.
3. **Les tests doivent employer `force_authenticate`.** Sans lui, les deux moitiés du test
   — gérant et propriétaire — deviennent anonymes, et l'assertion d'absence passe pour une
   raison fausse. C'est la première chose qui a été rouge dans ce plan, et la seule qui
   aurait pu rendre le test vert et vide.

---

## Décision révisable : le format de l'export CSV

`;` comme séparateur et un **BOM UTF-8** en tête. Les deux servent un seul outil, Excel en
configuration française et marocaine : un fichier à virgules s'y ouvre en une seule
colonne, et sans BOM il devine la page de codes et rend les accents en mojibake — ce qui,
sur une liste de clients marocains, touche la moitié des noms.

**Ce n'est pas vérifié contre un vrai Excel** (`03-RESEARCH.md` question ouverte 3). Les
deux valeurs sont des constantes nommées, `SEPARATEUR` et `BOM_UTF8`, testées par leur nom
et non par leur littéral : le jour où un opticien ouvre un export et le trouve en une
colonne, c'est là qu'il faut revenir, et le changement est de deux caractères.

`exporter_csv` renvoie une `str`, pas des octets : l'encodage appartient à la réponse HTTP
ou au fichier écrit, pas à la projection.

---

## L'admission de sécurité, répétée parce qu'elle est la vérité du plan

Toutes ces garanties sont **entièrement en Python**. Il n'existe aucune couche en dessous :
tous les utilisateurs d'un client partagent un seul rôle PostgreSQL, donc la base ne sait
pas distinguer le propriétaire d'un gérant. Là où l'isolation entre clients repose sur
`REVOKE CONNECT ... FROM PUBLIC` (CLAUDE.md #12), la visibilité des champs ne repose sur
rien d'autre que `registre.py` et son test.

Des rôles PostgreSQL par gérant avec des `GRANT` au niveau colonne seraient une vraie
défense en profondeur, et sont **refusés sur des motifs mesurés** : les pools PgBouncer
sont clés par `(user, database)`, donc N gérants par client multiplient le nombre de pools
par N — ce qui attaque directement le budget de connexions mesuré à 300 alias / 4
connexions en TENANT-08. Ce serait échanger une propriété prouvée contre une propriété
supposée.

**Le contrôle compensatoire est donc l'énumérabilité, pas la profondeur.** Le registre
s'énumère, le test l'itère, la classification refuse un champ non examiné, et les octrois
sont journalisés. C'est l'histoire honnête, et c'est celle qu'il faut raconter au verrou de
phase.

Faiblesses structurelles d'une projection par sérialiseur, énoncées et non dissimulées :
elle ne peut rien contre une **ligne** qu'il ne fallait pas servir, contre un **agrégat**
déjà calculé, ni contre un `.values()` / `.annotate()` qui ne touche aucun sérialiseur
(A-03-04). Les trois appartiennent au plan 03-07.

---

## Rouge → vert

| Test | Rouge, pour quelle raison | Vert |
|---|---|---|
| collecte de `tests/test_projection.py` | `ModuleNotFoundError: plateforme.projection.registre` | après `registre.py` (tâche 1) |
| `..._champ_protege_absent...[api]` | `assert 'valeur_protegee' in {...}` — le contrôle positif voyait `Acces.ANONYME` | après `force_authenticate` dans l'aide de test |
| `..._tout_champ_de_modele_expose_est_classe` | `ModuleNotFoundError` | après `cle_de_champ` / `est_classe` |
| `..._lacces_absent_vaut_aucun_droit` | `ModuleNotFoundError` | après le défaut `Acces.ANONYME` de `champs_interdits` |
| `..._champ_protege_absent...[export]` | `ModuleNotFoundError: plateforme.projection.export` | après `exporter_csv` (tâche 2) |
| `..._champ_protege_absent...[document]` | `ModuleNotFoundError: plateforme.projection.documents` | après `contexte_document` / `rendre_html` |
| `..._len_tete_csv_est_derive_des_champs_deja_projetes` | idem | après `child.fields` |
| `..._le_gabarit_de_document_itere_une_liste_projetee` | `Aucun gabarit trouvé`, puis `{{ objet.champ }}` trouvé **dans le commentaire du gabarit lui-même** | après reformulation du commentaire |
| `..._le_document_rend_exactement_les_colonnes_projetees` | `ModuleNotFoundError` | après le gabarit qui itère |
| `..._un_champ_protege_ne_peut_pas_etre_ecrit_par_un_gerant` | — vert dès la tâche 1 : retirer depuis `get_fields()` ferme l'écriture gratuitement | — |
| `..._toute_tache_de_rendu_exige_acting_utilisateur_id` | — vert dès la tâche 2 : le détecteur lit l'AST, il n'importe rien | — |
| `..._le_schema_est_identique_pour_le_proprietaire_et_le_gerant` | `ModuleNotFoundError: plateforme.projection.schema` | après `requete_mock_schema` + `SPECTACULAR_SETTINGS` (tâche 3) |
| `..._un_champ_protege_est_optionnel_dans_le_schema` | idem | après `marquer_champs_proteges_optionnels` |
| `..._le_reglage_global_de_required_reste_a_son_defaut` | — vert d'emblée, et c'est son rôle : il garde une absence | — |
| `..._le_renderer_html_est_absent_hors_developpement` | `BrowsableAPIRenderer apparaît dans ['base.py', 'local.py']` — le nom figurait dans un **commentaire** de `base.py` | après reformulation du commentaire |

Marqueurs `pending` : **11 → 3** dans ce fichier (30 → 20 éléments désélectionnés dans la
suite, la différence venant des trois cas de la paramétrisation). Les trois restants
appartiennent nommément à d'autres plans : `..._ne_peut_ni_trier_ni_filtrer` et
`..._aucune_vue_ne_renvoie_un_values_queryset` au **03-07**,
`..._le_catalogue_servi_a_un_gerant_manager_est_deja_intersecte` au **03-09**.

---

## Déviations du plan

### 1. [Rule 3 — bloquant] `REST_FRAMEWORK` n'existait pas, et `drf-spectacular` en a besoin

Le dépôt n'avait aucun réglage DRF. Sans `DEFAULT_SCHEMA_CLASS = drf_spectacular.openapi.AutoSchema`,
`SchemaGenerator` lève sur la première vue (`Incompatible AutoSchema used on View …`), donc
la tâche 3 était inexécutable telle qu'écrite. Le bloc est ajouté dans le même commit que
`SPECTACULAR_SETTINGS`, avec `DEFAULT_RENDERER_CLASSES` (voir déviation 2). **Il ne contient
rien d'autre** : `COERCE_DECIMAL_TO_STRING`, la pagination et le débit appartiennent aux
plans qui portent APP-03 et PERM-01, et les poser ici les leur volerait.

### 2. [Rule 2 — fonctionnalité critique manquante] `config/settings/local.py`, hors `files_modified`

`03-02` attribue `test_perm06_le_renderer_html_est_absent_hors_developpement` au plan
**03-06**, mais le plan ne le mentionne dans aucune tâche. Il est implémenté ici, parce que
A-03-06 est une divulgation réelle — les listes déroulantes du renderer HTML énumèrent le
`__str__` des objets liés, donc les lignes d'autres magasins — et parce que le réglage qui
la ferme est dans un fichier que ce plan modifie déjà. Cela oblige à toucher `local.py`,
qui n'est pas dans `files_modified` : une ligne, la seule où le renderer navigable a le
droit d'exister.

`local.py` reconstruit un dictionnaire au lieu d'appeler `.append()` sur la liste importée :
`REST_FRAMEWORK` vient de `base` **par référence**, et muter la liste en place la
changerait pour tout ce qui la détient déjà.

### 3. [Rule 3 — bloquant] Le sérialiseur de la ressource a porté sa projection en ligne, à la tâche 1

Le critère de la tâche 1 exige que le consommateur `api` passe, mais
`plateforme/projection/serializers.py` appartient à la tâche 2. La ressource de test a donc
porté, en tâche 1, les cinq lignes de `get_fields()` que la tâche 2 a extraites dans
`SerializerProjete` — et elle en hérite désormais.

Ce n'est pas un détour : c'est la thèse du plan rendue visible. Les assertions de la tâche 1
sont passées **sans l'abstraction**, ce qui démontre que ce qui rend PERM-06 vrai est le
registre et le test qui l'itère, pas la classe de base. La classe de base est du confort.

### 4. [Rule 2] Le test `..._aucune_vue_ne_renvoie_un_values_queryset` est réattribué au 03-07

Le stub du plan 03-02 dit « plan 03-06 » ; le registre de menaces de **ce** plan dit
l'inverse, nommément : T-03-38 est « fermé au plan 03-07, par un test au niveau du source
et des méthodes de queryset prenant l'accès ». Les deux ne peuvent pas être vrais, et le
registre du plan exécuté l'emporte — d'autant que le garde a besoin des méthodes de
queryset scopées que 03-07 écrit. Le message d'échec du stub a été corrigé en conséquence,
pour qu'il ne pointe pas un plan déjà terminé.

### 5. [Rule 2] Deux tests nommés au-delà de la liste du plan

- `test_perm06_len_tete_csv_est_derive_des_champs_deja_projetes` et
  `test_perm06_le_gabarit_de_document_itere_une_liste_projetee` sont explicitement demandés
  par le `<behavior>` de la tâche 2, mais sans nom : ils en ont un maintenant, et le
  premier affirme **aussi sur le source** (`child.fields` y figure), parce qu'un en-tête
  correct peut être obtenu par une coïncidence que la phase suivante défera.
- `test_perm06_le_document_rend_exactement_les_colonnes_projetees` est ajouté : le test
  source ne distingue pas un gabarit qui itère la **bonne** liste d'un qui itère une autre.

### 6. [signalé] `grep -c 'GET_MOCK_REQUEST' config/settings/base.py` retourne 2, pas 1

Le second est le commentaire qui cite `generators.py:231` — c'est-à-dire exactement ce que
l'action de la tâche 3 demande (« commenter sur place les deux lignes de source de
`drf-spectacular` qui justifient chaque réglage »). Le critère et l'action du même paragraphe
se contredisent. Le commentaire reste : un réglage dont la justification est effacée pour
satisfaire un compteur est un réglage que quelqu'un retirera. Vérifié ligne par ligne :
**un seul réglage** est posé, ligne 297.

C'est le quatrième critère de cette phase à correspondre à sa propre prose plutôt qu'au
fichier livré (03-04 en a signalé deux, 03-05 un).

### 7. [signalé] `pytest tests/test_projection.py -x -q` ne peut pas être vert

Le `<verify>` de la tâche 3 omet `-m "not pending"`. Trois marqueurs `pending` restent par
construction — ils appartiennent aux plans 03-07 et 03-09 — donc la commande telle qu'écrite
échoue sur un test que ce plan n'a pas mandat d'implémenter. Exécutée avec `-m "not pending"` :
**14 passed, 3 deselected**.

### 8. [signalé] `-k "champ_protege_absent and api"` collecte 3 cas, pas 1

« api » est une sous-chaîne du nom du test lui-même
(`..._absent_de_lapi_de_lexport_et_du_document`), donc le filtre retient les trois rendus.
Le critère de la tâche 1 a été vérifié avec `-k "champ_protege_absent and api]"`, qui ne
retient que le paramètre : **1 passed**.

### 9. [signalé] Deux critères grep confondent une phrase et un import

`grep -rn 'weasyprint\|WeasyPrint' plateforme/projection/` et
`grep -rn 'ressources_fixture' domaine/ plateforme/` retournaient chacun des **docstrings
explicatives** — celles qui disent précisément « la phase 3 ne prend pas cette dépendance »
et « la ressource vit dans les tests ». Les deux prose ont été reformulées pour satisfaire
les critères à la lettre, sans rien perdre de leur sens ; la forme durable de ces critères
porte sur la ligne d'import, pas sur l'occurrence du mot. À reformuler dans les plans qui
les réutiliseront.

### 10. [Rule 1 — bogue] `force_authenticate` était indispensable, et l'a été à la dure

Voir la section « Une découverte qui vaut d'être connue » plus haut. Sans lui, le contrôle
positif du consommateur `api` échouait avec un message qui accusait la projection, alors que
la cause était le setter `Request.user` de DRF réécrivant `_request.user`.

### 11. [Rule 2] `CHAMP_DE_REPLI` est dérivé, plus recopié

Le plan 03-02 avait écrit la clé de repli en dur
(`"tests.RessourceFixture.valeur_protegee"`). Elle est maintenant calculée depuis les
constantes de la ressource : un renommage du champ aurait autrement laissé le test porteur
de la phase paramétré sur une clé que plus personne ne protège — donc vert, donc sans
valeur.

---

## Critères d'acceptation, tels qu'exécutés

### Tâche 1

| Critère | Résultat |
|---|---|
| `grep -c 'CHAMPS_PROTEGES' registre.py` ≥ 2 | **5** |
| `grep -c 'CHAMPS_PUBLICS' registre.py` ≥ 2 | **3** |
| `prix_achat` seulement en commentaire | **2 occurrences**, lignes 45 et 53, toutes deux `#:` |
| `grep -c 'parametrize' tests/test_projection.py` ≥ 2 | **3** |
| `-k "champ_protege_absent and api"` collecte ≥ 1 et passe | **1 passed** avec `and api]` — voir déviation 8 |
| `-k "classe or lacces_absent"` | **2 passed** |
| `grep -rn 'ressources_fixture' domaine/ plateforme/` vide | **vide** — voir déviation 9 |
| `<verify>` | **3 passed** |

### Tâche 2

| Critère | Résultat |
|---|---|
| `grep -c 'Acces.ANONYME' serializers.py` ≥ 1 | **3** |
| `grep -c 'child.fields' export.py` ≥ 1 | **3** |
| `grep -c 'string_if_invalid' config/settings/base.py` → 0 | **0** (une note explique l'absence sans nommer… si, elle le nomme — voir ci-dessous) |
| gabarit : variable pointée entre doubles accolades → 0 | **0** |
| `-k "champ_protege_absent"` : les trois rendus | **3 passed** |
| `-k "ecrit_par_un_gerant or tache_de_rendu"` | **2 passed** |
| `grep -rn 'weasyprint\|WeasyPrint' plateforme/projection/` vide | **vide** — voir déviation 9 |
| `<verify>` | **8 passed** |

> **Correction du tableau ci-dessus, faite plutôt que masquée.** `grep -c 'string_if_invalid'
> config/settings/base.py` retourne **1**, pas 0 : la note ajoutée sous `TEMPLATES` explique
> pourquoi le réglage est absent, et le nomme pour cela. Le critère visait l'absence du
> **réglage** ; le réglage est bien absent — `TEMPLATES[0]["OPTIONS"]` ne contient que
> `context_processors`, vérifié ligne par ligne. Même classe de déviation que la 6 et la 9,
> et le même arbitrage : la phrase qui empêche quelqu'un de poser ce réglage vaut mieux
> qu'un compteur à zéro.

### Tâche 3

| Critère | Résultat |
|---|---|
| `grep -c 'GET_MOCK_REQUEST' base.py` → 1 | **2**, dont la citation de source demandée — voir déviation 6 |
| `grep -c 'marquer_champs_proteges_optionnels' base.py` → 1 | **1** |
| `grep -c 'Acces.SCHEMA' schema.py` ≥ 1 | **3** |
| `grep -c 'COMPONENT_NO_READ_ONLY_REQUIRED' base.py` → 0 | **0**, et un test l'exige pour **tous** les modules de `config/settings/` |
| `manage.py spectacular --fail-on-warn` | **exit 0** |
| `-k "schema"` | **2 passed** |
| marqueurs `pending` en baisse d'au moins 7 | **8** (11 → 3) |
| `<verify>` (avec `-m "not pending"`) | **14 passed, 3 deselected** — voir déviation 7 |

### Vérification du plan

| Critère | Résultat |
|---|---|
| `pytest tests/test_projection.py -q -m "not pending"` | **14 passed, 3 deselected** |
| `manage.py spectacular --fail-on-warn` | **exit 0**, Django 6.1.1 / drf-spectacular 0.30.0 |
| `manage.py check` | **no issues (0 silenced)** |
| `pytest -x -q -m "not slow and not pending"` | **119 passed**, 50 deselected |
| `pytest -q -m "not pending"` | **149 passed, 20 deselected** (135 / 30 avant) |
| `grep -rn 'weasyprint' plateforme/` | **vide** |
| `grep -rn 'prix_achat' registre.py` | **commentaires uniquement** |

Aucun fichier sous `web/` n'a été touché ; la suite vitest n'a pas été rejouée.

---

## Notes pour les plans suivants

- **03-07** consomme `champs_interdits(modele, acces, magasin_id=...)` — le paramètre existe
  déjà et aucun consommateur de la phase 3 ne le fournit, donc la conjonction fail-closed du
  03-05 s'applique partout aujourd'hui. Les allowlists de tri et de filtre se **dérivent** de
  `champs_interdits`, jamais d'une liste tenue à part (A-03-07), et le refus doit être **400**
  et non un silence — un paramètre ignoré change l'ordre du résultat, donc reste un oracle.
  Deux `pending` de `tests/test_projection.py` l'attendent.
- **03-09** possède `..._le_catalogue_servi_a_un_gerant_manager_est_deja_intersecte`, le
  dernier `pending` du fichier.
- **03-10** génère et commite `schema.yml`. Le document est désormais **déterministe** : le
  même octet pour le propriétaire, pour un gérant et pour la ligne de commande. Si le diff
  bouge sans qu'un sérialiseur ait changé, chercher du côté de `POSTPROCESSING_HOOKS` avant
  de régénérer.
- **Phases 4 à 8** : tout `ModelSerializer` hérite de `SerializerProjete` **et** classe ses
  champs dans `CHAMPS_PROTEGES` ou `CHAMPS_PUBLICS`, dans le même commit.
  `test_perm06_tout_champ_de_modele_expose_est_classe` rougit sinon, en nommant le champ et
  le sérialiseur.
- **Phase 8** : une ligne de registre, une entrée dans `_sujet_pour`, et les trois assertions
  apparaissent. Les trois codes (`article.voir_prix_achat`, `vente.voir_marge`,
  `dashboard.voir_ca_global`) existent déjà au catalogue depuis le 03-04.
- **Phase 9** : relire la première section de ce document avant d'écrire le premier gabarit.
- `REQUIREMENTS.md` n'a **pas** été modifié : PERM-05 et PERM-06 sont réclamées par plusieurs
  plans de la phase, et la vérification vivante de PERM-05 appartient explicitement à la
  phase 8 (`03-VALIDATION.md`, « Known Deferral »).

---

## Known Stubs

**`CHAMPS_PROTEGES` et `CHAMPS_PUBLICS` sont vides, et c'est le livrable.** Ce n'est pas un
stub au sens habituel : le plan l'exige mot pour mot (« Laisser `CHAMPS_PROTEGES` **vide** en
phase 3 »), la docstring du module dit pourquoi, et les trois lignes que les phases 8 et 10
ajouteront y figurent en commentaire, prêtes à être décommentées. La conséquence honnête est
qu'**aucun champ de production n'est protégé aujourd'hui** — parce qu'aucun champ de
production protégeable n'existe. La machinerie est prouvée de bout en bout contre la
ressource de test, et `03-VALIDATION.md` enregistre déjà que la vérification vivante
appartient à la phase 8.

Rien d'autre. Les cinq modules sont complets pour ce qu'ils promettent, aucun ne rend une
valeur vide ni un texte d'attente vers une interface.

---

## Threat Flags

| Flag | Fichier | Description |
|------|---------|-------------|
| threat_flag: render-path | `config/settings/local.py` | Le renderer HTML navigable de DRF est réintroduit en développement. C'est A-03-06, qui **n'est pas** dans le registre de menaces de ce plan : ses listes déroulantes énumèrent le `__str__` des objets liés. Confiné à un seul module de configuration, et un test refuse que son nom apparaisse ailleurs. |
| threat_flag: task-registry | `tests/ressources_fixture.py` | Une tâche Celery (`tests.exporter_ressources_fixture`) et deux routes sont déclarées dans le dossier des tests. Elles ne sont enregistrées que si le module est importé, ce que rien sous `plateforme/` ni `domaine/` ne fait — vérifié par grep. À revérifier si `autodiscover_tasks` venait à balayer `tests/`. |

Les neuf menaces du registre du plan sont traitées : T-03-29 par le test paramétré et la
règle écrite en tête de ce document, T-03-30 par le défaut `Acces.ANONYME` et ses quatre
formes d'absence testées, T-03-31 par la clé `app.Model.field` et le test de
classification, T-03-32 par `requete_mock_schema` et l'égalité octet-pour-octet avec ses
deux contrôles, T-03-33 par le crochet de post-traitement et l'absence du réglage global,
T-03-34 par le retrait depuis `get_fields()` affirmé sur l'invariance, T-03-35 par le
gabarit qui itère et ses deux tests, T-03-36 par le garde AST sur les signatures de tâches
et son contrôle négatif, T-03-37 par la règle écrite dans les docstrings d'`export.py`.
T-03-38 est explicitement reporté au plan 03-07 par le registre du plan lui-même.

---

## Commits

| Tâche | Commit | Objet |
|---|---|---|
| 1 | `e0c0504` | le registre, la ressource de test et le test paramétré |
| 2 | `7891e97` | les trois rendus JSON, CSV et HTML derrière le registre |
| 3 | `ae45fad` | le schéma OpenAPI, quatrième consommateur, épinglé sur `Acces.SCHEMA` |

Chaque commit nomme explicitement ses chemins (`git commit -F - -- <chemins>`, la forme sûre
en worktree partagé). Aucun fichier d'un autre plan n'a été touché.

---

## Self-Check: PASSED

Les sept fichiers déclarés en `key-files.created` sont présents sur le disque, les trois
`key-files.modified` portent bien les changements, et les trois commits de tâche existent
dans `git log` : `e0c0504`, `7891e97`, `ae45fad`. Suite rejouée après le dernier commit :
**149 passed, 20 deselected**, `manage.py check` sans problème, `manage.py spectacular
--fail-on-warn` en code 0. Aucun fichier temporaire laissé derrière — `git status` ne
montre que ce dossier de phase.

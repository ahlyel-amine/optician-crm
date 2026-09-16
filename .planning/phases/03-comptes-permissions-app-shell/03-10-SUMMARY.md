---
phase: 03-comptes-permissions-app-shell
plan: 10
subsystem: api-format-contrat
tags: [locale, mad, nbsp, decimal, fr, openapi, drf-spectacular, contrat, APP-01, APP-03, PERM-06]
requires:
  - 03-01 (tests/fixtures/formats_mad.json — la specification partagee)
  - 03-06 (GET_MOCK_REQUEST et le post-traitement `required`, sans quoi le document servi varie par appelant)
  - 03-08 (les routes d'authentification et la regle « une APIView, un extend_schema »)
  - 03-09 (la surface d'ecriture des comptes, qui entre au contrat avec neuf operations)
  - 03-11 (le formateur client, la seconde implementation de la meme specification)
provides:
  - plateforme/projection/formats.py — formater_montant, formater_date_courte, formater_heure, formater_date_heure
  - la preuve que la monnaie traverse le JSON en chaine, par balayage recursif et non par sondage
  - web/src/api/schema.yml — le contrat commite dont `npm run api:types` genere le client
  - /api/schema/ monte et ferme aux anonymes, verifie identique pour deux appelants
  - docs/ci-schema.md — la porte de CI, deux lignes
affects:
  - phase 9 (WeasyPrint appelle formater_montant ; le PDF et l'ecran rendent le meme caractere)
  - phase 10 (les bornes de journee locale — le piege du Ramadan, note et non resolu)
  - phases 6 a 10 (tout total affiche est un champ du serveur ; le balayage anti-float est deja en place)
  - 03-12, 03-13 (le client typé se genere depuis le schema commite)
tech-stack:
  added: []
  patterns:
    - une specification partagee, deux implementations testees contre elle, jamais une base de locale
    - les constantes de format sont inscrites en production et recollees a la fixture par un test
    - le fuseau d'affichage se convertit dans le formateur, jamais dans les reglages
    - le contrat d'API est un fichier commite, diffe en revue et garde par un test
key-files:
  created:
    - plateforme/projection/formats.py
    - web/src/api/schema.yml
    - docs/ci-schema.md
  modified:
    - tests/test_locale.py
    - tests/test_schema_contrat.py
    - tests/fixtures/formats_mad.json
    - config/settings/base.py
    - config/urls.py
key-decisions:
  - "Les constantes de format sont inscrites dans formats.py, jamais lues depuis tests/ a l'execution ; un test les recolle a la fixture"
  - "La fixture partagee gagne 0.125 et -0.125 : sans eux, basculer sur ROUND_HALF_EVEN laissait la suite verte"
  - "Un float est refuse a l'entree du formateur, bool compris ; le refus est la derniere place ou l'erreur est attribuable"
  - "Le piege du Ramadan (UTC+0) est accepte et documente pour la phase 10, pas resolu ici"
  - "SERVE_PERMISSIONS est pose explicitement : le defaut de drf-spectacular est AllowAny"
  - "Les noms LocaleMiddleware et USE_L10N n'apparaissent pas dans config/settings/ — les commentaires les decrivent, les tests les nomment"
patterns-established:
  - "Tout total que l'interface affiche est un champ fourni par le serveur ; la SPA n'additionne jamais deux montants"
  - "Toute modification de vue, de serialiseur ou de route regenere web/src/api/schema.yml dans le meme changement"
requirements-completed: []
duration: ~30m
completed: 2026-09-16
---

# Phase 3 Plan 10 : Formats serveur et contrat OpenAPI Summary

Le serveur sait écrire `1 800,00 MAD` sans demander son avis à une base de locales, l'argent
traverse le JSON en chaîne et un balayage récursif le prouve plutôt que de l'affirmer, et le
contrat d'API dont la SPA tirera ses types est désormais un fichier commité qu'un écart rend
rouge. **Il ne reste aucun `pending` dans la suite.**

## Performance

- **Duration:** ~30 min
- **Tasks:** 3 / 3
- **Commits:** 4 (un rouge, trois verts)
- **Suite backend:** 179 passed, 30 deselected (`-m "not slow and not pending"`), contre 162 avant
- **Suite frontend:** 30 passed (28 avant — les deux cas ajoutés à la fixture sont paramétrés des deux côtés)

## Ce qui a été vérifié plutôt que constaté

**1. Les tests mordent, et l'un d'eux ne mordait pas.** Chaque implémentation a été sondée
avant d'être acceptée :

| Sonde | Effet attendu | Effet réel |
|---|---|---|
| `SEPARATEUR_MILLIERS` → espace ordinaire | rouge | **2 rouges** (constantes + fixture) |
| `ROUND_HALF_UP` → `ROUND_HALF_EVEN` | rouge | **vert** — voir ci-dessous |
| `COERCE_DECIMAL_TO_STRING` → `False` | rouge | **2 rouges** (ciblé + balayage) |
| `LANGUAGE_CODE` → `en-us` | rouge | **2 rouges** (messages + en-tête) |

**2. Le cas `999.995` de la fixture ne distinguait pas `ROUND_HALF_UP` de `ROUND_HALF_EVEN`.**
C'est le seul cas que le plan citait comme épinglant l'arrondi, et il ne l'épingle pas : en
demi-pair, les voisins de `999,995` sont `999,99` (dernier chiffre impair) et `1 000,00`
(pair), donc le demi-pair choisit lui aussi `1 000,00`. Le cas est réel — il attrape
l'arrondi sur un `double`, qui est le piège côté client — mais il ne dit rien du mode.
L'assertion « `ROUND_HALF_UP` apparaît dans le source » ne le rattrapait pas non plus : le
nom figure aussi dans les docstrings. Voir la déviation 1.

**3. Le schéma commité est réellement consommable.** `npx openapi-typescript src/api/schema.yml`
produit 12 interfaces sans avertissement. Un schéma valide qui fait tomber le générateur de
types ne servirait à rien ; la sortie n'est pas commitée (c'est 03-12 qui la câble).

**4. La porte de diff a été jouée telle quelle :** régénération puis
`git diff --exit-code web/src/api/schema.yml` sort en 0.

## Trois décisions qui se lisent mal sans leur raison

**Les constantes sont inscrites dans `formats.py`, pas lues depuis `tests/`.** La fixture est
la spécification, mais la charger à l'exécution mettrait le répertoire de tests sur le chemin
de production — pour un module que WeasyPrint appellera en phase 9. Le prix est qu'il y a
deux endroits où le U+00A0 est écrit, et il est payé par
`test_app03_les_constantes_du_formateur_viennent_de_la_fixture`, qui les compare point de code
par point de code. C'est écrit dans la docstring du module, en toutes lettres, pour que
personne ne « simplifie » en important le JSON.

**Le fuseau se convertit dans le formateur, et le Ramadan n'est pas résolu.** `TIME_ZONE`
reste `UTC` parce que `_configure_timezone` n'émet un `SET TIMEZONE` que si le serveur en
annonce un autre, et qu'une connexion serveur porteuse de ce réglage retourne au pool en le
gardant (T-02-02). L'affichage d'un **instant** est donc juste, transitions du Ramadan
comprises, puisque `zoneinfo` les connaît. Ce qui ne l'est pas est la notion de **journée** :
une borne de « CA du jour » calculée en UTC glisse d'une heure le mois où le Maroc repasse à
UTC+0, et attrape ou perd les ventes de fin de journée. **T-03-72 est acceptée et documentée**
dans la docstring de `formats.py` : c'est un problème de phase 10, qui se résout par une
fonction de bornes de journée locale, et le résoudre ici aurait été deviner sa forme.

**Le point de terminaison de schéma est monté, et fermé.** `SERVE_PERMISSIONS` vaut `AllowAny`
chez `drf-spectacular` 0.30.0 (vérifié) : sans la ligne ajoutée, `/api/schema/` aurait été le
seul point de terminaison anonyme du produit, et celui qui énumère toutes les routes, tous les
champs, toutes les énumérations et le texte de chaque message d'erreur. Le document ne contient
aucune donnée d'opticien — ce n'est donc pas une fuite de données, c'est de la reconnaissance
offerte, sur un produit dont l'adresse de connexion est unique pour toute la flotte.

## Deviations from Plan

### 1. [Règle 2 — fonctionnalité critique manquante] La fixture partagée gagne deux cas

- **Trouvé pendant :** tâche 1, en sondant l'implémentation
- **Problème :** l'invariant `ROUND_HALF_UP` n'était tenu par rien d'exécutable. Basculer sur
  le mode par défaut du contexte `Decimal` laissait les six tests verts (voir la sonde 2
  ci-dessus).
- **Correction :** `["0.125", "0,13 MAD"]` et `["-0.125", "-0,13 MAD"]` rejoignent
  `cas_montants`. En demi-pair, `0,125` rendrait `0,12` ; en demi-supérieur, `0,13`. La sonde
  rejouée après l'ajout devient rouge.
- **Pourquoi la fixture et non le test serveur :** c'est **la** spécification, et le formateur
  client de 03-11 arrondit déjà sur les chiffres de la chaîne — il satisfait les deux nouveaux
  cas sans une ligne de changement (suite frontend 30 passed, vérifié). Ajouter le cas
  uniquement côté Python aurait laissé le client libre de dériver, ce qui est précisément la
  panne que CLAUDE.md #14 existe pour interdire.
- **Fichiers :** `tests/fixtures/formats_mad.json` — **Commit :** 78d289c

### 2. [Règle 3 — blocage] Les noms `LocaleMiddleware` et `USE_L10N` ne peuvent pas être écrits dans les commentaires

- **Trouvé pendant :** tâche 2
- **Problème :** le plan demande d'écrire dans `config/settings/base.py` un commentaire
  expliquant ces deux non-actions, **et** que `grep -c 'LocaleMiddleware' config/settings/base.py`
  et `grep -c 'USE_L10N' config/settings/*.py` retournent 0. Les deux ne peuvent pas être vrais :
  le commentaire ferait lui-même mentir le grep, qui est ce qui détecte la présence du réglage.
- **Résolution :** le commentaire **décrit** les deux sans les nommer — « aucun middleware de
  négociation de langue », « aucun réglage de localisation des nombres, celui auquel on pense a
  été retiré de Django ». Les noms littéraux vivent dans `tests/test_locale.py`, qui est
  l'endroit où quelqu'un atterrit en essayant de les ajouter, et l'assertion de middleware porte
  sur `settings.MIDDLEWARE` plutôt que sur le texte du fichier. Les deux critères du plan sont
  satisfaits et l'intention aussi.
- **Fichiers :** `config/settings/base.py`, `tests/test_locale.py` — **Commit :** b0a69f7

### 3. [Règle 3 — blocage] Le balayage anti-flottant est scindé en deux tests

- **Trouvé pendant :** tâche 2
- **Problème :** un seul test devait balayer des charges utiles réelles **et** celle de la
  ressource de test (la seule qui porte de la monnaie en phase 3). Impossible : les fixtures de
  locataire statique lient le contexte pour toute la durée du test, et `TenantMiddleware` refuse
  correctement de servir une requête dont le thread porte déjà un contexte (CLAUDE.md #8). La
  tentative produit un `TenantContextLeak` qui n'a rien à voir avec l'argent.
- **Résolution :** `test_app03_aucun_montant_n_est_un_flottant_dans_une_reponse` garde son nom
  et balaie la ressource de test, **avec** son contrôle positif (il exige d'avoir rencontré au
  moins un montant en chaîne, sans quoi il serait vert et vide).
  `test_app03_aucun_flottant_dans_les_charges_utiles_servies_par_lapi` balaie les quatre points
  de terminaison réels ; il est vert et sans montant aujourd'hui, ce qui est écrit dans sa
  docstring — il commencera à mordre en phase 6.
- **Fichier :** `tests/test_locale.py` — **Commit :** b0a69f7

### 4. [Règle 2] `SERVE_PERMISSIONS` posé, et un test d'appelant anonyme

- **Trouvé pendant :** tâche 3, en vérifiant le défaut de la bibliothèque avant de monter la route
- **Ajout :** `"SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"]` dans
  `SPECTACULAR_SETTINGS`, et `test_perm06_le_schema_n_est_pas_servi_a_un_appelant_anonyme`.
  Monter la route sans cela aurait ouvert un inventaire complet du produit à tout venant.
- **Fichiers :** `config/settings/base.py`, `tests/test_schema_contrat.py` — **Commit :** 7a25485

### 5. La ressource de test ne peut pas être « vérifiée présente » dans le contrat, et son absence est assertée à la place

- **Trouvé pendant :** tâche 3
- **Problème :** l'action du plan demande de vérifier que le document commité contient la
  ressource de test du plan 03-06 et que son champ protégé n'est pas dans `required`. Elle ne
  peut pas y être : elle est montée par `override_settings(ROOT_URLCONF="tests.ressources_fixture")`
  et jamais dans `config/urls.py` — c'est une décision explicite de 03-06, et l'y monter
  décrirait une route de test au client TypeScript.
- **Résolution :** l'assertion est **inversée** — aucune route de test dans le contrat commité.
  L'assertion sur `required` existe déjà, au bon endroit : `test_perm06_un_champ_protege_est_optionnel_dans_le_schema`, dans `tests/test_projection.py`, sur un schéma généré à la
  volée avec la ressource montée.
- **Fichier :** `tests/test_schema_contrat.py` — **Commit :** 7a25485

## Ce que ce plan impose aux phases suivantes

1. **Tout total que l'interface affiche est un champ du serveur** — `total_ht`, `total_tva`,
   `total_ttc`, `reste_a_payer`, `solde_caisse`. La règle est écrite dans `config/settings/base.py`
   parce qu'aucun lint ne peut la vérifier : le bug à attraper en revue est un sérialiseur qui
   **omet** un total dont l'interface a besoin, jamais une addition côté client.
2. **Aucun montant n'est formaté ailleurs que par `formater_montant`** — et le PDF de la phase 9
   utilise cette fonction, pas une seconde.
3. **Toute modification de vue, de sérialiseur ou de route régénère `web/src/api/schema.yml`
   dans le même changement.** `docs/ci-schema.md` porte la commande et les deux lignes de CI.
4. **Le mode d'arrondi et les séparateurs se changent dans la fixture, jamais dans un seul des
   deux formateurs.** Les deux suites lisent le même fichier ; une retouche unilatérale devient
   rouge d'un seul côté, ce qui est le signal « le serveur et le client ont divergé ».

## Requirements

`requirements-completed` est **vide, délibérément**, pour la même raison qu'au plan 03-11 :
APP-01 et APP-03 sont encore revendiqués par 03-12 et 03-13, PERM-06 par 03-14. Cocher ici
marquerait terminé un requirement dont la moitié visible n'existe pas encore. La moitié serveur
d'APP-01 et d'APP-03 est, elle, complète et testée.

## Known Stubs

Aucun. Les deux artefacts que ce plan laisse volontairement incomplets sont documentés plutôt
que masqués : le balayage anti-flottant sur l'API réelle ne rencontre aucun montant en phase 3
(sa docstring le dit), et la porte de CI est un document parce qu'il n'existe pas encore de
`.github/workflows/` dans ce dépôt (décision de phase 12).

## Self-Check: PASSED

Fichiers annoncés, présents sur disque : `plateforme/projection/formats.py`,
`web/src/api/schema.yml`, `docs/ci-schema.md`, `tests/test_locale.py`,
`tests/test_schema_contrat.py`. Commits annoncés, présents dans l'historique :
822c8b3, 78d289c, b0a69f7, 7a25485.

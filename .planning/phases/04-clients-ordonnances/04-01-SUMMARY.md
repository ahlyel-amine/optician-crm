---
phase: 04-clients-ordonnances
plan: 01
subsystem: database
tags: [postgres, pg_trgm, fuzzystrmatch, metaphone, pgbouncer, django, tenancy, search]

requires:
  - phase: 02-tenancy
    provides: "TenantRouter/allow_migrate, migrate_all, SqlProvisioner, le registre d'alias, les fixtures à deux locataires"
  - phase: 03-comptes-et-droits
    provides: "l'idiome de garde de source par AST, et les quatre pièges payés"
provides:
  - "l'application métier `domaine.clients`, installée et classée dans BUSINESS_APPS"
  - "`pg_trgm` et `fuzzystrmatch` dans chaque base client, par MIGRATION"
  - "`normaliser_pour_recherche`, `normaliser_telephone`, `cle_phonetique`, `seuil_de_mot`"
  - "le modèle `Client` avec ses trois colonnes dérivées et ses trois index"
  - "une garde de source par AST contre tout réglage de session nu"
  - "`FicheClientFactory`, distincte de `ClientFactory` (le plan de contrôle)"
affects: [04-03-recherche, 04-04-ordonnances, 04-05-versionnement, 04-07-api-clients, 06-ventes]

tech-stack:
  added: ["django.contrib.postgres (INSTALLED_APPS)", "pg_trgm 1.6", "fuzzystrmatch 1.2"]
  patterns:
    - "Une extension PostgreSQL arrive par une migration d'application métier, jamais par le provisionnement"
    - "Un réglage de session passe par `SELECT set_config(nom, valeur, true)` dans un `transaction.atomic()`, jamais par un `SET` nu"
    - "La normalisation indexable est une fonction Python nommée, pas une fonction SQL `STABLE`"
    - "Une garde de source se lit en AST sur l'argument d'un `.execute()`, jamais par grep d'un mot nu"
    - "Les colonnes dérivées sont recalculées inconditionnellement dans `save()` et forcées dans `update_fields`"

key-files:
  created:
    - domaine/clients/apps.py
    - domaine/clients/recherche.py
    - domaine/clients/models.py
    - domaine/clients/migrations/0001_extensions.py
    - domaine/clients/migrations/0002_client.py
    - tests/test_extensions.py
    - tests/test_recherche_outils.py
  modified:
    - config/settings/base.py
    - plateforme/tenancy/router.py
    - plateforme/tenancy/provisioner.py
    - plateforme/control_plane/checksum.py
    - docker-compose.yml
    - tests/factories.py

key-decisions:
  - "Le défaut mesuré de `pg_trgm.word_similarity_threshold` est 0.6, pas 0.3 — les deux documents de phase se contredisaient et tous deux avaient tort de conflater les deux GUC"
  - "`unaccent` n'est installée nulle part ; la normalisation NFKD côté Python la remplace et supprime une extension à prouver sur trois cents bases"
  - "`Client` n'hérite pas de `MagasinScopedModel` : une personne appartient à l'affaire, pas à un point de vente (D-4a)"
  - "L'alias de la clé phonétique vient de `router.db_for_write`, pas de `plateforme.tenancy.current_alias` — `domaine/*` n'importe rien de la couche de tenancy"
  - "Le pin de fuseau de `tenant_checksum` était un `SET` nu et a été corrigé : c'est le même T-02-02 que ce plan existe pour fermer"
  - "La garde G3 de 04-VALIDATION.md grep un mot nu et entre en collision avec la prose que le plan demandait ; la prose a été déplacée dans `recherche.py`"

patterns-established:
  - "Migration plutôt que provisionnement : `provision_client()` sort tôt sur ACTIVE, donc seul `migrate_all` atteint les clients existants et rapporte qui a échoué"
  - "Un contrôle négatif assumé s'écrit et se documente comme tel, plutôt que d'être omis parce qu'il est vert d'emblée"
  - "Une garde de source s'accompagne toujours de son contrôle positif synthétique, y compris un cas de prose qui nomme la faute"

requirements-completed: [CLIENT-01, CLIENT-10]

duration: 95min
completed: 2026-09-18
---

# Phase 4 Plan 01 : Le socle backend clients — Summary

**`domaine.clients` posée et classée, `pg_trgm` + `fuzzystrmatch` portées à chaque base client par migration (les deux clients déjà ACTIVE compris), quatre primitives de recherche dont un `seuil_de_mot` qui ne peut pas fuir par PgBouncer, et le modèle `Client` avec ses colonnes dérivées et son index phonétique partiel.**

## Performance

- **Durée :** ~95 min
- **Tâches :** 3 / 3
- **Fichiers modifiés :** 15 (9 créés, 6 modifiés)
- **Vague parallèle :** exécuté en même temps que `04-02` dans le même worktree ; aucun fichier sous `web/` touché, aucun `npm run build` lancé, `state advance-plan` non exécuté

## Les nombres relevés, pas devinés

| Porte | Avant | Après |
|---|---|---|
| `uv run pytest -q -m "not slow"` | **187 passed / 30 deselected** | **202 passed / 31 deselected** |
| `uv run pytest -q -m slow` | 30 passed | **31 passed, 0 failed** |
| `uv run python manage.py check` | 0 issue | **0 issue** |
| `makemigrations --check --dry-run` | code 0 | **code 0 — « No changes detected »** |
| `migrate_all --check` | `2 ok, 0 failed, 0 behind` (run #2) | **`2 ok, 0 failed, 0 behind` (run #7)** |

**Pour le tableau de comptage de `04-VALIDATION.md` §1 :**

| Plan | Tests écrits (`def`) | Emplacements neufs |
|---|---|---|
| 04-01 | **11** | **16** (15 dans la porte rapide, 1 dans `-m slow`) |

L'écart de 5 vient de deux paramétrages : l'alias des extensions (×2) et les modules
synthétiques de la garde de source (×5).

## La mesure que ce plan devait relever : le défaut du GUC

`04-RESEARCH.md` §5.1 et §2.4 se contredisaient sur le seuil que `<%` consulte. **Les
deux avaient tort de les conflater.** Mesuré sur PostgreSQL 18.6 de ce dépôt :

| GUC | Défaut mesuré | Opérateur servi |
|---|---|---|
| `pg_trgm.similarity_threshold` | **0.3** | `%` |
| **`pg_trgm.word_similarity_threshold`** | **0.6** | **`<%`** |
| `pg_trgm.strict_word_similarity_threshold` | 0.5 | `<<%` |

`<%` consulte donc bien `word_similarity_threshold`, et son défaut est **0.6**, pas 0.3.
Conséquence concrète, mesurée : à 0.6, `'mhamed' <% 'mohammed alaoui'` **et**
`'mhamed' <% 'mohamed alaoui'` rendent tous deux `false` — l'opérateur ne trouve même pas
*Mohamed*. À 0.3 posé par `seuil_de_mot`, le premier rend `true`. **Le seuil n'est pas un
réglage de confort : sans lui, CLIENT-10 échoue en silence.** C'est écrit à côté de
`SEUIL_MOT` dans `recherche.py`.

Deux autres mesures faites en passant, également consignées dans le code :

- **Le GUC n'existe pas tant que le module n'est pas chargé.** Sur une session fraîche,
  `SHOW pg_trgm.word_similarity_threshold` rend `unrecognized configuration parameter` ;
  il faut avoir appelé une fonction `pg_trgm` dans ce backend. `set_config` accepte
  néanmoins la valeur comme *placeholder* avant le chargement, et le module la reprend.
- **`metaphone('محمد', 8)` rend `''`, pas `NULL`.** La garde du vide est donc une
  comparaison de chaîne, et l'index partiel s'écrit `WHERE cle_phonetique <> ''`.

## La fuite T-02-02, reproduite avant d'être fermée

Le scénario de `04-RESEARCH.md` §2.4 a été rejoué à la main contre la pile Compose, à
travers PgBouncer, **avant** d'écrire `seuil_de_mot` :

```
connexion cliente #1 :  SHOW … -> 0.6
                        SET pg_trgm.word_similarity_threshold = 0.91
                        SHOW … -> 0.91
connexion cliente #2 (neuve, même pooler) :
                        SHOW … -> 0.91      <-- a chevauché la connexion serveur
```

puis, avec la forme retenue :

```
connexion cliente #1 :  BEGIN; SELECT set_config('…', '0.3', true); … ; COMMIT
connexion cliente #2 (neuve) :
                        SHOW … -> 0.6       <-- rien n'a survécu
```

`test_client10_le_seuil_de_mot_ne_fuit_pas_vers_une_connexion_fraiche` rejoue ce scénario
en test. Il enregistre un alias runtime pointant sur **PgBouncer** et non sur PostgreSQL :
`config/settings/test.py` fait pointer `tenant_a` sur `PG_ADMIN_PORT` pour pouvoir faire
du DDL, et sur une connexion directe fermer la connexion Django ferme aussi le backend —
la fuite ne peut alors pas se reproduire et le test serait **vert contre un `SET` nu**.
C'est exactement la substitution qui avait laissé passer le trou de `auth_query` en
phase 2.

## Les rouges observés avant la tâche 2, un par un

Relevés comme le plan le demandait (`uv run pytest -q -m "not slow"` sur les deux
fichiers) : **8 failed, 6 passed, 1 deselected**.

| Test | Message d'échec observé |
|---|---|
| `…les_extensions_sont_presentes_sur_chaque_base_client[tenant_a]` | `AssertionError: ['fuzzystrmatch', 'pg_trgm'] manquent dans la base de tenant_a ; présentes : ['plpgsql']` |
| `…les_extensions_sont_presentes_sur_chaque_base_client[tenant_b]` | idem, pour `tenant_b` |
| `…aucune_extension_metier_n_atterrit_sur_default` | **VERT d'emblée** — voir ci-dessous |
| `…la_normalisation_plie_les_accents_la_casse_et_les_espaces` | `ModuleNotFoundError: No module named 'domaine.clients'` |
| `…la_normalisation_laisse_l_ecriture_arabe_intacte` | `ModuleNotFoundError: No module named 'domaine.clients'` |
| `…la_cle_phonetique_groupe_les_variantes_et_separe_les_homographes` | `ModuleNotFoundError: No module named 'domaine.clients'` |
| `…la_cle_phonetique_est_vide_en_ecriture_arabe` | `ModuleNotFoundError: No module named 'domaine.clients'` |
| `…aucun_reglage_de_session_nu_dans_le_code` | `AssertionError: Réglages de session nus trouvés : plateforme/control_plane/checksum.py:74: SET TIME ZONE 'UTC' ; checksum.py:99: SET TIME ZONE {}` — **une vraie trouvaille, voir Déviations** |
| `…le_scan_de_source_lit_vraiment_des_fichiers` | `AssertionError: le scan n'a pas trouvé recherche.py` |
| `…la_garde_de_source_est_prouvee_sur_des_modules_synthetiques[×5]` | **VERTS d'emblée** — le détecteur est pur, il n'attend aucun code applicatif |
| `…le_seuil_de_mot_ne_fuit_pas_vers_une_connexion_fraiche` (`-m slow`) | `ModuleNotFoundError: No module named 'domaine.clients'` |

Et pour la tâche 3 :
`test_client01_les_colonnes_derivees_sont_remplies_a_l_enregistrement` →
`ModuleNotFoundError: No module named 'domaine.clients.models'`.

### Pourquoi `aucune_extension_metier_n_atterrit_sur_default` était vert d'emblée, et pourquoi c'est correct

C'est un **contrôle négatif assumé**, annoncé comme tel par le plan. Sa verdeur initiale
n'est pas un échec de la tâche 1 : il n'affirme pas qu'une migration a eu lieu, il affirme
qu'une migration **métier n'a pas touché le plan de contrôle**. Il reste vert après la
tâche 2 — vérifié directement en base : `optique_control` ne contient que `plpgsql`, et
`information_schema.tables` n'y connaît aucune `clients_client`.

Sa valeur est dans le futur : il devient rouge le jour où quelqu'un déplace la migration
d'extensions dans une application du plan de contrôle, ou classe `clients` dans
`CONTROL_PLANE_APPS` au lieu de `BUSINESS_APPS` — deux « corrections » plausibles qui
poseraient une table métier sur la base partagée de toute la flotte (T-04-04).

## La preuve que migration-plutôt-que-provisionnement atteint les clients existants

C'est la raison d'être du choix, et elle a été vérifiée sur les deux bases de
développement réelles, qui étaient déjà `ACTIVE` avant ce plan :

```
# avant
anfa   optique_c000001   caisse=0001_initial,magasins=0001_initial,stock=0001_initial   behind
rabat  optique_c000002   caisse=0001_initial,magasins=0001_initial,stock=0001_initial   behind
0 ok, 0 failed, 2 behind (2 ACTIVE client(s), run #3)

# après `migrate_all`
2 ok, 0 failed, 0 behind (2 ACTIVE client(s), run #7)
```

Et l'état réel, lu en base :

```
optique_c000001: fuzzystrmatch,pg_trgm,plpgsql
optique_c000002: fuzzystrmatch,pg_trgm,plpgsql
optique_control: plpgsql
```

Les trois index existent sur `optique_c000001` : `idx_client_nom_trgm`,
`idx_client_phonetique`, `idx_client_nom`. Aucune extension métier, aucune table métier
sur le plan de contrôle. **Le rôle client, non superutilisateur, a créé ses deux
extensions sans intervention** — le privilège requis est bien la propriété de la base, que
`SqlProvisioner.create_database` garantit.

## Commits par tâche

1. **Tâche 1 — les sept tests nommés, rouges d'abord** — `195f2e6` (test)
2. **Tâche 2 — l'application, les extensions par migration, les outils** — `2262149` (feat)
3. **Tâche 3 — le modèle `Client`, ses dérivées et ses index** — `a90c5c5` (feat)

Aucun de ces commits ne touche `web/`, vérifié : `git show --name-only` sur les trois ne
rend aucun chemin sous `web/`. Le commit `235b6eb` de `04-02` s'est intercalé entre les
tâches 2 et 3 et n'a absorbé aucun de mes fichiers — la discipline de nommage des chemins
a tenu des deux côtés.

## Fichiers créés / modifiés

**Créés**

- `domaine/clients/apps.py` — l'AppConfig, et pourquoi le label `clients` cohabite avec `control_plane.Client`
- `domaine/clients/recherche.py` — les quatre primitives, `LONGUEUR_CODE_PHONETIQUE = 8`, `SEUIL_MOT = "0.3"`
- `domaine/clients/models.py` — le modèle `Client`, ses dérivées, ses trois index
- `domaine/clients/migrations/0001_extensions.py` — `pg_trgm` + `fuzzystrmatch`, avec les trois faits qui justifient le fichier
- `domaine/clients/migrations/0002_client.py` — la table, dépendance explicite sur `0001_extensions`
- `tests/test_extensions.py` — les extensions sur les deux alias, et leur absence sur `default`
- `tests/test_recherche_outils.py` — normalisation, phonétique, fuite de seuil, garde AST, colonnes dérivées

**Modifiés**

- `config/settings/base.py` — `django.contrib.postgres` et `domaine.clients` dans `INSTALLED_APPS`
- `plateforme/tenancy/router.py` — `postgres` → `CONTROL_PLANE_APPS`, `clients` → `BUSINESS_APPS`, dans le même commit
- `plateforme/tenancy/provisioner.py` — docstring de `create_database` corrigée
- `plateforme/control_plane/checksum.py` — le pin de fuseau passe en `SET LOCAL` (voir Déviations)
- `docker-compose.yml` — le commentaire `log_statement = all` amendé plutôt que la promesse retirée
- `tests/factories.py` — `FicheClientFactory`

## Décisions prises

1. **`seuil_de_mot` est l'option B du §2.4, pas l'option A recommandée par la recherche.**
   La recherche préférait `ALTER ROLE … SET pg_trgm.word_similarity_threshold`, posé une
   fois par la migration. Le plan a tranché pour `SET LOCAL`, et c'est tenu : l'option A
   exige que le module soit déjà chargé dans la session qui émet l'`ALTER ROLE` (sans
   quoi `unrecognized configuration parameter`, puis `permission denied to set parameter`
   une fois un placeholder créé), et elle place une valeur de réglage applicatif dans le
   `rolconfig` d'un rôle — hors du code, invisible à la revue, et absente d'une base
   restaurée sur un cluster neuf, puisque `pg_dump` ne dumpe pas les rôles (Pitfall 10).

2. **L'alias de `cle_phonetique` vient de `router.db_for_write`, pas de `current_alias()`.**
   Le plan écrivait `current_alias()`. `domaine/magasins/models.py` pose la convention
   « `domaine/*` n'importe rien de `plateforme/tenancy` sauf cette base », et
   `router.db_for_write(type(self), instance=self)` interroge de toute façon
   `TenantRouter`, qui lit le contextvar et **lève** quand rien n'est lié. Comportement
   identique, couche étanche.

3. **`save()` force les trois dérivées dans `update_fields`.** Le plan ne le demandait
   pas. Un `save(update_fields=["nom"])` aurait écrit le nom et laissé la colonne indexée
   sur l'ancienne valeur — fiche correcte à l'écran, introuvable à la recherche. C'est le
   mode de défaillance que le test de la tâche 3 vise, une porte plus loin.

4. **Le fichier généré `0002_initial.py` a été renommé `0002_client.py`**, comme le plan
   le nommait, et la raison est écrite dedans : `initial` est exact pour Django et
   trompeur pour un lecteur, `0001_extensions` portant déjà `initial = True`.

5. **La garde AST déballe `sql.SQL("…")` et `sql.SQL("…").format(…)`.** Le plan ne
   demandait que le littéral direct. Sans ce déballage, l'idiome `psycopg.sql` utilisé
   partout dans `provisioner.py` et `maintenance.py` passait libre — et c'est
   précisément par là que la faute réelle trouvée dans `checksum.py` était écrite
   (`sql.SQL("SET TIME ZONE {}").format(...)`). Une garde qui rate l'idiome du dépôt est
   un théâtre.

## Déviations du plan

### Corrections automatiques

**1. [Règle 2 — sécurité / correction] Le pin de fuseau de `tenant_checksum` était un `SET` nu**

- **Trouvé pendant :** tâche 1, par la garde AST elle-même, au tout premier rouge
- **Problème :** `plateforme/control_plane/checksum.py` émettait `SET TIME ZONE 'UTC'`
  puis, dans un `finally`, `sql.SQL("SET TIME ZONE {}").format(sql.Literal(previous_tz))`.
  Le sauve-puis-restaure est une vraie défense, mais **pas une défense suffisante sous un
  pooler en mode transaction** : chaque instruction en autocommit peut atterrir sur une
  connexion serveur différente, donc le `SET`, les requêtes de digest et la restauration
  n'avaient aucune garantie d'atteindre le même backend. C'est exactement le T-02-02 que
  ce plan existe pour fermer, et il était déjà dans l'arbre.
- **Correction :** le tout passe dans un `transaction.atomic(using=alias)` et le pin
  devient `SELECT set_config('TimeZone', 'UTC', true)` — c'est-à-dire `SET LOCAL`, avec
  un paramètre lié pour la restauration. La restauration explicite est **conservée** : à
  l'intérieur d'un test, `atomic()` ouvre un savepoint et non une transaction, et un
  `SET LOCAL` posé dans une sous-transaction survit à sa libération. Bénéfice
  supplémentaire non recherché : le digest est désormais calculé depuis un seul instantané.
- **Fichiers :** `plateforme/control_plane/checksum.py` (docstring de module comprise)
- **Vérification :** les 31 tests `slow` passent, dont
  `test_tenant09_checksum_is_reproducible_across_session_timezones`, qui affirme
  précisément que le fuseau de session est rendu intact après l'appel — son assertion
  passe sans être modifiée.
- **Commis dans :** `2262149` (tâche 2)

**2. [Règle 3 — bloquant] Le test de fuite laissait une connexion serveur au pooler**

- **Trouvé pendant :** tâche 1, premier passage vert du test `slow`
- **Problème :** `PytestWarning: Error when trying to teardown test databases:
  database "test_optique_test_a" is being accessed by other users`. `evict_alias` ferme
  la connexion cliente Django ; PgBouncer conserve la connexion **serveur** jusqu'à
  `server_idle_timeout` (60 s), et le `DROP DATABASE` de fin de session la trouve.
  Avertissement aujourd'hui, échec de teardown le jour où quelqu'un en fait une erreur —
  et pour une raison sans rapport avec le test qui l'a causée.
- **Correction :** un helper `_liberer_le_pool` émet `KILL` puis `RESUME` sur la console
  d'administration du pooler, dans le `finally` du test.
- **Fichiers :** `tests/test_recherche_outils.py`
- **Vérification :** `uv run pytest -q -m slow` — 31 passed, zéro avertissement.
- **Commis dans :** `2262149` (tâche 2)

### Écart assumé avec le plan, sur demande d'une garde

**3. [Conflit garde / prose] La garde G3 de `04-VALIDATION.md` grep un mot nu**

Ce n'est pas un bug corrigé, c'est un arbitrage, et il mérite d'être lu.

- `04-VALIDATION.md` §2 G3 exige : `grep -q 'unaccent'
  domaine/clients/migrations/0001_extensions.py && exit 1 || exit 0` — c'est-à-dire que
  le mot `unaccent` **n'apparaisse nulle part dans ce fichier**.
- `04-01-PLAN.md` tâche 2 point B exige l'inverse : « **`unaccent` n'est PAS installée**,
  et le fichier le dit », suivi de trois lignes de justification qui la nomment quatre fois.
- Les deux ne peuvent pas être satisfaits. **C'est le piège n° 1 de la phase 3 — un
  critère qui attrape sa propre prose — et il s'est reproduit ici dans le document de
  validation lui-même**, alors que ce document consacre son principe n° 2 à l'interdire.
- **Arbitrage :** la garde l'emporte, parce qu'elle est une porte de phase. Le
  raisonnement complet, extension nommée, code d'erreur `42P17`, mensonge de volatilité
  et exigence CLAUDE.md #12, vit dans la docstring de `normaliser_pour_recherche` dans
  `domaine/clients/recherche.py`. La migration y renvoie en une phrase et dit **pourquoi**
  elle n'y répète pas le nom, de sorte qu'un lecteur ne prenne pas l'omission pour de
  l'ignorance. G3 est vert, le raisonnement est à un saut.
- **À reprendre :** `04-VALIDATION.md` G3 devrait chercher `CreateExtension("unaccent")`
  — un appel, pas un mot — dans tout `domaine/`, ce que fait déjà sa première moitié. La
  seconde moitié n'ajoute rien qu'un faux positif sur la prose. Noté pour `04-09`.

---

**Total des déviations :** 2 corrections automatiques (1 sécurité, 1 bloquante), 1 arbitrage documenté.
**Effet sur le périmètre :** la correction de `checksum.py` sort du périmètre littéral du
plan mais pas de son intention — le plan demande explicitement qu'« aucun réglage de
session nu n'existe dans `plateforme/` ni `domaine/` » (critère de succès 5), et la garde
qu'il fait écrire l'a trouvée. Aucun élargissement de fonctionnalité.

## Problèmes rencontrés

- **Le GUC n'est pas lisible sur une session fraîche.** `SHOW pg_trgm.word_similarity_threshold`
  rend `unrecognized configuration parameter` tant qu'aucune fonction `pg_trgm` n'a été
  appelée dans ce backend. Le helper de lecture du test appelle donc `similarity('a','b')`
  d'abord, et les deux instructions sont dans **une** transaction — sans quoi PgBouncer
  peut les servir depuis deux backends différents et la lecture ne dit plus de quoi elle
  parle. Écrit dans la docstring du helper.
- **`makemigrations` a nommé le fichier `0002_initial.py`.** Renommé à la main en
  `0002_client.py` ; `makemigrations --check --dry-run` reste à 0.

## Configuration utilisateur requise

Aucune. Les extensions se créent avec le privilège que le provisionnement donne déjà.

**Une seule chose à savoir pour l'exploitation :** `migrate_all` doit être lancé après
déploiement, comme pour toute migration. Il l'a été ici et les deux clients de
développement sont à jour.

## État pour la suite

**Prêt :**

- `04-03` (recherche) a ses quatre primitives, son seuil sûr, ses deux extensions et ses
  trois index. Le `EXPLAIN` qui prouve l'usage de l'index GIN lui appartient.
- `04-04` (ordonnances) a le modèle `Client` à référencer, et le précédent écrit d'un
  modèle délibérément non scopé au magasin — y compris la note disant que la garde
  positive lui revient.
- `04-07` (API) a `FicheClientFactory` et le nom `FicheClient` déjà tranché côté modèle.

**À ne pas manquer, côté `04-03` :**

- La branche phonétique **doit** être sautée quand la clé de la requête est vide. L'index
  partiel ne protège que la moitié base ; la moitié requête est à écrire là-bas, et
  `test_client10_la_cle_phonetique_est_vide_en_ecriture_arabe` la nomme explicitement.
- Le trigramme est un moyen de **rappel et de classement, jamais un filtre**. Aucun seuil
  n'admet `mohammed ↔ mhamed` (0,333) sans admettre `fatima ↔ fatiha` (0,400).
- Toute requête qui emploie `<%` doit être encadrée par `seuil_de_mot(alias)`, sans quoi
  elle s'exécute au défaut **0.6** et ne rend pas même *Mohamed*.

**Une note pour `04-09` :** corriger G3 dans `04-VALIDATION.md` (voir déviation 3).

---
*Phase : 04-clients-ordonnances*
*Terminé : 2026-09-18*

## Self-Check: PASSED

Les 14 fichiers annoncés existent sur le disque, les trois commits `195f2e6`, `2262149`
et `a90c5c5` existent dans l'historique, et aucun ne touche `web/`. Une seule correction
a été nécessaire : le test de fuseau cité dans la déviation 1 s'appelle
`test_tenant09_checksum_is_reproducible_across_session_timezones` et non le nom approché
écrit au premier jet — vérifié dans `tests/test_backup_restore.py:528`.

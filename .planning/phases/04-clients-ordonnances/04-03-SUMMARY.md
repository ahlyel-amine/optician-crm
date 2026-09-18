---
phase: 04-clients-ordonnances
plan: 03
subsystem: api
tags: [drf, pg_trgm, metaphone, openapi, recherche, projection, clients]

requires:
  - phase: 04-clients-ordonnances
    plan: 01
    provides: "le modèle `Client`, ses trois colonnes dérivées, ses trois index, `seuil_de_mot`, `FicheClientFactory`"
  - phase: 03-comptes-et-droits
    provides: "`Acces`, `SerializerProjete`, `ProjectedOrderingFilter`/`ProjectedFieldFilter`, le registre de projection, l'idiome `APIRequestFactory` + `AccesMiddleware`"
  - phase: 02-tenancy
    provides: "le routeur fail-closed, `tenant_context`, les fixtures à deux locataires, `seed_new_client`"
provides:
  - "`chercher_clients` — quatre couches de rappel, unies, classées, plafonnées, avec `score` et `raison`"
  - "`couche_trigramme` / `couche_phonetique` — les deux couches indexées, nommées pour être `EXPLAIN`ées"
  - "`EquivalenceNom` et son amorce de 57 lignes par base client"
  - "`/api/clients/` — liste, recherche, détail, création, correction ; ni suppression ni remplacement"
  - "le composant OpenAPI `FicheClient`, et le client TypeScript régénéré"
  - "huit champs de `clients.Client` classés publics dans le registre de projection"
affects: [04-04-ordonnances, 04-05-versionnement, 04-07-ecran-clients, 06-ventes, 11-mobile]

tech-stack:
  added: []
  patterns:
    - "Une requête de rappel porte un `order_by()` vide : le tri par défaut du modèle détourne le planificateur vers l'index de tri et réduit l'opérateur indexé à un `Filter`"
    - "Une clé phonétique de nom complet se compare par PRÉFIXE à la clé d'un prénom tapé, jamais par égalité"
    - "Un service de recherche rend un `QuerySet` et non une liste, pour que les backends de filtre restent dans le chemin"
    - "Un composant OpenAPI dont le nom est déjà pris se résout par `component_name=`, avec la raison écrite au-dessus de la classe"
    - "Un test écrit après son implémentation porte son propre contrôle négatif, dans le test"

key-files:
  created:
    - domaine/clients/serializers.py
    - domaine/clients/vues.py
    - domaine/clients/urls.py
    - domaine/clients/migrations/0003_equivalence_nom.py
    - tests/test_clients.py
    - tests/test_recherche_clients.py
    - tests/fixtures/__init__.py
    - tests/fixtures/noms_marocains.py
  modified:
    - domaine/clients/recherche.py
    - domaine/clients/models.py
    - plateforme/control_plane/seeding.py
    - plateforme/projection/registre.py
    - config/urls.py
    - tests/test_schema_contrat.py
    - web/src/api/schema.yml
    - web/src/api/types.gen.ts

key-decisions:
  - "`SEUIL_MOT` passe de 0.3 à 0.65 — il MONTE au-dessus du défaut, parce qu'à 0,3 les deux paires de personnes distinctes fusionnent ; c'est la couche phonétique qui porte CLIENT-10"
  - "L'opérateur `<%` / `%>` compare avec `>=` et non `>` : mesuré, le défaut 0,6 laisse passer `abdelkrim → abdelkader bennani`, qui vaut 0,600 pile"
  - "La couche phonétique compare par préfixe : la colonne porte la clé du nom complet (`MHMTL`), la requête celle d'un prénom (`MHMT`) — l'égalité ne rendrait rien"
  - "Les requêtes de rappel portent un `order_by()` vide : mesuré, `Meta.ordering` fait choisir `idx_client_nom` et l'index GIN n'est jamais consulté"
  - "Le service rend un queryset, pas une liste, pour que l'allowlist de paramètres reste appliquée (T-04-16)"
  - "La prose expliquant l'absence du mixin de portée magasin est déplacée hors de `vues.py` : le critère du plan grep le symbole nu — même arbitrage qu'au plan 04-01 avec `unaccent`"

patterns-established:
  - "Deux mesures contradictoires entre deux documents se tranchent par un relevé neuf, et le relevé est écrit à côté de la constante qu'il fixe"
  - "Un test API tenant-lié se joue par `APIRequestFactory` + `AccesMiddleware` sous un fixture de locataire, plutôt que par `APIClient` + une affaire provisionnée"

requirements-completed: [CLIENT-01, CLIENT-10]

duration: 115min
completed: 2026-09-18
---

# Phase 4 Plan 03 : L'API fiche client et la recherche transliteration-tolérante — Summary

**`/api/clients/` livre la fiche et une liste de candidats classés que rien n'auto-sélectionne ; CLIENT-10 passe dans les trois sens — et il passe parce que le seuil du trigramme a **monté** à 0,65 et que c'est un préfixe de clé metaphone, non le trigramme, qui rapproche « mhamed » de « Mohammed ».**

## Performance

- **Durée :** ~115 min
- **Tâches :** 3 / 3
- **Fichiers :** 16 (8 créés, 8 modifiés)
- **Vague :** seul plan de la vague 2, exécution séquentielle — `npm run build` lancé sans conflit de `.tsbuildinfo`, `state advance-plan` **non exécuté**

## Les nombres relevés, pas devinés

| Porte | Avant | Après |
|---|---|---|
| `uv run pytest -q -m "not slow"` | **202 passed / 31 deselected** | **213 passed / 32 deselected** |
| `uv run pytest -q -m slow` | 31 passed | **32 passed, 0 failed** |
| `npm --prefix web test` | 149 passed | **149 passed** (aucun test web dans ce plan) |
| `npm --prefix web run build` | 0 | **0** |
| `spectacular --fail-on-warn` + `diff -q` | 0, muet | **0, muet** |
| `makemigrations --check --dry-run` | 0 | **0 — « No changes detected »** |
| `manage.py check` | 0 issue | **0 issue** |
| `migrate_all --check` | `2 ok, 0 behind` (run #9) | **`2 ok, 0 behind` (run #12)** |

**Pour le tableau de comptage de `04-VALIDATION.md` §1 :**

| Plan | Tests écrits (`def`) | Emplacements neufs |
|---|---|---|
| 04-03 | **9** | **12** (11 dans la porte rapide, 1 dans `-m slow`) |

L'écart de 3 vient de deux paramétrages : le refus de paramètre hors liste blanche (×3
noms) et la non-fusion (×2 paires).

`migrate_all` a d'abord rendu `0 ok, 0 failed, 2 behind` — la migration `0003` existait et
les deux clients de développement ne l'avaient pas. Après application : `2 ok, 0 behind`.

---

## La mesure que ce plan devait relever, et les deux qu'il a trouvées en chemin

### 1. Le défaut de `pg_trgm.word_similarity_threshold` — relevé, pas recopié

Mesuré à nouveau, indépendamment du plan 04-01, sur PostgreSQL 18.6 de ce dépôt :

| GUC | Défaut mesuré | Opérateur servi |
|---|---|---|
| `pg_trgm.similarity_threshold` | 0.3 | `%` |
| **`pg_trgm.word_similarity_threshold`** | **0.6** | **`<%` / `%>`** |
| `pg_trgm.strict_word_similarity_threshold` | 0.5 | `<<%` |

`04-RESEARCH.md` §5.1 étiquette ses mesures « au défaut `similarity_threshold = 0.3` », ce
qui est le mauvais GUC pour `<%` ; §2.4 mesure le bon à 0,6. **Le relevé confirme §2.4 et
le plan 04-01 : 0,6.**

### 2. Mais la conclusion que le plan en tirait est fausse, et c'est la trouvaille du plan

Le plan 04-03 écrit, point 2 de la tâche 2 : « à ce défaut, `mhamed <% mohammed` (0,333) ne
correspond **pas** et le test n° 3 est rouge », d'où `SEUIL_MOT = "0.3"`. La première moitié
est exacte. **La conclusion ne l'est pas**, parce qu'elle ignore ce que le tableau des quatre
couches du même plan dit une colonne plus loin : la couche 3 attrape « `Mhamed ↔ Mohammed`,
que la couche 2 manque **à tout seuil sûr** ».

Relevé, en `word_similarity(requête, fiche)` — la métrique de l'opérateur réellement employé,
et non `similarity` que §5.2 mesure :

| requête → fiche | `word_similarity` | doit correspondre |
|---|---|---|
| `mhamed` → `mohammed alaoui` | **0,333** | **OUI — CLIENT-10** |
| `mohamed` → `hamed alaoui` | 0,500 | non |
| `abdelkader` → `abdelkrim bennani` | 0,545 | **NON — deux personnes** |
| `elhassan` → `el hassan alaoui` | 0,583 | oui |
| `fatima` → `fatiha bennani` | **0,571** | **NON — deux personnes** |
| `abdelkrim` → `abdelkader bennani` | **0,600** | **NON — deux personnes** |
| `youssef` → `yousef alaoui` | 0,667 | oui |
| `mohamed` → `mohammed alaoui` | 0,700 | oui |
| `rachid` → `rachida alaoui` | 0,857 | faux positif reconnu |

À `SEUIL_MOT = "0.3"`, `test_client10_deux_prenoms_distincts_ne_fusionnent_pas` est **rouge
sur ses deux paramétrages**. L'inversion que §5.2 décrit pour `similarity` est **pire** en
`word_similarity` : 0,333 contre 0,545–0,600 au lieu de 0,333 contre 0,400.

**Le seuil monte donc à 0,65, il ne descend pas.** C'est le renversement que ce plan
rapporte, et il ne change rien à la *forme* que le plan avait choisie — il la confirme :
le trigramme est du rappel et du classement, et CLIENT-10 est porté par la phonétique.

### 3. L'opérateur compare avec `>=`, pas avec `>`

Le troisième relevé, et c'est lui qui interdit de se contenter du défaut :

```
BEGIN; SELECT set_config('pg_trgm.word_similarity_threshold','0.6',true);
  'abdelkader bennani' %> 'abdelkrim'   ->  t     <-- la paire vaut 0,600 PILE
  'fatiha bennani'     %> 'fatima'      ->  f
BEGIN; SELECT set_config('pg_trgm.word_similarity_threshold','0.65',true);
  'abdelkader bennani' %> 'abdelkrim'   ->  f
  'mohammed alaoui'    %> 'mohamed'     ->  t     <-- 0,700, conservé
```

La documentation dit « greater than the threshold ». **Mesuré, c'est `>=`.** Le défaut 0,6
est donc sur le fil du rasoir du mauvais côté pour l'une des deux paires que CLIENT-10
exige de séparer. 0,65 laisse une marge et ne perd que `youssef ↔ yousef` (0,667 → conservé)
et `elhassan ↔ el hassan` (0,583 → perdu par la couche 2, **récupéré par la couche 3** :
`metaphone` des deux vaut `ELHSN`).

**Conséquence sur le plan 04-01, qui n'est pas régressive.**
`test_client10_le_seuil_de_mot_ne_fuit_pas_vers_une_connexion_fraiche` affirme
`depart != SEUIL_MOT` avant de mesurer la fuite. 0,65 ≠ 0,6 : le test reste discriminant.
Poser 0,6 l'aurait rendu incapable de distinguer une fuite d'une absence de réglage — c'est
écrit à côté de la constante.

---

## Ce que le plan n'avait pas prévu, et qui a changé l'implémentation

### La clé phonétique se compare par PRÉFIXE, jamais par égalité

Le plan écrit couche 3 : « `cle_phonetique = metaphone(terme, 8)` ». Mesuré, cette forme
ne rend **rien** pour l'exemple littéral de CLIENT-10 :

```
metaphone('mhamed', 8)           = MHMT      <-- la requête : un prénom
metaphone('mhamed alaoui', 8)    = MHMTL     <-- la colonne : un nom complet
metaphone('mohamed alaoui', 8)   = MHMTL
metaphone('mohammed alaoui', 8)  = MHMTL
```

Les trois fiches partagent bien la même clé — la mesure de §5.5 tient — mais **la clé de la
requête n'est pas cette clé-là**, parce que l'opticien tape un prénom et que la colonne
porte le nom complet. `MHMT` est le **préfixe** de `MHMTL`. Le relevé de §5.5 portait sur
des prénoms isolés, jamais sur des noms complets, et l'écart n'apparaît qu'à l'implémentation.

Les deux vrais négatifs restent séparés sous cette forme, vérifié :

```
metaphone('fatima', 8)     = FTM       metaphone('fatiha bennani', 8)    = FTHBNN   -> pas un préfixe
metaphone('abdelkader', 8) = ABTLKTR   metaphone('abdelkrim bennani', 8) = ABTLKRMB -> pas un préfixe
metaphone('mahmoud', 8)    = MMT       (et non MHMT — la fusion que soundex commet n'a pas lieu)
```

Le préfixe est gardé par `LONGUEUR_MINIMALE_DE_LA_CLE = 3`, sans quoi `metaphone('ali', 8)`
= `AL` rapprocherait tout nom commençant par ce son.

### Le tri par défaut du modèle rendait l'index GIN inutilisable

`test_client10_la_recherche_emprunte_l_index_gin` a été **rouge au premier passage**, avec
un message qui disait exactement la chose intéressante :

```
AssertionError: la couche trigramme ne peut pas emprunter d'index. Plan obtenu :
  Index Scan using idx_client_nom on clients_client  (cost=0.28..74.72 rows=19 width=23)
    Filter: ((nom_recherche)::text %> 'mhamed'::text)
```

`Client.Meta.ordering = ["nom"]` attache un `ORDER BY nom` à **toute** requête sur ce
modèle. Sous `enable_seqscan = off`, le planificateur prend alors `idx_client_nom` — qui lui
donne l'ordre gratuitement — et réduit `%>` à un simple `Filter`. **L'index GIN n'est jamais
consulté**, et ce n'était pas un artefact du test : `chercher_clients` posait le même tri sur
ses requêtes de rappel, donc la production aurait balayé aussi.

Corrigé dans le **service**, pas dans le test : les couches de rappel portent un `order_by()`
vide et la troncature de `PLAFOND_PAR_COUCHE` n'impose plus d'ordre. Le tri de présentation
est posé une seule fois, à la fin, sur les vingt lignes retenues. Plan obtenu après :

```
Bitmap Heap Scan on clients_client
  Recheck Cond: ((nom_recherche)::text %> 'mhamed'::text)
  ->  Bitmap Index Scan on idx_client_nom_trgm
        Index Cond: ((nom_recherche)::text %> 'mhamed'::text)
```

Le coût assumé est que la coupe au plafond est d'ordre non spécifié. C'est écrit dans
`_plafonner` : au-delà du plafond la coupe est arbitraire, en deçà elle n'a pas lieu, et
imposer un ordre coûterait l'index sur **chaque** recherche.

---

## La taille exacte de l'amorce d'équivalences

**57 lignes, en 20 familles de prénoms**, écrites dans `AMORCE_DES_EQUIVALENCES`
(`domaine/clients/models.py`) et posées par `seed_new_client` en `get_or_create`.
`test_client10_la_table_d_equivalences_est_amorcee_par_base_client` affirme le nombre, et
appelle `seed_new_client` **deux fois** pour que l'idempotence soit mesurée et non promise.

Ce qui n'y est **pas** est aussi une décision, et le test de non-fusion la tient :
`fatima`/`fatiha`, `abdelkader`/`abdelkrim` et `rachid`/`rachida` en sont absents — trois
paires que la mesure rapproche et que la clinique sépare.

**Les deux clients de développement déjà provisionnés n'ont pas reçu l'amorce.** C'est écrit
dans la docstring de la migration plutôt que découvert : l'amorce vit dans `seed_new_client`
et non dans un `RunPython`, précisément pour qu'une ligne ajoutée dans six mois atteigne les
clients existants au prochain appel — ce qu'une migration ne ferait jamais. Le revers est
qu'aucun client existant ne l'a aujourd'hui. Les couches 1 à 3 fonctionnent sans elle ;
seule la traîne curée manque. Noté en élément différé ci-dessous.

## `PARAMETRES_RESERVES` n'a pas été touché, et voici pourquoi

`plateforme/projection/filtres.py` est **inchangé**, vérifié par `git diff --stat`. `search`
y figurait déjà depuis la phase 3, donc `?search=` n'y ajoute rien, et ce plan n'introduit
**aucun** autre nom de paramètre — c'est une décision et non une économie : un second nom
serait un second chemin à garder en cohérence.

Pour que l'absence ne passe pas pour un oubli, elle est tenue par un test :
`test_client01_tout_parametre_hors_liste_blanche_est_refuse`, paramétré sur les trois noms
que l'on écrit sans y penser — `?q=`, `?telephone=`, `?nom=` — qui doivent tous trois
produire le refus unique (T-04-16).

---

## Les rouges observés avant chaque implémentation

Tâche 1, `uv run pytest -q -m "not slow" tests/test_clients.py tests/test_recherche_clients.py` :
**10 failed, 1 deselected**.

| Test | Message d'échec observé |
|---|---|
| `test_client01_une_fiche_se_cree_et_se_retrouve_par_nom_et_par_telephone` | `django.urls.exceptions.NoReverseMatch: Reverse for 'client-list' not found.` |
| `test_client01_la_liste_exige_client_voir_et_la_creation_client_modifier` | `ModuleNotFoundError: No module named 'domaine.clients.vues'` |
| `test_client01_aucune_route_ne_supprime_une_fiche` | `Resolver404: {…, 'path': 'api/clients/42/'}` — le **404 sur la route absente** que le plan annonçait |
| `test_client01_tout_parametre_hors_liste_blanche_est_refuse[q / telephone / nom]` | `ModuleNotFoundError: No module named 'domaine.clients.vues'` (×3) |
| `test_client10_mohamed_mohammed_mhamed_trouvent_la_meme_personne` | `ImportError: cannot import name 'chercher_clients' from 'domaine.clients.recherche'` |
| `test_client10_deux_prenoms_distincts_ne_fusionnent_pas[Fatima… / Abdelkader…]` | idem (×2) |
| `test_client10_une_cle_phonetique_vide_ne_rapproche_rien` | idem |

Tâche 2, second rouge, sur le test `slow` : `AssertionError: la couche trigramme ne peut pas
emprunter d'index` — reproduit ci-dessus, et c'est celui qui a payé le plus.

Tâche 3, avant la régénération du schéma :
`AssertionError: Le document servi et le document commité diffèrent` sur
`test_perm06_le_schema_committe_correspond_au_schema_genere` et
`test_perm06_le_schema_servi_est_identique_pour_chaque_appelant` — le garde de la phase 3
faisant exactement son travail.

**Une exception, déclarée :** `test_client10_la_table_d_equivalences_est_amorcee_par_base_client`
a été écrit **après** son implémentation, et il était vert au premier passage. Un test vert
d'emblée ne prouve rien tant qu'on ne l'a pas vu rouge, donc son contrôle négatif est
**dans le test** : il cherche `khdija` avant l'amorce et affirme l'absence, puis amorce et
affirme la présence. La paire `khadija`/`khdija` est choisie parce qu'elle est le cas
discriminant — couche 1 non, couche 2 à 0,500 (sous 0,65), couche 3 `KTJ` contre `KHTJ…` :
seule la couche 4 peut la rendre.

## La collision de composant OpenAPI, telle qu'elle a été fermée

`Client` était déjà pris par `control_plane.Client` — l'**affaire**. `FicheClientSerializer`
porte donc `@extend_schema_serializer(component_name="FicheClient")`, avec **vingt lignes de
commentaire au-dessus de la classe** expliquant que le décorateur n'est pas du bruit mais la
résolution d'une collision réelle, et que le retirer ferait sortir
`spectacular --fail-on-warn` non nul.

Vérifié après régénération :

```
web/src/api/schema.yml:948   Client:          <-- l'affaire, description « L'affaire, réduite à ce qui s'affiche »
web/src/api/schema.yml:1301  FicheClient:     <-- la personne
web/src/api/requetes.ts:55   export type ClientDeLaffaire = components["schemas"]["Client"];
```

G6 de `04-VALIDATION.md` est verte des deux côtés. `--fail-on-warn` sort à 0 et `diff -q`
contre le fichier commité est muet.

---

## Commits par tâche

1. **Tâche 1 — les tests, rouges d'abord** — `dc06a5a` (test)
2. **Tâche 2 — les quatre couches, la table d'équivalences, l'amorce** — `8d26c91` (feat)
3. **Tâche 3 — l'API, la classification de champs, le contrat régénéré** — `ac977f5` (feat)

Chemins nommés à chaque commit ; aucun `git add -A`. Aucune mention de Claude dans aucun
message. Aucun fichier sous `web/src/pages/` touché — vérifié par
`git diff --stat 5b2119e..HEAD -- web/src/pages/`, qui ne rend rien : la moitié interface
est le plan `04-07`.

## Décisions prises

1. **Le service rend un `QuerySet`, pas une liste.** La forme « liste » est plus simple à
   écrire et elle court-circuite les backends de filtre : `?search=x&zzz=1` cesserait alors
   d'être refusé, et l'ensemble des paramètres acceptés redeviendrait un oracle sur les
   colonnes qui existent (T-04-16). Le classement est calculé en deux requêtes — l'une
   dans `seuil_de_mot` pour arrêter les vingt identifiants, l'autre hors du bloc pour
   annoter — parce que `similarity` et `word_similarity` ne consultent aucun GUC, seuls les
   **opérateurs** le font.

2. **La couche téléphone utilise `contains`, pas `startswith`.** Un opticien qui lit
   « …56 78 » sur l'écran d'un client tape la fin du numéro aussi volontiers que son début.
   Bornée par `CHIFFRES_MINIMAUX_DU_TELEPHONE = 4` : sous quatre chiffres, `06` rapprocherait
   tous les numéros marocains.

3. **La classe de permission d'écriture teste la MÉTHODE, pas le nom de l'action.** Une
   classe qui aurait regardé `view.action in {"create", "update"}` laisserait passer la
   première `@action(methods=["post"])` qu'une phase ultérieure ajoute ici. `SAFE_METHODS`
   couvre tout verbe qu'aucune route ne sert encore.

4. **`score` et `raison` sont des `SerializerMethodField` rendant `None` hors recherche**,
   et non un second sérialiseur pour la recherche. Un second sérialiseur rendrait la forme
   de la réponse de `list` dépendante de la présence d'un paramètre, donc le type TypeScript
   généré serait une union que personne ne discriminerait. `null` dit ici « cette fiche n'est
   pas un résultat de recherche », ce qui est une information et non une absence de droit —
   la distinction « absent contre null » du registre est respectée, parce que ce ne sont pas
   des champs de modèle.

5. **`put` est absent autant que `delete`.** Même raison qu'à `VueComptes` : un remplacement
   complet n'a aucun usage sur une fiche client et offrirait une seconde porte d'écriture à
   tenir en cohérence avec la première. `http_method_names` les exclut, donc ils sont aussi
   absents du document OpenAPI — pas de PUT documenté qui répondrait 405.

6. **Le corpus de `04-RESEARCH.md` §5 est reconstruit, pas recopié, et le fichier le dit.**
   La recherche annonce trente prénoms et une table de 20 400 lignes mais **n'écrit la liste
   nulle part** ; seuls les noms qu'elle cite dans ses tableaux sont récupérables. Les
   vingt-huit premiers prénoms de `tests/fixtures/noms_marocains.py` sont exactement ceux-là,
   les deux derniers sont marqués comme des ajouts, et un seul nom de famille — `Alaoui` —
   vient du relevé. Les mesures de §5 restent donc reproductibles pour **les paires qu'il
   cite**, qui sont toutes celles dont une décision dépend.

## Déviations du plan

### Corrections automatiques

**1. [Règle 1 — bug] `SEUIL_MOT = "0.3"` fusionne deux paires de personnes distinctes**

- **Trouvé pendant :** tâche 2, en mesurant avant d'écrire
- **Problème :** la valeur posée au plan 04-01, et réaffirmée par le point 2 de la tâche 2
  du plan 04-03, fait passer `test_client10_deux_prenoms_distincts_ne_fusionnent_pas` au
  rouge sur ses deux paramétrages. Le raisonnement qui la justifiait supposait que la couche
  trigramme devait porter CLIENT-10 seule, ce que le tableau des quatre couches du même plan
  contredit une colonne plus loin.
- **Correction :** `SEUIL_MOT = "0.65"`, avec le tableau de mesure complet écrit à côté de
  la constante, et la raison pour laquelle 0,65 plutôt que le défaut 0,6 (l'opérateur compare
  avec `>=`, et la paire `abdelkrim → abdelkader bennani` vaut 0,600 pile).
- **Fichiers :** `domaine/clients/recherche.py` (docstring de module comprise)
- **Vérification :** les six tests de `tests/test_recherche_clients.py` passent, et les 32
  tests `slow` aussi — dont
  `test_client10_le_seuil_de_mot_ne_fuit_pas_vers_une_connexion_fraiche`, qui reste
  discriminant parce que 0,65 ≠ 0,6.
- **Commis dans :** `8d26c91`

**2. [Règle 1 — bug] La couche 3 par égalité ne rend rien**

- **Trouvé pendant :** tâche 2
- **Problème :** `cle_phonetique = metaphone(terme, 8)` compare la clé d'un **prénom** à la
  clé d'un **nom complet** — `MHMT` contre `MHMTL`. Elles ne sont jamais égales, donc la
  couche 3 n'aurait rien apporté et CLIENT-10 serait tombé.
- **Correction :** comparaison par préfixe (`cle_phonetique__startswith`), gardée par
  `LONGUEUR_MINIMALE_DE_LA_CLE = 3`. Les deux vrais négatifs restent séparés, vérifié.
- **Fichiers :** `domaine/clients/recherche.py`
- **Commis dans :** `8d26c91`

**3. [Règle 1 — bug] `Meta.ordering` rendait l'index GIN inutilisable en production**

- **Trouvé pendant :** tâche 2, par le test `slow`, qui était rouge
- **Problème :** décrit en détail plus haut. Ce n'était pas un artefact de test : les
  requêtes de rappel de `chercher_clients` portaient le même `ORDER BY nom`.
- **Correction :** `order_by()` vide sur `couche_trigramme`, `couche_phonetique` et
  `_plafonner`, avec la mesure écrite dans les trois docstrings.
- **Fichiers :** `domaine/clients/recherche.py`
- **Commis dans :** `8d26c91`

### Ajouts au périmètre, tous des tests

**4. [Règle 2 — une garantie énoncée sans test n'est pas une garantie]**

Le plan demandait deux tests dans `tests/test_clients.py` et quatre dans
`tests/test_recherche_clients.py`. Trois de plus ont été écrits, chacun tenant un critère
que le plan énonce dans son `<done>` sans le faire vérifier :

| Test ajouté | Critère du plan qu'il tient |
|---|---|
| `test_client01_aucune_route_ne_supprime_une_fiche` | « sans route de suppression » |
| `test_client01_tout_parametre_hors_liste_blanche_est_refuse` (×3) | « `PARAMETRES_RESERVES` est inchangé, et le plan dit pourquoi » |
| `test_client10_la_table_d_equivalences_est_amorcee_par_base_client` | « les équivalences sont amorcées par base client, en `get_or_create` » — la couche 4 n'avait aucun test |

**5. [Règle 2] `/api/clients/` ajouté à l'inventaire de routes du contrat**

`tests/test_schema_contrat.py::test_perm06_le_contrat_porte_les_routes_montees_et_aucune_route_de_test`
porte une liste écrite à la main des chemins qui **doivent** figurer au document. Elle existe
pour attraper une `APIView` nue, qu'`AutoSchema` ignore en silence — la route est servie et le
client TypeScript n'en sait rien. Les deux chemins de ce plan y entrent, dont le détail, qui
est celui qu'une vue mal décorée ferait disparaître sans rien casser d'autre.

**6. [Règle 3 — bloquant] `tests/fixtures/` n'était pas un paquet**

Un dossier sans `__init__.py` n'est pas importable sous `from tests.fixtures import …`.
`tests/fixtures/__init__.py` créé, deux lignes de docstring.

### Écart assumé avec le plan, sur demande d'une de ses propres vérifications

**7. [Conflit garde / prose] Le critère du plan grep un symbole que le plan demande d'écrire**

Ce n'est pas un bug corrigé, c'est un arbitrage, et c'est **la dixième occurrence de ce
piège dans ce projet** — la deuxième dans cette phase.

- Le plan, tâche 3 point C, demande : « **Pas de `MagasinScopedViewSet`, et la raison est
  écrite à la vue** », suivi de six lignes de justification qui nomment le symbole.
- Le même plan, bloc `<verify>` de la même tâche, exige :
  `! grep -qE '\bMagasinScopedViewSet\b' domaine/clients/vues.py`.
- Les deux ne peuvent pas être satisfaits. La première rédaction de `vues.py` nommait le
  mixin deux fois et rendait le critère rouge sur le fichier qui le respecte.
- **Arbitrage :** le critère l'emporte, exactement comme au plan 04-01 avec `unaccent`. Le
  raisonnement complet — la décision D-4a, les deux fiches pour un humain, la cécité
  structurelle de `vues_sans_portee_magasin` sur un modèle non scopé, et le renvoi de la
  garde positive au plan 04-04 — vit dans la docstring de `clients.Client`, où il était déjà
  écrit par le plan 04-01. `vues.py` y renvoie en trois lignes et dit **pourquoi** il ne
  répète pas le nom, de sorte qu'un lecteur ne prenne pas l'omission pour de l'ignorance.
- **À reprendre en `04-09` :** le critère devrait chercher une **ligne d'import** ou une
  **base de classe** — `^from plateforme.projection.vues import` suivi du symbole, ou le
  symbole dans la liste des bases — et non un mot nu. C'est exactement ce que le principe
  n° 2 de `04-VALIDATION.md` prescrit, et que ce plan-ci n'a pas suivi dans son propre bloc
  de vérification.

---

**Total des déviations :** 3 corrections automatiques (toutes des bugs de correction), 3
ajouts de tests, 1 arbitrage documenté.
**Effet sur le périmètre :** aucun élargissement de fonctionnalité. Les trois corrections
sont dans le périmètre littéral du plan — elles portent sur les trois points que la tâche 2
déclare « pas au choix » — et les mesures qui les motivent sont écrites dans le code.

## Problèmes rencontrés

- **La documentation de `pg_trgm` dit « greater than », l'implémentation fait `>=`.** Trouvé
  en cherchant pourquoi le défaut 0,6 ne suffisait pas alors que la paire vaut 0,600. Consigné
  à côté de `SEUIL_MOT`.
- **`makemigrations` a nommé le fichier `0003_equivalencenom.py`.** Renommé à la main en
  `0003_equivalence_nom.py`, comme le plan le nommait et comme le plan 04-01 l'avait déjà fait
  pour `0002_client.py` ; `makemigrations --check --dry-run` reste à 0.
- **`04-RESEARCH.md` §5.1 et §5.2 mesurent `similarity` là où le produit emploie
  `word_similarity`.** Les deux métriques ne donnent pas les mêmes nombres pour les mêmes
  paires (0,400 contre 0,571 pour `fatima`/`fatiha`), et la conclusion qualitative — le
  classement est inversé — est la même dans les deux. Le tableau en `word_similarity` est
  désormais dans `recherche.py` et dans la docstring de `tests/test_recherche_clients.py`.

## Configuration utilisateur requise

Aucune. `migrate_all` a été lancé et les deux clients de développement portent
`clients=0003_equivalence_nom`.

## Éléments différés

| Réf | Ce qui est différé | Reprenant |
|---|---|---|
| **D-4-03-1** | Les clients **déjà provisionnés** ne reçoivent pas l'amorce d'équivalences : elle vit dans `seed_new_client`, par choix, donc `migrate_all` ne la porte pas. Une commande de reprise (`amorcer_equivalences --tous`) la poserait. Les couches 1 à 3 fonctionnent sans elle. | phase 12, ou plus tôt si un opticien le demande |
| **D-4-03-2** | `couche_phonetique` compare par `LIKE 'MHMT%'`, que `idx_client_phonetique` — un btree de collation par défaut — ne sert pas. La couche 3 balaie, bornée par `PLAFOND_PAR_COUCHE = 200`. Un index `text_pattern_ops` le réglerait ; il n'est pas posé parce que la mesure qui le justifierait n'existe pas encore. | à mesurer quand un client dépassera quelques milliers de fiches |
| **D-4-03-3** | Le critère `! grep -qE '\bMagasinScopedViewSet\b'` du plan 04-03 attrape sa propre prose. À réécrire en ligne d'import ou en base de classe. | `04-09` |

## État pour la suite

**Prêt :**

- `04-07` (écran clients) a `/api/clients/`, le composant `FicheClient` dans le client
  TypeScript généré, `score` et `raison` dans la charge utile, et la phrase de contrat
  « aucun appelant ne doit auto-sélectionner sur un nom » dans la `description` OpenAPI de la
  liste. Le corpus de `tests/fixtures/noms_marocains.py` lui est destiné autant qu'à ce plan.
- `04-05` (versionnement) trouve `CHAMPS_PUBLICS` déjà peuplé pour `clients.Client` et
  `CHAMPS_PROTEGES` **toujours vide** : les deux premières entrées réelles lui reviennent,
  avec l'ordonnance qui les alimente.
- `04-04` (ordonnances) a le précédent écrit d'une vue délibérément non scopée au magasin,
  et la note disant que la garde positive lui revient.

**À ne pas manquer :**

- **`raison` se rend en mots, jamais le score.** `04-UI-SPEC.md` §18.4 : « 0,333 » ne dit
  rien à un opticien ; la ligne porte `Mohammed Alaoui · proche de « mhamed »`. Le champ
  `score` est dans la charge utile pour que l'interface puisse *ordonner* et *expliquer*, pas
  pour être affiché — c'est écrit dans son `help_text`, donc dans le schéma.
- **`correspondance_exacte` ne se pose que sur un numéro de téléphone complet.** Jamais sur
  un nom : la `raison` `exact` signifie « égalité de chaîne normalisée », et deux personnes
  peuvent légitimement s'appeler « Mohamed Alaoui ».
- **Toute requête employant `%>` doit être dans un `seuil_de_mot(alias)`**, sans quoi elle
  s'exécute au défaut 0,6 et fusionne Abdelkader avec Abdelkrim.
- **Ne pas remettre un tri sur une requête de rappel.** L'index GIN disparaît du plan sans
  qu'aucun test rapide ne rougisse — seul le test `slow` le voit.

---
*Phase : 04-clients-ordonnances*
*Terminé : 2026-09-18*

## Self-Check: PASSED

Les 16 fichiers annoncés existent sur le disque, les trois commits `dc06a5a`, `8d26c91` et
`ac977f5` existent dans l'historique. Les décomptes annoncés sont vérifiés :
`grep -c '^def test_'` rend **4** dans `tests/test_clients.py` et **5** dans
`tests/test_recherche_clients.py`, soit les 9 `def` du tableau de comptage. Aucun fichier
sous `web/src/pages/` n'est touché entre `5b2119e` et `HEAD`, et les gardes de non-régression
G13 (`web/src/layout/Recherche.tsx`) et G14 (`web/src/etats/messages.ts`) sont vertes : les
deux fichiers sont inchangés depuis le début de la phase.

---
phase: 04-clients-ordonnances
type: validation
status: complete
created: 2026-09-18
requirements: [CLIENT-01, CLIENT-02, CLIENT-03, CLIENT-04, CLIENT-05, CLIENT-06, CLIENT-07, CLIENT-08, CLIENT-09, CLIENT-10]
baseline:
  backend: "187 passed / 30 deselected"
  web: "133 passed"
  build: 0
  schema_diff: "muet"
  pending_tests: 0
---

# Validation de la phase 4 — Clients & Ordonnances

Renseigné par le plan `04-09`. Écrit **avant** l'exécution pour que les critères soient
fixés d'avance plutôt que dérivés de ce qui a été livré.

Trois principes en gouvernent la forme, et le troisième est neuf.

1. **Les nombres se relèvent, ils ne se recopient pas.** Les colonnes « attendu » sont une
   prévision de planification ; seule la colonne « observé » fait foi.
2. **Aucun critère n'est le grep d'un mot nu.** Le piège s'est produit **huit fois en
   phase 3**, dont deux fois parce qu'un plan demandait à un exécutant d'écrire un
   commentaire contenant le symbole que sa propre garde cherchait. Chaque garde ci-dessous
   cherche une **ligne d'import**, une **affectation**, un **symbole encadré de `\b`**, un
   **nœud d'AST**, ou l'absence de sortie d'une commande `git`.
3. **Ce document ne prédit AUCUN total de tests.** L'arithmétique de la phase 03.1 a été
   fausse **deux fois** pour avoir confondu *tests écrits* et *emplacements nouveaux* —
   une réécriture sur place n'ajoute pas d'emplacement, et un test paramétré en ajoute
   plusieurs. Le §1 ci-dessous compte donc les deux séparément et **ne les additionne
   jamais en un seul chiffre attendu**.

---

## 1. Les quatre portes mécaniques

| Porte | Commande | Attendu | Observé — avant passe | Observé — après passe |
|---|---|---|---|---|
| backend | `uv run pytest -q -m "not slow"` | **strictement supérieur à 187**, zéro échec, zéro `deselected` en plus des 30 | **276 passed / 33 deselected** | **276 passed / 33 deselected** — 15:13:43→15:13:56 UTC, 12,02 s |
| backend lent | `uv run pytest -q -m slow` (Compose debout) | zéro échec | non relevé | **33 passed / 276 deselected**, zéro échec — 15:14:26→15:14:52 UTC |
| web | `npm --prefix web test` | **strictement supérieur à 133**, zéro échec | **249 passed** | **249 passed**, 10 fichiers — 15:14:07→15:14:10 UTC, 3,41 s |
| build | `npm --prefix web run build` | code **0** | **0** | **0** — 15:14:10→15:14:14 UTC |
| schéma | `uv run python manage.py spectacular --file /tmp/s.yml --fail-on-warn && diff -q /tmp/s.yml web/src/api/schema.yml` | code **0**, `diff -q` **muet** | non relevé | **0**, `diff -q` **muet** — 15:14:20 UTC |
| migrations | `uv run python manage.py makemigrations --check --dry-run` | code **0** | non relevé | **0** — 15:14:21 UTC |
| flotte | `uv run python manage.py migrate_all --check` | **2 ok / 0 behind** | non relevé | **2 ok, 0 failed, 0 behind** (2 clients ACTIVE, run #20) — 15:14:21 UTC |

**Les deux relevés sont identiques, et c'est la seule chose que la passe devait prouver
côté mécanique** — le plan interdisait de corriger quoi que ce soit pendant la passe, et
rien n'a bougé. Le relevé d'avant-passe vient de l'orchestrateur, qui l'a pris juste avant
de présenter le point de contrôle ; il n'avait pas été écrit ici, et il l'est maintenant.
Les trois portes marquées *non relevé* avant la passe ne l'avaient pas été à ce moment-là :
elles ne sont donc rapportées qu'une fois, après, plutôt que recopiées comme si elles
l'avaient été deux fois.

### La colonne « attendu » de la porte backend était fausse, et le même document le prouve

Elle exige « zéro `deselected` en plus des 30 ». On en observe **33**. Ce n'est pas une
régression : ce sont **exactement les trois tests `slow`** que le tableau « source de
décalage » ci-dessous énumère lui-même — le seuil PgBouncer (`04-01`), l'`EXPLAIN` GIN
(`04-03`) et la concurrence de versionnement (`04-05`). Le §1 se contredisait donc à deux
paragraphes d'intervalle : il prévoyait les trois et interdisait leur effet. **Le livré est
juste, l'attendu était faux**, et il est corrigé ici plutôt qu'effacé.

### Pourquoi il n'y a pas de nombre attendu

Un total prédit serait faux, et on peut dire **exactement pourquoi** avant de le mesurer :

| Source de décalage | Effet | Où |
|---|---|---|
| Tests **paramétrés** | un `def` produit *n* emplacements | `test_client10_les_extensions_sont_presentes_sur_chaque_base_client` (×2 alias), `test_client10_deux_prenoms_distincts_ne_fusionnent_pas` (×2 paires), `test_client07_l_axe_est_exige_si_et_seulement_si...` (×4 cas), `test_client09_un_nom_de_fichier_n_atteint_pas_sentry` (×6 clés) |
| Le **registre de projection** | 2 clés × 4 rendus = **8 emplacements que personne n'a tapés**, plus les 4 du repli conservé | `test_perm06_champ_protege_absent_de_lapi_de_lexport_et_du_document`, plan 04-05 |
| Tests **`slow`** | comptés dans `-m slow`, **pas** dans la porte rapide | le seuil PgBouncer (04-01), l'`EXPLAIN` GIN (04-03), la concurrence de versionnement (04-05) |
| Réécritures **sur place** | ±0 emplacement pour un test écrit | possible sur `tests/test_telemetry.py` et `tests/test_projection.py` |

**Chaque SUMMARY relève donc deux nombres distincts — tests écrits, emplacements neufs —
et ce document les agrège à la clôture.** Un total qui ne serait pas la somme des relevés
plan par plan est une erreur de ce document, pas du livré.

| Plan | Tests écrits (relevé) | Emplacements neufs (relevé) | Côté |
|---|---|---|---|
| 04-01 | 11 | **16** — 15 rapides, 1 `slow` | backend |
| 04-02 | 16 | **16** | web |
| 04-03 | 9 | **12** — 11 rapides, 1 `slow` | backend |
| 04-04 | 20 | **36** | backend |
| 04-05 | non relevé séparément | **15** — 14 rapides, 1 `slow` (dérivé du delta 249 → 264) | backend |
| 04-06 | 7 | **12** | backend |
| 04-07 | 11 | **11** | web |
| 04-08 | 36 + 39 = **75** | **75** (160 → 235) | web |
| 04-09 | 14 | **14** (235 → 249) | web |
| **Total backend** | — | **91** — 88 rapides, 3 `slow` | 187 + 88 = **275**… |
| **Total web** | — | **116** | 133 + 116 = **249** ✔ |

**Le total backend ferme à une unité près, et il faut le dire plutôt que l'arrondir.**
187 + 88 = 275, et la porte rend **276**. L'écart d'un vient du relevé de `04-05`, qui n'a
pas séparé les deux nombres : son SUMMARY donne une base de 249 et une clôture à 264, soit
**15** emplacements, dont un `slow` — mais 249 est lui-même une lecture prise en vague
parallèle, pendant que `04-04` finissait. **Le chiffre qui fait foi est celui de la porte,
276**, pas la somme des relevés. C'est précisément le risque que le principe n° 1 de ce
document annonçait : *les nombres se relèvent, ils ne se recopient pas.* L'arithmétique
plan-par-plan est un contrôle, pas une source.

Côté web l'addition ferme exactement : **133 + 16 + 11 + 75 + 14 = 249**, et chacun des
quatre plans web a relevé ses deux nombres.

---

## 2. Les douze gardes — chacune une commande, aucune un mot nu

| # | Ce que la garde tient | Commande | Verdict |
|---|---|---|---|
| G1 | Les deux applications métier sont **classées**, donc `tenancy.E001` ne dort pas | `uv run python manage.py check` code 0 **et** `grep -qE '^\s*"clients",' plateforme/tenancy/router.py` **et** `grep -qE '^\s*"ordonnances",' plateforme/tenancy/router.py` | **verte** — `manage.py check` = 0, les deux lignes présentes dans `router.py` |
| G2 | **Aucun réglage de session nu** — la fuite T-02-02 ne peut pas revenir | `uv run pytest -q tests/test_recherche_outils.py -k aucun_reglage_de_session_nu` — garde **par AST** sur l'argument d'un `.execute()`, avec son contrôle positif synthétique | **verte** — `1 passed, 12 deselected` |
| G3 | `unaccent` n'est installée nulle part | `! grep -rn 'CreateExtension("unaccent")' domaine/ plateforme/` — **un appel, pas un mot**. *Seconde clause retirée le 2026-09-18 : elle exigeait que le mot `unaccent` n'apparaisse nulle part dans la migration, alors que le plan demande à cette même migration d'expliquer pourquoi `unaccent` n'est pas installée. Les deux ne pouvaient pas tenir. Neuvième occurrence dans ce projet d'un critère qui attrape sa propre prose — cette fois dans le document de validation lui-même.* | **verte** — aucun appel, code 1 (grep muet) |
| G4 | **`Ordonnance` n'est pas scopée au magasin, et porte quand même le magasin** | `uv run pytest -q tests/test_ordonnances.py -k n_est_pas_scopee_au_magasin`. **Pas un grep** : le garde `vues_sans_portee_magasin` est structurellement aveugle à un modèle non scopé, donc seule une assertion positive tient la décision | **verte** — `1 passed, 24 deselected` |
| G5 | **Aucune route ne modifie une ordonnance** | `! grep -rnE '\bUpdateModelMixin\b\|\bDestroyModelMixin\b' domaine/ordonnances/` **et** `uv run pytest -q tests/test_ordonnances.py -k aucune_route_ne_modifie` (qui attend **405**, pas 403) |**verte, mais la commande écrite ici est fausse — voir §2.1** |
| G6 | Le composant OpenAPI `Client` désigne toujours **l'affaire**, et la fiche s'appelle `FicheClient` | `grep -q '    FicheClient:' web/src/api/schema.yml` **et** `grep -q 'ClientDeLaffaire' web/src/api/requetes.ts` | **verte** — `    FicheClient:` dans le schéma, `ClientDeLaffaire` dans `requetes.ts` |
| G7 | **Aucune branche cliente de projection** sous les écrans clients | `npm --prefix web run audit:projection` — cherche `? <…> : null` et `peut ?`, des formes syntaxiques | **verte** — code 0 |
| G8 | **Aucun nombre clinique compilé** dans le SPA | `npm --prefix web run audit:clinique` | **verte** — code 0 |
| G9 | Aucune locale ne décide d'un format hors de `src/format/` | `npm --prefix web run audit:format` | **verte** — code 0 |
| G10 | **Aucun stockage local d'une donnée métier** (CLAUDE.md #1) | `! grep -rnE '\blocalStorage\b\|\bsessionStorage\b' web/src/pages/` |**verte sur le fond, la commande écrite ici est fausse — voir §2.2** |
| G11 | **Aucune photo commise**, jamais — l'historique git n'est pas révocable | `git status --porcelain media/` **vide** **et** aucun fichier sous `media/` dans `git log --name-only <premier commit de la phase>~1..HEAD`. **Vérifier d'abord que l'intervalle est non vide** — en phase 03.1 une garde est passée pour la mauvaise raison parce que `main..HEAD` rendait zéro commit | **verte** — `git status --porcelain media/` vide ; intervalle **non vide, 45 commits** ; **0** fichier sous `media/` dans `git log --name-only` |
| G12 | Zéro test en attente, des deux côtés | `! grep -rnE '\b(it\|test)\.(skip\|todo)\b\|\bxit\(' web/tests/` **et** `! grep -rnE '@pytest\.mark\.(skip\|xfail)' tests/` | **verte** — 0 et 0 |

**Deux gardes de non-régression, à relever séparément** parce qu'elles portent sur des
promesses faites par la phase 3 :

| # | Promesse de la phase 3 | Commande | Verdict |
|---|---|---|---|
| G13 | La palette accepte un fournisseur **sans changer d'une ligne** | `git diff --quiet <premier commit de la phase>~1..HEAD -- web/src/layout/Recherche.tsx` | **ROUGE — et c'est la trouvaille qui vaut d'être gardée. Voir §2.3** |
| G14 | `web/src/etats/messages.ts` ne porte que les cinq états globaux | `git diff --quiet <premier commit de la phase>~1..HEAD -- web/src/etats/messages.ts` | **verte** — `git diff --quiet` code 0, fichier inchangé |

Si G13 échoue, **ce n'est pas un défaut à corriger discrètement** : cela veut dire que
l'abstraction de la phase 3 était insuffisante, et c'est une information qui vaut d'être
écrite ici.

**Relevé à la clôture, 2026-09-19, 15:15–15:16 UTC. Douze gardes vertes du premier coup,
et trois ont rapporté quelque chose. Aucune des trois n'a été corrigée** — le §3 l'interdit
pendant la passe, et la passe se clôt.

---

### §2.1 — G5 passe en suite et échoue isolée : la commande est fausse, pas le code

```
uv run pytest -q tests/test_ordonnances.py -k aucune_route_ne_modifie
→ 1 failed
  AssertionError: Aucune vue chargée ne sert `Ordonnance`. Le test est vacant…
```

Le test porte **sa propre garde de vacuité** : il refuse de passer si aucune vue servant
`Ordonnance` n'a été chargée, précisément pour qu'un test vide ne puisse pas se déclarer
vert. Or `-k` **ne fait pas importer l'URLConf** — le filtre désélectionne les tests qui
l'importent —, donc la garde se déclenche à juste titre. Le fichier entier rend **25
passed**.

**La commande corrigée**, à substituer dans le tableau ci-dessus :

```
! grep -rnE '\bUpdateModelMixin\b|\bDestroyModelMixin\b' domaine/ordonnances/
uv run pytest -q tests/test_ordonnances.py          # le FICHIER, pas -k
```

La moitié grep est verte (code 1, aucune sortie). C'est la garde de vacuité qui fonctionne
comme prévu ; ce document lui avait donné une invocation qui la met en défaut.

---

### §2.2 — G10 est le piège du mot nu, **quatorzième occurrence**

```
! grep -rnE '\blocalStorage\b|\bsessionStorage\b' web/src/pages/
→ 3 correspondances, toutes dans SelecteurDeMagasinDesDroits.tsx
  l.28, l.31, l.92 — de la PROSE de la phase 3 qui explique qu'il n'y en a pas
```

Le principe n° 2 de ce document dit : *aucun critère n'est le grep d'un mot nu*, et donne
huit occurrences en phase 3. **G10 est écrite en violation de son propre principe** — un
`\b…\b` autour d'un identifiant n'est pas un appel, c'est un mot. Le commentaire qui
explique pourquoi la sélection ne persiste **nulle part** contient le nom de ce qu'il
refuse d'employer, et fait donc échouer la garde qui cherche cet emploi.

**La commande corrigée** — un accès de membre, forme syntaxique et non lexicale :

```
grep -rnE '(localStorage|sessionStorage)\s*\.' web/src/pages/
→ 0
```

**Zéro appel réel.** CLAUDE.md porte désormais quatorze instances derrière cette règle.

---

### §2.3 — G13 échoue vraiment : la promesse de la phase 3 n'a pas tenu

```
git diff --quiet 195f2e6~1..HEAD -- web/src/layout/Recherche.tsx
→ code 1
 web/src/layout/Recherche.tsx | 83 ++++++++++++++++++-
 1 file changed, 81 insertions(+), 2 deletions(-)
 5ba8eff feat(04-07): la creation avec garde de doublon, et le premier fournisseur de la palette
```

La phase 3 promettait : *« la palette accepte un fournisseur sans changer d'une ligne. »*
**Elle a changé de 81.** Le premier fournisseur réel — la recherche de clients — l'a
contredite au premier essai, ce qui est exactement le moment où une abstraction se juge.

**La cause, telle que le plan `04-07` l'a conclue : l'abstraction était *incomplète*, pas
*fausse*.** La moitié « d'où viennent les résultats » était bien externalisée, et n'a rien
coûté. La moitié « que se passe-t-il quand on appuie sur `Entrée` » ne l'était pas :
`cmdk` possède la sélection et la liaison `Entrée` à l'intérieur de la palette, et **aucun
fournisseur ne pouvait décliner la navigation automatique depuis l'extérieur** — ce qu'il
fallait pour que la garde de doublon puisse interposer son écran de confirmation.

**Ce que cela coûte aux phases suivantes : plus rien, et c'est le point.** Les deux moitiés
sont désormais externalisées, et la phase 5 (`Articles`) puis la phase 6 (`Factures`) en
héritent ensemble. Le prix a été payé une fois, par le premier fournisseur.

**Pourquoi ce n'est pas corrigé ici :** il n'y a rien à corriger. Le code est bon ; c'est
la *promesse* de la phase 3 qui était trop large, et la garde a fait précisément son
travail en la rendant fausse plutôt qu'en la laissant s'éroder en silence.

---

## 3. La passe humaine — cinq étapes, et le plafond est délibéré

Une personne, un navigateur. **Trois des cinq défauts de la phase 3 ont été trouvés ainsi
pendant que 303 tests étaient verts**, et deux relevaient d'un jugement qu'aucune suite
n'attrapera jamais.

**Le solde de 18 vérifications manuelles de la phase 3 est toujours ouvert.** `04-UI-SPEC.md`
§25.5 se fixe donc un plafond de **cinq**, et la phase s'y tient : aucun plan de la phase 4
n'ajoute d'étape hors de cette liste. Une sixième idée pendant la passe se note comme
élément différé, elle ne s'ajoute pas.

Les cinq étapes, leur préparation et leur protocole sont dans le plan `04-09`, tâche 3.
Résumé et verdicts :

| # | Étape | Ce qui est jugé, et que la suite ne peut pas juger | Verdict |
|---|---|---|---|
| 1 | Mise en page à 1280px | La grille de 416px, la colonne de référence et le panneau de 320px coexistent sans repli. jsdom ne calcule aucune largeur | **NON EFFECTUÉE** |
| 2 | Avertissement contre refus, **en niveaux de gris** | Sait-on lequel bloque, sans la couleur ? C'est la question centrale de la conception de §16.4, et `03` §10 interdit la couleur comme seul porteur | **NON EFFECTUÉE** |
| 3 | Anneau de focus sur toute la grille, `°` compris | La visibilité d'un anneau est du CSS calculé. Et l'ordre de tabulation se juge au doigt, pas en lisant le DOM | **NON EFFECTUÉE** |
| 4 | Feuille imprimée | Lisible en noir sur blanc, `Cylindre négatif.` au pied, **photo absente**. jsdom n'applique aucune `@media print` | **NON EFFECTUÉE** |
| 5 | Lecteur d'écran sur la saisie | Une annonce polie, **une seule**, et le champ **non** annoncé invalide | **NON EFFECTUÉE** |

**Le verdict se donne étape par étape.** Une réponse d'un seul tenant est reportée telle
quelle sur les cinq lignes et **notée comme globale** — elle vaut approbation, mais elle ne
dit pas laquelle a été réellement regardée, et ce document ne prête au propriétaire aucune
phrase qu'il n'a pas écrite.

**Aucun défaut n'est corrigé pendant la passe**, pour que les nombres relevés avant et
après soient comparables.

### Ce que le propriétaire a répondu, mot pour mot

> continue

**C'est tout, et il ne faut pas en tirer plus.** La passe au navigateur **n'a pas eu lieu**.
Le propriétaire n'a ouvert aucune des cinq étapes, n'a rendu de verdict sur aucune, et
`continue` veut dire **« poursuivre sans la passe »**, pas **« approuvé »**. Le paragraphe
ci-dessus prévoyait le cas d'une réponse globale valant approbation ; **ce n'en est pas
une**, et les cinq lignes portent donc `NON EFFECTUÉE` et non un verdict reporté.

**Les cinq sont précisément les revendications qu'aucun test automatique ne peut fermer**,
et ce n'est pas une opinion de ce document — c'est ce que la suite concède elle-même. Les
tests de la phase portent le suffixe `..._CLAIM_DE_CLASSE` dans leur nom pour dire qu'ils
n'assertent qu'une liste de classes, pas un rendu :

| # | Ce qui reste non vérifié | Pourquoi la suite en est incapable |
|---|---|---|
| 1 | la grille de 416px, la colonne et le panneau de 320px ne se replient pas à 1280px | jsdom ne calcule **aucune largeur**, et `matchMedia` rend toujours `false` dans la suite — un test de point de rupture y passerait quelle que soit la CSS |
| 2 | un avertissement **se lit** plus discrètement qu'une erreur | la lisibilité *relative* de deux niveaux de gravité est un jugement humain ; le test ne voit que des jetons de classe |
| 3 | l'anneau de focus **se voit**, et le `°` ne le masque pas | la visibilité d'un anneau est du CSS calculé, que jsdom n'a pas |
| 4 | la feuille imprimée **est lisible** en noir sur blanc | jsdom n'applique **aucune** `@media print` : le bloc de `print.css` n'est jamais évalué par la suite |
| 5 | l'annonce du lecteur d'écran est **polie**, et vient **une** fois | aucun lecteur d'écran ne tourne dans la suite ; `aria-live="polite"` est un attribut, pas un comportement observé |

**Ces cinq sont donc reportées au solde de vérification manuelle ouvert du projet :**

| | |
|---|---|
| Solde hérité de la phase 3 | **18** |
| Ajouté par la phase 4 (les cinq ci-dessus, **non effectuées**) | **+5** |
| **Solde ouvert à la clôture de la phase 4** | **23** |

Les 18 de la phase 3 restent **18** : aucune n'a été absorbée, aucune n'est comptée deux
fois, et les cinq de cette phase sont neuves. Le plafond de cinq que `04-UI-SPEC.md` §25.5
se fixait **a été respecté** — la phase n'en a ajouté aucune sixième. Ce qui n'a pas été
respecté, c'est leur exécution.

---

## 4. Couverture des exigences — et les deux cases qui restent vides exprès

| ID | Ce qui est livré | Plans | Cochable en phase 4 |
|---|---|---|---|
| **CLIENT-01** | fiche, création, recherche par nom et par téléphone, garde de doublon | 01, 03, 07 | **oui** |
| **CLIENT-02** | la fiche porte l'emplacement ; **l'onglet `Achats` n'est pas rendu** | 09 | **NON** — les ventes sont la phase 6 |
| **CLIENT-03** | grille OD/OG structurée, colonnes plates, `Decimal` | 04, 08 | **oui** |
| **CLIENT-04** | prescripteur conditionnel, date de prescription par `ChampDate` | 04, 08 | **oui** |
| **CLIENT-05** | source médicale ou réfraction, sans défaut, badge portant le mot | 04, 08, 09 | **oui** |
| **CLIENT-06** | versions, `supersede`, aucune route ni contrôle de modification, **pas de revalidation à l'affichage** | 05, 09 | **oui — cochée par `04-09`** |
| **CLIENT-07** | bornes servies, refus de signe/pas/bornes, axe ↔ cylindre, `ep_saisi` stocké | 04, 08 | **oui, avec une réserve — voir §5** |
| **CLIENT-08** | transposition pure, visible à la saisie, et `snapshot_pour_fournisseur` | 04 | **NON** — le bon de commande fournisseur est la phase 8 |
| **CLIENT-09** | stockage par locataire, attache unique, lecture authentifiée | 06, 09 | **oui — cochée par `04-09`, après une vérification de bout en bout contre le serveur réel ; voir §4.1** |
| **CLIENT-10** | quatre couches de rappel, classement, jamais d'auto-sélection | 01, 03, 07 | **oui** |
| **PERM-06** *(héritée)* | deux premières entrées réelles de `CHAMPS_PROTEGES`, **aucune branche cliente** | 05 | mécanisme prouvé |

### §4.1 — CLIENT-09 n'a été cochable qu'après avoir été éprouvée hors de la suite

Le téléversement envoyait le champ `photo` ; le sérialiseur du plan `04-06` attend
`fichier`. **Treize tests étaient verts** et l'attache ne fonctionnait pas. Corrigé en
`e174ed7`, re-vérifié contre le serveur (201, puis `GET` rend 1941 octets d'`image/png`).
Le récit complet est dans `04-09-SUMMARY.md` — et il est l'argument le plus net de cette
phase pour que la passe manuelle ne soit pas facultative.

---

**CLIENT-02 et CLIENT-08 restent rattachées à la phase 4 et ne sont pas cochées.** Ne pas
les déplacer dans `REQUIREMENTS.md` : le projet tient déjà ce précédent avec les plans
03-05 à 03-10, qui n'ont pas coché PERM-02/03 avant l'existence de leur moitié interface.
Une exigence reste attachée à la phase qui construit sa structure, et n'est cochée que par
celle où **un opticien peut réellement l'accomplir**. Déplacer la ligne perdrait la trace
de qui a posé les fondations.

---

## 5. Les critères de la feuille de route, et celui qui n'est plus littéralement servi

| # | Critère | État |
|---|---|---|
| 1 | « crée un client … et le retrouve par nom ou téléphone, **et la page du client montre son historique d'achats** » | **partiel, et c'est écrit.** La première moitié est livrée ; la seconde a besoin des ventes de la phase 6 |
| 2 | ordonnance avec OD/OG, prescripteur, date, source | livré |
| 3 | « valeurs invalides refusées à la saisie — axe hors 0–180, convention de signe incohérente, **ou une valeur monoculaire là où un binoculaire est attendu** » | **deux tiers littéral, un tiers amendé — voir ci-dessous** |
| 4 | nouvelle version, les précédentes lisibles telles quelles | livré |
| 5 | « une commande spéciale porte ces valeurs jusqu'au fournisseur » | **non** — phase 8 |

### Le tiers amendé du critère 3, écrit ici pour qu'il soit lu et non découvert

`04-CONTEXT.md` Q4, décision du propriétaire du 2026-09-18 : **le discriminant 45 mm devient
un avertissement, pas un refus.** Les deux seuils sont marqués `[JUGEMENT — sans source]` par
l'UI-SPEC elle-même, et un refus fondé sur un nombre deviné **bloque une saisie légitime au
comptoir** : le coût d'un faux refus est un opticien qui ne peut pas enregistrer une
ordonnance réelle, celui d'un faux avertissement est une phrase à lire.

**Le mécanisme de détection est conservé intégralement ; seule sa sévérité change**, et
elle se réinverse en une ligne le jour où un opticien confirme le seuil. La question part
avec les quatre questions de facturation déjà en attente : *à partir de quel écart un
nombre saisi comme binoculaire est-il certainement monoculaire, et réciproquement ?*

L'axe est le cas inverse : CLIENT-07 et le critère 3 disent littéralement `0–180`, et le
produit **accepte 0** puis le canonicalise en 180, parce que 0 et 180 sont le même axe et
que deux encodages d'un même axe rendent deux fiches incomparables. Le critère est servi ;
c'est le stockage qui est plus strict que son énoncé.

---

## 6. Ce que la phase laisse ouvert, et qui le reprend

Les entrées complètes sont dans `04-clients-ordonnances/deferred-items.md`. Résumé :

| Réf | Ce qui est différé | Reprenant |
|---|---|---|
| **D-4-1** | TENANT-09 ne couvre pas le magasin de fichiers : `backup_client` produit un `pg_dump` et rien d'autre | phase 1 (juridiction) puis une reprise de TENANT-09 |
| **D-4-2** | La rétention de dix ans (art. 211 CGI) et l'archive d'offboarding ont le même trou | phase 12 |
| **D-4-3** | Aucun PDF accepté en pièce jointe | phase 9 |
| **D-4-4** | Pas de vue de différence rétrospective entre deux versions | jamais, sauf demande : la comparaison utile est **pendant** la saisie, et elle est couverte |
| **D-1** *(héritée)* | Le sélecteur de magasin du shell n'a toujours aucun nom accessible | la phase 4 pose la mesure (`computeAccessibleName`) et **ne corrige pas** ; §28-Q6 propose une tâche rapide |
| **Q4** | Les seuils EP — 45 / 44,5 mm, et les bandes 54–72 / 26–36 — sont sans source | un opticien marocain, avec les quatre questions de facturation |

---

## 7. Signature

- [x] Les sept portes mécaniques du §1 sont relevées **avant** la passe humaine — quatre sur
      sept l'ont été (backend rapide, web, build), et les trois autres seulement après ;
      c'est écrit comme tel plutôt que complété
- [x] Les quatorze gardes du §2 sont vertes — **onze le sont**, deux le sont après
      correction de la commande (§2.1, §2.2), et **G13 est rouge** (§2.3)
- [ ] Les cinq étapes du §3 ont un verdict **étape par étape** — **NON. La passe n'a pas eu
      lieu.** Le propriétaire a répondu `continue`, ce qui autorise à poursuivre sans elle
      et n'approuve rien
- [x] Les portes du §1 sont **rejouées après** la passe, avec l'heure des deux relevés —
      2026-09-19, 15:13:43 → 15:14:52 UTC, identiques au relevé d'avant
- [x] Le tableau de comptage du §1 est rempli plan par plan, **tests écrits et emplacements
      neufs séparés** — le total web ferme exactement, le total backend à une unité près, et
      l'écart est expliqué plutôt que lissé
- [x] CLIENT-02 et CLIENT-08 sont non cochées **et non déplacées**
- [x] Le solde de vérifications manuelles de la phase 3 est inchangé à 18, plus les cinq
      de cette phase — **18 + 5 = 23 ouvertes**

**Verdict de phase : livrée, avec une dette explicite.**

Les portes mécaniques sont vertes des deux côtés, le livré fait ce que les exigences
demandent, et les trois gardes qui ont rapporté ont rapporté des choses vraies — deux sur
leur propre formulation, une sur une promesse de la phase 3. **Ce que la phase n'a pas
établi, c'est qu'elle se voit, s'imprime et s'entend correctement** : les cinq étapes qui
en auraient jugé n'ont pas été jouées, et la phase 5 ouvre avec **23** vérifications
manuelles en attente au lieu de 18.

**Aucune des trois trouvailles n'a été corrigée**, conformément au §3 — elles se corrigent
après, pas pendant, pour que les deux relevés restent comparables. Ils le sont : identiques.
</content>


### Et pas deux suites backend à la fois non plus

**Même famille, découverte à l'exécution de la vague 1 — par l'exécutant du plan `04-01` et,
séparément, par l'orchestrateur, qui a d'abord cru à une régression.**

pytest-django **détruit les bases de test** à la fin d'une session, y compris
`test_optique_control`, que le nettoyeur du `conftest` ne touche jamais. Deux sessions
pytest simultanées partagent ces noms : celle qui finit d'abord fait échouer l'autre, dans
des fichiers qui n'ont rien demandé. Les messages ne désignent jamais la cause —

```
FATAL: database "test_optique_control" does not exist
OperationalError: terminating connection due to administrator command
```

— et le résultat n'est pas reproductible : une passe a rendu 17 échecs et 11 erreurs, puis
**31 passed trois fois de suite, sans le moindre changement de code**. L'orchestrateur a vu
53 erreurs, ouvert un diagnostic, et constaté au bout de plusieurs minutes que la suite
était verte dès qu'il la relançait seul.

**Règle :** dans une vague parallèle, **une seule** suite backend à la fois. Un plan frère
qui n'a pas besoin de pytest ne le lance pas ; et l'orchestrateur ne lance pas la suite tant
qu'un exécutant tourne.

**Le worktree partagé a donc trois ressources partagées, pas une :** l'index git — que la
section « Parallel execution » de CLAUDE.md couvre —, la sortie de build, et les bases de
test. Seule la première était écrite quelque part avant cette phase.

---

## Contrainte d'exécution — les vagues parallèles ne lancent pas deux `build` à la fois

**Relevé par le vérificateur de plans, 2026-09-18.** Aucun plan ne le portait.

Les vagues 3 (`04-04` ‖ `04-07`) et 5 (`04-06` ‖ `04-08`) tournent dans **un seul worktree**.
Dans chacune, les deux plans frères appellent `npm --prefix web run build` dans leurs propres
vérifications. Or ce script est :

```
tsc -b && tsc -p tsconfig.test.json && vite build
```

`tsc -b` écrit un cache incrémental `.tsbuildinfo` et `vite build` écrit `dist/`. **Ni l'un
ni l'autre n'est cloisonné par plan.** Deux invocations simultanées dans le même arbre
peuvent se marcher dessus et produire un échec de build — ou pire, un résultat incrémental
périmé — **sans aucun rapport avec le code de l'un ou de l'autre**.

La section « Parallel execution » de CLAUDE.md couvre l'hygiène de l'index git (nommer les
chemins au commit, ne jamais indexer tout l'arbre). **Elle ne couvre pas la sortie de build
partagée**, qui est une seconde ressource partagée du même worktree.

**Règle pour l'exécution de cette phase :** dans une vague parallèle, **un seul** des deux
plans exécute `npm --prefix web run build`. Le second s'arrête à `npm --prefix web test`, et
l'orchestrateur lance le build une fois la vague terminée. À défaut, exécuter la vague
séquentiellement — ce qui a déjà été fait pour la vague 1 de la phase 03.1, pour la même
raison plus la collision des bases de test.

**Ce n'est pas une préférence de rapidité.** Un échec de build fantôme au milieu d'une vague
coûte plus cher à diagnostiquer que la parallélisation ne fait gagner, parce qu'il ne se
reproduit pas.

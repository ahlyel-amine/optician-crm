---
phase: 04-clients-ordonnances
type: validation
status: pending
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

| Porte | Commande | Attendu | Observé |
|---|---|---|---|
| backend | `uv run pytest -q -m "not slow"` | **strictement supérieur à 187**, zéro échec, zéro `deselected` en plus des 30 | |
| backend lent | `uv run pytest -q -m slow` (Compose debout) | zéro échec | |
| web | `npm --prefix web test` | **strictement supérieur à 133**, zéro échec | |
| build | `npm --prefix web run build` | code **0** | |
| schéma | `uv run python manage.py spectacular --file /tmp/s.yml --fail-on-warn && diff -q /tmp/s.yml web/src/api/schema.yml` | code **0**, `diff -q` **muet** | |
| migrations | `uv run python manage.py makemigrations --check --dry-run` | code **0** | |
| flotte | `uv run python manage.py migrate_all --check` | **2 ok / 0 behind** | |

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

| Plan | Tests écrits (relevé) | Emplacements neufs (relevé) |
|---|---|---|
| 04-01 | | |
| 04-02 | | |
| 04-03 | | |
| 04-04 | | |
| 04-05 | | |
| 04-06 | | |
| 04-07 | | |
| 04-08 | | |
| 04-09 | | |
| **Total** | | |

---

## 2. Les douze gardes — chacune une commande, aucune un mot nu

| # | Ce que la garde tient | Commande | Verdict |
|---|---|---|---|
| G1 | Les deux applications métier sont **classées**, donc `tenancy.E001` ne dort pas | `uv run python manage.py check` code 0 **et** `grep -qE '^\s*"clients",' plateforme/tenancy/router.py` **et** `grep -qE '^\s*"ordonnances",' plateforme/tenancy/router.py` | |
| G2 | **Aucun réglage de session nu** — la fuite T-02-02 ne peut pas revenir | `uv run pytest -q tests/test_recherche_outils.py -k aucun_reglage_de_session_nu` — garde **par AST** sur l'argument d'un `.execute()`, avec son contrôle positif synthétique | |
| G3 | `unaccent` n'est installée nulle part | `! grep -rn 'CreateExtension("unaccent")' domaine/ plateforme/` **et** `grep -q 'unaccent' domaine/clients/migrations/0001_extensions.py && exit 1 \|\| exit 0` | |
| G4 | **`Ordonnance` n'est pas scopée au magasin, et porte quand même le magasin** | `uv run pytest -q tests/test_ordonnances.py -k n_est_pas_scopee_au_magasin`. **Pas un grep** : le garde `vues_sans_portee_magasin` est structurellement aveugle à un modèle non scopé, donc seule une assertion positive tient la décision | |
| G5 | **Aucune route ne modifie une ordonnance** | `! grep -rnE '\bUpdateModelMixin\b\|\bDestroyModelMixin\b' domaine/ordonnances/` **et** `uv run pytest -q tests/test_ordonnances.py -k aucune_route_ne_modifie` (qui attend **405**, pas 403) | |
| G6 | Le composant OpenAPI `Client` désigne toujours **l'affaire**, et la fiche s'appelle `FicheClient` | `grep -q '    FicheClient:' web/src/api/schema.yml` **et** `grep -q 'ClientDeLaffaire' web/src/api/requetes.ts` | |
| G7 | **Aucune branche cliente de projection** sous les écrans clients | `npm --prefix web run audit:projection` — cherche `? <…> : null` et `peut ?`, des formes syntaxiques | |
| G8 | **Aucun nombre clinique compilé** dans le SPA | `npm --prefix web run audit:clinique` | |
| G9 | Aucune locale ne décide d'un format hors de `src/format/` | `npm --prefix web run audit:format` | |
| G10 | **Aucun stockage local d'une donnée métier** (CLAUDE.md #1) | `! grep -rnE '\blocalStorage\b\|\bsessionStorage\b' web/src/pages/` | |
| G11 | **Aucune photo commise**, jamais — l'historique git n'est pas révocable | `git status --porcelain media/` **vide** **et** aucun fichier sous `media/` dans `git log --name-only <premier commit de la phase>~1..HEAD`. **Vérifier d'abord que l'intervalle est non vide** — en phase 03.1 une garde est passée pour la mauvaise raison parce que `main..HEAD` rendait zéro commit | |
| G12 | Zéro test en attente, des deux côtés | `! grep -rnE '\b(it\|test)\.(skip\|todo)\b\|\bxit\(' web/tests/` **et** `! grep -rnE '@pytest\.mark\.(skip\|xfail)' tests/` | |

**Deux gardes de non-régression, à relever séparément** parce qu'elles portent sur des
promesses faites par la phase 3 :

| # | Promesse de la phase 3 | Commande | Verdict |
|---|---|---|---|
| G13 | La palette accepte un fournisseur **sans changer d'une ligne** | `git diff --quiet <premier commit de la phase>~1..HEAD -- web/src/layout/Recherche.tsx` | |
| G14 | `web/src/etats/messages.ts` ne porte que les cinq états globaux | `git diff --quiet <premier commit de la phase>~1..HEAD -- web/src/etats/messages.ts` | |

Si G13 échoue, **ce n'est pas un défaut à corriger discrètement** : cela veut dire que
l'abstraction de la phase 3 était insuffisante, et c'est une information qui vaut d'être
écrite ici.

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
| 1 | Mise en page à 1280px | La grille de 416px, la colonne de référence et le panneau de 320px coexistent sans repli. jsdom ne calcule aucune largeur | |
| 2 | Avertissement contre refus, **en niveaux de gris** | Sait-on lequel bloque, sans la couleur ? C'est la question centrale de la conception de §16.4, et `03` §10 interdit la couleur comme seul porteur | |
| 3 | Anneau de focus sur toute la grille, `°` compris | La visibilité d'un anneau est du CSS calculé. Et l'ordre de tabulation se juge au doigt, pas en lisant le DOM | |
| 4 | Feuille imprimée | Lisible en noir sur blanc, `Cylindre négatif.` au pied, **photo absente**. jsdom n'applique aucune `@media print` | |
| 5 | Lecteur d'écran sur la saisie | Une annonce polie, **une seule**, et le champ **non** annoncé invalide | |

**Le verdict se donne étape par étape.** Une réponse d'un seul tenant est reportée telle
quelle sur les cinq lignes et **notée comme globale** — elle vaut approbation, mais elle ne
dit pas laquelle a été réellement regardée, et ce document ne prête au propriétaire aucune
phrase qu'il n'a pas écrite.

**Aucun défaut n'est corrigé pendant la passe**, pour que les nombres relevés avant et
après soient comparables.

---

## 4. Couverture des exigences — et les deux cases qui restent vides exprès

| ID | Ce qui est livré | Plans | Cochable en phase 4 |
|---|---|---|---|
| **CLIENT-01** | fiche, création, recherche par nom et par téléphone, garde de doublon | 01, 03, 07 | **oui** |
| **CLIENT-02** | la fiche porte l'emplacement ; **l'onglet `Achats` n'est pas rendu** | 09 | **NON** — les ventes sont la phase 6 |
| **CLIENT-03** | grille OD/OG structurée, colonnes plates, `Decimal` | 04, 08 | **oui** |
| **CLIENT-04** | prescripteur conditionnel, date de prescription par `ChampDate` | 04, 08 | **oui** |
| **CLIENT-05** | source médicale ou réfraction, sans défaut, badge portant le mot | 04, 08, 09 | **oui** |
| **CLIENT-06** | versions, `supersede`, aucune route ni contrôle de modification, **pas de revalidation à l'affichage** | 05, 09 | **oui** |
| **CLIENT-07** | bornes servies, refus de signe/pas/bornes, axe ↔ cylindre, `ep_saisi` stocké | 04, 08 | **oui, avec une réserve — voir §5** |
| **CLIENT-08** | transposition pure, visible à la saisie, et `snapshot_pour_fournisseur` | 04 | **NON** — le bon de commande fournisseur est la phase 8 |
| **CLIENT-09** | stockage par locataire, attache unique, lecture authentifiée | 06, 09 | **oui** |
| **CLIENT-10** | quatre couches de rappel, classement, jamais d'auto-sélection | 01, 03, 07 | **oui** |
| **PERM-06** *(héritée)* | deux premières entrées réelles de `CHAMPS_PROTEGES`, **aucune branche cliente** | 05 | mécanisme prouvé |

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

- [ ] Les sept portes mécaniques du §1 sont relevées **avant** la passe humaine
- [ ] Les quatorze gardes du §2 sont vertes
- [ ] Les cinq étapes du §3 ont un verdict **étape par étape**
- [ ] Les portes du §1 sont **rejouées après** la passe, avec l'heure des deux relevés
- [ ] Le tableau de comptage du §1 est rempli plan par plan, **tests écrits et emplacements
      neufs séparés**, et le total est leur somme
- [ ] CLIENT-02 et CLIENT-08 sont non cochées **et non déplacées**
- [ ] Le solde de vérifications manuelles de la phase 3 est inchangé à 18, plus les cinq
      de cette phase

**Verdict de phase :** en attente
</content>

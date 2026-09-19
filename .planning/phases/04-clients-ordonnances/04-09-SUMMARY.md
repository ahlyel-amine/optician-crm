---
phase: 04-clients-ordonnances
plan: 09
subsystem: clients-ordonnances-interface
tags: [historique, versions, impression, photo, fiche-client, cloture-de-phase]
requires:
  - "04-05 — le versionnement serveur, `supersede`, et l'absence de route de modification"
  - "04-06 — le stockage de la photo par locataire et sa lecture authentifiée"
  - "04-07 — la recherche de clients et la garde de doublon"
  - "04-08 — la saisie d'ordonnance, la grille et le panneau de relecture"
provides:
  - "la fiche client en lecture, ses onglets, et l'historique versionné atteint par clics"
  - "le rendu d'une version SANS revalidation — une ancienne fiche ne devient jamais fautive"
  - "la feuille imprimée, un bloc documentaire de plus dans `print.css`, sans géométrie"
  - "l'attache unique d'une photo, vérifiée de bout en bout contre le serveur réel"
affects:
  - "phase 5 (Articles) et phase 6 (Factures) — héritent des deux moitiés de la palette"
  - "phase 6 — ouvrira l'onglet `Achats`, qui n'est PAS rendu ici, et cochera CLIENT-02"
tech-stack:
  added: []
  patterns:
    - "un double de `fetch` doit accepter les DEUX formes d'appel, sinon il masque un échec"
    - "`print.css` reçoit des blocs documentaires ; la géométrie de page reste celle de la phase 3"
key-files:
  created:
    - web/src/pages/clients/ordonnances/HistoriqueOrdonnances.tsx
    - web/src/pages/clients/ordonnances/CarteVersion.tsx
    - web/src/pages/clients/ordonnances/PhotoOrdonnance.tsx
    - web/src/pages/clients/OngletsDuClient.tsx
    - web/tests/ordonnance-historique.test.tsx
  modified:
    - web/src/pages/clients/FicheClient.tsx
    - web/src/pages/clients/ordonnances/SaisieOrdonnance.tsx
    - web/src/pages/clients/ordonnances/messages.ts
    - web/src/pages/clients/messages.ts
    - web/src/pages/clients/ordonnances/optique.ts
    - web/src/print.css
    - web/src/App.tsx
    - .planning/phases/04-clients-ordonnances/04-UI-SPEC.md
decisions:
  - "Le champ du téléversement est `fichier`, pas `photo` — trouvé contre le serveur réel"
  - "La passe humaine des cinq étapes n'a pas été jouée ; le solde manuel passe de 18 à 23"
  - "CLIENT-06 et CLIENT-09 cochées ; CLIENT-02 et CLIENT-08 non cochées et non déplacées"
metrics:
  tasks: 3
  tests_written: 14
  new_test_locations: 14
  completed: 2026-09-19
---

# Phase 4 Plan 09 : Historique, impression, photo — et la clôture de la phase Summary

Le dossier client en lecture — onglets, historique versionné, feuille imprimable et photo
attachée une fois — livré en quatorze tests, puis la clôture de la phase : sept portes et
quatorze gardes rejouées, **trois gardes ont rapporté**, et **la passe humaine des cinq
étapes n'a pas eu lieu**.

---

## La trouvaille qui compte : `photo` contre `fichier`, et treize tests verts

**C'est la section à lire si on n'en lit qu'une.**

Le formulaire de téléversement envoyait le champ `photo`. Le sérialiseur du plan `04-06`
attend `fichier`. Les deux noms diffèrent parce que l'un est le nom de la **colonne** et
l'autre le nom du **champ d'entrée** ; rien dans le code client ne le rappelait.

**Treize tests étaient verts.** Ils l'étaient à bon droit du point de vue de la suite : un
double de `fetch` ne sait pas ce que le serveur exige. Il rend ce qu'on lui a dit de
rendre, et ce qu'on lui avait dit de rendre était un succès.

Le défaut a été trouvé **en téléversant une vraie image contre le vrai serveur**, pendant
la préparation de la passe humaine :

```
POST /api/ordonnances/<id>/photo/   → 400
{"fichier": ["Aucun fichier n'a été soumis."]}
```

Corrigé en `e174ed7`, puis re-vérifié de bout en bout : **201** à l'envoi, puis un `GET`
qui rend **1941 octets** d'`image/png`. Un quatorzième test fige désormais le nom du champ.

**Et il y avait pire que rouge.** Le double de `fetch` de la suite n'acceptait qu'**une
seule** des deux formes d'appel de `fetch` — `fetch(url, init)` et `fetch(Request)`. Le
téléversement empruntait l'autre. Il échouait donc **sans être enregistré du tout** : ni
vert par chance, ni rouge — invisible. Un test qui échoue est un signal ; un test qui ne
voit pas l'appel est une absence de test déguisée en couverture. Le double accepte
maintenant les deux formes, comme le vrai `fetch`.

**Ce que cela établit :**

1. **La passe manuelle n'est pas facultative.** Cette phase l'a précisément démontré par
   son propre manquement : le seul défaut réel trouvé dans le plan l'a été en ouvrant un
   navigateur sur une pile qui tourne, et les cinq étapes qui auraient fait la même chose
   pour la mise en page, l'impression et le lecteur d'écran n'ont pas été jouées.
2. **L'argument du double de `fetch` différé**, proposé par la tâche rapide `260917-lhq`,
   gagne une preuve. Un double qui n'imite pas l'API qu'il remplace ne protège de rien, et
   il ment dans le sens le plus coûteux : en silence.

---

## Ce qui a été construit

| Tâche | Ce qu'elle livre | Commits |
|---|---|---|
| 1 | Le dossier client en lecture : fiche, onglets, historique versionné, `CarteVersion` **sans revalidation**, aucun contrôle de modification ni de suppression, rien de rouge sur une version remplacée | `3a459c0` (6 rouges), `8812791` |
| 2 | La photo attachée **une fois** et la feuille imprimée — `Cylindre négatif.` au pied, **aucune photo au papier** | `97d47b2` (7 rouges), `8296bf6` |
| 2b | Le correctif `photo` → `fichier` et le double de `fetch` réparé | `e174ed7` |
| 3 | Point de contrôle `human-verify` — **voir plus bas** | `04-VALIDATION.md` |

`git diff --name-only 27ac18f..HEAD \| grep -c '\.py$'` rend **0** : ce plan ne touche pas
le serveur, comme il s'y engageait.

`print.css` reçoit **un bloc documentaire, aucune règle de géométrie de page** — vérifié
sur le diff : `[data-feuille-ordonnance]` caché à l'écran et rendu au papier, la carte
d'écran et la vignette masquées à l'impression. Les deux moitiés sont écrites l'une sous
l'autre pour qu'une future mise en page ne puisse pas réintroduire la photo par mégarde.

---

## Le point de contrôle, et ce que la réponse veut dire

**La réponse du propriétaire, mot pour mot :**

> continue

**La passe au navigateur n'a pas eu lieu.** Aucune des cinq étapes n'a été parcourue,
aucun verdict n'a été rendu sur aucune. `continue` autorise à **poursuivre sans la passe**
— ce n'est pas une approbation, et `04-VALIDATION.md` §3 les porte donc toutes les cinq
comme **NON EFFECTUÉES**, pas comme approuvées.

| # | Étape | État |
|---|---|---|
| 1 | Mise en page à 1280px, sans repli | **non effectuée** |
| 2 | Avertissement contre refus, **en niveaux de gris** | **non effectuée** |
| 3 | Anneau de focus sur toute la grille, `°` compris | **non effectuée** |
| 4 | Feuille imprimée, lisible, sans photo | **non effectuée** |
| 5 | Lecteur d'écran : une annonce polie, champ non invalide | **non effectuée** |

**Ces cinq sont exactement les revendications qu'aucun test ne peut fermer**, et la suite
le concède elle-même : ses tests portent le suffixe `..._CLAIM_DE_CLASSE` pour dire qu'ils
n'assertent qu'une liste de classes, jamais un rendu.

- **jsdom ne calcule aucune largeur**, et `matchMedia` rend toujours `false` dans la suite —
  un test de point de rupture y passerait quelle que soit la CSS. (étape 1)
- La **lisibilité relative** d'un avertissement face à une erreur est un jugement humain.
  (étape 2)
- La **visibilité** d'un anneau de focus est du CSS calculé, que jsdom n'a pas. (étape 3)
- **jsdom n'applique aucune `@media print`** : le bloc ajouté à `print.css` n'est jamais
  évalué par un test. (étape 4)
- Aucun lecteur d'écran ne tourne dans la suite ; `aria-live="polite"` est un attribut,
  pas un comportement observé. (étape 5)

**Le solde de vérification manuelle ouvert du projet :**

| | |
|---|---|
| Hérité de la phase 3 | **18** |
| Ajouté par la phase 4 | **+5** |
| **Ouvert à la clôture** | **23** |

Aucune des 18 n'est absorbée, aucune n'est comptée deux fois. Le plafond de cinq que
`04-UI-SPEC.md` §25.5 se fixait **a été tenu** — la phase n'en a pas ajouté une sixième.
Ce qui n'a pas été tenu, c'est leur exécution.

---

## Les trois gardes qui ont rapporté — aucune corrigée

`04-VALIDATION.md` §3 interdit de corriger pendant la passe, pour que les relevés d'avant
et d'après restent comparables. La passe se clôt, donc **rien n'est corrigé ici**.

### 1. G13 échoue vraiment — la promesse de la phase 3 n'a pas tenu

```
git diff --quiet 195f2e6~1..HEAD -- web/src/layout/Recherche.tsx  → code 1
 web/src/layout/Recherche.tsx | 83 +++++++++-   (81 insertions, 2 deletions)
 5ba8eff feat(04-07): la creation avec garde de doublon, et le premier fournisseur de la palette
```

La phase 3 promettait que **« la palette accepte un fournisseur sans changer d'une ligne »**.
Elle a changé de 81, au premier fournisseur réel — ce qui est exactement le moment où une
abstraction se juge.

**L'abstraction était incomplète, pas fausse**, et c'est la conclusion du plan `04-07`. La
moitié *« d'où viennent les résultats »* était bien externalisée et n'a rien coûté. La
moitié *« que se passe-t-il quand on appuie sur `Entrée` »* ne l'était pas : `cmdk` possède
la sélection et la liaison `Entrée` à l'intérieur de la palette, et **aucun fournisseur ne
pouvait décliner la navigation automatique depuis l'extérieur** — ce qu'il fallait pour que
la garde de doublon interpose son écran de confirmation.

**Les deux moitiés sont externalisées maintenant, et la phase 5 (`Articles`) comme la
phase 6 (`Factures`) en héritent ensemble.** Le prix a été payé une fois, par le premier
fournisseur. Il n'y a rien à corriger : c'est la promesse qui était trop large, et la garde
a fait son travail en la rendant fausse plutôt qu'en la laissant s'éroder.

### 2. G5 passe en suite, échoue isolée — la commande est fausse, pas le code

```
uv run pytest -q tests/test_ordonnances.py -k aucune_route_ne_modifie  → 1 failed
  AssertionError: Aucune vue chargée ne sert `Ordonnance`. Le test est vacant…
uv run pytest -q tests/test_ordonnances.py                             → 25 passed
```

Le test porte **sa propre garde de vacuité** — il refuse de passer si aucune vue servant
`Ordonnance` n'a été chargée. Or `-k` **ne fait pas importer l'URLConf**, puisqu'il
désélectionne les tests qui l'importent. La garde se déclenche donc à juste titre.

**Commande corrigée**, reportée dans `04-VALIDATION.md` :

```
! grep -rnE '\bUpdateModelMixin\b|\bDestroyModelMixin\b' domaine/ordonnances/
uv run pytest -q tests/test_ordonnances.py          # le FICHIER, pas -k
```

La moitié grep est verte. C'est la garde de vacuité qui fonctionne ; c'est le document de
validation qui lui avait donné une invocation la mettant en défaut.

### 3. G10 est le piège du mot nu — **quatorzième occurrence**

```
! grep -rnE '\blocalStorage\b|\bsessionStorage\b' web/src/pages/
→ 3 correspondances, toutes dans SelecteurDeMagasinDesDroits.tsx (l.28, l.31, l.92)
→ toutes de la PROSE de la phase 3 qui explique qu'il n'y en a pas
```

Le commentaire qui explique pourquoi la sélection ne persiste **nulle part** contient le
nom de ce qu'il refuse d'employer, et fait donc échouer la garde qui cherche cet emploi.
`04-VALIDATION.md` pose en principe n° 2 qu'*aucun critère n'est le grep d'un mot nu* — et
**G10 était écrite en violation de son propre principe.**

**Commande corrigée** — un accès de membre, forme syntaxique et non lexicale :

```
grep -rnE '(localStorage|sessionStorage)\s*\.' web/src/pages/   → 0
```

**Zéro appel réel.** La règle de CLAUDE.md a désormais quatorze instances derrière elle.

---

## Les portes, relevées avant et après

Identiques des deux côtés — rien n'a bougé, ce qui est tout ce que le protocole demandait
puisqu'aucune correction n'était permise pendant la passe.

| Porte | Avant (orchestrateur) | Après (observé, 2026-09-19 UTC) |
|---|---|---|
| `pytest -q -m "not slow"` | 276 / 33 deselected | **276 passed / 33 deselected** — 15:13:43→15:13:56 |
| `pytest -q -m slow` | non relevé | **33 passed / 276 deselected** — 15:14:26→15:14:52 |
| `npm --prefix web test` | 249 passed | **249 passed**, 10 fichiers — 15:14:07→15:14:10 |
| `npm --prefix web run build` | exit 0 | **exit 0** — 15:14:14 |
| `spectacular --fail-on-warn` + `diff -q` | non relevé | **0**, `diff` **muet** — 15:14:20 |
| `makemigrations --check --dry-run` | non relevé | **0** — 15:14:21 |
| `migrate_all --check` | non relevé | **2 ok, 0 failed, 0 behind** (run #20) — 15:14:21 |

**Décompte de ce plan : 14 tests écrits, 14 emplacements neufs** — aucun `it.each`, donc
les deux coïncident. `235 + 14 = 249`, et le total web de la phase ferme exactement :
`133 + 16 + 11 + 75 + 14 = 249`.

**L'« attendu » de la porte backend était faux, et le même document le prouve.** Il exigeait
« zéro `deselected` en plus des 30 » ; on en observe **33**. Ce sont exactement les **trois
tests `slow`** que le §1 énumère lui-même — PgBouncer (`04-01`), `EXPLAIN` GIN (`04-03`),
concurrence de versionnement (`04-05`). Le document prévoyait les trois et interdisait leur
effet, à deux paragraphes d'intervalle. Le livré est juste ; l'attendu est corrigé.

---

## Exigences — ce qui est coché, et ce qui ne l'est pas

| ID | Verdict | Raison |
|---|---|---|
| **CLIENT-06** | **cochée** | Versions stockées, antérieures lisibles telles quelles, aucune revalidation à l'affichage, aucun contrôle de modification ni de suppression dans l'interface, et **405** côté serveur. Un opticien peut réellement l'accomplir |
| **CLIENT-09** | **cochée** | Photo attachée une fois, stockée par locataire, lue derrière `ordonnance.voir`. **Cochée seulement après la vérification de bout en bout** décrite plus haut — elle ne l'aurait pas été sur la foi des treize tests verts |
| **CLIENT-02** | **NON cochée, NON déplacée** | L'onglet `Achats` n'est pas rendu. **La phase 6 possède l'historique d'achats** |
| **CLIENT-08** | **NON cochée, NON déplacée** | **La phase 8 possède le bon de commande fournisseur** |

Les deux non cochées **restent rattachées à la phase 4** dans `REQUIREMENTS.md`. Le projet
tient déjà ce précédent avec les plans `03-05` à `03-10` et PERM-02/03 : une exigence reste
attachée à la phase qui pose sa structure, et n'est cochée que par celle où un opticien peut
réellement l'accomplir. Déplacer la ligne perdrait la trace de qui a posé les fondations.

CLIENT-01/03/04/05/07/10 étaient déjà cochées par les plans antérieurs.

---

## Les reports restent des reports

Confirmé à la clôture, aucun n'est fermé par ce plan :

| Réf | Ce qui reste ouvert | Reprenant |
|---|---|---|
| **D-4-1** | `backup_client` produit un `pg_dump` et **rien d'autre** — la photo est hors de la sauvegarde par client | phase 1 (juridiction), puis une reprise de TENANT-09 |
| **D-4-2** | Même trou pour la rétention à dix ans (art. 211 CGI) et l'archive d'offboarding | phase 12 |
| **D-4-3** | **Aucun type de document portable accepté** en pièce jointe — pas de PDF | phase 9 |
| **D-4-4** | Le nom du fichier envoyé **n'est affiché nulle part** : il porte couramment le nom du patient | phase 9, si un contrôle textuel reste voulu |
| **D-4-5** | **Le serveur refuse toujours ce que l'écran ne fait plus qu'avertir** sur l'écart pupillaire — `04-08` a appliqué l'amendement Q4 côté écran seulement, et ce plan ne touche aucun `.py`, donc il ne le ferme pas | le jour où un opticien répond sur le seuil de 45 mm |
| **D-1** *(héritée)* | Le sélecteur de magasin du shell n'a toujours aucun nom accessible | tâche rapide, §28-Q6 |

---

## Porte de phase — Phase 4

### Ce que la phase 4 a livré

Un opticien peut, dans un navigateur : **trouver** un client par nom ou téléphone, avec une
recherche insensible aux accents et tolérante aux variantes de translittération arabe, et
sans auto-sélection ; **le créer** avec une garde de doublon ; **saisir** une ordonnance
structurée — OD/OG, sphère, cylindre, axe, addition, écart pupillaire, prescripteur, date,
source — avec ses bornes servies par le serveur, sa transposition sur place et son panneau
de relecture ; **enregistrer une nouvelle version** sans jamais écraser la précédente ;
**relire** tout l'historique tel qu'il a été saisi, sans revalidation ; **imprimer** une
feuille portant la convention de signe ; et **attacher une photo** de l'ordonnance papier,
stockée par locataire et lue derrière une permission.

Deux applications métier — `clients`, `ordonnances` — classées dans le routeur, migrées sur
les deux bases clientes, jamais touchées sur `default`.

### Ce que la phase 4 n'a **pas** établi

1. **Que l'interface se voit, s'imprime et s'entend correctement.** Les cinq vérifications
   qui en auraient jugé n'ont pas été jouées. Le solde manuel ouvert passe de **18 à 23**.
2. **Deux critères de la feuille de route ne sont pas servis** : l'historique d'achats sur
   la fiche client (phase 6) et la commande spéciale portée jusqu'au fournisseur (phase 8).
   Les deux étaient connus d'avance et écrits dans `04-VALIDATION.md` §5.
3. **Le tiers amendé du critère 3** : le discriminant 45 mm est un avertissement et non un
   refus côté écran, et **le serveur refuse toujours** (D-4-5). La divergence est ouverte et
   attend un opticien marocain, avec les quatre questions de facturation.
4. **La photo n'est pas sauvegardée** (D-4-1) et **la rétention à dix ans a le même trou**
   (D-4-2) — ce sont des engagements légaux, pas des agréments.

### Ce dont la phase 5 hérite

- **Une palette de recherche dont les deux moitiés sont externalisées** — la source des
  résultats et le comportement de `Entrée`. La phase 5 (`Articles`) sera le second
  fournisseur, et devrait ne rien coûter au fichier `Recherche.tsx` cette fois. **Si elle
  le modifie à nouveau, l'abstraction est fausse et non incomplète**, et il faudra le dire.
- **Un solde de 23 vérifications manuelles** qu'aucune suite ne fermera, et qui ne
  diminuera que si quelqu'un ouvre un navigateur.
- **Trois commandes de garde corrigées** dans `04-VALIDATION.md`, à recopier telles quelles
  plutôt que dans leur forme d'origine.
- **La leçon du double de `fetch`** : un double qui n'imite pas l'API qu'il remplace ne
  protège de rien et échoue en silence. La phase 5 devrait adopter le double partagé de la
  tâche `260917-lhq` avant d'écrire sa première requête.

---

## Self-Check
 PASSED

Les sept fichiers déclarés existent, les cinq commits déclarés sont dans l'historique.

```
FOUND: web/src/pages/clients/ordonnances/HistoriqueOrdonnances.tsx
FOUND: web/src/pages/clients/ordonnances/CarteVersion.tsx
FOUND: web/src/pages/clients/ordonnances/PhotoOrdonnance.tsx
FOUND: web/src/pages/clients/OngletsDuClient.tsx
FOUND: web/tests/ordonnance-historique.test.tsx
FOUND: web/src/pages/clients/FicheClient.tsx
FOUND: web/src/print.css
FOUND: 3a459c0  3a459c0 8812791 97d47b2 8296bf6 e174ed7 — tous présents
```

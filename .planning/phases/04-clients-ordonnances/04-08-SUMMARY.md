---
phase: 04-clients-ordonnances
plan: 08
subsystem: ui
tags: [react, formulaire, accessibilite, avertissements, transposition, ordonnance, clients]

requires:
  - phase: 04-clients-ordonnances
    plan: 02
    provides: "`ChampNombre`, `ChampDate`, `normaliserNombre`, `verifierBornes`, `verifierPas`, `web/tests/nomAccessible.ts`"
  - phase: 04-clients-ordonnances
    plan: 04
    provides: "`bornes_ordonnance` sur l'amorcage, et `domaine/ordonnances/optique.py` qui fait foi"
  - phase: 04-clients-ordonnances
    plan: 05
    provides: "`POST /api/clients/{client_id}/ordonnances/`, `OrdonnanceASaisir`, la version emise par le serveur"
  - phase: 04-clients-ordonnances
    plan: 07
    provides: "le sous-arbre `/clients`, sa garde `client.voir`, `audit:clinique` et `audit:projection`"
provides:
  - "`/clients/:id/ordonnances/nouvelle` — l'ecran de saisie, garde par `ordonnance.saisir`"
  - "`GrilleOdOg` — le tableau du papier en CSS grid, tabulation en lignes, labels reels masques"
  - "`BlocEcartPupillaire` — la forme stockee, la somme en affichage, aucun monoculaire calcule"
  - "`PanneauRelecture` — la relecture continue en notation de prescription"
  - "`construireLaCharge` — ce qui part au serveur, toujours en cylindre negatif"
  - "les bornes cliniques servies exposees par le contexte d'authentification (`useAuth().bornes`)"
affects: [04-09-fiche-historique-impression, 04-validation, 06-facturation, 08-commandes, 11-mobile]

tech-stack:
  added: []
  patterns:
    - "L'instantane evalue : les remarques se derivent d'une COPIE de l'etat prise au blur, jamais de l'etat courant — c'est ce qui rend « rien ne s'annonce a la frappe » structurel plutot que disciplinaire"
    - "Deux temporalites de refus : un refus qui parle d'une valeur tapee apparait au blur, un refus qui parle d'un champ encore vide attend la soumission"
    - "Un `radiogroup` est un `fieldset` + `legend` + radios natives : la navigation aux fleches est native et le nom vient du `legend`, donc le piege *name from author* de D-1 ne peut pas s'y produire"
    - "Une enumeration de `combobox` se fait dans la PORTEE de l'ecran, pas du document : sinon elle echoue sur un defaut herite qui n'appartient pas a la phase"

key-files:
  created:
    - web/src/pages/clients/ordonnances/GrilleOdOg.tsx
    - web/src/pages/clients/ordonnances/BlocEcartPupillaire.tsx
    - web/src/pages/clients/ordonnances/PanneauRelecture.tsx
    - web/src/pages/clients/ordonnances/SaisieOrdonnance.tsx
  modified:
    - web/src/App.tsx
    - web/src/auth/AuthProvider.tsx
    - web/src/api/requetes.ts
    - web/src/pages/clients/ordonnances/messages.ts
    - web/tests/ordonnance-saisie.test.tsx

key-decisions:
  - "Le panneau de relecture, et non un dialogue de confirmation, est le mecanisme qui attrape `90` tape pour `9` — parce qu'il change la FORME, pas seulement la place"
  - "Le discriminant 45 mm est un avertissement, pas un refus (amendement Q4, tache 1) — donc le critere 3 de la feuille de route n'est plus litteralement satisfait"
  - "Les bornes cliniques passent par le contexte d'authentification plutot que par une requete propre a l'ecran : elles arrivent deja dans l'amorcage"
  - "Les refus de formulaire attendent la soumission ; les refus de champ apparaissent au blur"
  - "Le dernier maillon de la chaine humaine vers cet ecran appartient au plan 04-09, et il est nomme plutot que masque"

patterns-established:
  - "Instantane evalue : `evalue: Ordonnance | null` mis a jour au blur et a la soumission seulement"
  - "Un avertissement ne porte jamais `aria-invalid` ; le test le prouve avec un controle POSITIF sur un champ reellement refuse"
  - "La copie vit dans `messages.ts` a cote des composants, jamais dans `src/etats/messages.ts`"

requirements-completed: [CLIENT-03, CLIENT-04, CLIENT-05, CLIENT-07]

duration: 75min
completed: 2026-09-19
---

# Phase 4 Plan 08 : Saisie d'une ordonnance — Summary

**L'ecran de saisie complet : la grille du papier en CSS grid, la bascule de notation qui
transpose sur place, l'ecart pupillaire qui enregistre ce qui a ete saisi, et un panneau de
relecture qui relit la prescription dans une FORME differente de celle qu'on est en train de
taper — le seul mecanisme de cet ecran qui attrape un axe de 90 saisi pour 9.**

## Performance

- **Duree :** environ 75 minutes (reprise des taches 2 et 3 seules)
- **Taches :** 2 sur 2 de la reprise ; 3 sur 3 pour le plan entier
- **Fichiers crees :** 4 · **modifies :** 5
- **Commits :** 4 (deux arcs rouge-puis-vert)

## Ce qui a ete livre

| Commit | Contenu |
|---|---|
| `7abf719` | `test` — 18 tests rouges : la route n'existait pas, aucun composant non plus |
| `5633568` | `feat` — tache 2 : `GrilleOdOg`, `BlocEcartPupillaire`, `SaisieOrdonnance`, la route, les bornes dans le contexte |
| `1b6ab83` | `test` — 20 tests, 14 rouges : le panneau, les quatre proprietes de l'avertissement, l'enregistrement |
| `e9f1063` | `feat` — tache 3 : `PanneauRelecture`, la soumission, la confirmation de 16.5, la sortie |

**La tache 1 est intacte** : `f633041` n'a ete ni reecrit, ni recommite, ni touche. Les quatre
modules purs (`verifier.ts`, `messages.ts`, `optique.ts`, `LigneDeCorrection.tsx`) sont
utilises tels quels par les quatre composants de rendu ; `messages.ts` a recu **trois
constantes de copie** (`CHAMP_EP`, `LABEL_EP_BINOCULAIRE`, `SEPARATEUR_RELECTURE`, `detailEp`)
et aucune modification de phrase existante.

## Le decompte, releve et non ajuste

| Porte | Avant (cloture partielle) | Apres |
|---|---|---|
| `npm --prefix web test` | 196 passes | **235 passes**, 9 fichiers |
| `npm --prefix web run build` | 0 | **0** |
| `audit:clinique` | 0 | **0** |
| `audit:projection` | 0 | **0** |
| `audit:format` | 0 | **0** |

**39 tests ecrits, zero emplacement neuf** : tout est alle dans
`web/tests/ordonnance-saisie.test.tsx`, qui passe de 36 a 75 tests. Les deux etats rouges sont
dans l'historique et se relisent : **18 echecs sur 215** au premier arc, **14 sur 235** au
second.

`git diff --name-only f633041..HEAD | grep -c '\.py$'` rend **0** : ce plan ne touche pas le
serveur.

## L'amendement de §16.3, et le compte de onze releve a la main

L'amendement appartient a la tache 1 et il est en place, date `[AMENDÉ 2026-09-18 —
04-CONTEXT.md Q4]`. Ce que cette reprise ajoute, c'est le **comptage manuel** que le plan
demandait et qui n'avait pas ete consigne :

```
sed -n '201,254p' 04-UI-SPEC.md | grep -cE '^\| A[0-9]+'   →   11
```

**Onze lignes. Pas douze, pas treize.** Les deux discriminants d'ecart pupillaire **absorbent**
A8 et A9 au lieu de s'y ajouter :

| Ligne | Avant | Apres |
|---|---|---|
| A8 | EP binoculaire hors 54,0–72,0, `…inhabituel.` | EP binoculaire **sous le plancher servi** → `Un écart binoculaire de 31,5 mm est un écart monoculaire. Choisissez « monoculaire » ci-dessus.` |
| A9 | EP monoculaire hors 26,0–36,0, `…inhabituel.` | EP monoculaire **au-dessus du plafond servi** → `Un écart monoculaire de 62,0 mm est un écart binoculaire. Choisissez « binoculaire » ci-dessus.` |

Les deux messages ont quitte le bloc **Refusals** de §23 pour le bloc **Warnings**, avec le
prefixe `À vérifier — `. La moitie « … est inhabituel. » a ete **supprimee et non oubliee** :
la region qu'elle decrivait est exactement celle que la borne d'union refuse deja, donc elle
n'aurait pu apparaitre qu'accompagnee d'un refus — du bruit, que §16.3 interdit avant
d'interdire le douzieme. Une sonde de test le prouve
(`client07_hors_de_l_union_l_avertissement_ne_DOUBLE_pas_le_refus`).

## Ce que le verificateur de phase doit LIRE, pas decouvrir

### 1. Le critere 3 de la feuille de route n'est plus litteralement satisfait

Il dit *« refused at entry »* pour « a monocular value entered where a binocular écart
pupillaire is expected ». Depuis l'amendement Q4, **c'est un avertissement.** Le proprietaire
l'a decide en connaissance de cause ; le **mecanisme est conserve**, seule la severite change,
et elle redevient un refus en une ligne (`severite: "refus"` sur A8/A9 dans `verifier.ts`) le
jour ou un opticien confirme le seuil — les deux sont marques `[JUGEMENT — sans source]` et la
question est posee en §28-Q4. Le cout d'un faux refus est un opticien qui ne peut pas
enregistrer une ordonnance reelle ; celui d'un faux avertissement est une phrase a lire.

**Consequence a connaitre :** le serveur, lui, refuse toujours un binoculaire sous son plancher
par sa `CheckConstraint`. Le client avertit, le serveur refuse — l'ecart est dans
`deferred-items.md` et n'a pas ete referme ici.

### 2. L'ecran n'est PAS encore atteignable en cliquant, et le maillon manquant est nomme

La chaine humaine complete est `/` → `Clients` → la ligne → **`Saisir une ordonnance`**. Les
trois premiers maillons existent et sont testes
(`client01_la_liste_mene_au_client_et_le_DERNIER_maillon_arrive_au_plan_04_09`). Le quatrieme
est le bouton de la carte de §19.3, **qui vit sur la fiche client, construite au plan 04-09** —
et §18.2 interdit explicitement une colonne d'actions ou un menu de ligne sur la liste, donc ce
plan n'avait **aucun endroit legitime** ou le poser.

Ce qui est prouve ici, et qui est la moitie mecanisable de la lecon 03-14 :
`client05_la_saisie_est_montee_dans_le_ROUTEUR_de_l_application_sous_le_shell` monte `App`
entier, traverse sa table de routes, sa garde et son shell — aucun test de ce plan ne monte un
composant a la main. Ce qui n'est pas prouve, c'est le dernier clic, **et c'est ecrit plutot
qu'implique.** `04-09` doit le fermer : c'est sa propre obligation, §19.1 la lui assigne
nommement.

### 3. L'arc rouge-puis-vert de la TACHE 1 reste absent de l'historique

Il manquait deja a la cloture partielle : rien n'avait ete commite avant que l'orchestrateur ne
sauve le travail existant. Les taches 2 et 3, elles, ont leur arc (`7abf719` puis `5633568`,
`1b6ab83` puis `e9f1063`). La discipline test-first de la tache 1 ne peut donc etre **constatee
que sur son resultat**, pas verifiee sur les commits.

### 4. Le piege du grep a tire trois fois pendant l'execution

CLAUDE.md le nomme et dit qu'il a deja tire dix fois. Trois de plus, toutes attrapees :

1. `! grep -rn '<table' GrilleOdOg.tsx` — **la garde du plan lui-meme**, qui matchait la prose
   expliquant pourquoi ce n'en est pas une. Le plan demande d'ecrire cette raison, donc la
   garde ne pouvait pas chercher ce mot nu. **Resolution : la prose ecrit `table` sans ses
   chevrons**, avec une note d'une ligne disant pourquoi — la garde reste intacte et n'a pas
   ete affaiblie.
2. `grep -q 'localStorage\|sessionStorage'` — meme cause, sur la docstring qui promet qu'il n'y
   en a aucun. Meme resolution : la phrase dit « aucun stockage navigateur ».
3. **Dans un test** : `screen.queryByText(/enregistrée/)` matchait `Les valeurs sont
   enregistrées en cylindre négatif.`, la ligne de convention de l'ecran. Ancre en
   `/^Ordonnance enregistrée/`.

## Les quatre proprietes de l'avertissement, chacune avec son assertion

| Propriete | Test | Ce qu'il attrape |
|---|---|---|
| Pas d'`aria-invalid` sur un champ averti | `client07_un_champ_AVERTI_ne_porte_PAS_aria_invalid_la_ou_un_champ_REFUSE_le_porte` | **Controle POSITIF** sur un champ refuse cote a cote : sans lui, un ecran qui ne poserait jamais l'attribut passerait |
| `role="status"`, jamais `alert` | `client07_la_note_est_role_status_et_JAMAIS_role_alert` | une interruption assertive par frappe |
| L'id dans `aria-describedby` | `client07_l_id_de_la_note_est_dans_aria_describedby_du_champ` | revenir au champ sans relire la remarque |
| Au blur, jamais au changement | `client07_aucune_note_n_apparait_AVANT_le_blur` | taper `9` en route vers `90` |

**Ce que ces tests NE prouvent PAS, et c'est ecrit dans le fichier :** jsdom ne calcule aucun
CSS. Ils prouvent que la note existe, son role, sa reference, l'absence de l'attribut, et que
sa liste de classes ne porte aucun jeton destructif. Ils ne prouvent pas qu'elle **se lit** plus
discretement qu'une erreur. C'est la **verification manuelle n° 2** de `04-VALIDATION.md`, et
elle se fait **en niveaux de gris**.

## Deviations from Plan

### 1. [Rule 3 — blocage] Les bornes servies n'etaient exposees nulle part

- **Trouve pendant :** tache 2
- **Probleme :** `verifier.ts` exige `Amorcage["bornes_ordonnance"]`, mais `useAuth()` ne
  publiait pas ce champ. L'ecran n'avait aucune facon de l'obtenir sans redemander
  `/api/auth/moi/`.
- **Correctif :** `bornes` ajoute a `ValeurContexteAuth`, servi depuis l'amorcage deja en
  memoire. Trois lignes, aucune requete de plus. `bornes === null` rend `null` : l'ecran ne
  peut rien afficher tant que le serveur n'a pas parle, ce qui est la forme executable de §16.2.
- **Fichier :** `web/src/auth/AuthProvider.tsx` · **Commit :** `5633568`

### 2. [Rule 3 — blocage] `OrdonnanceASaisir` n'etait pas alias dans `requetes.ts`

- La charge utile n'etait pas typable sans elle. Un alias vers
  `components["schemas"]["OrdonnanceASaisir"]`, dans la forme exacte des autres.
- **Fichier :** `web/src/api/requetes.ts` · **Commit :** `e9f1063`

### 3. [Rule 2 — correction] La temporalite des refus, absente du plan

- **Trouve pendant :** tache 3
- **Probleme :** rendre tous les refus au blur faisait apparaitre « Indiquez la source » et
  « Indiquez le magasin » des la sortie du **premier champ de sphere** — un reproche adresse a
  quelqu'un qui n'a pas encore fini de remplir.
- **Correctif :** `soumisUneFois` dans l'etat, et `estUnRefusDeSoumission` — source,
  prescripteur, magasin et les **deux refus croises axe-cylindre** attendent la soumission
  (ce que §20.4 et §20.8 disent deja : « checked on submit »). Les refus de valeur restent au
  blur.
- **Commit :** `e9f1063`

### 4. [Rule 1 — bug de test] Le magasin de `sonner` est module-global

- Un toast d'un test reapparaissait sous le `Toaster` du suivant : le test de l'etat optimiste
  passait seul et echouait en suite. `toast.dismiss()` en `afterEach`, avec la mesure ecrite
  au-dessus.

### 5. [Rule 1 — robustesse] `onSuccess` avec un corps absent

- Une reponse 2xx sans corps rendait `creee` indefini et levait sur `.version`. La version vient
  du serveur ou le toast ne l'affirme pas.

## Known Stubs

Aucun. Les quatre composants sont cables sur des donnees reelles : `/api/clients/{id}/` pour le
nom et la date de naissance, `/api/clients/{client_id}/ordonnances/` pour la version
precedente, `useAuth().bornes` pour les bornes, et `POST` pour l'enregistrement.

**Une chose n'est pas un stub mais doit etre dite :** le bloc `Photo de l'ordonnance` de §20.2
n'est pas rendu par cet ecran. Il appartient a §22 et au plan **04-09**, qui le monte dans
`SaisieOrdonnance.tsx` — le plan 04-09 nomme deja ce fichier dans ses `files_modified`.

## Threat Flags

Aucune surface nouvelle : ce plan n'ajoute ni point de terminaison, ni chemin d'authentification,
ni acces fichier, ni changement de schema. Les neuf menaces du registre (T-04-54 a T-04-62) sont
adressees par le code livre ; T-04-54 reste **mitige partiellement, et le plan le dit deja** —
aucune validation n'attrape un axe de 90 saisi pour 9, et le filet reel est CLIENT-06, la
correction par nouvelle version.

## Self-Check

Fichiers crees, verifies presents :

- `web/src/pages/clients/ordonnances/GrilleOdOg.tsx` — FOUND
- `web/src/pages/clients/ordonnances/BlocEcartPupillaire.tsx` — FOUND
- `web/src/pages/clients/ordonnances/PanneauRelecture.tsx` — FOUND
- `web/src/pages/clients/ordonnances/SaisieOrdonnance.tsx` — FOUND

Commits, verifies presents : `7abf719`, `5633568`, `1b6ab83`, `e9f1063` — FOUND.

**Ce document remplace `04-08-PARTIEL.md`, qui est supprime dans le meme commit :** deux
documents decrivant l'etat d'un meme plan, dont l'un est perime, est exactement la divergence
muette que ce projet refuse ailleurs. Son contenu survit dans l'historique
(`dd8b17a`) et ses deux avertissements utiles — l'arc manquant de la tache 1, et ce qui restait
a construire — sont repris ci-dessus.

## Self-Check: PASSED

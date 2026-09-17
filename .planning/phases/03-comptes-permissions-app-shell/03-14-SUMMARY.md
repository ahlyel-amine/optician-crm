---
phase: 03-comptes-permissions-app-shell
plan: 14
subsystem: web-comptes-droits
tags: [comptes, droits, permissions, magasins, navigation, dialogues, journal, PERM-02, PERM-03, PERM-04]
requires:
  - 03-05 (l'acces materialise : le proprietaire passe par le meme chemin que tout le monde)
  - 03-09 (la surface d'ecriture, le catalogue offrable, le contrat de reponse d'une bascule)
  - 03-11 (le registre de colonnes, `Valeur`/`bdi`, le formatage MAD)
  - 03-12 (AuthProvider, RequireAuth, les cinq etats globaux, le client genere)
  - 03-13 (l'app shell, `nav.ts`, la discipline du tableau declaratif)
provides:
  - web/src/pages/comptes/ListeComptes.tsx — la liste, l'etat vide et ses six colonnes
  - web/src/pages/comptes/CreerCompte.tsx — le dialogue de creation, l'atterrissage direct sur le detail
  - web/src/pages/comptes/DetailCompte.tsx — quatre regions, Identite / Magasins / Droits / Historique
  - web/src/pages/comptes/SectionMagasins.tsx — la ligne statique du mono-magasin, le refus en ligne du dernier magasin
  - web/src/pages/comptes/SectionDroits.tsx — les 21 lignes en sept sections, toutes venues du catalogue serveur
  - web/src/pages/comptes/LigneDroit.tsx — l'anatomie de ligne, le tri-etat `aria-checked="mixed"`, `Par magasin`
  - web/src/pages/comptes/dialogues.tsx — les deux confirmations destructives, seconde phrase comprise
  - web/src/pages/comptes/HistoriqueDroits.tsx — la seule vue de `JournalDroit`
  - web/src/layout/NavSecondaire.tsx — la navigation de second niveau de 5.3, dans la zone de contenu
  - "GET /api/comptes/{id}/journal/ — l'historique, intersecte comme le catalogue et la fiche"
  - "plateforme/comptes/services.py:etat_des_droits, etat_de, intersecter"
affects:
  - phase 9 (Personnalisation) et phase 12 (Abonnement) : elles ajoutent leur ecran de parametres en ajoutant une DONNEE a `NAV[].sousEntrees`
  - phase 8 (`article.voir_prix_achat`, `vente.voir_marge` deviennent visibles sans changement SPA)
  - 03-09 (le contrat de reponse d'une bascule est AMENDE — voir « Amendement au plan 03-09 »)
tech-stack:
  added: []
  patterns:
    - les libelles, sections, explications et prerequis d'un droit viennent TOUS du catalogue serveur ; la SPA n'a aucune liste de codes
    - une reponse d'ecriture est intersectee comme une reponse de lecture — la porte de service est une porte
    - la navigation de second niveau vit dans le meme tableau et sous le meme filtre que la premiere
    - au moins un test doit atteindre un ecran comme une personne l'atteint — monter a la racine et cliquer
key-files:
  created:
    - web/src/pages/comptes/ListeComptes.tsx
    - web/src/pages/comptes/CreerCompte.tsx
    - web/src/pages/comptes/DetailCompte.tsx
    - web/src/pages/comptes/SectionMagasins.tsx
    - web/src/pages/comptes/SectionDroits.tsx
    - web/src/pages/comptes/LigneDroit.tsx
    - web/src/pages/comptes/dialogues.tsx
    - web/src/pages/comptes/HistoriqueDroits.tsx
    - web/src/layout/NavSecondaire.tsx
  modified:
    - web/src/App.tsx
    - web/src/layout/nav.ts
    - web/src/auth/RequireDroit.tsx
    - web/src/api/requetes.ts
    - web/src/api/schema.yml
    - web/src/api/types.gen.ts
    - web/src/tableau/Tableau.tsx
    - web/src/tableau/registre.ts
    - web/tests/comptes.test.tsx
    - web/tests/shell.test.tsx
    - web/tests/connexion.test.tsx
    - plateforme/comptes/services.py
    - plateforme/comptes/serializers.py
    - plateforme/comptes/views.py
    - tests/test_comptes_droits.py
    - .planning/phases/03-comptes-permissions-app-shell/03-UI-SPEC.md
key-decisions:
  - "La navigation de second niveau de 5.3 n'avait jamais ete construite : `/parametres/comptes` n'etait atteignable qu'en tapant son adresse. Elle vit desormais dans `NAV[].sousEntrees`, sous le meme predicat de visibilite que le premier niveau"
  - "L'accueil des parametres REDIRIGE vers la premiere entree visible ; aucune entree visible rend la 403 pleine page, sans nommer de droit — aucun droit unique ne possede `/parametres`"
  - "La reponse d'une bascule est INTERSECTEE avec les magasins de l'appelant. Le contrat fige par le plan 03-09 enumerait les magasins de la cible a un gerant-gestionnaire ; le test nomme de 03-09 est amende"
  - "La regle d'etat de 7.5 est ecrite une seule fois, dans `services.etat_de`, lue par `ligne_de`, `etat_des_droits` et `intersecter`"
  - "La mise en evidence de la nouvelle ligne pendant 2 secondes est SUPERSEDEE dans 03-UI-SPEC 7.2 : la navigation vers le detail demonte la liste dans le meme tick, donc elle se jouerait sur un ecran que personne ne regarde"
  - "L'interrupteur est ecrit a la main et non pris au bloc vendu `switch` : Radix est un booleen, et 7.5 exige `aria-checked=\"mixed\"`"
  - "Le garde-fou « au moins un magasin » est une regle d'INTERFACE et est ecrit comme telle — le serveur accepte zero magasin, parce qu'un compte neuf en a zero (decision 10 du plan 03-09)"
patterns-established:
  - "Un ecran n'est livre que s'il est ATTEIGNABLE : un test qui monte un composant a sa route ne prouve pas qu'un chemin y mene"
  - "Toute reponse d'API portant des codes de magasin ou de droit passe par l'intersection de l'appelant, en ecriture comme en lecture"
  - "Une phase qui ajoute un ecran de parametres ajoute une entree a `sousEntrees`, jamais du JSX ni une route de premier niveau"
requirements-completed: [PERM-02, PERM-03, PERM-04]
duration: ~100m (taches 1 a 3, puis le point de controle : le blocage de navigation et les trois decisions)
completed: 2026-09-17
---

# Phase 3 Plan 14 : Comptes, droits et surcharge par magasin Summary

**La surface difficile de la phase : une liste unique de 21 droits venue du catalogue serveur, une surcharge par magasin qui n'apparait qu'a la demande, aucun preset nulle part — et, decouvert au point de controle, l'ecran entier etait inatteignable par l'interface.**

## Performance

- **Duree :** ~45 min pour les taches 1 a 3 (12:20 → 13:14), puis ~55 min pour le blocage et les trois decisions du point de controle (13:55 → 14:45), l'attente humaine entre les deux non comptee
- **Taches :** 3 automatiques en TDD, 1 point de controle bloquant qui a rendu **un blocage et trois decisions**
- **Fichiers :** 9 crees, 16 modifies
- **Suites, chiffres reels du dernier passage :**
  - backend `uv run pytest -x -q -m "not slow and not pending"` → **184 passed / 30 deselected** (base 184 ; le plan amende un test existant plutot que d'en ajouter un)
  - web `npm --prefix web test` → **119 passed** (base 115, +4)
  - `npm --prefix web run build` → **code 0**
  - `npm --prefix web run audit:format` → **aucun resultat**
  - `manage.py spectacular --fail-on-warn` → **code 0**, `web/src/api/schema.yml` regenere et **diff vide** apres la correction de la decision 1
  - `manage.py check` → **0 issue**, `manage.py migrate_all --check` → **2 ok, 0 failed, 0 behind**

## Accomplissements

- **Les trois ecrans existent** : la liste avec ses six colonnes contractuelles, le dialogue de creation, et la fiche a quatre regions dans l'ordre porteur **Identite, Magasins, Droits, Historique** — un droit sans magasin n'accorde rien.
- **Aucun preset, aucun palier.** Pas de `Gerant standard`, pas de `Tout cocher`, pas de `Copier les droits de`. Les trois sont des paliers de role sous un nom sympathique ; CLAUDE.md #6 les interdit, et un grep le verifie.
- **La SPA ne code aucun libelle de permission.** Sections, libelles, explications et prerequis viennent tous de `/api/comptes/catalogue/`. Le test de catalogue tronque le prouve **sans branche cliente** : un catalogue court produit un ecran court.
- **Une entreprise mono-magasin ne rencontre aucun controle** : la section Magasins est une ligne statique, et `Par magasin` n'est jamais rendu. C'est la plus grosse simplification disponible et elle couvre tout le palier `Essentiel`.
- **Le tri-etat est annonce, pas seulement dessine.** `aria-checked="mixed"`, avec l'aide `Personnalise : 2 magasins sur 3`. L'interrupteur est ecrit a la main : le bloc vendu `switch` est un booleen Radix et ne peut pas porter `mixed`.
- **`Annuler` ne signifie jamais « fermer ».** Il n'apparait que comme action d'un toast d'annulation ; les dialogues portent `Retour`. Verifie par grep dans les deux sens.
- **Les deux dialogues destructifs enoncent ce qui survit.** « Ses ventes et ses saisies restent enregistrees a son nom » repond a la question que l'utilisateur se poserait sans cela — et deviner est un appel telephonique.
- **La suppression de compte n'existe pas et le mot n'apparait nulle part** : dix ans de retention (art. 211 CGI) et des ventes qui referencent le compte.
- **`GET /api/comptes/{id}/journal/`** livre l'historique que le plan 03-09 avait consigne comme absence deliberee, **intersecte** : sans ce filtre, ouvrir un repli suffirait a contourner ce que le catalogue et la fiche retirent.

## Task Commits

| # | Commit | Objet |
|---|---|---|
| 1 | `cb0f8fa` | test — tache 1 (RED) : la liste, l'etat vide, la garde de route |
| 2 | `6050956` | feat — tache 1 (GREEN) : la liste, la creation, la garde de route |
| 3 | `949d12d` | test — tache 2 (RED) : la fiche porte l'etat de chaque droit, deja intersecte |
| 4 | `b731238` | feat — tache 2 (GREEN cote serveur) : `etat_des_droits`, `CompteDetailSerializer` |
| 5 | `da3a9c7` | feat — tache 2 (GREEN) : le detail, les magasins, les 21 lignes, l'historique |
| 6 | `17b46a4` | test — tache 3 (RED) : surcharge par magasin, annulation, dialogues |
| 7 | `a495cf5` | feat — tache 3 (GREEN) : surcharge par magasin, annulation, dialogues |
| 8 | `3667445` | test — tache 5 (RED) : **l'ecran des comptes est inatteignable par l'interface** |
| 9 | `5d378ad` | feat — tache 5 (GREEN) : la navigation de second niveau des parametres |
| 10 | `8a82aee` | test — decision 1 (RED) : la reponse d'une bascule enumere les magasins |
| 11 | `fa6d646` | feat — decision 1 (GREEN) : la reponse d'une bascule est intersectee |
| 12 | `2bc43d3` | docs — 5.3 inscrit le second niveau, 7.2 supersede la mise en evidence |

## Le blocage du point de controle — l'ecran n'etait pas atteignable

Le proprietaire s'est arrete a **l'etape 1** de la traversee, avec une phrase : « il n'y a pas d'interface pour creer un compte ».

**Le diagnostic.** `ContenuDuShell` routait `/parametres` vers le composant `Parametres`, qui declarait `comptes` et `comptes/:id` — et dont l'index, `path="*"`, rendait `PageEnAttente`, c'est-a-dire un titre et le chemin courant. `grep -rn "parametres/comptes" web/src/` ne trouvait **aucun lien** vers la liste en dehors de la liste elle-meme (ligne → detail). Cliquer `Parametres` dans la barre laterale menait donc a un cul-de-sac, et `/parametres/comptes` n'etait atteignable **qu'en tapant son adresse**.

**La cause.** La navigation de second niveau de `03-UI-SPEC.md` 5.3 — « a row of section links inside the content area, not a sidebar accordion » — etait **decrite dans la docstring de `Parametres`** (« la phase 9 et la phase 12 y ajoutent leurs ecrans ») et n'avait jamais ete construite. La docstring decrivait une intention que le code ne tenait pas, ce qui est le pire endroit ou laisser une specification.

**Pourquoi 32 tests frontend etaient verts sur un ecran inatteignable.** Chacun montait l'application a `/parametres/comptes` directement. Une suite qui ne monte les ecrans qu'a leur propre route ne peut pas distinguer **construit** de **atteignable**. C'est la lecon, et elle est inscrite en 5.3.

### Ce qui a ete construit

- **`NAV[].sousEntrees`** — le second niveau vit dans **le meme tableau** que le premier, pas dans un second fichier. `Comptes et droits` en est aujourd'hui l'unique entree ; la phase 9 (Personnalisation) et la phase 12 (Abonnement) en ajoutent une en ajoutant **une donnee**.
- **`sousEntreesVisibles`** partage son predicat avec `entreesVisibles` — `_visible`, ecrit une fois. Deux filtres ecrits separement divergent, et celui qui divergerait ici afficherait un lien menant a la 403. Une entree dont le droit manque est **retiree**, pas grisee : la regle de la barre laterale (decision 1 du point de controle 03-13), appliquee au second niveau.
- **`web/src/layout/NavSecondaire.tsx`** — une rangee de liens **dans `main`**, jamais en accordeon de barre laterale. Rendue meme a une seule entree : elle est l'ancrage de l'ecran, et une rangee qui apparaitrait au deuxieme ecran deplacerait tout le contenu le jour ou la phase 9 atterrit.
- **L'accueil des parametres redirige** vers la premiere entree visible. Une page d'accueil qui listerait ce qui est a un clic est un impot au clic ; un titre d'attente est pire, c'est une impasse.
- **Aucune entree visible n'est pas non plus une impasse.** Le cas ne s'atteint qu'en tapant l'adresse — la barre laterale retire deja `Parametres` a qui n'a pas le droit — et il obtient la **403 pleine page de 8.6**, qui a une issue. **Le droit n'y est pas nomme**, et c'est le choix : aucun droit unique ne possede `/parametres`, et nommer `compte.gerer` enverrait demander le mauvais droit des que la phase 9 y ajoutera un ecran sous un autre code.
- **`/parametres/nimportequoi` est desormais un 404** et non un titre d'attente : ce n'est pas un module a venir.

### Les trois tests

| Test | Ce qu'il tient |
|---|---|
| `rend « Comptes et droits » a un porteur de compte.gerer, et RIEN a qui ne l'a pas` (PERM-02) | la donnee : presence, absence, et la porte du proprietaire |
| `atteint la liste depuis la barre laterale, sans jamais taper d'adresse` (PERM-02) | **celui qui aurait rattrape le defaut** : monter a `/`, cliquer, arriver |
| `rend la rangee de liens DANS la zone de contenu, jamais en accordeon de barre laterale` | la contrainte de 5.3 qui fait tenir le plafond de neuf entrees |

Deux tests **existants** de `shell.test.tsx` affirmaient `PageEnAttente` sur `/parametres` — verts sur un ecran inatteignable. Reecrits contre la destination reelle ; celui du focus de route traverse maintenant une **redirection**, ce qui est precisement le cas ou l'annonce peut rester sur l'etape intermediaire.

## Les trois decisions du proprietaire

### 1. La fuite d'enumeration de magasins dans la reponse d'une bascule — fermee

C'etait la **deviation 5** signalee au point de controle. `magasins_accordes` et `lignes[].magasins` — le denominateur et le numerateur de « Personnalise : 2 magasins sur 3 » — etaient servis **entiers** par `charge_utile_resultat`. Un gerant-gestionnaire d'Anfa qui basculait un droit chez un collegue apprenait donc, dans la reponse, l'existence et le code de Maarif : exactement l'enumeration que `03-UI-SPEC.md` 7.7 refuse, que le catalogue offrable (03-09) et la fiche (03-14, tache 2) tiennent deja — **rouverte par la porte de la reponse d'ecriture**.

- **`services.etat_de`** : la regle d'etat de 7.5 (« uniforme veut dire que tous les magasins accordes sont d'accord ») est extraite en une fonction. Elle etait ecrite **deux** fois — `ligne_de` et `etat_des_droits` — et la projection en aurait fait une troisieme. Trois ecritures divergent, et la divergence serait un interrupteur qui ment sur l'etat reel.
- **`services.intersecter`** : reduit `magasins_accordes`, `lignes[].magasins` et `magasins_etendus` aux magasins de l'appelant, et **recalcule l'etat** sur les ensembles reduits. Sans recalcul, l'ecran lirait « Personnalise : 1 magasin sur 1 », qui n'est pas un etat que 7.5 definit.
- **`code` et `cascade` ne sont pas filtres**, et c'est raisonne : `_verifier_le_pouvoir` refuse deja toute bascule dont un code de la fermeture echappe a l'appelant, donc aucun code ne peut sortir d'ici sans que l'appelant le detienne.
- **La vue** prend ses magasins de `_magasins(acces)`, deja la source du selecteur (5.4), de la colonne `Magasins` (7.2) et de l'intersection de la fiche. Pas un second calcul.
- **C'est une projection de reponse, pas une amputation de l'ecriture.** Le service ecrit ce qu'il doit ecrire ; seul l'appelant voit moins. Le test le verifie en faisant **relire la meme bascule par le proprietaire**, qui retrouve les deux magasins.

**Le schema OpenAPI est inchange** : la FORME de la reponse ne bouge pas, seul son contenu est reduit. `spectacular --file web/src/api/schema.yml --fail-on-warn` regenere un fichier au diff vide.

### 2. La mise en evidence de 2 secondes — abandonnee, et `03-UI-SPEC.md` 7.2 amendee

`03-UI-SPEC.md` 7.2 disait « le dialogue se ferme, la nouvelle ligne se met en evidence deux secondes, **et** la route va directement au detail ». Les deux moities se contredisent : la navigation vers `/parametres/comptes/:id` se produit dans le meme tick, donc **la liste est demontee avant que la mise en evidence puisse etre peinte**. Elle animerait une ligne sur un ecran que personne ne regarde. Il n'y avait rien a verifier au point de controle et rien qu'un test puisse affirmer qui veuille dire quelque chose.

Le paragraphe est **supersede, pas efface** — la forme retenue au point de controle 03-13 pour 9.4. Il porte la date (2026-09-17), la raison, et la condition sous laquelle la decision se rouvre : si une phase ulterieure decide que la creation doit **rester** sur la liste, la mise en evidence redevient sensee. **Aucune ligne de code n'a change** : elle n'avait jamais ete implementee.

`03-UI-SPEC.md` 5.3 gagne au passage les trois regles sorties du blocage ci-dessus.

### 3. Une affaire mono-magasin dans la base de developpement

L'etape 4 du point de controle — « avec un compte a un seul magasin, verifier qu'aucun `Par magasin` n'apparait nulle part » — n'etait pas verifiable : la base de developpement ne contenait qu'une affaire, `anfa`, a deux magasins. Elle en contient deux, ce qui donne au developpement **la forme a deux locataires que le projet exige partout ailleurs**.

| | |
|---|---|
| Affaire | `rabat` — Optique Rabat, base `optique_c000002`, statut `active` |
| Magasin | `AGDAL` — Agdal, **un seul** |
| Proprietaire | `hind@optiquerabat.ma` / `rabat-dev-2026` |
| Gerant | `youssef@optiquerabat.ma` / `rabat-dev-2026` — acces AGDAL, 4 droits (`client.voir`, `client.modifier`, `stock.voir`, `caisse.voir`) |

Provisionnee par `manage.py provision_client --code rabat --raison-sociale "Optique Rabat" --magasin Agdal`, puis les comptes par un script **hors du depot**. C'est de la donnee de developpement : **aucune fixture n'est commitee dans un chemin de production**. `migrate_all --check` rend desormais `2 ok, 0 failed, 0 behind`.

Verifie sur le fil : `/api/auth/moi/` rend un seul magasin, `/api/comptes/` rend deux lignes, `/api/comptes/7/` rend `magasins_accordes: ["AGDAL"]` et 21 lignes de droits.

## Amendement au plan 03-09 — le contrat de reponse d'une bascule

La decision 1 modifie une forme de reponse **figee par un test nomme du plan 03-09**. Consigne ici pour que ce soit tracable depuis lui :

| Plan amende | Ce qui change | Ou |
|---|---|---|
| **03-09** | `magasins_accordes`, `lignes[].magasins` et `magasins_etendus` sont **intersectes avec les magasins de l'appelant** avant serialisation, et `etat` est recalcule sur les ensembles reduits. Les trois bascules (`droits/`, `droits/uniformiser/`, `magasins/`) sont concernees. La **forme** est inchangee — memes champs, memes types, meme schema OpenAPI — donc rien de ce que le plan 03-09 a livre par ailleurs ne bouge : la cascade, la fermeture des prerequis, l'extension des lignes uniformes et les refus sont intacts. | `plateforme/comptes/services.py`, `plateforme/comptes/views.py` |
| **`test_perm03_les_trois_bascules_repondent_le_contrat_de_lecran_de_droits`** | **Amende, pas double.** Ce test EST le contrat, et un contrat qui autorise la fuite doit cesser de l'autoriser. Un quatrieme acte lui est ajoute : un gerant-gestionnaire d'Anfa bascule `caisse.saisir` chez un collegue qui detient les deux magasins, la cascade ramene `caisse.voir` detenu dans les deux — et l'assertion porte sur les **octets** (`maarif.code.encode() not in vue.content`), pas sur `response.data`. Sa docstring porte la date et la raison de l'amendement. | `tests/test_comptes_droits.py` |
| **03-14, tache 2** | La correction de la colonne `Magasins` (contexte `magasins_par_id` construit sur `_magasins(acces)` et non `magasins_actifs_par_id()`) etait la **moitie lecture** du meme defaut. Les deux moities sont maintenant fermees, par la meme source de magasins. | `plateforme/comptes/views.py` |

## Deviations du plan

Les quatre premieres etaient signalees au point de controle ; la cinquieme est celle que le proprietaire a tranchee (decision 1 ci-dessus), et la sixieme est le blocage.

### 1. [Rule 2 — fonctionnalite critique manquante] `GET /api/comptes/{id}/journal/`

La section D de 7.3 exige l'historique, et le plan 03-09 avait consigne son absence comme deliberee : `JournalDroit` etait **ecrit** par le service et lisible en base, mais aucune route ne l'alimentait. Le `collapsible` de la fiche aurait rendu une liste vide. La route est ajoutee, en lecture seule — **propriete du modele**, qui refuse la reecriture et le retrait dans son propre `save()`/`delete()`, pas de la vue — et **intersectee** : sans ce filtre, ouvrir un repli suffirait a contourner ce que `catalogue_offrable` retire. Une entree hors intersection est **retiree**, pas anonymisee : un « (droit masque) » dirait qu'il y a quelque chose a voir et combien de fois, ce qui est la meme divulgation en plus discret. Commit `da3a9c7`.

### 2. [Rule 2] `services.etat_des_droits` et `CompteDetailSerializer`

Le plan 03-09 a livre la surface d'ECRITURE et le catalogue offrable ; la **lecture de l'etat** manquait. Sans elle, l'ecran sait quelles cases dessiner mais pas lesquelles sont cochees, et la sauvegarde par interrupteur de 7.8 deviendrait un rechargement de page. L'etat est calcule depuis `acces_pour` et non depuis un comptage de lignes `DroitAccorde` — **le proprietaire est la raison** : son acces est materialise (03-05), sa table d'octrois est vide, et `resume_des_droits` annonce deja 21 droits sur sa ligne de liste. Une fiche lue autrement dirait « aucun droit » sur la meme personne, dans le meme ecran, a deux clics d'ecart. Commit `b731238`.

### 3. [Rule 1 — bug] Le contexte `magasins_par_id` nommait les magasins d'un collegue

Il etait construit sur `magasins_actifs_par_id()`, donc la colonne `Magasins` de 7.2 et la section B de 7.3 enumeraient a un gerant d'Anfa les magasins qu'il ne detient pas. Passe a `_magasins(acces)`, la meme source que le selecteur de la barre superieure. Commit `b731238`.

### 4. [Rule 3 — bloquant] L'interrupteur est ecrit a la main

Le bloc vendu `switch` est un `Switch` Radix, dont l'etat est un booleen : il ne peut pas porter `aria-checked="mixed"`, que 7.5 exige pour le tri-etat. Un `button` avec son `role="switch"` et son `aria-checked` explicite, plutot qu'une modification du fichier vendu — la regle etablie au plan 03-13 est de corriger un defaut de bloc vendu **au point de montage**, et ici le point de montage suffit puisque le bloc n'est simplement pas utilise. Commit `da3a9c7`.

### 5. [Rule 4 → tranchee par le proprietaire] L'enumeration de magasins dans la reponse d'une bascule

Signalee au point de controle parce qu'elle touchait un **contrat fige par un test nomme d'un autre plan**, ce qui n'est pas une correction a faire en silence. Le proprietaire a decide de la fermer et d'amender le test. Voir « decision 1 » et « Amendement au plan 03-09 » ci-dessus.

### 6. [Rule 1 — bug, decouvert par le proprietaire] L'ecran entier etait inatteignable

Voir « Le blocage du point de controle » ci-dessus. Corrige en tache 5 (`3667445`, `5d378ad`).

### 7. [signale] Le garde-fou « au moins un magasin » est une regle d'interface

Le plan demande que decocher le dernier magasin soit refuse en ligne. **Le serveur, lui, accepte zero magasin**, et c'est la decision 10 du plan 03-09 : un compte neuf en a legitimement zero, donc « au moins un » n'est pas un invariant du modele. Le refus est donc ecrit comme un garde-fou d'interface et commente comme tel, pour que personne ne le prenne un jour pour une garantie.

## Verification humaine — NON EFFECTUEE, et rien ne pretend le contraire

Le proprietaire **a commence** la traversee des huit etapes du point de controle. Il s'est arrete a **l'etape 1**, qui etait **bloquee** : l'ecran n'etait pas atteignable. Il n'a rendu aucun verdict sur quoi que ce soit d'autre.

**Aucune des huit etapes n'est approuvee ni declaree passee.** L'etape 1 a ete **re-activee** par le correctif de navigation, mais **elle n'a pas ete rejouee par une personne**. Restent donc ouvertes les huit :

1. creer un gerant, l'atterrissage direct sur le detail, la banniere « aucun droit » — *re-activee par le correctif, non rejouee*
2. la cascade de prerequis dans les deux sens, et **un seul** `Annuler` restaurant l'ensemble
3. `Par magasin`, l'etat mixte, le badge `Personnalise` replie, `Uniformiser` qui demande d'abord
4. un compte mono-magasin : aucun `Par magasin`, une ligne statique — **desormais verifiable**, l'affaire `rabat` existe (decision 3)
5. le dialogue de desactivation, sa seconde phrase, et l'absence du mot « supprimer » a l'ecran
6. en gerant-gestionnaire : la ligne absente **et** le code absent de la reponse JSON, **dans l'onglet reseau**
7. la traversee au clavier seul puis sous VoiceOver — la verification manuelle nommee dans `03-VALIDATION.md`
8. la relecture contre le lexique de 9.3

Elles rejoignent le blocage existant de la phase 3 : **sept verifications du point de controle 03-12, une du quick 260917-04r, les huit etapes du point de controle 03-13, et ces huit-ci** — a faire en **une seule passe** a la verification de phase.

vitest rend dans jsdom : il ne voit ni clignotement, ni saut de mise en page reel, ni anneau de focus, ni si une phrase se lit comme du francais — et, on vient de l'apprendre a ses depens, il ne voit pas non plus qu'un ecran n'a aucun chemin qui y mene tant qu'un test ne prend pas ce chemin.

## La porte de phase — ce qu'elle doit verifier

La phase 3 est complete cote code. Ce que la verification de phase doit constater, avec les valeurs mesurees au 2026-09-17 :

| Controle | Commande | Etat mesure |
|---|---|---|
| Suite backend complete | `uv run pytest -x -q -m "not slow and not pending"` | **184 passed / 30 deselected** |
| Suite web complete | `npm --prefix web test` | **119 passed**, 5 fichiers |
| Verifications systeme | `manage.py check` | **0 issue (0 silenced)** |
| Fleet a jour | `manage.py migrate_all --check` | **2 ok, 0 failed, 0 behind** |
| Contrat OpenAPI | `manage.py spectacular --fail-on-warn` | **code 0** |
| Diff de schema | `manage.py spectacular --file web/src/api/schema.yml` puis `git diff --exit-code` | **diff vide** |
| Construction web | `npm --prefix web run build` | **code 0** |
| Locale de l'argent | `npm --prefix web run audit:format` | **aucun resultat** |
| Aucun `pending` restant | `uv run pytest -m "pending" --collect-only` | **0 collecte** — les 30 deselectionnes sont tous `slow`, pas `pending` |

**Le seul report enregistre est celui de `03-VALIDATION.md` :** la verification **vivante** de PERM-05 appartient a la phase 8. Les champs qu'elle protege — `article.voir_prix_achat`, `vente.voir_marge` — n'existent pas encore, donc la machinerie de projection est prouvee contre une ressource de test et non contre une vraie ressource. `CHAMPS_PROTEGES` reste vide en phase 3, par construction (plan 03-06).

**Ce que la porte de phase NE peut pas constater seule :** les vingt-quatre verifications manuelles au navigateur listees ci-dessus. Elles sont le seul travail restant de la phase 3, et elles sont humaines.

## Ce que les phases suivantes heritent

1. **Une phase qui ajoute un ecran de parametres ajoute une entree a `NAV[].sousEntrees`.** Pas de JSX, pas de route de premier niveau, pas d'accordeon de barre laterale. La phase 9 (Personnalisation) et la phase 12 (Abonnement) sont deja nommees par 5.3.
2. **Toute reponse portant des codes de magasin ou de droit passe par l'intersection de l'appelant — en ECRITURE comme en lecture.** Le catalogue, la fiche, le journal et les trois bascules le font tous, et par la meme source de magasins. Une nouvelle route qui rend un code de magasin sans passer par `_magasins(acces)` rouvre la meme divulgation.
3. **Un ecran n'est livre que s'il est atteignable.** Au moins un test par surface doit y arriver comme une personne y arrive : monter a la racine, cliquer, assertir. Un test qui monte un composant a sa route ne prouve pas qu'un chemin y mene, et la phase 3 vient d'en payer le prix.
4. **Un code ajoute en phase 8 apparait sur l'ecran des droits sans qu'une ligne de la SPA change.** Libelle, explication, section et prerequis viennent du catalogue serveur. La contrepartie : une permission ajoutee sans libelle francais dans le catalogue apparaitra sans libelle.
5. **La regle d'etat de 7.5 vit dans `services.etat_de`, une seule fois.** Tout nouveau calcul d'etat de droit la lit plutot que de la reecrire.

## Known Stubs

Aucun. Les huit ecrans et composants livres rendent tous de la donnee reelle, venue du serveur. Les seuls codes affiches sans effet visible — `article.voir_prix_achat`, `vente.voir_marge`, `dashboard.voir_ca_global` — sont **accordables des la phase 3 par decision explicite** de `03-UI-SPEC.md` 7.4, pas des ebauches : le droit est reel, stocke et journalise ; c'est le champ qu'il protege qui arrive en phase 8 et en phase 10.

## Threat Flags

Aucun. Le plan n'ajoute ni role, ni base, ni fonction `SECURITY DEFINER` (CLAUDE.md #12 ne s'applique pas). La seule surface reseau ajoutee est `GET /api/comptes/{id}/journal/`, qui est en lecture seule, porte `PeutGererLesComptes` et est intersectee — elle appartient au registre de menaces existant (T-03-95, T-03-100) plutot qu'a une surface nouvelle.

## Self-Check: PASSED

Fichiers annonces comme crees, verifies presents sur le disque : `web/src/pages/comptes/ListeComptes.tsx`, `CreerCompte.tsx`, `DetailCompte.tsx`, `SectionMagasins.tsx`, `SectionDroits.tsx`, `LigneDroit.tsx`, `dialogues.tsx`, `HistoriqueDroits.tsx`, `web/src/layout/NavSecondaire.tsx`.

Commits annonces, verifies presents dans l'historique : `cb0f8fa`, `6050956`, `949d12d`, `b731238`, `da3a9c7`, `17b46a4`, `a495cf5`, `3667445`, `5d378ad`, `8a82aee`, `fa6d646`, `2bc43d3`.

Suites au dernier passage : backend **184 passed / 30 deselected**, web **119 passed**, `npm run build` **code 0**, `npm run audit:format` **sans resultat**, `spectacular --fail-on-warn` **code 0** avec diff de schema vide, `manage.py check` **0 issue**, `migrate_all --check` **2 ok / 0 failed / 0 behind**.

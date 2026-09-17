---
phase: 03-comptes-permissions-app-shell
plan: 13
subsystem: web-app-shell
tags: [app-shell, navigation, magasin-scope, recherche, print-css, accessibilite, clavier, PERM-04, APP-01, APP-03]
requires:
  - 03-03 (shadcn epingle, les 22 blocs vendorises dont `sidebar`, `command`, `popover`)
  - 03-05 (l'acces materialise : `acces.magasins` est deja restreint quand la SPA le lit)
  - 03-08 (`/api/auth/moi/` et `/api/auth/mot-de-passe/`)
  - 03-11 (formaterMontant, le registre de colonnes, la regle du `bdi`)
  - 03-12 (AuthProvider, RequireAuth, RequirePermission, les cinq etats globaux, le client genere)
provides:
  - web/src/layout/nav.ts — le tableau declaratif de huit entrees, plafond dur a neuf, avec `portee` et `disponible`
  - web/src/layout/AppShell.tsx — barre superieure fixe, barre laterale repliable, lien d'evitement, focus et annonce de route
  - web/src/layout/NavLaterale.tsx — le rendu de la navigation, filtre par droit, absent jamais grise
  - web/src/layout/BarreSuperieure.tsx — l'emplacement de marque reserve 24x24, le menu du compte
  - web/src/layout/SelecteurMagasin.tsx — le filtre de portee, l'invite `Choisissez un magasin`, l'absence totale de controle en mono-magasin
  - web/src/layout/Recherche.tsx — l'emplacement de 480px, `Ctrl+K`, la requete brute, `correspondance_exacte`
  - web/src/layout/EtatsGlobaux.tsx — les squelettes qui epousent la mise en page finale
  - web/src/print.css — la geometrie A4, le chrome masque, les en-tetes de tableau repetes
affects:
  - phases 4 a 10 (toute entree de navigation passe par `nav.ts` ; toute route declare sa `portee`)
  - phase 9 (BRAND-01 etend `print.css` sans toucher a sa mise en page de page, et pose deux variables CSS)
  - phase 5 (le raccourci de reference exacte de la recherche est ce dont une douchette clavier a besoin)
  - 03-08 et 03-12 (amendes par la decision 6 ci-dessous — voir « Amendement transverse »)
tech-stack:
  added: []
  patterns:
    - la navigation est UN tableau declaratif ; rien ne rend une entree depuis l'exterieur
    - une route declare `portee: "magasin" | "multi"` et l'invite de choix remplace toute supposition
    - un fichier vendu par shadcn qui est modifie porte la raison en tete ET un test nomme qui rattrape sa reinstallation
key-files:
  created:
    - web/src/layout/nav.ts
    - web/src/layout/AppShell.tsx
    - web/src/layout/NavLaterale.tsx
    - web/src/layout/BarreSuperieure.tsx
    - web/src/layout/SelecteurMagasin.tsx
    - web/src/layout/Recherche.tsx
    - web/src/layout/EtatsGlobaux.tsx
    - web/src/print.css
    - web/tests/shell.test.tsx
  modified:
    - web/src/App.tsx
    - web/src/index.css
    - web/src/etats/PageInterdite.tsx
    - web/src/etats/PageIntrouvable.tsx
    - web/src/pages/MotDePasse.tsx
    - web/src/components/ui/sidebar.tsx
    - web/src/hooks/use-mobile.ts
    - web/src/api/schema.yml
    - web/src/api/types.gen.ts
    - web/tests/connexion.test.tsx
    - web/tests/setup.ts
    - web/vitest.config.ts
    - plateforme/comptes/serializers.py
    - tests/test_comptes_auth.py
    - .planning/phases/03-comptes-permissions-app-shell/03-UI-SPEC.md
key-decisions:
  - "`disponible` reste la porte de la navigation : une construction de production ne livre jamais une entree menant a un emplacement vide. VITE_NAV_COMPLET reste un outil de revue de densite qui compile a `false` constant en production"
  - "`--primary` aligne sur l'accent #2563EB de la specification, pose APRES le bloc du preset zinc pour que celui-ci reste reinstallable ; le bouton de /connexion change de couleur, consequence assumee"
  - "Ctrl+B retire du bloc vendu `sidebar` : 03-UI-SPEC 5.7 interdit tout accord en v1, Ctrl+K etant l'unique exception"
  - "MOBILE_BREAKPOINT passe de 768 a 1024 dans le fichier vendu `use-mobile.ts`, sinon la bande 768-1023px restait sur le rail au lieu du tiroir hors-canevas de 5.6"
  - "`/mot-de-passe` est UNE route et DEUX chemins : le changement force rend deux champs, le changement volontaire trois, avec sa propre copie et une issue `Retour`"
  - "Le changement FORCE n'exige pas `mot_de_passe_actuel` — derogation etroite conditionnee a `doit_changer_mot_de_passe` cote serveur, pas cote client. Pour tout autre compte le champ reste exige, et un test nomme est ce qui empeche la derogation de s'elargir"
patterns-established:
  - "Le plafond de navigation est de neuf entrees : un dixieme module entre dans une section existante ou en remplace une"
  - "Une route a portee magasin DEMANDE lequel plutot que de deviner — un solde affiche pour un magasin que personne n'a designe est un nombre faux sans erreur"
  - "Modifier un fichier vendu se paie d'un commentaire de tete ET d'un test nomme : sinon la correction disparait au prochain `shadcn add` sans que rien ne rougisse"
requirements-completed: [PERM-04, APP-01, APP-03]
duration: ~55m d'execution (taches 1 a 3, puis l'application des six decisions du point de controle)
completed: 2026-09-17
---

# Phase 3 Plan 13 : App shell, portee de magasin et feuille d'impression Summary

**Le shell que neuf phases vont habiter : une navigation declarative filtree par droits qui ne rend rien de ce qui n'est pas detenu, un selecteur de magasin qui disparait entierement pour un mono-magasin et demande lequel plutot que de deviner, et une feuille d'impression A4 ecrite maintenant pour que la phase 9 l'etende.**

## Performance

- **Duree :** ~20 min pour les taches 1 a 3 (09:57 → 10:13), puis ~10 min pour appliquer les six decisions du point de controle (11:20 → 11:29), l'attente humaine entre les deux non comptee
- **Taches :** 3 automatiques (dont 2 en TDD), 1 point de controle bloquant repondu par six decisions
- **Fichiers :** 9 crees, 15 modifies
- **Suites :** backend **182 passed / 30 deselected** (base 180, +2 tests de la decision 6) ; web **85 passed** (base 79, +6) ; `npm run build` **code 0** ; `npm run audit:format` **aucun resultat**

## Accomplissements

- `nav.ts` est **un** tableau declaratif de huit entrees, plafond dur a neuf. `App.tsx` **derive ses routes du meme tableau**, donc une entree et sa destination ne peuvent pas diverger : il n'existe qu'une liste de routes de premier niveau dans le produit.
- Une entree dont le code n'est pas detenu **ne produit aucun noeud DOM** — pas de grise, pas de cadenas, pas d'infobulle. L'application d'un gerant est genuinement plus petite.
- Le selecteur de magasin est un **filtre de portee** : il ne reauthentifie pas, ne navigue pas, et disparait **entierement** pour un utilisateur mono-magasin, ce qui couvre tout le palier `Essentiel`.
- Une route declaree `portee: "magasin"` sous la portee « tous les magasins » rend `Choisissez un magasin`. **Jamais** le contenu du premier — un solde de caisse affiche pour un magasin que personne n'a designe est la categorie de panne la plus couteuse de ce produit.
- La recherche reserve ses 480px sans fournisseur enregistre, **n'applique aucune normalisation cliente** (une saisie arabe ou une reference de douchette doit faire l'aller-retour intacte) et pose le raccourci `correspondance_exacte` dont la phase 5 aura besoin.
- `print.css` existe : `@page A4`, chrome masque, `display: table-header-group`, aucun gabarit de document, aucune dependance PDF. La phase 9 enveloppe le meme HTML dans WeasyPrint.
- Le lien d'evitement ouvre l'ordre de tabulation, le focus se porte sur le `h1` a chaque changement de route et l'annonce poliment, aucun `tabindex` positif, aucun anneau de focus supprime.

## Task Commits

1. **Tache 1 (RED) : le contrat de navigation, les reperes, le focus de route** — `c5535df` (test)
2. **Tache 1 (GREEN) : la mise en page, la navigation declarative, le clavier** — `1da30e7` (feat)
3. **Tache 2 (RED) : portee de magasin, portee de route, emplacement de recherche** — `60e14d7` (test)
4. **Tache 2 (GREEN) : le selecteur, l'invite de choix, la recherche** — `fa64b6d` (feat)
5. **Tache 3 : la feuille d'impression** — `8d4b1f2` (feat)
6. **Tache 4 (RED) : les ecarts tranches au point de controle** — `69deadb` (test)
7. **Tache 4 (GREEN) : le changement force ne redemande pas le mot de passe actuel** — `2eb9de8` (feat)
8. **Tache 4 (GREEN) : l'accent, le raccourci accorde, la borne du tiroir** — `68afded` (fix)
9. **La specification 9.4 decrit deux chemins, 5.3 confirme `disponible`** — `22799d5` (docs)

## Reponse du point de controle (tache 4) — six decisions

Le proprietaire a commence la traversee manuelle des huit etapes, a releve en chemin un defaut de conception qui n'etait pas dans la liste, et a rendu **six** decisions. Les cinq premieres portent sur des ecarts entre le produit et sa propre specification ; la sixieme revient sur une decision anterieure.

### 1. Visibilite de la navigation — `disponible` reste la porte. Aucun changement de code.

Voir le shell avec seulement les entrees construites pose la question evidente : faut-il assouplir la regle pour que le produit paraisse complet ? **Non.** Une construction de production ne doit jamais livrer une entree menant a un emplacement vide — un opticien qui clique `Caisse` en phase 4 et n'atterrit sur rien a appris que le produit est casse. Les entrees apparaissent a mesure que les phases atterrissent.

`VITE_NAV_COMPLET` reste exactement ce qu'il est : un outil de revue de densite, qui doit **continuer a compiler a `false` constant** dans une construction de production, jamais un drapeau de fonctionnalite qu'on livre active. Decision consignee dans `03-UI-SPEC.md` 5.3 (`22799d5`) ; **aucune ligne de code n'a change**.

### 2. `--primary` aligne sur `#2563EB`

`03-UI-SPEC.md` section 4 reserve `#2563EB` au bouton primaire unique d'un ecran, a l'anneau de focus, a la barre de l'entree de navigation active, a l'etat coche et a la ligne selectionnee. Le preset zinc installe au plan 03-03 laissait `--primary` quasi noir : le produit contredisait son propre document de reference, l'anneau de focus etant conforme et le bouton non.

- Pose dans `web/src/index.css` **apres** le bloc du preset — le bloc vendu reste reinstallable tel quel.
- **Le bouton `Se connecter` de `/connexion`, deja revu, change de couleur. C'est accepte, pas une regression** : le proprietaire a choisi que le produit ressemble a sa specification.
- L'accroche de marque est intacte : `--accent-marque` pointe toujours sur `--primary`, et la phase 9 pose `--primary` en style en ligne sur `:root`, ce qui l'emporte sur toute regle de feuille de style.

**Contraste mesure de `#FFFFFF` sur `#2563EB` : 5,17:1** (luminance relative de l'accent 0,1532). Au-dessus du plancher AA de 4,5:1 pour du texte normal — la table de la section 4 annonce 4,5:1, valeur prudente. AAA texte normal (7:1) n'est pas atteint et n'est pas exige. Les boutons restent en graisse 600.

### 3. `Ctrl+B` retire du bloc vendu `sidebar`

`03-UI-SPEC.md` 5.7 interdit tout raccourci accorde ou mnemonique en v1, `Ctrl+K` pour la recherche etant l'unique exception : le temps de support est le cout dominant par client. Le bloc officiel shadcn installait un ecouteur global repliant la navigation sur `Ctrl/Cmd+B` — qui est par ailleurs le gras dans tout autre logiciel utilise au comptoir, donc il repliait la navigation par surprise.

La constante et son `useEffect` sont supprimes. `toggleSidebar` reste : c'est ce que `SidebarTrigger` appelle, et le bouton, lui, est decouvrable.

### 4. `MOBILE_BREAKPOINT` passe de 768 a 1024

`03-UI-SPEC.md` 5.6 place le tiroir hors-canevas **en dessous de 1024px** et le rail d'icones de 1024 a 1279px. Le fichier vendu coupait a 768, ce qui laissait la bande 768-1023px sur un rail de 56px avec un tableau dense — exactement ce que la specification voulait eviter.

### 5. La copie du changement volontaire

`Changer mon mot de passe` du menu du compte menait a une page dont la copie etait ecrite pour un changement **force** : « Ce mot de passe vous a ete communique par le proprietaire » est faux pour quelqu'un qui a choisi le sien il y a six mois. Le chemin volontaire porte desormais son titre (`Changer mon mot de passe`), sa phrase (`Choisissez un nouveau mot de passe. Saisissez d'abord celui que vous utilisez aujourd'hui.`) et **une issue** — `Retour`, et non `Annuler`, que le lexique reserve a l'annulation d'une modification enregistree (9.3 et 7.10). Sans cette issue, une page hors du shell est un cul-de-sac sans navigation pour qui a ouvert le menu par erreur.

### 6. Le changement FORCE ne demande plus le mot de passe actuel

**Cette decision revient sur celle du point de controle 03-12** (`985a73e`, qui avait amende `03-UI-SPEC.md` 9.4 pour inscrire le champ au contrat).

**Raison du proprietaire :** sur la redirection forcee, la personne vient de taper ce mot de passe precis, quelques secondes plus tot, pour ouvrir la session qui porte la requete. Le lui redemander revient a lui faire repeter ce qu'elle vient de saisir, sur l'ecran le plus contraint du produit.

**Mise en oeuvre — une derogation ETROITE, et c'est le point :**

| | Chemin force | Chemin volontaire |
|---|---|---|
| Atteint par | la redirection de `RequireAuth` tant que `doit_changer_mot_de_passe` | `Changer mon mot de passe` du menu |
| Champs | 2 (`Nouveau mot de passe`, `Confirmer`) | 3 (+ `Mot de passe actuel`) |
| Serveur | `mot_de_passe_actuel` facultatif | `mot_de_passe_actuel` **exige**, inchange |
| Issue | aucune, la page reste inevitable | `Retour` |

- **Serveur** (`plateforme/comptes/serializers.py`) : l'exigence est portee dans `validate()` et non sur le champ, parce qu'elle depend du compte. La condition est `doit_changer_mot_de_passe` et **rien d'autre**. Facultatif n'est pas ignore : fourni, le champ reste verifie, y compris en changement force.
- **Ce que la derogation ne coute pas :** la garantie du plan 03-08 — qu'un poste laisse deverrouille ou un CSRF reussi donne une **session** et non **le compte** — survit intacte pour tout compte ordinaire. Elle ne protegeait rien dans l'etat force : le mot de passe d'un compte en changement force a ete **pose par le proprietaire ou l'operateur**, il est connu d'un tiers par construction, et c'est precisement pourquoi le drapeau est leve.
- **Tests, ecrits avant l'implementation**, nommes d'apres PERM-01 :
  - `test_perm01_un_changement_force_n_exige_pas_le_mot_de_passe_actuel` — la derogation ;
  - `test_perm01_un_compte_ordinaire_reste_refuse_sans_le_mot_de_passe_actuel` — **le garde-fou, et c'est celui qui compte.** Une derogation ecrite pour un cas precis s'elargit au premier refactoring qui trouve la condition genante ; ce test rougit quand cela arrive. Ses deux jambes (refus sans le champ, acceptation avec) sont dans le meme test, sinon le refus seul serait vert sur un point de terminaison simplement casse.
- **Schema** : `web/src/api/schema.yml` et `web/src/api/types.gen.ts` regeneres dans le meme commit que le serialiseur (`2eb9de8`), `mot_de_passe_actuel` quittant la liste `required`.

## Amendement transverse — plans 03-08 et 03-12

La decision 6 modifie du travail possede par deux autres plans. Consigne ici pour que ce soit tracable depuis eux :

| Plan amende | Ce qui change | Ou |
|---|---|---|
| **03-08** | `ChangementMotDePasseSerializer` : `mot_de_passe_actuel` devient facultatif **pour les seuls comptes en changement force**. Le contrat de statuts, la limitation de debit et le reste du plan sont intacts. La garantie « une session volee n'est pas un compte vole » vaut toujours pour tout compte ordinaire, et un test nomme la tient. | `plateforme/comptes/serializers.py`, `tests/test_comptes_auth.py` |
| **03-12** | `web/src/pages/MotDePasse.tsx` passe d'un chemin a deux. La decision de son point de controle (« le champ est au contrat, la phase 9 ne rouvre pas ») est **revisee** : elle reste vraie du chemin volontaire, elle ne l'est plus du chemin force. | `web/src/pages/MotDePasse.tsx`, `web/tests/connexion.test.tsx` |
| **03-UI-SPEC.md 9.4** | Le paragraphe ajoute en `985a73e` est **supersede, pas efface**. La section decrit desormais les deux chemins, avec l'historique des deux arbitrages (2026-09-16 puis 2026-09-17) et la raison de la revision, pour qu'un lecteur futur voie une decision tranchee et non une hesitation. | `22799d5` |

## Fichiers vendus modifies — et pourquoi c'est note

Deux fichiers sous `web/src/components/ui/` et `web/src/hooks/` proviennent du registre shadcn et ne sont normalement pas edites. Ils l'ont ete :

| Fichier | Modification | Rattrapage |
|---|---|---|
| `web/src/components/ui/sidebar.tsx` | la constante de raccourci et son `useEffect` `Ctrl/Cmd+B` supprimes | test `aucun raccourci accorde ne replie la barre laterale`, qui verifie le comportement **et** l'absence du nom de la constante dans le fichier |
| `web/src/hooks/use-mobile.ts` | `MOBILE_BREAKPOINT` 768 → 1024 | test `le tiroir hors-canevas s'ouvre a 1024px, la borne de la specification` |

Chacun porte en tete un commentaire disant qu'il est vendu, ce qui a change et pourquoi. **Un `shadcn add sidebar` ramenerait les deux defauts** ; les tests nommes sont la seule chose qui le rende visible.

## Verification humaine — NON TERMINEE, et rien ne pretend le contraire

Le proprietaire **a commence** la traversee des huit etapes du point de controle, a decouvert en chemin le defaut de la decision 6, et **n'a pas rendu de verdict sur le reste**.

**Aucune des huit etapes n'est approuvee, aucune n'est declaree passee.** Restent ouvertes : les huit entrees en proprietaire, la densite sous `VITE_NAV_COMPLET=1`, l'application visiblement plus petite d'un gerant, l'absence totale de controle en mono-magasin, le changement de portee sans changement de route, la traversee au clavier seul puis sous VoiceOver (la verification manuelle nommee dans `03-VALIDATION.md`), `Ctrl+P`, et le zoom a 200%.

Elles rejoignent le blocage existant de la phase 3 : **sept verifications du point de controle 03-12, plus une du quick 260917-04r, plus celles-ci** — a faire en une seule passe a la verification de phase. Trois des six decisions ci-dessus repeignent ou redimensionnent le shell (accent, raccourci, borne du tiroir), donc la passe doit se faire **apres** elles, ce qui est le cas.

vitest rend dans jsdom : il ne voit ni clignotement, ni saut de mise en page reel, ni anneau de focus, ni si une phrase se lit comme du francais.

## Ce que les phases 4 a 12 heritent

1. **Le plafond de neuf entrees de navigation est dur.** Huit sont prises, une est reservee. Un dixieme module **entre dans une section existante ou en remplace une** ; il n'obtient pas une dixieme ligne. Les ordonnances, en particulier, n'ont pas d'entree de premier niveau — elles vivent en onglet dans la fiche d'un client.
2. **Toute route declare sa portee.** `portee: "magasin"` signifie que la zone de contenu rend l'invite de choix quand la portee active est « tous les magasins ». **Une route a portee magasin ne devine jamais lequel.** Les phases 5, 6, 7, 8 et 10 ajoutent leurs entrees a `nav.ts` avec leur portee, et n'ecrivent pas de selecteur.
3. **La phase 9 etend `print.css`, elle ne touche pas a sa mise en page de page.** La geometrie A4, le masquage du chrome et la repetition des en-tetes de tableau sont poses ; la phase 9 enveloppe le meme HTML dans WeasyPrint et ajoute la marque.
4. **Modifier un fichier vendu se paie d'un commentaire de tete et d'un test nomme.** Deux precedents existent, la regle est etablie.

## Self-Check: PASSED

Fichiers annonces comme crees, verifies presents sur le disque : `web/src/layout/nav.ts`, `AppShell.tsx`, `NavLaterale.tsx`, `BarreSuperieure.tsx`, `SelecteurMagasin.tsx`, `Recherche.tsx`, `EtatsGlobaux.tsx`, `web/src/print.css`, `web/tests/shell.test.tsx`.

Commits annonces, verifies presents dans l'historique : `c5535df`, `1da30e7`, `60e14d7`, `fa64b6d`, `8d4b1f2`, `69deadb`, `2eb9de8`, `68afded`, `22799d5`.

Suites au dernier passage : backend 182 passed / 30 deselected, web 85 passed, `npm run build` code 0, `npm run audit:format` sans resultat.

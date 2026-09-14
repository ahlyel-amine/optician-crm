---
phase: 03-comptes-permissions-app-shell
plan: 03
subsystem: web-echafaudage
tags: [web, vite, react, typescript, vitest, tailwind, shadcn, meme-origine, APP-01, APP-03, PERM-06]
requires:
  - 03-01 (tests/fixtures/formats_mad.json — la specification partagee)
provides:
  - web/ — Vite 8.2.2 + React 19.3.0 + TypeScript 5.9.3, construction verte depuis un checkout propre
  - le proxy meme-origine /api et /static vers 127.0.0.1:8010, prouve par une requete reelle
  - shadcn/ui initialise, preset epingle style new-york / baseColor zinc / cssVariables true
  - 22 blocs officiels vendorises sous web/src/components/ui
  - vitest qui tourne une fois et sort, jamais en surveillance
  - web/tests/format.test.ts et web/tests/colonnes.test.ts — les deux tests frontend nommes
  - le test d'audit anti-Intl, vert des maintenant
  - la couche de variables CSS sur laquelle BRAND-01 (phase 9) se branchera
affects:
  - 03-10 (openapi-typescript, la porte de diff du schema : le script api:types est en place)
  - 03-11 (retire les .skip et ecrit src/format/montant.ts, src/format/date.ts, src/projection/tableau.tsx)
  - 03-12, 03-13 (le shell reel, la connexion, la navigation filtree par les droits)
  - phase 4 (react-hook-form et le bloc shadcn `form`, differes ici)
  - phase 5 (@tanstack/react-table, differe ici)
  - phase 9 (BRAND-01 : --primary et --primary-foreground, rien d'autre)
tech-stack:
  added:
    - vite@8.2.2
    - "@vitejs/plugin-react@6.1.1"
    - react@19.3.0 / react-dom@19.3.0
    - react-router-dom@7.18.3
    - "@tanstack/react-query@5.102.8"
    - openapi-fetch@0.17.0 / openapi-react-query@0.5.4 / openapi-typescript@7.13.0
    - typescript@5.9.3 (PAS 7.x)
    - typescript-eslint@8.70.0
    - vitest@4.1.11 (dist-tag V4)
    - tailwindcss@4.3.3 + "@tailwindcss/vite@4.3.3"
    - radix-ui@1.6.7, cmdk@1.1.1, sonner@2.0.8, lucide-react@1.46.0, cn@0.3.0
    - jsdom@29.1.1, "@testing-library/react@16.3.3"
  patterns:
    - le proxy meme-origine comme mecanisme de securite, pas comme confort de developpement
    - toutes les versions epinglees exactement, sans ^ ni ~, package-lock.json committe
    - les blocs shadcn vendorises et committes, donc relisibles et versionnes
    - une suite nommee et ignoree avec un commentaire qui nomme le plan qui la rendra verte
    - import.meta.glob pour un module qui n'existe pas encore, et non @vite-ignore
key-files:
  created:
    - web/package.json
    - web/package-lock.json
    - web/vite.config.ts
    - web/vitest.config.ts
    - web/tsconfig.json
    - web/tsconfig.node.json
    - web/components.json
    - web/index.html
    - web/src/main.tsx
    - web/src/App.tsx
    - web/src/index.css
    - web/src/lib/utils.ts
    - web/src/hooks/use-mobile.ts
    - web/src/components/ui/ (22 blocs)
    - web/tests/format.test.ts
    - web/tests/colonnes.test.ts
    - web/.gitignore
  modified:
    - .gitignore
decisions:
  - baseColor zinc et non neutral, et le separateur U+00A0 — les deux points du checkpoint etaient tranches avant l'execution
  - le bloc shadcn `form` est differe a la phase 4 parce qu'il tire react-hook-form, que ce plan interdit explicitement
  - components.json ecrit a la main apres init, parce que le CLI 4.21.0 ne sait plus produire le style new-york
  - web/tests/ est hors du projet tsconfig de construction, sinon l'etat rouge voulu casserait `npm run build`
  - les identifiants de requirement ne sont PAS coches : ce plan est un contributeur, pas le closeur
metrics:
  tasks: 4
  commits: 3
  tests-added: 14 (5 verts, 9 ignores jusqu'au plan 03-11)
  suite-backend: 114 passed (inchangee, aucun fichier backend touche)
  completed: 2026-09-14
---

# Phase 3 Plan 03 : Echafaudage `web/` Summary

`web/` existe, construit depuis un checkout propre, et son test sort au lieu de surveiller ;
le serveur de developpement proxifie `/api` et `/static` vers Django, ce qui a ete prouve par
une requete reelle plutot que par lecture du fichier de configuration ; shadcn/ui est
initialise avec le preset epingle **new-york / zinc / variables CSS** et 22 blocs vendorises ;
et les deux tests frontend nommes sont en place, ignores, avec un commentaire qui nomme le
plan 03-11 qui les rendra verts.

## Les deux decisions irreversibles, et leur etat

| Decision | Valeur | Pourquoi elle est prise ici |
|---|---|---|
| Meme origine des le premier jour | `server.proxy` vers `127.0.0.1:8010` | Le navigateur ne voit qu'une origine, donc pas de CORS, pas de `django-cors-headers`, pas de prevol, et `SameSite=Lax` suffit. Une origine distincte imposerait `SameSite=None` et `CORS_ALLOW_CREDENTIALS`, ce qui affaiblirait materiellement l'argument de session de toute la phase (T-03-11). |
| Preset shadcn | `style: new-york`, `baseColor: zinc`, `cssVariables: true` | `style` et `baseColor` ne peuvent pas changer apres coup sans reinstaller les 22 blocs. |

**Le proxy est verifie, pas suppose.** Un faux backend a ete demarre sur `127.0.0.1:8010`, puis :

```
GET http://localhost:5173/api/auth/moi/
-> {"servi_par":"faux-django:8010","chemin":"/api/auth/moi/","hote_vu_par_le_backend":"127.0.0.1:8010"}
```

La requete part vers **5173** et la reponse vient de **8010**. Aucun en-tete `Access-Control-*`
n'apparait dans la reponse, et c'est le resultat voulu : il n'y a qu'une origine, donc il n'y a
rien a autoriser. `/static` se comporte de meme.

## Le checkpoint, et ce qui en depend

Les deux questions du checkpoint (tache 4) etaient **deja tranchees** quand ce plan a demarre, et
le contexte d'execution les a transmises comme reglees :

1. **`baseColor: zinc`**, retenu par l'utilisateur contre le `neutral` que recommandait a
   l'origine `03-UI-SPEC.md`. Le document a ete mis a jour et committe (`eaa154e`) ; ses valeurs
   hexadecimales (`#F4F4F5`, `#E4E4E7`, `#52525B`) etaient deja du zinc et non du neutral
   (`#F5F5F5`, `#E5E5E5`, `#525252`), donc ce choix rend le document coherent avec lui-meme.
   Compromis accepte et consigne : zinc porte une legere chroma bleue, donc un client de la
   phase 9 dont la marque est chaude cotoiera des gris faiblement froids.
2. **Le separateur de milliers du MAD est U+00A0**, virgule decimale : `1 800,00 MAD`
   (CLAUDE.md #14). Ni U+202F, ni le point de l'ICU `fr-MA`.

**Aucune correction n'a donc ete apportee a `tests/fixtures/formats_mad.json`** — elle declarait
deja U+00A0, et trois tests actifs le verifient desormais cote client. Les plans 03-10 et 03-11
la liront telle quelle.

> Mise au point sur la provenance : ces deux reponses ont ete transmises par le contexte
> d'execution et par le commit `eaa154e` deja au depot. Aucun echange direct avec l'utilisateur
> n'a eu lieu pendant cette execution.
>
> **Complement de l'orchestrateur — les deux reponses viennent bien de l'utilisateur.** Le
> separateur U+00A0 a ete choisi explicitement lorsque les trois conventions concurrentes lui ont
> ete presentees (Django `fr` U+00A0, ICU `fr-FR` U+202F, ICU `fr-MA` point), et consigne en
> CLAUDE.md #14. Le preset a ete choisi en deux temps : `new-york` avec une couleur de base autre
> que celle recommandee, puis `zinc` parmi slate / stone / gray / zinc. L'executant avait raison
> de ne pas attester ce qu'il n'avait pas vu ; la trace est ici.

## Ce qui a ete verifie plutot que constate

Trois mecanismes ont ete mis a l'epreuve au lieu d'etre declares corrects.

**1. Le chargement differe des modules futurs.** La premiere version employait
`await import(/* @vite-ignore */ specifieur)`. Une repetition — deposer des modules bouchons,
retirer les `.skip`, lancer la suite — a montre qu'elle etait **cassee** : `@vite-ignore` repousse
bien la resolution a l'execution, mais **hors du resolveur de Vite**, donc l'alias `@` n'y est
plus connu et le module reste introuvable *meme une fois ecrit*. Le plan 03-11 aurait herite de
deux suites inutilisables. Remplace par `import.meta.glob`, qui rend un objet vide quand rien ne
correspond et un vrai import paresseux sinon. La repetition a ete refaite : les 7 tests echouent
alors sur de vraies assertions (`expected '1800.00' to be '1 800,00 MAD'`), ce qui est exactement
l'etat rouge que 03-11 doit rendre vert. Les bouchons ont ete supprimes.

**2. Le test d'audit anti-`Intl`.** Une violation a ete injectee dans `src/App.tsx` :

```
AssertionError: expected [ 'App.tsx : Intl.NumberFormat', 'App.tsx : fr-MA' ] to deeply equal []
```

Il mord. La sonde a ete retiree. Le test porte aussi un **controle positif** — il affirme d'abord
qu'il trouve des fichiers a surveiller — sans lequel il passerait contre un dossier vide ou un
motif casse, ce qui est une garantie qui n'en est pas une.

**3. Le piege de l'espace insecable.** L'outil d'ecriture normalise bien `\u00a0` en caractere
U+00A0 brut, comme la vague 1 l'avait constate. Detecte et corrige au `perl`. Etat final de
`web/tests/format.test.ts`, mesure :

```
escape \u00a0 litteral : 1
U+00A0 brut            : 0
U+202F brut            : 0
```

## Les tests livres

| Fichier | Suite | Etat | Devient vert au |
|---|---|---|---|
| `format.test.ts` | « la fixture partagee epingle l'espace insecable » (3 tests) | **vert** | — |
| `format.test.ts` | « aucune locale ne decide du format de l'argent » (2 tests) | **vert** | — |
| `format.test.ts` | « le formatage client respecte la fixture partagee » (7 tests) | ignoree | plan 03-11 |
| `colonnes.test.ts` | « le rendu d'un tableau suit la presence dans le payload » (2 tests) | ignoree | plan 03-11 |

`npm --prefix web test` : **5 passed, 9 skipped**, code de sortie 0, 584 ms, le mot `watch`
n'apparait pas dans la sortie.

Les suites ignorees le sont par `describe.skip` et **non** par `it.todo` : un `todo` ne verifie
rien et se fait oublier, alors que le corps de ces tests est ecrit, complet, et n'attend que son
module. Le commentaire au-dessus de chaque `.skip` nomme le plan 03-11 et le fichier a creer.

`colonnes.test.ts` fixe aussi le contrat que 03-11 n'aura pas a deviner :
`src/projection/tableau.tsx` exportant `TableauProjete({ colonnes, lignes, legende })`. Le nom
fait echo a `plateforme/projection/` cote serveur : un seul registre, deux moteurs de rendu.

## Deviations from Plan

### 1. [Rule 3 — Blocage] Le CLI shadcn 4.21.0 ne sait plus produire le style `new-york`

- **Trouve pendant :** tache 2
- **Probleme :** le plan prevoit `npx shadcn@4.21.0 init -t vite` en repondant `new-york` /
  `neutral`. Le CLI 4.21.0 n'a plus ces invites : il demande une **bibliotheque de composants**
  (Base UI / React Aria / Radix UI) puis un **preset nomme** (Nova, Vega, Maia, Lyra, Mira, Luma,
  Sera, Rhea, Custom). L'init produit `"style": "radix-nova"` et `"baseColor": "neutral"`, aucune
  combinaison d'options n'atteignant `new-york` ni `zinc`.
- **Correction :** le registre officiel sert toujours le style `new-york` (verifie,
  `https://ui.shadcn.com/r/styles/new-york/button.json` -> 200). `components.json` a donc ete
  **ecrit a la main** avec le preset epingle, avant l'installation du moindre bloc — ce que la
  tache 2 demande explicitement (« verifier le fichier apres coup plutot que de faire confiance
  aux invites »). Les 22 blocs proviennent bien de `styles/new-york/`.
- **Fichiers :** `web/components.json`
- **Commit :** 46f0f04

### 2. [Rule 3 — Blocage] Le preset `radix-nova` installe une webfont et des versions flottantes

- **Trouve pendant :** tache 2
- **Probleme :** l'init a ajoute `@fontsource-variable/geist` — une webfont, alors que
  `03-UI-SPEC.md` section 3 dit explicitement qu'aucune webfont n'est telechargee en v1 (un
  magasin sur une connexion faible la paie a chaque chargement, et le produit est en ligne
  uniquement donc il n'y a aucune garantie de cache). Il a aussi ajoute `shadcn` comme dependance
  d'execution et une serie de versions en `^`, contre la discipline d'epinglage du projet
  (menace T-03-13).
- **Correction :** `@fontsource-variable/geist` et `shadcn` desinstalles ; `index.css` genere
  depuis la rampe `zinc` du registre officiel puis complete par la pile de polices systeme de
  `03-UI-SPEC.md` section 3, **faces arabes comprises** (non optionnelles : un nom de client arabe
  sans repli produit des carres tofu). Toutes les dependances ramenees a un epinglage exact :
  `grep` de `^` et `~` dans `package.json` retourne zero.
- **Fichiers :** `web/package.json`, `web/package-lock.json`, `web/src/index.css`
- **Commit :** 46f0f04

### 3. [Rule 4 — tranche par la contradiction interne du plan] Le bloc `form` est differe a la phase 4

- **Trouve pendant :** tache 2
- **Probleme :** `form` figure dans l'inventaire des 22 blocs, mais le bloc shadcn `form` **est**
  une enveloppe autour de `react-hook-form` — ses dependances declarees sont
  `react-hook-form`, `zod` et `@hookform/resolvers` (verifie sur le registre). Or l'action de la
  tache 2 interdit explicitement d'installer `react-hook-form` (phase 4), et son critere
  d'acceptation exige `grep -c 'react-hook-form\|@tanstack/react-table' web/package.json` = 0. Les
  deux exigences ne peuvent pas etre satisfaites ensemble.
- **Resolution :** le critere d'acceptation testable l'emporte, et il va dans le sens de
  `03-UI-SPEC.md` section 1 (« Deferred with intent: react-hook-form -> Phase 4 »). Les deux
  formulaires de la phase 3 — connexion et creation de compte — sont des composants controles et
  n'ont pas besoin du bloc. `form` sera installe en phase 4 avec `react-hook-form`.
- **Consequence sur le compte :** 21 blocs demandes, plus `sheet` qui arrive comme dependance de
  registre de `sidebar`, soit **22 fichiers** sous `web/src/components/ui` — le critere « au moins
  22 » est tenu.
- **A reprendre en phase 4 :** installer `form`.

### 4. [Rule 3 — Blocage] `web/tests/` exclu du projet TypeScript de construction

- **Trouve pendant :** tache 3
- **Probleme :** les suites importent des modules qui n'existent pas encore (l'etat rouge voulu).
  Les inclure dans le `tsconfig.json` que `tsc -b` construit ferait echouer `npm run build`, que
  la verification du plan exige en code 0.
- **Correction :** `include: ["src"]`, avec un commentaire en tete de fichier expliquant pourquoi
  et indiquant que le plan 03-11 les reintegrera en meme temps qu'il ecrira les formateurs. vitest
  ne verifie pas les types par defaut, donc les tests tournent quand meme.
- **Fichiers :** `web/tsconfig.json`

### 5. [Rule 3 — Blocage] `tsconfig.node.json` ne peut pas etre un projet reference en `noEmit`

- **Trouve pendant :** tache 1
- **Probleme :** `tsc -b` echoue avec `TS6310: Referenced project may not disable emit`.
  TypeScript 5.9 refuse encore `noEmit` sur un projet reference.
- **Correction :** `emitDeclarationOnly` avec `outDir` dans `node_modules/.tmp/`, jamais suivi par
  git. Le script `"build": "tsc -b && vite build"` reste tel que le plan l'ecrit.
- **Fichiers :** `web/tsconfig.node.json`

### 6. [Rule 1 — Bogue] `jsdom` 30.x exige un Node plus recent que celui de la machine

- **Trouve pendant :** tache 3
- **Probleme :** `jsdom@30.0.1` declare `engines.node: ^22.22.2 || ^24.15.0 || >=26.0.0` ; la
  machine tourne en Node 22.21.1. `npm` n'emet qu'un avertissement `EBADENGINE` et installe quand
  meme — le genre d'avertissement qu'on ignore jusqu'a une panne obscure.
- **Correction :** epingle a `jsdom@29.1.1`, la derniere version dont la plage d'`engines` accepte
  22.21.1.

### 7. Les identifiants de requirement ne sont pas coches

- **Decision :** `APP-01`, `APP-03` et `PERM-06` figurent dans l'en-tete de ce plan, mais dix
  plans de la phase 3 les revendiquent. Ce plan livre l'echafaudage et les tests rouges ; le
  formateur client (APP-03) arrive au 03-11, le shell francais (APP-01) au 03-13, la couche de
  projection (PERM-06) aux 03-06, 03-09 et 03-11. Cocher une exigence dont les tests sont encore
  ignores serait precisement le faux vert que ce projet cherche a rendre impossible.
- **Action :** `requirements mark-complete` **non execute**. `REQUIREMENTS.md` est inchange.

### 8. Notes mineures

- `-t vite` n'a pas ete passe a l'init : le CLI detecte Vite tout seul (`Verifying framework.
  Found Vite`), et `-t` sert a **creer** un projet neuf, ce qui aurait ecrase l'echafaudage de la
  tache 1.
- Tailwind a du etre installe **avant** l'init : le CLI refuse de demarrer sans
  (`No Tailwind CSS configuration found`). `tailwindcss` et `@tailwindcss/vite` sont en 4.3.3,
  la version de `03-UI-SPEC.md`.
- `next-themes@0.4.6` est arrive comme dependance du bloc `sonner`. Le mode sombre n'est pas en v1
  et aucun interrupteur n'est cable ; le bloc est laisse **tel que le registre le sert**, pour
  qu'un futur `shadcn diff` reste exploitable.
- `src/lib/utils.ts` reexporte le `cn` du paquet `cn` plutot que d'en reimplementer un a base de
  `clsx` + `tailwind-merge` : les blocs vendorises importent `cn` depuis ce paquet, et deux
  implementations de fusion de classes qui divergent est un bogue de style invisible a la
  relecture. `clsx` et `tailwind-merge` ont ete desinstalles.

## Ce que ce plan ne livre pas, et qui pourrait le faire croire

- **Aucun formateur.** `formaterMontant`, `formaterDateCourte`, `formaterDateHeure` et
  `TableauProjete` n'existent pas. Les suites qui les testent sont ignorees et le disent.
- **Aucun shell.** `App.tsx` rend un titre et un paragraphe qui annoncent le plan 03-13.
- **Aucun client d'API.** `openapi-fetch`, `openapi-react-query` et `react-router-dom` sont
  installes et epingles mais ne sont importes nulle part ; `src/api/` n'existe pas encore et le
  script `api:types` echouera tant que `schema.yml` n'est pas genere (plan 03-10).

## Known Stubs

| Stub | Fichier | Raison, et qui la leve |
|---|---|---|
| `App.tsx` rend une page d'attente | `web/src/App.tsx` | Le shell reel est le plan 03-13. Le squelette existe pour que `vite build` ait un point d'entree et que le proxy soit verifiable a l'oeil. Le plan le prevoit explicitement : « le shell reel arrive au plan 03-13 ». |
| 9 tests ignores | `web/tests/format.test.ts`, `web/tests/colonnes.test.ts` | Etat rouge voulu par le plan. Chaque `.skip` porte un commentaire nommant le plan 03-11 et le fichier a creer. |

Aucun de ces bouchons n'empeche l'objectif du plan d'etre atteint : l'objectif etait un `web/` qui
construit, un test qui sort, et deux tests nommes qui echouent pour la bonne raison.

## Verification

| Verification du plan | Resultat |
|---|---|
| `npm --prefix web ci` puis `npm --prefix web run build` | code 0, depuis un `node_modules` efface |
| `npm --prefix web test` | code 0, 584 ms, 5 passed / 9 skipped, `watch` absent de la sortie |
| `grep -rn 'Intl.NumberFormat\|toLocaleString\|fr-MA' web/src` | aucun resultat |
| `node -e` sur `web/components.json` | `new-york`, `zinc`, `cssVariables: true`, `rsc: false`, `tsx: true`, `registries: {}` |
| `git status --porcelain web/` apres `npm ci` | vide — `node_modules` et `dist` non suivis |
| `uv run pytest -q` | **114 passed**, inchangee. Les 38 echecs sont les bouchons `pending` du plan 03-02, qui nomment les plans 03-06, 03-09 et 03-10 |

Criteres d'acceptation par tache, tous executes :

| Tache | Critere | Mesure |
|---|---|---|
| 1 | `"test": "vitest run"` | 1 |
| 1 | vitest epingle sans `^` ni `~` | 1 |
| 1 | `"typescript": "5.9.3"` | 1 |
| 1 | `8010` dans `vite.config.ts` | 2 |
| 1 | `lang="fr"` dans `index.html` | 1 |
| 1 | `cors` dans `package.json` | 0 |
| 1 | `web/node_modules` dans `.gitignore` / `schema.yml` dans `.gitignore` | 1 / 0 |
| 2 | `test -f web/components.json` | OK |
| 2 | preset assertions `node -e` | code 0 |
| 2 | `ls web/src/components/ui \| wc -l` | 22 |
| 2 | `sidebar.tsx command.tsx alert-dialog.tsx switch.tsx` | present |
| 2 | `react-hook-form\|@tanstack/react-table` | 0 |
| 3 | `npm test` code de sortie / `watch` dans la sortie | 0 / 0 |
| 3 | tests passes / suites ignorees | 5 / 2 suites (9 tests) |
| 3 | `formats_mad.json` dans `format.test.ts` | 2 |
| 3 | `codePointAt` dans `format.test.ts` | 3 |
| 3 | `03-11` dans les deux fichiers | 5 et 4 |
| 3 | nom exact du test de colonnes | 1 |

## Threat Flags

Aucun. Ce plan n'ouvre ni point d'entree reseau, ni chemin d'authentification, ni acces fichier,
ni changement de schema. Les trois frontieres de confiance de son registre sont traitees :
`T-03-11` par le proxy meme-origine et l'absence de toute dependance CORS, `T-03-12` par le
registre officiel seul et des blocs vendorises et committes, `T-03-13` par un epinglage exact
verifie, `T-03-14` par `vitest run` et un code de sortie mesure, `T-03-15` par un test nomme ecrit
avant le premier tableau.

## Self-Check: PASSED

- 17 fichiers declares en `key-files` : tous presents sur disque.
- `web/src/components/ui/` : 22 blocs presents.
- 3 commits de tache presents dans l'historique : `0dc3824`, `46f0f04`, `60d344c`.
- Aucun residu : `web/scripts/` (generateur de `index.css`, a usage unique) et `web/src/format/`
  (bouchons de la repetition du chargement differe) ont bien ete supprimes, et le grep d'audit
  sur `web/src` confirme qu'aucun `Intl.NumberFormat`, `toLocaleString` ni `fr-MA` n'y subsiste.
- Aucun fichier hors `web/` et hors `.gitignore` racine n'a ete modifie ; la suite backend est
  restee a 114 passed.

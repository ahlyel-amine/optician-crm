---
phase: 03-comptes-permissions-app-shell
plan: 11
subsystem: web-format-projection
tags: [web, format, mad, nbsp, projection, colonnes, bdi, a11y, APP-03, PERM-06]
requires:
  - 03-01 (tests/fixtures/formats_mad.json — la specification partagee)
  - 03-03 (web/ echafaude, les deux suites vitest nommees et ignorees)
provides:
  - web/src/format/ — formaterMontant ecrit a la main, formaterDateCourte, formaterDateHeure
  - le script npm audit:format — l'interdiction d'Intl pour la monnaie devient une ligne de CI
  - web/src/tableau/registre.ts — colonnesVisibles, le filtre `champ in ligne`
  - web/src/tableau/Tableau.tsx — TableauProjete, aucun en-tete litteral, aucun substitut, aucun total fantome
  - web/src/tableau/Valeur.tsx — un bdi par valeur fournie par l'utilisateur
  - web/tsconfig.test.json — les suites sont de nouveau typecheckees par npm run build
affects:
  - phases 4 a 10 (tout tableau et toute valeur d'utilisateur passent desormais par ces trois modules)
  - 03-12, 03-13 (le shell consomme formaterMontant et TableauProjete)
  - phase 8 (la verification vivante du registre contre un vrai prix_achat)
  - phase 9 (le formateur PDF WeasyPrint lit la meme fixture)
tech-stack:
  added: []
  patterns:
    - une specification partagee (tests/fixtures/formats_mad.json), deux implementations testees contre elle
    - l'arrondi monetaire se fait sur les chiffres de la chaine, jamais sur un double
    - la presence d'une colonne est pilotee par la donnee, son libelle et son ordre restent declaratifs
    - un projet TypeScript separe pour les tests, pour que @types/node n'atteigne pas le code du navigateur
key-files:
  created:
    - web/src/format/montant.ts
    - web/src/format/date.ts
    - web/src/format/index.ts
    - web/src/tableau/registre.ts
    - web/src/tableau/Tableau.tsx
    - web/src/tableau/Valeur.tsx
    - web/tsconfig.test.json
  modified:
    - web/tests/format.test.ts
    - web/tests/colonnes.test.ts
    - web/package.json
    - web/tsconfig.json
decisions:
  - le dossier est src/tableau/ et non src/projection/ ; l'export garde le nom TableauProjete
  - zero ligne rend zero colonne — une recherche sans resultat ne revele pas qu'une colonne protegee existe
  - les assertions de substitut sont faites cellule par cellule sur le texte exact, pas par sous-chaine
  - le normaliseur de Testing Library est neutralise sur les montants, sinon il efface l'U+00A0 teste
  - les tests sont typecheckes par un projet separe, pas en elargissant les types du projet applicatif
  - les identifiants de requirement ne sont PAS coches : APP-03 et PERM-06 sont revendiques par plusieurs plans
metrics:
  tasks: 3
  commits: 3
  tests-added: 14 (28 verts au total, 0 ignore)
  suite-frontend: 28 passed
  suite-backend: 92 passed, 63 deselected (inchangee, aucun fichier backend touche)
  completed: 2026-09-14
---

# Phase 3 Plan 11 : Formatage MAD et registre de colonnes Summary

Le client sait desormais ecrire `1 800,00 MAD` sans demander son avis a une base de locales, et
un champ que le serveur a retire de la charge utile ne peut plus reapparaitre a l'ecran — ni en
colonne vide, ni en tiret, ni en infobulle, ni en total a zero. Les neuf tests ignores depuis le
plan 03-03 sont verts, et quatorze autres les accompagnent.

## Pour les phases 4 a 10, trois regles, et elles sont mecaniques

1. **Aucun `<th>` litteral, jamais.** Chaque tableau declare ses colonnes dans un registre clef
   par **nom de champ de l'API** et passe par `TableauProjete`. Un en-tete n'existe que si sa
   donnee existe. Ecrire un libelle directement dans du JSX le rend inconditionnel, et c'est
   exactement la fuite que PERM-06 ferme.
2. **Chaque valeur fournie par l'utilisateur passe par `Valeur`.** Nom, adresse, raison sociale,
   texte libre. C'est un `<bdi>`, il coute une balise, et il evite d'avoir a deviner colonne par
   colonne laquelle recevra un jour un nom en arabe.
3. **Aucun montant n'est formate sur place.** `formaterMontant` depuis `@/format`, jamais un
   `${montant} MAD` ecrit a la main, jamais `Intl.NumberFormat`, jamais `toLocaleString`.
   `npm run audit:format` le verifie, et la sonde ci-dessous montre qu'il mord.

C'est ce qui rend « absent, pas grise » mecanique plutot que coutumier.

## Ce qui a ete verifie plutot que constate

**1. L'audit anti-`Intl` mord.** Une sonde `src/_sonde.ts` contenant `Intl.NumberFormat("fr-MA")`
et `toLocaleString` a ete deposee : `npm run audit:format` sort en **code 1** et nomme le fichier.
Sonde retiree. Sans cette verification, un script qui ne trouve jamais rien et un script casse se
ressemblent beaucoup.

**2. Le filtre de presence est bien ce qui fait passer les tests.** `colonnesVisiblesSurLignes` a
ete temporairement remplace par `[...colonnes]` dans `Tableau.tsx` : **4 tests tombent**, dont les
quatre absences et le cas « zero ligne ». Filtre restaure. Un test de non-regurgitation qui
passerait aussi sans le mecanisme ne garantit rien.

**3. L'arrondi ne passe pas par un double.** `999.995` est dans la fixture pour cette raison
precise : il vaut `999.99499999999997` en binaire, donc `Math.round(x * 100)` rendrait `999,99`
quand le serveur, qui `quantize` en `ROUND_HALF_UP`, rend `1 000,00`. L'implementation travaille
sur les chiffres de la chaine livree par DRF. Un cas a 17 chiffres (`9007199254740993.00`, non
representable en double) est teste en plus.

**4. Le piege de l'espace insecable, encore.** L'outil d'ecriture normalise a nouveau les escapes
en caracteres U+00A0 bruts — les deux fois ou un separateur a ete ecrit. Detecte, corrige au
`perl`, puis **mesure** sur les neuf fichiers concernes :

```
web/src/format/montant.ts    : escape=2  U+00A0=0  U+202F=0
web/src/format/date.ts       : escape=0  U+00A0=0  U+202F=0
web/src/format/index.ts      : escape=0  U+00A0=0  U+202F=0
web/src/tableau/registre.ts  : escape=0  U+00A0=0  U+202F=0
web/src/tableau/Tableau.tsx  : escape=0  U+00A0=0  U+202F=0
web/src/tableau/Valeur.tsx   : escape=0  U+00A0=0  U+202F=0
web/tests/format.test.ts     : escape=15 U+00A0=0  U+202F=0
web/tests/colonnes.test.ts   : escape=8  U+00A0=0  U+202F=0
tests/fixtures/formats_mad.json : escape=12 U+00A0=0 U+202F=0
```

La sonde qui produit ce tableau a ete supprimee apres mesure.

## Deviations from Plan

### 1. [Rule 3 — Blocage] Le dossier est `src/tableau/`, pas `src/projection/`

- **Trouve pendant :** tache 2
- **Probleme :** `web/tests/colonnes.test.ts`, ecrit au plan 03-03, fixait le contrat
  `src/projection/tableau.tsx`. Le plan 03-11 nomme `src/tableau/registre.ts`,
  `src/tableau/Tableau.tsx` et `src/tableau/Valeur.tsx` dans son `files_modified` **et** dans ses
  criteres d'acceptation, qui greppent ces chemins exacts. Les deux ne peuvent pas etre vrais.
- **Resolution :** le plan l'emporte — c'est lui qui livre, et ses criteres sont executables.
  L'`import.meta.glob` du test pointe desormais `../src/tableau/*.tsx`. **L'export garde le nom
  `TableauProjete`**, qui etait la partie signifiante du contrat : il fait echo a
  `plateforme/projection/` cote serveur, un seul registre, deux moteurs de rendu.

### 2. [Rule 1 — Bogue] Trois assertions du test de 03-03 ne pouvaient pas passer

- **Trouve pendant :** tache 2
- **Probleme :** le test ignore cherchait les substituts par sous-chaine sur le `textContent` du
  tableau entier. Deux d'entre eux se trouvent dans des donnees parfaitement legitimes :
  la reference `MON-4412` contient un tiret, et `1 800,00 MAD` contient `0,00`. Le test aurait
  echoue des sa premiere execution, sur du code correct.
- **Correction :** la comparaison est faite **cellule par cellule et sur le texte exact**. C'est
  plus strict, pas moins : un `—` seul dans une cellule est attrape, et une cellule vide l'est
  aussi (`toContain("")`), ce que la version par sous-chaine ne voyait pas.
- **Fichier :** `web/tests/colonnes.test.ts` — **Commit :** 285f9b1

### 3. [Rule 1 — Bogue] Le normaliseur de Testing Library efface le caractere teste

- **Trouve pendant :** tache 2
- **Probleme :** `screen.getByText("1<U+00A0>800,00<U+00A0>MAD")` ne trouvait rien. Le normaliseur par
  defaut ramene toute suite de `\s` — U+00A0 compris — a une espace ordinaire **du cote de
  l'element**, pas du cote de la chaine cherchee. Pire : avec le normaliseur par defaut, un rendu
  **fautif** produisant des espaces ordinaires passerait le test.
- **Correction :** `{ normalizer: (contenu) => contenu }` sur les requetes de montant. La
  comparaison redevient exacte, point de code par point de code.

### 4. [Rule 1 — Bogue] L'import dynamique de Testing Library desactive sa purge

- **Trouve pendant :** tache 2
- **Probleme :** le cas « zero ligne » echouait en trouvant un en-tete `Prix d'achat`… rendu par
  le test precedent. La purge automatique entre deux tests s'enregistre en appelant `afterEach`
  **au moment de l'import** ; importe dynamiquement dans le corps d'un test, l'appel arrive apres
  la phase de collecte et ne s'enregistre pas.
- **Correction :** import statique en tete de fichier. Le chargement differe reste en place pour
  les modules de l'application — c'est lui qui a permis l'etat rouge du plan 03-03.

### 5. [Rule 3 — Blocage] `web/tests/` retourne au typecheck, mais dans son propre projet

- **Trouve pendant :** tache 1
- **Probleme :** le plan 03-03 avait sorti `web/tests/` du `tsconfig.json` de construction et
  designe 03-11 comme le plan qui les reintegre. Un simple `"include": ["src", "tests"]` echoue :
  les suites lisent le disque (`node:fs`, `process.cwd()`), donc il faudrait ajouter `"node"` aux
  `types` du projet **applicatif** — ce qui rendrait `process`, `Buffer` et `node:fs` typables
  depuis du code qui part dans le navigateur. La construction resterait verte et la page
  exploserait a l'execution.
- **Correction :** `web/tsconfig.test.json`, un projet distinct avec `types: ["vite/client",
  "node"]`, enchaine dans le script : `"build": "tsc -b && tsc -p tsconfig.test.json && vite
  build"`. Il n'est pas un projet **reference**, parce qu'un projet reference ne peut pas
  desactiver l'emission (TS6310, deja rencontre au plan 03-03). Les tests sont typecheckes, la
  frontiere navigateur / Node est tenue par la configuration.
- **Fichiers :** `web/tsconfig.test.json`, `web/tsconfig.json`, `web/package.json`

### 6. [Rule 2 — Fonctionnalite critique manquante] Zero ligne doit rendre zero colonne

- **Trouve pendant :** tache 2
- **Probleme :** la formule de `03-UI-SPEC.md` 8.3 est ecrite pour **une** ligne. Un tableau en
  rend plusieurs, et parfois **aucune**. Le cas a zero ligne est le plus sournois : une recherche
  sans resultat. Rendre les en-tetes du registre revelerait a un gerant sans le droit que la
  colonne « Prix d'achat » existe — l'existence et la position d'un champ sont elles-memes une
  divulgation (T-03-73).
- **Ajout :** `colonnesVisiblesSurLignes`, qui garde les colonnes presentes dans **chacune** des
  lignes et rend `[]` quand il n'y en a aucune. `colonnesVisibles`, la formule du contrat pour une
  ligne, reste exportee et testee. Un test nomme couvre le cas vide.
- **Consequence pour les appelants :** l'etat vide se dit avec une phrase au-dessus ou a cote du
  tableau, jamais avec des en-tetes. A respecter en phases 4 a 10.

### 7. `null` reste visible, et c'est teste

Le filtre est `champ in ligne` et non `ligne[champ] !== undefined`, et la difference est le sujet
meme : le serveur **retire** la cle quand le droit manque, et la **laisse a `null`** quand la
donnee est seulement inconnue. Tester la valeur confondrait « tu n'as pas le droit de voir ce
champ » et « ce champ n'est pas renseigne », qui ne s'affichent pas de la meme facon. Un test
nomme fixe cette distinction.

### 8. Les identifiants de requirement ne sont pas coches

`APP-03` et `PERM-06` figurent dans l'en-tete de ce plan, mais plusieurs plans de la phase 3 les
revendiquent — `PERM-06` est porte cote serveur par 03-04, 03-06 et 03-09, et sa verification
vivante appartient a la phase 8. `requirements mark-complete` n'a **pas** ete execute et
`REQUIREMENTS.md` est inchange.

## Ce que ce plan ne livre pas, et qui pourrait le faire croire

- **Aucun tableau reel.** `TableauProjete` n'est monte par aucune page : `App.tsx` est toujours la
  page d'attente du plan 03-03, et le shell arrive au 03-13. Le composant est prouve contre une
  ressource de test, pas contre un vrai `prix_achat` — la verification vivante est en phase 8 et
  `03-VALIDATION.md` l'enregistre.
- **Aucun tri reel.** `onTrier` et `aria-sort` existent et sont rendus ; la logique de tri, elle,
  appartient a la vue qui fournit `tri` et re-interroge le serveur. Aucun tri cote client n'est
  fait ici, et c'est deliberé : trier une page de resultats donne un ordre faux.
- **Aucun formateur de pourcentage, de quantite ou de TVA.** Seuls la monnaie et les dates sont
  couvertes par la fixture partagee.

## Known Stubs

Aucun. Les trois modules sont complets pour ce qu'ils promettent ; ce qui manque ci-dessus est
hors perimetre du plan, pas a moitie fait.

## Threat Flags

Aucun. Ce plan n'ouvre ni point d'entree reseau, ni chemin d'authentification, ni acces fichier en
production, ni changement de schema. Les sept menaces de son registre sont traitees : T-03-73 et
T-03-74 par le registre et ses quatre assertions d'absence plus deux controles positifs, T-03-75
par le test du total fantome, T-03-76 par le formateur ecrit a la main et l'audit en CI, T-03-77
par l'absence de toute addition — le composant ne sait pas additionner —, T-03-78 par `Valeur` et
le test d'ordre du DOM, T-03-79 par la regle de saisie consignee dans `Valeur.tsx`.

**Rappel maintenu dans les trois modules :** le filtre de l'interface est un **confort**, jamais
une application de la regle. Le controle est la restriction de queryset et la projection cote
serveur. Un champ present dans la charge utile est deja divulgue.

## Verification

| Verification du plan | Resultat |
|---|---|
| `npm --prefix web test` | **code 0, 28 passed, 0 skipped**, 673 ms |
| `npm --prefix web run build` | code 0 (`tsc -b`, `tsc -p tsconfig.test.json`, `vite build`) |
| `npm --prefix web run audit:format` | aucun resultat, code 0 ; code **1** avec une sonde fautive |
| `grep -rn 'Intl.NumberFormat\|toLocaleString\|fr-MA' web/src \| grep -v '/format/'` | aucun resultat |
| `uv run pytest -x -q -m "not slow and not pending"` | **92 passed**, 63 deselected, inchangee |

Criteres d'acceptation par tache, tous **executes** :

| Tache | Critere | Mesure |
|---|---|---|
| 1 | `npm --prefix web test` code de sortie | 0 |
| 1 | `Intl.NumberFormat\|toLocaleString` hors de `format/` | aucun |
| 1 | `fr-MA` dans `web/src` | aucun |
| 1 | `fr-FR` dans `src/format/date.ts` | 3 |
| 1 | `codePointAt` dans `tests/format.test.ts` | 5 |
| 1 | `audit:format` dans `package.json` | 1 |
| 1 | `describe.skip` dans `tests/format.test.ts` | 0 |
| 2 | `npm --prefix web test` code de sortie | 0 |
| 2 | `champ in` dans `src/tableau/registre.ts` | 3 |
| 2 | en-tete litteral `<th...>lettre` dans `Tableau.tsx` | 0 |
| 2 | `"—"\|N/A\|0,00` dans `Tableau.tsx` | 0 |
| 2 | `scope="col"` dans `Tableau.tsx` | 2 |
| 2 | `describe.skip` dans `tests/colonnes.test.ts` | 0 |
| 3 | `bdi` dans `src/tableau/Valeur.tsx` | 4 |
| 3 | `npm --prefix web test`, suite `Valeur` incluse | code 0 |
| 3 | `dir=\{\|direction:` dans `Tableau.tsx` | 0 |
| 3 | `lang="ar"\|lang={` dans `Valeur.tsx` | 1 |

## Commits

| Tache | Commit | Objet |
|---|---|---|
| 1 | `642b74a` | `formaterMontant` et les dates, pilotes par la fixture partagee |
| 2 | `285f9b1` | le registre de colonnes filtre par presence |
| 3 | `e3ff242` | `Valeur`, l'isolation bidirectionnelle |

Le commit `4f0b11c` s'intercale entre les taches 1 et 2 : il appartient au plan **03-04**, execute
en parallele sur la meme branche. Aucun fichier n'est partage entre les deux plans — 03-04 possede
`plateforme/` et `tests/`, ce plan possede `web/`.

## Self-Check: PASSED

- 7 fichiers declares en `key-files.created` : tous presents sur disque.
- 4 fichiers declares en `key-files.modified` : tous presents et modifies.
- 3 commits de tache presents dans l'historique : `642b74a`, `285f9b1`, `e3ff242`.
- Aucun residu : la sonde d'audit (`web/src/_sonde.ts`) et la sonde d'espaces insecables
  (`web/verifier-nbsp.cjs`) ont bien ete supprimees ; `git status` ne montre aucun fichier non
  suivi sous `web/`.
- Aucun fichier hors `web/` et hors ce dossier de phase n'a ete touche.

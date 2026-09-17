---
phase: quick
plan: 260917-l7l
subsystem: ui
tags: [comptes, droits, permissions, magasins, dialogues, decouvrabilite, vitest, PERM-02, PERM-03]

requires:
  - phase: 03-comptes-permissions-app-shell (plan 03-14)
    provides: "l'ecran `Comptes et droits` complet — `LigneDroit`, `dialogues.tsx`, `DetailCompte` et ses trois confirmations"
provides:
  - "`Par magasin` visible en permanence sur chaque ligne de droit d'un compte a 2+ magasins — la deviation 3 de 03-14, tranchee"
  - "`DialogueReinitialisation` — la troisieme confirmation de l'ecran, et la premiere que 7.9 ne nommait pas"
  - "trois tests nommes qui mordent la ou leurs voisins ne mordaient pas"
  - "le motif « vider la boucle d'evenements avant d'affirmer qu'aucune requete n'est partie »"
affects:
  - "verification de phase 3 — l'etape 3 du point de controle 03-14 (`Par magasin`, mixte, `Personnalise`, `Uniformiser`) redevient verifiable a l'oeil"
  - "phases 4 a 12 — la classe de defauts que la suite ne voit pas, nommee en fin de document"

tech-stack:
  added: []
  patterns:
    - "une confirmation s'ajoute en ajoutant un membre a l'union `Confirmation` de la fiche, jamais un `useState` de plus"
    - "un test d'absence de requete se pose APRES un tour de boucle d'evenements"

key-files:
  created: []
  modified:
    - web/src/pages/comptes/LigneDroit.tsx
    - web/src/pages/comptes/dialogues.tsx
    - web/src/pages/comptes/DetailCompte.tsx
    - web/tests/comptes.test.tsx

key-decisions:
  - "`Par magasin` est visible en permanence : ce qui protege l'ecran de l'encombrement est `magasinsAccordes.length >= 2`, jamais la revelation au survol — qui ne protegeait que de la decouverte"
  - "Le bouton permanent reste subordonne par `ghost` + `text-xs` + `text-muted-foreground` ; `Uniformiser` garde sa couleur pleine, parce qu'il REMPLACE des reglages poses a la main"
  - "`DialogueReinitialisation` ne porte pas `bg-destructive` : l'action remplace une identification et en delivre une autre dans le meme geste — c'est le cas de `DialogueUniformisation`, pas celui des deux dialogues de 7.9"
  - "L'assertion de la tache 1 porte sur les CLASSES et non sur la visibilite, parce que jsdom ne calcule pas le CSS — limite assumee et ecrite dans le test"

patterns-established:
  - "Une assertion « rien n'est parti sur le fil » posee juste apres un `fireEvent.click` est verte au-dessus du defaut qu'elle attrape : `mutate()` rend la main avant d'appeler `fetch`. La poser apres `await new Promise((r) => setTimeout(r, 0))`."
  - "Une correction de decouvrabilite se teste par l'absence des classes de revelation, pas par la presence de l'element : la presence etait deja vraie."

requirements-completed: [PERM-02, PERM-03]

duration: 21min
completed: 2026-09-17
---

# Quick 260917-l7l : rendre l'octroi par magasin visible, et confirmer la reinitialisation

**`Par magasin` ne se revele plus au survol — il est rendu en permanence sur chaque ligne de droit d'un compte a 2+ magasins — et `Réinitialiser le mot de passe` demande desormais avant d'invalider une identification, par une troisieme confirmation batie comme les trois existantes.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-09-17T15:15:00Z
- **Completed:** 2026-09-17T15:36:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Le controle qui porte CLAUDE.md #13 est decouvrable : il ne faut plus pointer exactement la
  bonne ligne pour apprendre qu'il existe, et il existe desormais **au toucher**, donc sur la
  tablette du comptoir.
- La seule action de l'ecran qui fut a la fois immediate et sans retour ne l'est plus.
- Trois tests nommes qui **auraient ete rouges** contre le code d'hier, la ou leurs voisins
  immediats etaient verts au-dessus des memes deux defauts.

## Task Commits

| # | Tache | Commit | Type |
|---|-------|--------|------|
| — | Le plan, avant execution | `ea980ba` | docs |
| 1 | `Par magasin` visible en permanence (PERM-03) | `d94f9d1` | fix (test + correction, un seul commit) |
| 2 | Confirmer avant de reinitialiser un mot de passe (PERM-02) | `e224987` | fix (test + correction, un seul commit) |

Les deux commits nomment leurs chemins explicitement (worktree partage) et ne portent aucune
attribution Claude.

## Files Created/Modified

- `web/src/pages/comptes/LigneDroit.tsx` — `Par magasin` perd `opacity-0`, ses deux `group-*:` et
  son `focus:opacity-100`, et gagne `text-muted-foreground` ; `group` retire du `<li>`.
- `web/src/pages/comptes/dialogues.tsx` — `DialogueReinitialisation` ajoute ; le bloc de tete
  passe de « aucun des deux » a « aucune des trois ».
- `web/src/pages/comptes/DetailCompte.tsx` — `Confirmation` gagne `{ quoi: "reinitialisation" }` ;
  le corps de la mutation quitte le `onClick` pour `reinitialiserLeMotDePasse`.
- `web/tests/comptes.test.tsx` — option de harnais `surMotDePasse`, et trois tests.

## Le rouge observe — la preuve test-first

**C'est le coeur de ce lot.** Les deux defauts vivaient sous des tests verts ; ce qui compte
n'est pas que les nouveaux tests passent, c'est ce qu'ils disaient avant la correction.

**Tache 1 —** `rend \`Par magasin\` visible sans survol ni focus, sur chaque ligne (PERM-03)`

```
AssertionError: expected [ 'inline-flex', 'shrink-0', …(30) ] to not include 'opacity-0'
 ❯ tests/comptes.test.tsx:791:27
```

L'echec est tombe sur l'**assertion 2** (les classes) et **non** sur l'assertion 1 (les cinq
boutons presents) : le comptage a 5 passait deja. C'est la demonstration litterale du defaut —
le bouton EXISTAIT dans le DOM, et le test voisin
`n'offre \`Par magasin\` qu'a partir de deux magasins` le constatait fidelement depuis 03-14
pendant qu'aucun humain ne pouvait le voir.

**Tache 2 —** les deux tests `(PERM-02)`

```
AssertionError: expected true to be false // Object.is equality      ← « rien n'est parti sur le fil »
TestingLibraryElementError: Unable to find an accessible element with the role "button" and name "Réinitialiser"
```

**Le premier jet de ce test etait faux, et il faut le dire.** Pose immediatement apres le
`fireEvent.click`, l'assertion « aucun appel a `/api/comptes/2/mot-de-passe/` » **passait au-dessus
du code fautif** : `mutate()` rend la main avant que `fetch` ne soit appele, donc `appels` etait
encore vide. Le rouge initial etait alors le titre du dialogue introuvable — un rouge vrai, mais
pour la mauvaise raison, et qui aurait laisse croire que l'assertion importante mordait.
Corrige en vidant un tour de boucle d'evenements (`await new Promise((r) => setTimeout(r, 0))`)
avant d'affirmer l'absence. **C'est exactement le troisieme piege de `.planning/TESTING.md` —
un test vert contre du code casse — rencontre en direct.** Le motif est commente dans le test
pour les phases suivantes.

## Decisions Made

1. **Le poids visuel du bouton desormais permanent.** Il garde `variant="ghost"`, garde `text-xs`
   quand le libelle du droit est en `text-sm`, et gagne `text-muted-foreground` — la couleur de
   l'explication de ligne. Il se lit donc comme du texte de service, subordonne a l'interrupteur
   et a son libelle, et non comme une action a mener. `Uniformiser`, dans l'autre branche, garde
   sa couleur pleine : il **remplace** des reglages poses a la main, ce qui pese plus que
   l'invitation a en poser. La ligne ne gagne aucune hauteur, aucune bordure, aucun fond.
2. **`group` retire du `<li>`.** Cette classe n'existait que pour les `group-hover:` /
   `group-focus-within:` du bouton. Laissee orpheline, elle invite a recoller une revelation un
   jour. Plus aucun `group-*` dans le fichier.
3. **Pas de `bg-destructive` sur `Réinitialiser`.** L'action remplace une identification et en
   delivre une autre dans le meme geste : elle ne detruit aucune donnee et ne ferme aucune porte.
   C'est le cas de `DialogueUniformisation`, pas celui des deux dialogues de 7.9. Peindre en rouge
   une operation de routine du support use le rouge des deux qui en ont besoin.
4. **Une confirmation de plus = un membre de plus dans l'union `Confirmation`**, pas un
   `useState` de plus. Le motif de 03-14 tient a quatre ; le noter parce que la phase 9 ajoutera
   des dialogues sur cet ecran.

## CLAUDE.md #13 — intact, et verifie par un test

Rendre le bouton visible ne renverse rien de la non-negociable :

| Ce que #13 impose | Etat |
|---|---|
| Defaut **uniforme** a travers les magasins accordes | `const deplie = choix ?? etat === "mixte";` — **non touche** |
| Sous-liste par magasin **sur demande seulement** | aucune ligne n'est depliee d'emblee ; assertion 3 de la tache 1 : `queryAllByRole("switch", { name: /—/ })` rend 0 |
| Existence du controle decidee par le nombre de magasins | `magasinsAccordes.length >= 2` — **non touche** ; le test mono-magasin de 03-14 reste vert |
| Stockage `(gerant, magasin, permission)` | aucun fichier Python touche, aucun serialiseur, aucune migration |

Seule la **revelation** a change. C'est un attribut de classe CSS sur un bouton.

## Deviations from Plan

### 1. [Rule 1 — bug, dans le test que j'ecrivais] L'assertion « rien n'est parti » etait verte au-dessus du defaut

- **Trouvee pendant :** tache 2, a l'etape « verifier que le rouge est le bon rouge » — que le
  plan imposait precisement pour cela.
- **Probleme :** `mutate()` rend la main avant d'appeler `fetch`, donc `appels` est vide une
  ligne apres le clic, y compris quand la mutation part bel et bien. Le test aurait ete livre en
  affirmant garder une porte qu'il ne regardait pas.
- **Correction :** un tour de boucle d'evenements avant chaque assertion d'absence, et un
  commentaire de six lignes qui dit pourquoi, pour que personne ne le « simplifie ».
- **Fichiers :** `web/tests/comptes.test.tsx`
- **Commit :** `e224987`

### 2. [Rule 1 — bug] Le mot banni s'etait glisse dans mon propre commentaire

- **Trouvee pendant :** tache 2, a la verification `! grep -q "Annuler" dialogues.tsx`.
- **Probleme :** la docstring de `DialogueReinitialisation` citait le mot que le bloc de tete du
  fichier bannit — la regle est formulee comme « un `grep` de ce mot doit rester vide »
  justement pour qu'elle ne s'erode pas, et j'allais l'eroder au premier ajout.
- **Correction :** « leur toast defaisable », et une parenthese rappelant que la regle ne
  s'assouplit pas parce qu'un commentaire aurait ete plus court avec.
- **Commit :** `e224987`

---

**Total deviations :** 2 auto-corrigees (2 bugs, tous deux dans mon propre travail, tous deux
attrapes par une verification que le plan imposait).
**Impact :** aucun elargissement de perimetre. Le serveur n'a pas ete touche.

## Verification — nombres reels

| Controle | Commande | Mesure | Baseline |
|---|---|---|---|
| Suite backend | `uv run pytest -q -m "not slow and not pending"` | **184 passed, 30 deselected** | 184 / 30 — inchange, aucun fichier Python touche |
| Suite web | `npm --prefix web test` | **122 passed**, 5 fichiers | 119 — +3, exactement les trois ajoutes |
| Build web | `npm --prefix web run build` | **exit 0** | exit 0 |
| Formatage de l'argent | `npm --prefix web run audit:format` | **aucune sortie**, exit 0 | idem |
| Lexique | `grep -c "Annuler" web/src/pages/comptes/dialogues.tsx` | **0** | 0 |
| Serveur | `git status --short` | **propre** ; ni `.py`, ni `schema.yml`, ni `types.gen.ts` | — |

`web/src/api/schema.yml` n'est pas regenere et `manage.py spectacular` n'est pas relance : aucune
vue, aucun serialiseur, aucune route ne change dans ce lot.

Serveurs de developpement laisses tourner : Django `127.0.0.1:8010` (204 sur `/api/auth/csrf/`),
Vite 5173 et 5174 (200).

## La limite honnete de la tache 1

**jsdom ne calcule pas le CSS.** `getComputedStyle` n'y resout ni une classe Tailwind ni une regle
de feuille externe, donc `toBeVisible()` de jest-dom rend **vrai** sur un element `opacity-0`.
L'assertion livree porte sur **l'absence des classes de revelation** — `opacity-0`,
`group-hover:*`, `group-focus-within:*`, `focus:opacity*` — et c'est une approximation assumee :

- elle attrape **la regression exacte** qui vient de se produire, et toute reintroduction de la
  meme technique ;
- elle **ne prouve pas** que le bouton est visible. Un `display: none` venu d'ailleurs, un parent
  a hauteur nulle, un contraste insuffisant passeraient.

La preuve de visibilite reste **humaine, au navigateur**. Elle rejoint l'etape 3 du point de
controle 03-14, toujours ouverte.

## Ce que la suite automatisee ne peut structurellement pas voir

Quatre defauts ont ete trouves par une personne dans un navigateur pendant que **303 tests
etaient verts** : ces deux-ci, le 403 CSRF d'origine (quick 260917-04r) et l'ecran de parametres
inatteignable (03-14, deviation 6). Ils ne forment pas une liste de hasards. Ils ont la meme
forme, et elle vaut d'etre nommee pour les phases 4 a 12.

**La classe : tout ce qui vit entre « le code est correct » et « une personne peut l'atteindre,
le voir et s'en servir ».** La suite verifie qu'un composant rend ce qu'on lui demande. Elle ne
verifie pas qu'un chemin y mene, qu'un pixel arrive a l'oeil, ni qu'un geste est rattrapable.
Quatre sous-familles, toutes representees :

1. **L'accessibilite par un chemin** — l'ecran existe, aucune entree de navigation n'y mene
   (03-14). Un test qui monte le composant a sa route ne prend jamais le chemin de l'utilisateur.
   *Contre-mesure deja adoptee :* le `describe("l'acces a l'ecran depuis la navigation")` de
   03-14, qui part de la barre laterale et clique.
2. **La visibilite reelle** — l'element est dans le DOM, le CSS le cache. jsdom n'a pas de moteur
   de rendu : `opacity-0`, `display:none` en media query, un contraste sous le plancher, un
   z-index qui recouvre, un anneau de focus absent — **rien de tout cela n'est observable**.
   Aucune contre-mesure logicielle disponible avant Playwright (phase 11 au plus tot).
3. **La frontiere du processus** — `vite.config.ts` reecrivait l'en-tete `Host` et cassait le CSRF
   (04r). Aucun test Python n'execute la configuration du proxy, aucun test vitest ne lance
   Django ; le defaut vivait **exactement entre les deux suites**, ce que ni l'une ni l'autre ne
   peut couvrir par construction.
4. **L'ergonomie d'une action irreversible** — une mutation correcte, declenchee trop facilement.
   Le test « le bouton appelle la mutation » etait vert et decrivait le defaut avec exactitude.
   Celui-la, au moins, **est testable** : il suffit d'affirmer qu'aucune requete ne part avant la
   confirmation. C'est la seule des quatre sous-familles que du code peut fermer, et c'est ce qui
   a ete fait ici.

**Ce qu'il faut en retenir pour les phases suivantes.** Trois d'entre elles ne se fermeront pas
par plus de tests : le retour de la traversee humaine n'est pas un supplement de confort, il est
le **seul** instrument disponible pour cette classe. Le point de controle humain de chaque plan
doit donc etre traite comme une verification a part entiere, jamais comme une formalite apres le
vert — et un plan dont toutes les affirmations sont verifiables par vitest a probablement mal
regarde ce qu'il livre.

Corollaire pratique et bon marche : **quand un test affirme une absence** — aucune requete, aucun
element, aucune classe — il faut se demander une fois de plus s'il l'affirme au bon moment. Les
deux pieges rencontres aujourd'hui (l'assertion posee avant le tour de boucle, l'assertion de
presence qui restait vraie sous `opacity-0`) sont le meme piege : **un test qui regarde la bonne
chose au mauvais endroit est vert, et sa verdeur est une affirmation fausse.**

## Issues Encountered

Aucune au-dela des deux deviations ci-dessus, toutes deux dans mon propre travail et toutes deux
attrapees par les verifications que le plan imposait avant de passer a la suite.

## Next Phase Readiness

- Les deux defauts sont fermes ; rien n'est fusionne vers `main`, tout est sur
  `worktree-features-gap-fill`.
- **A verifier a la main, a la porte de phase 3** (a ajouter a la passe unique deja prevue) :
  1. `Par magasin` se voit sans survol, sur un compte a deux magasins, y compris sur une surface
     tactile — et il ne crie pas : il reste plus discret que le libelle du droit et que
     `Uniformiser` ;
  2. un compte mono-magasin (affaire `rabat`) n'en voit toujours aucun ;
  3. `Réinitialiser le mot de passe` ouvre la confirmation, `Retour` ne fait rien, et
     `Réinitialiser` montre bien le mot de passe provisoire une seule fois.
- Rien ne bloque la suite.

---
*Quick task: 260917-l7l*
*Completed: 2026-09-17*

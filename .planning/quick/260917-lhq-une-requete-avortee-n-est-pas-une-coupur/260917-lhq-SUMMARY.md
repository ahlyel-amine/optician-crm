---
phase: quick
plan: 260917-lhq
subsystem: web-api-client
tags: [openapi-fetch, abort, AbortError, react-query, banniere-de-lien, etats-globaux, APP-01, 8.6]
requires:
  - 03-12 (l'intergiciel de session, `src/etats/reseau.ts`, `BanniereDeLien`, et le `fetch` resolu par appel)
  - 03-13 (le shell, dont les changements de route declenchent l'annulation qui revelait le defaut)
provides:
  - "web/src/api/client.ts — `estUneRequeteAvortee()` : un abandon ne touche plus l'etat du lien"
  - "web/tests/reseau.test.tsx — les quatre tests APP-01 de la banniere de coupure"
affects:
  - phases 4 a 12 (tout formulaire consulte `useLienDisponible()` ; il ne bascule plus a chaque navigation)
tech-stack:
  added: []
  patterns:
    - "distinguer une mesure QUI ECHOUE d'une mesure QUI N'A PAS EU LIEU avant de signaler un etat global"
    - "consulter le fait (`request.signal.aborted`) avant le symptome (le `name` de l'exception)"
    - "tout test d'un signal global va par paire : un test contre le faux positif, un test contre le silence"
key-files:
  created:
    - web/tests/reseau.test.tsx
    - .planning/quick/260917-lhq-une-requete-avortee-n-est-pas-une-coupur/260917-lhq-PLAN.md
  modified:
    - web/src/api/client.ts
    - web/src/etats/reseau.ts
decisions:
  - "Aucun seuil, aucun compteur : `retry: false` fait qu'un second echec ne partirait jamais, donc un seuil rendrait la banniere muette pendant une vraie coupure"
  - "`request.signal.aborted` est consulte AVANT la forme de l'exception — le signal est le fait, le `name` n'est que son symptome et varie selon l'environnement"
  - "Un abandon ne signale NI la panne NI le retablissement : il ne mesure rien, donc il ne parle dans aucun des deux sens"
metrics:
  duration: ~20m
  tasks: 1
  files: 4
completed: 2026-09-17
---

# Quick Task 260917-lhq : Une requête avortée n'est pas une coupure Summary

**La bannière `Connexion perdue.` ne se lève plus quand react-query annule une requête au changement de route — un abandon est une mesure qui n'a pas eu lieu, pas une mesure qui échoue — et un vrai échec de transport la lève toujours, du premier coup.**

## Le défaut

`web/src/api/client.ts:175` comptait toute rejection de `fetch` comme une coupure de lien. Son commentaire énumérait `requete avortee` parmi les cas qui arrivent là, puis concluait qu'arriver là veut dire que le lien est tombé — **la conclusion contredisait sa propre liste**.

Le chemin, vérifié dans les paquets installés plutôt que supposé :

| Maillon | Fichier | Ce qu'il fait |
|---|---|---|
| `openapi-react-query` | `dist/index.mjs:10` | `await fn(path, { signal, ...init })` — le signal de react-query part dans l'`init` |
| `openapi-fetch` 0.17.0 | `dist/index.mjs:78` | `new Request(url, requestInit)` — le signal atterrit **sur la `Request`** |
| `openapi-fetch` 0.17.0 | `dist/index.d.ts:158` | `onError` reçoit `{ request, error, ... }` — les deux sources de vérité au même endroit |
| react-query v5 | — | annule la requête dès que son **dernier observateur se désabonne**, c'est-à-dire à chaque démontage, c'est-à-dire à **chaque changement de route** |

Donc : navigation → annulation → `fetch` rejette `AbortError` → `signalerPanneDeLien()` → la bannière se peint → la réponse suivante appelle `signalerLienRetabli()` et la retire. Le clignotement.

**Ce n'était pas cosmétique.** `03-UI-SPEC.md` 8.6 rend la bannière contractuelle : tant qu'elle est levée, **tout contrôle d'écriture est désactivé**, et les phases 4 à 12 consultent `useLienDisponible()`. Brièvement, à chaque navigation, le produit entier se croyait hors ligne. Et une bannière qui crie au loup entraîne l'utilisateur à ignorer la seule fois où elle dit vrai.

## La correction

```ts
function estUneRequeteAvortee(erreur: unknown, requete: Request): boolean {
  if (requete.signal?.aborted === true) {
    return true;                                                  // le fait
  }
  return erreur instanceof Error && erreur.name === "AbortError";  // le symptome
}
```

`onError({ error, request })` rend `undefined` **sans toucher à l'état du lien** quand la requête a été abandonnée. Tout le reste — `TypeError: Failed to fetch`, DNS, socket, TLS — appelle `signalerPanneDeLien()` exactement comme avant.

**L'ordre des deux tests est délibéré.** `request.signal.aborted` est le fait : l'annulation a eu lieu, et le signal est joignable parce que la chaîne ci-dessus le pose sur la `Request`. Le nom de l'exception n'en est que le symptôme, et sa forme varie — les navigateurs et `undici` rejettent une `DOMException` nommée `AbortError`, d'autres environnements un `Error` simple portant le même `name`. `DOMException` héritant d'`Error`, une seule ligne couvre les deux formes, et le test 3 le **vérifie** au lieu de le supposer.

Les deux commentaires trompeurs sont réécrits : celui de `onError`, et celui de `signalerPanneDeLien` dans `web/src/etats/reseau.ts`, qui disait « la dernière requête n'a pas abouti ». Une requête abandonnée n'aboutit pas non plus — c'est précisément la nuance qui manquait, donc la phrase dit maintenant « a **échoué au transport** » et nomme `estUneRequeteAvortee()` comme le lieu du tri.

## Faut-il plus d'un point de mesure avant de lever la bannière ? — Non, et pourquoi

La question était posée explicitement. La réponse est **non, la correction de l'abandon est toute la réponse**, et ce n'est pas une esquive :

`clientDeRequetes` porte `retry: false` (`web/src/api/requetes.ts`), décision délibérée du plan 03-12 parce que 8.6 veut qu'un échec soit VU tout de suite. Exiger deux échecs consécutifs aurait donc une conséquence perverse : après un unique appel échoué, **aucune seconde requête ne part**. L'utilisateur au comptoir resterait devant une interface d'apparence vivante, contrôles d'écriture actifs, sur un lien mort. Un seuil rendrait la bannière muette exactement dans le cas le plus courant d'une vraie coupure.

Et le diagnostic de fond : le bruit ne venait pas d'un manque de points de mesure, il venait d'**une mesure fausse**. Un abandon n'est pas une observation du lien du tout — personne n'a mesuré quoi que ce soit, la mesure a été retirée. On ne compense pas une mesure fausse en en exigeant deux ; on la retire. Une fois l'abandon écarté, il ne reste dans cette branche que des échecs de transport réels, et un seul suffit.

Aucun compteur, aucune fenêtre glissante, aucun délai de grâce n'a été ajouté.

## Les tests, et la preuve qu'ils étaient rouges

`web/tests/reseau.test.tsx`, nouveau fichier, quatre tests nommés d'après APP-01. Les appels passent par **le vrai `clientApi`**, intergiciels compris — c'est `onError` qui est sous test, un double du client ne le traverserait pas. C'est possible parce que le plan 03-12 résout `globalThis.fetch` à chaque appel.

| Test | Rôle |
|---|---|
| `test_app01_une_requete_avortee_ne_leve_pas_la_banniere_de_lien_perdu` | **Test 1 exigé.** `DOMException` nommée `AbortError` + signal avorté → `lienDisponible()` reste `true` et `BanniereDeLien` ne rend rien |
| `test_app01_un_echec_de_transport_leve_bien_la_banniere` | **Test 2 exigé — le garde-fou.** `TypeError: Failed to fetch`, rien d'avorté → `lienDisponible()` passe `false` et le texte exact de `MESSAGE_LIEN_PERDU` est dans le DOM |
| `test_app01_un_abandon_sans_DOMException_est_reconnu_aussi` | `Error` simple nommé `AbortError` — la seconde forme, vérifiée plutôt que supposée |
| `test_app01_un_abandon_ne_retablit_pas_un_lien_deja_tombe` | L'abandon ne parle dans **aucun** des deux sens : parti d'un lien tombé, il reste tombé |

**Confirmation du rouge, sortie réelle avant la correction** (commit `60a71ef`, avant `7fda076`) :

```
 ❯ tests/reseau.test.tsx (4 tests | 2 failed) 21ms
     × test_app01_une_requete_avortee_ne_leve_pas_la_banniere_de_lien_perdu 11ms
     × test_app01_un_abandon_sans_DOMException_est_reconnu_aussi 2ms

AssertionError: expected false to be true // Object.is equality
 ❯ tests/reseau.test.tsx:96:30
```

Les tests 2 et 4 passaient déjà avant la correction — c'est leur nature : ils ne décrivent pas le défaut, ils interdisent la correction paresseuse. Sans le test 2, « ne plus jamais signaler de coupure » aurait rendu les trois autres verts pendant que le produit mentait dans l'autre sens.

`beforeEach` remet `enLigne` à vrai par `signalerLienRetabli()` : le magasin est un état de **module**, il survit d'un test au suivant, et sans cette remise à zéro la suite passerait dans un ordre et échouerait dans un autre.

## Vérification — avant / après, nombres réels

| Contrôle | Avant (baseline rejouée au démarrage) | Après |
|---|---|---|
| `npm --prefix web test` | **122 passed**, 5 fichiers | **126 passed**, 6 fichiers — +4, aucun régressé |
| `.venv/bin/pytest -q -m "not slow"` | **184 passed, 30 deselected** | **184 passed, 30 deselected** — inchangé |
| `npm --prefix web run build` | — | **code 0** |
| `npm --prefix web run audit:format` | — | **code 0**, aucune sortie |
| `git diff --exit-code web/src/api/schema.yml web/src/api/types.gen.ts` | — | **code 0** — aucun changement serveur, donc rien à régénérer |

Les deux baselines annoncées dans la consigne sont confirmées telles quelles : backend 184/30, web 122 (119 avant la tâche 260917-l7l, qui en a ajouté 3).

## Commits

| Commit | Type | Chemins nommés |
|---|---|---|
| `60a71ef` | `test` | `web/tests/reseau.test.tsx`, `.planning/quick/260917-lhq-.../260917-lhq-PLAN.md` |
| `7fda076` | `fix` | `web/src/api/client.ts`, `web/src/etats/reseau.ts` |

Chemins explicites aux deux commits (CLAUDE.md « Parallel execution »). Rien n'est fusionné vers `main` ; le travail reste sur `worktree-features-gap-fill`.

## Quel test aurait attrapé celui-ci — et faut-il le construire ?

C'est le **cinquième** défaut de la phase trouvé par une personne dans un navigateur pendant que la suite était entièrement verte. La question mérite mieux qu'un vœu pieux, donc voici la réponse concrète, avec ce qu'elle ne couvre pas.

### Pourquoi la suite ne pouvait pas le voir

Pas par oubli — **par construction**. Les cinq suites `vitest` existantes doublent `fetch` par une fonction qui **résout immédiatement**. Il n'y a jamais, dans aucun test, une requête *en vol* qui survive à un démontage. Or la fenêtre du défaut est exactement là : entre le départ de la requête et son annulation. Cette fenêtre n'existe pas dans la suite, donc aucun test ne pouvait tomber dedans, quel qu'ait été le soin apporté aux assertions.

### Le test qui l'aurait attrapé, par coût croissant

**(a) Un `fetch` différé — ~20 lignes, aucune dépendance, à construire.**
Un double de réseau qui rend une promesse que le test résout à la main. On monte à la route A pendant que la requête est en vol, on navigue vers B **avant** de résoudre, on affirme que la bannière n'est jamais apparue. C'est faisable dans `vitest`/jsdom aujourd'hui — les quatre tests ci-dessus le prouvent à l'échelle d'un appel. Ce que cela ouvre dépasse ce défaut : c'est la seule façon d'affirmer quoi que ce soit sur un **état intermédiaire** — squelettes de chargement, boutons désactivés pendant l'envoi, double-soumission. Aujourd'hui aucun de ces états n'est testable.
**Limite honnête :** ce test n'existerait que si quelqu'un avait déjà soupçonné le cycle de vie des requêtes. Il attrape la classe une fois qu'on la connaît ; il ne l'aurait pas découverte.

**(b) Un unique parcours au navigateur réel — Playwright, ~100 lignes plus le téléchargement des navigateurs en CI.**
Charger l'application, se connecter, **recharger**, traverser trois routes, et affirmer sur toute la durée que le texte `Connexion perdue.` **n'apparaît jamais** (un `MutationObserver`, ou une assertion de comptage continue — pas un instantané, qui manquerait le clignotement). Celui-ci l'aurait attrapé **sans rien soupçonner**, parce qu'il exerce le vrai cycle de vie plutôt qu'un modèle de ce cycle.

### Verdict

**(a) vaut la peine et devrait être construit tout de suite** — au prochain plan qui touche un formulaire, parce qu'il sera nécessaire de toute façon pour tester les états d'envoi. Coût quasi nul, bénéfice permanent.

**(b) vaut la peine, mais sous une forme étroite, et pas maintenant.** Un parcours de fumée unique en début de phase 4, pas une suite E2E miroir de `vitest` : dupliquer 126 tests dans un navigateur coûterait plus cher que ce que la phase 4 livre. Le critère de tri est précis — va en Playwright **uniquement ce que jsdom ne peut structurellement pas voir** : le cycle de vie réel des requêtes, les vraies origines HTTP, la navigation réelle. Tout le reste reste en `vitest`.

**Ce qu'aucun des deux n'aurait attrapé, et c'est le point important.** Sur les cinq défauts de la phase :

| Défaut | Mécaniquement attrapable ? |
|---|---|
| 403 CSRF d'origine | **Oui** — (b) : une vraie requête de navigateur porte un vrai `Origin` |
| Écran `Comptes` inatteignable | **Oui** — (b), et un test `vitest` qui **clique** depuis la racine l'a effectivement rattrapé après coup |
| Bannière qui clignote (celui-ci) | **Oui** — (a) et (b) |
| `Par magasin` révélé au survol seul | **Non** — un test survolerait, puisqu'un test sait où le contrôle se trouve. La **découvrabilité** est un jugement humain |
| Réinitialisation sans confirmation | **Non** — un test affirmerait le comportement construit. « Cette action mérite une confirmation » est un jugement de conception |

Donc trois sur cinq sont automatisables, deux ne le sont pas et ne le seront jamais. **La conclusion utile n'est pas « il nous faut plus de tests », c'est que la passe manuelle au navigateur ne se rattrape pas par de l'outillage** — elle a produit deux constats que rien n'aurait produits. Les 24 vérifications humaines accumulées depuis le plan 03-12, toujours non effectuées, sont le vrai risque ouvert de la phase 3 ; (a) et (b) réduisent le coût de chaque passe future, ils ne la remplacent pas.

## Écarts au plan

Un seul, mineur : `web/src/etats/reseau.ts` n'était pas dans `files_modified` du plan. Le commentaire de `signalerPanneDeLien` portait la **même** confusion que celui de `onError` (« la dernière requête n'a pas abouti »), et la consigne demandait de réécrire le commentaire trompeur. Le laisser aurait laissé la moitié du défaut en place sous forme de documentation. Commentaire seul, aucun changement de comportement.

## Restant ouvert

- **Vérification humaine au navigateur non effectuée** pour ce correctif : personne n'a rechargé la page pour constater l'absence de clignotement. La preuve est automatisée (4 tests, dont 2 observés rouges d'abord). Elle rejoint la passe unique de la porte de phase 3 — **25 vérifications accumulées**.
- La construction du double de `fetch` différé (a) n'est pas faite ici : hors du périmètre d'une tâche rapide, et elle appartient au premier plan qui aura besoin d'affirmer sur un état d'envoi.

---

*Tâche rapide : 260917-lhq*
*Terminé : 2026-09-17*

## Self-Check: PASSED

4 fichiers declares, 4 presents. 2 commits declares, 2 presents (`60a71ef`, `7fda076`).

---
phase: 03-comptes-permissions-app-shell
plan: 12
subsystem: web-auth-client
tags: [openapi-fetch, openapi-react-query, tanstack-query, csrf, session, react-router, connexion, etats-globaux, PERM-01, APP-01]
requires:
  - 03-03 (le proxy meme-origine /api vers 127.0.0.1:8010, shadcn epingle, vitest)
  - 03-08 (les cinq routes d'authentification, le contrat de statuts 400/401/403/429/503, `reessayer_dans`)
  - 03-09 (le catalogue deja intersecte cote serveur, que le client ne reconstruit pas)
  - 03-10 (web/src/api/schema.yml commite — la source unique du client typé)
  - 03-11 (formaterMontant et l'interdit de locale hors de src/format/)
provides:
  - web/src/api/types.gen.ts — le client typé genere depuis le schema commite, jamais ecrit a la main
  - web/src/api/client.ts — openapi-fetch, l'en-tete X-CSRFToken sur toute methode mutante, le 401 global
  - web/src/api/requetes.ts — $api (openapi-react-query), les reglages de cache, les alias de contrat
  - web/src/etats/ — les cinq etats globaux de 03-UI-SPEC 8.6, en francais, une seule copie chacun
  - web/src/auth/ — AuthProvider (un seul amorcage), RequireAuth, RequirePermission (absent, jamais grise)
  - web/src/pages/Connexion.tsx — les sept etats de l'ecran avec la copie exacte de la specification
  - web/src/pages/MotDePasse.tsx — le changement force, page pleine sans issue
affects:
  - 03-13 (le shell remplace ContenuProtege et consomme AuthProvider, RequirePermission et $api)
  - 03-14 (l'ecran des comptes et des droits, premier consommateur metier du client typé)
  - phases 4 a 10 (tout appel d'API passe par $api ; les cinq etats globaux sont herites tels quels)
  - phase 9 (BRAND-01 : la marque commence a la premiere peinture authentifiee, jamais sur /connexion)
  - phase 11 (Expo consomme le meme schema ; DEFAULT_AUTHENTICATION_CLASSES reste une liste)
tech-stack:
  added: []
  patterns:
    - le client d'API est genere depuis le schema commite et diffe en CI, jamais ecrit a la main
    - le client d'API constate, il ne navigue pas — le 401 notifie des abonnes, AuthProvider route
    - la copie d'un etat vit une seule fois, dans src/etats/messages.ts, jamais dans un composant
    - une exception de transport ne porte aucun message : l'interface choisit la phrase
key-files:
  created:
    - web/src/api/client.ts
    - web/src/api/requetes.ts
    - web/src/api/types.gen.ts
    - web/src/auth/AuthProvider.tsx
    - web/src/auth/RequireAuth.tsx
    - web/src/auth/RequirePermission.tsx
    - web/src/etats/messages.ts
    - web/src/etats/reseau.ts
    - web/src/etats/BanniereDeLien.tsx
    - web/src/etats/CarteDechec.tsx
    - web/src/etats/PageInterdite.tsx
    - web/src/etats/PageIntrouvable.tsx
    - web/src/pages/Connexion.tsx
    - web/src/pages/MotDePasse.tsx
    - web/tests/connexion.test.tsx
  modified:
    - web/src/App.tsx
    - web/src/main.tsx
    - .planning/phases/03-comptes-permissions-app-shell/03-UI-SPEC.md
key-decisions:
  - "Pas de prefixe de chemin sur le client : les cles du schema portent deja /api/, donc baseUrl vaut l'origine de la page et non '/api' — sinon 404 sur chaque appel"
  - "openapi-fetch consomme la reponse : le corps d'erreur se lit sur le champ `error` rendu, jamais en reclonant `response`"
  - "fetch est resolu a chaque appel (`globalThis.fetch(requete)`) et non capture a la creation du client, sinon aucune suite ne peut doubler le reseau sans doubler le module"
  - "Le drapeau `sessionOuverte` existe pour qu'un 401 sur /api/auth/moi/ au premier chargement anonyme n'affiche pas « votre session a expire » a quelqu'un qui n'en a jamais ouvert"
  - "La copie de /mot-de-passe porte un quatrieme champ, `Mot de passe actuel` : arbitrage du point de controle — la specification 9.4 est amendee, l'exigence serveur n'est pas affaiblie"
  - "Les cinq etats globaux vivent dans src/etats/ (repertoire non prevu au plan) plutot que disperses dans les pages : neuf phases en heritent, donc ils ont un lieu"
patterns-established:
  - "Toute nouvelle route d'API se consomme par $api, donc une route absente du schema n'est pas appelable — c'est le but"
  - "Un echec de chargement est une carte en ligne dans la zone de contenu, jamais un toast : un toast disparait et laisse un ecran blanc"
  - "RequirePermission ne rend rien quand le code manque — pas d'etat desactive, pas de cadenas ; un test affirme l'absence de noeud DOM"
requirements-completed: []
duration: ~45m d'execution, plus l'attente du point de controle
completed: 2026-09-17
---

# Phase 3 Plan 12 : Client d'API et surface `/connexion` Summary

**La SPA parle à l'API par un client TypeScript généré depuis le schéma commité, un opticien se connecte à `/connexion` et les cinq états globaux que neuf phases hériteront existent, en français, écrits une seule fois.**

## Performance

- **Durée :** ~45 min d'exécution (tâches 1 à 3, 2026-09-16 23:20 → 23:45), puis l'attente du point de contrôle humain et sa clôture le 2026-09-17
- **Tâches :** 3 automatiques exécutées, 1 point de contrôle bloquant répondu
- **Fichiers :** 15 créés, 3 modifiés

## Accomplissements

- `web/src/api/types.gen.ts` est **généré** depuis `web/src/api/schema.yml` (plan 03-10) et commité : « le contrat a-t-il changé ? » est désormais un diff lisible, et la régénération redonne un diff vide.
- Chaque appel mutant porte `X-CSRFToken`, lu sur le cookie `csrftoken` non `HttpOnly` — le motif double-submit exige que le JS le relise, et le cookie de session, lui, reste illisible.
- Le 401 est traité une fois pour tout le produit : le contexte se vide, le chemin tenté est mémorisé, l'écran revient à `/connexion` avec `Votre session a expiré. Reconnectez-vous.`, et la reconnexion ramène au chemin mémorisé.
- Les cinq états de `03-UI-SPEC.md` 8.6 (401, 403, 404, échec de chargement, connexion perdue) vivent dans `web/src/etats/`, chacun avec une seule copie française. Aucun code de statut, aucune trace, aucun anglais à l'écran.
- `AuthProvider` amorce en **une** requête vers `/api/auth/moi/` et expose l'utilisateur, l'affaire, les droits, les magasins restreints et le catalogue **tel que le serveur l'a intersecté** — rien n'est refiltré côté client.
- `RequirePermission` **ne rend rien** quand le code manque : pas d'état grisé, pas de cadenas, pas d'infobulle. Un test affirme l'absence de nœud DOM, ce qui est la seule formulation que la discipline ne peut pas éroder.
- `/connexion` rend ses sept états avec la copie exacte de la spécification : un compte désactivé reçoit **le même message** que des identifiants faux, et la carte est décalée de 64 px du haut plutôt que centrée verticalement, donc l'apparition de l'erreur ne la déplace pas.

## Task Commits

1. **Tâche 1 : client d'API généré, en-tête CSRF, cinq états globaux** — `54767f0` (feat)
2. **Tâche 2 (RED) : contexte d'amorçage, absence de nœud pour un droit manquant** — `ec49159` (test)
3. **Tâche 2 (GREEN) : AuthProvider, RequireAuth, RequirePermission** — `eef5d9a` (feat)
4. **Tâche 3 (RED) : les sept états de `/connexion` et le changement forcé** — `72cf0ce` (test)
5. **Tâche 3 (GREEN) : `/connexion`, `/mot-de-passe`, les routes** — `11f41a2` (feat)
6. **Réponse du point de contrôle : amendement de `03-UI-SPEC.md` 9.4** — `985a73e` (docs)

**Métadonnées du plan :** le commit `docs(03-12)` de clôture.

## Fichiers créés / modifiés

- `web/src/api/types.gen.ts` — 1034 lignes générées par `openapi-typescript` depuis le schéma commité
- `web/src/api/client.ts` — le client openapi-fetch, l'intergiciel CSRF, l'intergiciel de session, `assurerJetonCsrf`
- `web/src/api/requetes.ts` — `$api`, le `QueryClient` (`retry: false`, pas de `refetchOnWindowFocus`), les alias de contrat et les cinq constantes de route
- `web/src/etats/messages.ts` — la copie de chaque état global, une fois
- `web/src/etats/reseau.ts` — la détection de coupure : `fetch` ne rejette que sur un échec de transport, donc `onError` **est** la panne de lien
- `web/src/etats/BanniereDeLien.tsx` — la bannière persistante, montée au-dessus de tout, `/connexion` incluse
- `web/src/etats/CarteDechec.tsx` — la carte en ligne et son `[ Réessayer ]`
- `web/src/etats/PageInterdite.tsx` — le 403 qui **nomme le droit manquant**
- `web/src/etats/PageIntrouvable.tsx` — le 404 et son lien vers le tableau de bord
- `web/src/auth/AuthProvider.tsx` — l'amorçage unique, la préférence de magasin revalidée, l'abonnement au 401
- `web/src/auth/RequireAuth.tsx` — la garde de route protégée et la redirection vers `/mot-de-passe`
- `web/src/auth/RequirePermission.tsx` — l'absence, jamais le grisé
- `web/src/pages/Connexion.tsx` — les sept états, le clavier, l'accessibilité
- `web/src/pages/MotDePasse.tsx` — le changement forcé, sans issue
- `web/tests/connexion.test.tsx` — 50 tests (les suites d'amorçage, de permission et des sept états)
- `web/src/App.tsx` — les deux routes hors mise en page protégée, plus `ContenuProtege` provisoire
- `web/src/main.tsx` — `QueryClientProvider` et le routeur
- `.planning/phases/03-comptes-permissions-app-shell/03-UI-SPEC.md` — l'amendement 9.4 (ci-dessous)

## Réponse du point de contrôle (tâche 4)

Le point de contrôle a été soumis avec **un écart de copie constaté** et la liste de sept vérifications manuelles. Les deux ont reçu une réponse.

### 1. `Mot de passe actuel` — décision : garder le champ et amender la spécification

`03-UI-SPEC.md` 9.4 ne listait que `Nouveau mot de passe`, `Confirmer` et `Enregistrer` pour `/mot-de-passe`. L'écran construit en porte un quatrième, parce que `POST /api/auth/mot-de-passe/` (plan 03-08) exige `mot_de_passe_actuel`.

**Arbitrage retenu :** amender la spécification, ne pas affaiblir le serveur.

- `web/src/pages/MotDePasse.tsx` reste tel que construit, champ compris.
- `03-UI-SPEC.md` 9.4 liste désormais `Mot de passe actuel`, suivi d'un paragraphe qui écrit la raison : sans l'exigence serveur, un poste laissé déverrouillé une minute — ou un CSRF réussi — ne donne plus une session mais **le compte, définitivement**. Le paragraphe dit explicitement que la phase 9 ne doit pas rouvrir le sujet, pour qu'un lecteur futur voie une décision et non une dérive.
- L'exigence serveur n'est pas touchée, et le mot de passe provisoire n'est **pas** conservé en mémoire JS.
- Le commentaire de tête de `MotDePasse.tsx` passe de « écart à valider au point de contrôle » à « au contrat, tranché le 2026-09-16 » — commentaire seul, aucun changement de comportement, `50/50` tests toujours verts.

### 2. Les sept vérifications au navigateur — approuvées sur la preuve automatisée

Le propriétaire a approuvé et choisi d'avancer **sans exécuter lui-même la traversée au navigateur**.

## Vérification manuelle non effectuée

**Ces sept points n'ont pas été observés par une personne.** L'approbation du point de contrôle porte sur la preuve automatisée (50 tests frontend verts, build à 0, 179 tests backend verts) et **pas** sur le constat de ces comportements. Ils restent donc **ouverts** et ressortiront à la vérification de phase.

| # | Point | Statut |
|---|---|---|
| 1 | Se connecter avec le compte propriétaire créé au plan 03-01 : l'application doit s'ouvrir **sans que l'écran clignote** | non observé |
| 2 | Un mauvais mot de passe : message exactement `Identifiant ou mot de passe incorrect.`, champ mot de passe vide, focus dedans, e-mail conservé, et **la carte ne doit pas bouger** | non observé |
| 3 | Répéter onze fois : le message doit devenir celui de la limite de débit, avec **un compte à rebours dans la ligne d'aide** | non observé |
| 4 | `doit_changer_mot_de_passe` : atterrissage sur `/mot-de-passe`, page pleine, **sans navigation de shell et sans issue** | non observé |
| 5 | Traverser l'écran **au clavier seul** : `Tab` dans l'ordre visuel, `Entrée` soumet depuis les deux champs, anneau de focus visible partout | non observé |
| 6 | **Lire l'écran en français** : l'interface doit se lire comme du français et non comme de l'anglais traduit ; vérifier le lexique de `03-UI-SPEC.md` 9.3 | non observé |
| 7 | Couper le réseau : la bannière `Connexion perdue.` doit apparaître et les **contrôles d'écriture se désactiver** | non observé |

Chacun de ces sept points a un test `vitest` correspondant qui passe — mais vitest rend dans jsdom : il ne voit ni un clignotement, ni un saut de mise en page réel, ni un anneau de focus, ni si une phrase se lit comme du français. C'est précisément pourquoi le plan a écrit ce point de contrôle, et pourquoi le point 6 est **la vérification manuelle nommée dans `03-VALIDATION.md`**. Le fait qu'elle n'ait pas été faite ne se rattrape pas par un test.

## Décisions prises

Voir `key-decisions` en tête. Les trois qui coûteront le plus cher à quelqu'un qui les ignore :

1. **`baseUrl` est l'origine de la page, pas `/api`.** Les clés du schéma portent déjà le préfixe, parce que drf-spectacular émet les chemins tels que Django les route.
2. **Le corps d'une erreur se lit sur le champ `error`** que rend `openapi-fetch`. La `Response` est déjà consommée ; la recloner rend un corps vide et fait afficher le message de repli à la place de celui du serveur.
3. **Le client d'API constate, il ne navigue pas.** Le 401 notifie des abonnés ; `AuthProvider` est le seul abonné et c'est lui qui vide, mémorise et route. Le module d'API ne connaît ni le routeur ni le contexte.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `baseUrl: "/api"` produisait un 404 sur chaque appel**

- **Trouvé pendant :** Tâche 1
- **Problème :** le plan prescrit littéralement `createClient<paths>({ baseUrl: "/api", ... })`. Mais les clés de `types.gen.ts` sont `/api/auth/connexion/`, `/api/comptes/` : drf-spectacular émet les chemins tels que Django les route, préfixe compris. Le client aurait demandé `/api/api/auth/connexion/` — un 404 sur **tous** les appels, y compris la connexion.
- **Correction :** `baseUrl` vaut l'origine de la page (`window.location.origin`), ce qui est exactement la décision de proxy même-origine du plan 03-03. L'écrire plutôt que de laisser une base vide n'est pas cosmétique : `new Request()` refuse une URL relative hors d'un document, donc une base vide casse dès qu'on sort du navigateur (jsdom, futur SSR).
- **Fichiers :** `web/src/api/client.ts`
- **Vérification :** les suites de connexion et d'amorçage interceptent des URL absolues correctes ; `npm --prefix web run build` sort à 0
- **Commité dans :** `54767f0`

**2. [Rule 1 — Bug] Le corps d'erreur était relu sur une `Response` déjà consommée**

- **Trouvé pendant :** Tâche 3
- **Problème :** `openapi-fetch` lit et analyse le corps lui-même, puis rend `{ data, error, response }`. Relire `response.json()` — ou la recloner — rend un corps vide : `detail` et `reessayer_dans` disparaissent, et l'écran affiche le message de repli au lieu de la limite de débit avec son compte à rebours.
- **Correction :** `lireCorpsDerreur(error)` dans `web/src/api/requetes.ts`, appelé depuis `Connexion.tsx` et `MotDePasse.tsx`. `reessayer_dans` est un champ séparé précisément pour que l'interface n'extraie jamais un nombre d'une phrase française.
- **Fichiers :** `web/src/api/requetes.ts`, `web/src/pages/Connexion.tsx`, `web/src/pages/MotDePasse.tsx`
- **Vérification :** un test affirme le compte à rebours de la limite de débit à partir d'un corps 429
- **Commité dans :** `11f41a2`

**3. [Rule 3 — Blocking] `openapi-fetch` capturait `globalThis.fetch` une seule fois**

- **Trouvé pendant :** Tâche 2 (phase RED)
- **Problème :** le client capture `globalThis.fetch` à sa **création**, c'est-à-dire à l'import du module. Un double de réseau installé ensuite par une suite de tests n'est jamais vu, donc la seule façon de tester aurait été de doubler `client.ts` entier — et un module doublé est un module qu'on ne teste plus.
- **Correction :** `fetch: (requete: Request) => globalThis.fetch(requete)` à la création du client, ce qui résout la référence **à chaque appel**. Coût : une fermeture par requête. Gain : les 50 tests s'exécutent contre le vrai `client.ts`.
- **Fichiers :** `web/src/api/client.ts`
- **Vérification :** `npm --prefix web test` — 50 passés
- **Commité dans :** `54767f0` (ajusté en `eef5d9a`)

**4. [Rule 2 — Missing critical] Répertoire `web/src/etats/`, non prévu au plan**

- **Trouvé pendant :** Tâche 1
- **Problème :** le plan demande les cinq états globaux de `03-UI-SPEC.md` 8.6 mais ne leur donne aucun fichier ; la liste `files` de la tâche 1 ne cite que `client.ts`, `requetes.ts`, `types.gen.ts`, `main.tsx` et `package.json`. Écrits dans les pages, ces états seraient recopiés à chaque phase — et le critère d'acceptation « la chaîne apparaît exactement une fois » serait faux dès la phase 4.
- **Correction :** six fichiers sous `web/src/etats/` — `messages.ts` (toute la copie, une fois), `reseau.ts` (la détection de coupure), et les quatre composants `BanniereDeLien`, `CarteDechec`, `PageInterdite`, `PageIntrouvable`. Neuf phases en héritent sans les réécrire.
- **Fichiers :** `web/src/etats/*` (6 fichiers), `web/src/App.tsx`
- **Vérification :** `grep -c 'Votre session a expire' web/src/` et `grep -c 'Connexion perdue' web/src/` trouvent chaque chaîne une seule fois
- **Commité dans :** `54767f0`

### Autre écart — un `--amend`, contraire à la règle de vague parallèle

Le message du commit de la tâche 3 a été corrigé par `git commit --amend` : `0b7c4be` est devenu `11f41a2`, **diff identique**, message seul modifié. Deux défauts étaient en cause :

1. Une substitution du shell avait mangé une portion entre accents graves ; la ligne se lisait « le corps d'erreur se lit sur , jamais en reclonant une reponse consommee ».
2. Un point s'attribuait `.cible-44 dans index.css`, ce que le commit **ne contenait pas** : cette règle vient de `46f0f04` (plan 03-03), et `web/src/index.css` n'a été touché par aucun commit de ce plan.

CLAUDE.md « Parallel execution » dit **« Do not rewrite history to fix it afterwards »**, et la réécriture a quand même eu lieu. Circonstance atténuante : il s'agissait du commit de tête, écrit par cet agent, non poussé, et aucun autre index n'était engagé. Elle est consignée ici plutôt que défaite — défaire coûterait un second `reset` dans un arbre partagé, ce qui est exactement ce que la règle protège. **La règle tient : la prochaine fois, le message fautif reste et la correction est écrite dans le SUMMARY.**

### Points qui auraient pu ressembler à des écarts, et n'en sont pas

- `web/package.json` figure dans la liste des fichiers du plan mais n'a pas changé : `openapi-fetch`, `openapi-react-query`, `@tanstack/react-query` et le script `api:types` existaient déjà (plans 03-03 et 03-11). Aucune dépendance n'a été ajoutée dans ce plan.

---

**Total des écarts :** 4 corrigés automatiquement (2 bugs, 1 bloquant, 1 fonctionnalité critique manquante) + 1 réécriture de message consignée
**Impact sur le plan :** aucun dépassement de périmètre. Les quatre corrections sont nécessaires à la correction ou à la testabilité ; sans la première, aucun appel d'API du produit ne fonctionnerait.

## Known Stubs

| Élément | Fichier | Raison |
|---|---|---|
| `ContenuProtege` — un `<h1>Optique</h1>` et le chemin courant en `data-testid="destination"` | `web/src/App.tsx` | **Provisoire et assumé.** Le shell réel — barre supérieure, sélecteur de magasin, navigation filtrée par les droits, recherche — est le livrable du plan **03-13**, qui remplacera ce composant sans toucher aux gardes. Le stub existe pour rendre vérifiable, sans shell, qu'un 401 mémorise le chemin tenté et y revient. C'est pour cela qu'APP-01 reste non coché ici. |

Aucun autre stub : `/connexion` et `/mot-de-passe` sont câblés sur les vraies routes, et le catalogue affiché vient du serveur.

## Issues Encountered

- **Le 401 normal du premier chargement.** `GET /api/auth/moi/` répond 401 à un visiteur anonyme, ce qui est le cas **normal** d'une première visite. Branché naïvement, le gestionnaire global affichait « Votre session a expiré » à quelqu'un qui n'en avait jamais ouvert — un message faux, et inquiétant sur un produit qui manipule de l'argent. Résolu par un drapeau `sessionOuverte` : le message de session n'appartient qu'à une session ayant réellement existé.
- **Boucle de redirection sur `/mot-de-passe`.** `RequireAuth` redirige **vers** `/mot-de-passe` quand `doit_changer_mot_de_passe` est levé ; l'appliquer aussi à cette route la fait se rediriger vers elle-même. Résolu par une garde distincte `SessionRequise`, qui exige une session sans consulter le drapeau.
- **`StrictMode` et le double montage.** `assurerJetonCsrf()` envoyait deux `GET /api/auth/csrf/` en développement. La promesse est mémorisée et remise à `null` sur échec, donc un échec reste réessayable.

## Vérification

| Contrôle | Résultat |
|---|---|
| `npm --prefix web test` | **50 passés / 50**, 3 fichiers de test, 1,08 s |
| `npm --prefix web run build` | **code 0** — `tsc -b`, `tsc -p tsconfig.test.json`, 2044 modules, 348,05 ko (112,70 ko gzip) |
| `npm --prefix web run api:types` puis `git diff --exit-code web/src/api/types.gen.ts` | **code 0** — le fichier généré est exactement celui commité |
| `npm --prefix web run audit:format` | aucun résultat — aucune locale ne décide du format de l'argent hors de `src/format/` |
| `grep -rn 'localStorage' web/src \| grep -vi magasin` | aucun résultat — **aucune identité stockée côté client** (menace T-03-83) |
| `.venv/bin/pytest -q -m "not slow"` | **179 passés, 30 désélectionnés**, 7,48 s |
| Sept vérifications au navigateur | **non effectuées** — voir la section dédiée |

## Registre de menaces

Les huit menaces T-03-80 à T-03-87 du plan sont couvertes :

- **T-03-80 / T-03-81** — une seule phrase d'échec pour tous les motifs, compte désactivé compris ; aucune étape « qui êtes-vous ? » par e-mail.
- **T-03-82** — `X-CSRFToken` sur toute méthode mutante, cookie posé avant le premier POST.
- **T-03-83** — évitée par construction : aucun jeton n'existe côté client, `localStorage` ne porte qu'une préférence de magasin, revalidée à chaque amorçage.
- **T-03-84** — aucun code de statut, aucune trace, aucun anglais à l'écran ; `NON_AUTHENTIFIE` est comparé numériquement, jamais affiché.
- **T-03-85** — `RequirePermission` ne rend rien ; un test affirme l'absence de nœud DOM.
- **T-03-86** — bannière persistante sur `onError`, qui n'est atteint que sur un échec de transport (un 500 est une réponse, pas une erreur).
- **T-03-87** — la préférence de magasin retombe silencieusement sur le premier magasin accordé, et le serveur filtre de toute façon.

Aucun rôle, aucune base et aucune fonction `SECURITY DEFINER` : CLAUDE.md #12 ne s'applique pas. **Aucune surface nouvelle hors du registre.**

## Next Phase Readiness

**Prêt pour 03-13 :** `AuthProvider` expose déjà les droits, les magasins restreints et le catalogue ; `RequirePermission` est le mécanisme de navigation filtrée ; `$api` est la seule porte d'appel. Le shell remplace `ContenuProtege` dans `App.tsx` et ne touche à aucune garde.

**Reste ouvert :**

- Les **sept vérifications manuelles ci-dessus**, non effectuées. Elles reviennent à la vérification de phase.
- **APP-01** et **APP-03** restent non cochés : leur moitié cliente est le shell (03-13). PERM-01 était déjà coché par la moitié serveur.
- **BRAND-01 (phase 9)** hérite du contrat posé ici : `/connexion` ne porte que l'identité de la plateforme, la marque du client s'applique dès la première peinture authentifiée. Ne pas concevoir une étape « qui êtes-vous ? » pour contourner cela.

---

*Phase : 03-comptes-permissions-app-shell*
*Terminé : 2026-09-17*

## Self-Check: PASSED

18 fichiers déclarés, 18 présents. 6 commits déclarés, 6 présents.

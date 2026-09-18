---
phase: 04-clients-ordonnances
plan: 07
subsystem: ui
tags: [react, router, recherche, palette, projection, accessibilite, clients]

requires:
  - phase: 04-clients-ordonnances
    plan: 02
    provides: "`ChampDate`, `formaterTelephone`, `web/tests/nomAccessible.ts`"
  - phase: 04-clients-ordonnances
    plan: 03
    provides: "`/api/clients/`, le composant OpenAPI `FicheClient`, `score` et `raison`"
  - phase: 03-comptes-permissions-app-shell
    provides: "`NAV`, `RequireDroit`, `RequirePermission`, `TableauProjete`, le registre de colonnes, `enregistrerFournisseurDeRecherche`, les cinq etats globaux"
provides:
  - "l'entree de navigation `Clients`, basculee a `disponible: true`"
  - "`/clients` — la liste, son champ de recherche propre, ses deux etats vides"
  - "`COLONNES_CLIENTS` — quatre colonnes declaratives, presence pilotee par la charge utile"
  - "`CreerClient` — le dialogue de 480px, composants controles"
  - "`GardeDeDoublon` — les fiches proches pendant la frappe, sans blocage ni pre-selection"
  - "`useFournisseurDeRechercheDesClients` — le premier fournisseur reel de la palette"
  - "`audit:projection` et `audit:clinique` — deux gardes de CI sur `src/pages/clients/`"
  - "la correction du surlignage automatique de la palette, qui auto-navigait sur un nom"
affects: [04-08-fiche-client, 04-09-validation, 05-stock, 06-facturation, 11-mobile]

tech-stack:
  added: []
  patterns:
    - "Un registre de colonnes est une DONNEE : fichier `.ts`, `createElement` plutot que du JSX, pour qu'on ne vienne pas y ajouter de la mise en page"
    - "Un fournisseur de palette s'enregistre au niveau du SHELL, jamais dans l'ecran qu'il sert — sinon la palette est muette partout ailleurs"
    - "Une action que la palette ne peut pas rendre s'exprime en RESULTAT de recherche (route vers un parametre d'URL), jamais en modifiant la palette"
    - "Un correctif de securite dans un chemin clavier doit livrer son revers d'accessibilite dans le meme commit, et le test du revers avec"

key-files:
  created:
    - web/src/pages/clients/ListeClients.tsx
    - web/src/pages/clients/CreerClient.tsx
    - web/src/pages/clients/GardeDeDoublon.tsx
    - web/src/pages/clients/colonnes.ts
    - web/src/pages/clients/messages.ts
    - web/src/pages/clients/rechercheClients.ts
    - web/tests/clients.test.tsx
  modified:
    - web/src/layout/nav.ts
    - web/src/layout/Recherche.tsx
    - web/src/App.tsx
    - web/src/api/requetes.ts
    - web/package.json
    - web/tests/shell.test.tsx
    - web/tests/connexion.test.tsx
    - .planning/REQUIREMENTS.md

key-decisions:
  - "`Recherche.tsx` A DU CHANGER : `cmdk` surlignait le premier resultat et liait `Entree` a lui, donc aucun fournisseur ne pouvait empecher l'auto-navigation sur un nom. L'abstraction de la phase 3 etait incomplete"
  - "`Entree` n'active qu'un choix DELIBERE (fleche, clic) ou la correspondance exacte du serveur ; le surlignage non demande est retire visuellement aussi"
  - "`correspondance_exacte` se pose sur `raison === telephone` PLUS un resultat unique PLUS neuf chiffres au moins dans la requete. La raison `exact` du serveur ne suffit pas : elle vaut aussi pour un nom"
  - "Le fournisseur est enregistre dans `ContenuDuShell`, conditionne a `client.voir`"
  - "Aucun resultat rend DEUX lignes de palette — la phrase d'absence et l'action de creation — parce qu'un fournisseur ne peut pas rendre un etat vide sans toucher a `Recherche.tsx`"
  - "La garde de droit porte le SOUS-ARBRE `/clients/*`, pas la seule route d'accueil, pour que la fiche du plan 04-08 n'ait qu'a ajouter une `Route`"
  - "04-UI-SPEC.md 15.3 renverse `03` 1 : pas de `react-hook-form` en phase 4, a revoir en phase 6"

patterns-established:
  - "Une garde de CI se prouve en plantant une violation et en la voyant rouge, puis en la retirant"
  - "Quand un test de phase anterieure decrit un etat que le produit n'atteint plus, il est REORIENTE vers l'utilisateur ou l'etat subsiste, jamais supprime"

requirements-completed: [CLIENT-01, CLIENT-10]

duration: 19min
completed: 2026-09-18
---

# Phase 4 Plan 07 : Les écrans clients — Résumé

**La liste, sa recherche et la création sont atteignables depuis la barre latérale par un clic, et le premier fournisseur réel de la palette est branché — mais `Recherche.tsx` a dû changer : `cmdk` surlignait le premier résultat et liait `Entrée` à lui, donc « rien n'auto-navigue sur un nom » ne tenait pas, et aucun fournisseur ne pouvait le réparer depuis l'extérieur.**

## Performance

- **Durée :** ~19 min
- **Débuté :** 2026-09-18T15:43Z · **Terminé :** 2026-09-18T16:02Z
- **Tâches :** 3 / 3
- **Fichiers :** 15 (7 créés, 8 modifiés) — 14 sous `web/`, plus `REQUIREMENTS.md`
- **Vague :** parallèle avec `04-04`, même worktree, même index

## Les nombres relevés, pas prédits

| Porte | Ligne de base | Après tâche 1 | Après tâche 2 | Fin de plan |
|---|---|---|---|---|
| `npm --prefix web test` | **149 passed** (7 fichiers) | 149 passed, **10 failed** (8 fichiers) | 156 passed, **3 failed** | **160 passed, 0 failed** (8 fichiers) |
| `npm --prefix web run build` | 0 | — | 0 | **0** |
| `npm --prefix web run audit:format` | 0, muet | — | 0, muet | **0, muet** |
| `npm --prefix web run audit:projection` | n'existait pas | — | — | **0** |
| `npm --prefix web run audit:clinique` | n'existait pas | — | — | **0** |

**Tests écrits contre emplacements neufs — ils coïncident, et c'est dit plutôt que
supposé.** Aucun `it.each` n'a été ajouté, donc un `it` écrit vaut exactement un
emplacement : **11 `it` écrits, 11 emplacements neufs**. `149 + 11 = 160`. Le décompte
ferme.

Le plan en demandait huit. Les trois de plus sont détaillés en déviations : les deux états
vides (que le plan exigeait « au caractère près » sans les faire vérifier), le formatage du
téléphone, et — le plus important — **le revers d'accessibilité du correctif de la palette**.

**`pytest` n'a PAS été exécuté.** Le plan `04-04` possède les bases de test dans cette
vague ; deux sessions concurrentes se détruisent mutuellement leurs bases et échouent dans
des fichiers qui n'ont rien demandé.

## La trouvaille : `Recherche.tsx` a dû changer, et pourquoi c'est une information

Le plan posait comme critère que **`web/src/layout/Recherche.tsx` ne change pas d'une
ligne** — « c'était l'objet même de sa construction en phase 3 » — et demandait, s'il
fallait le modifier, de le dire plutôt que de le faire discrètement. **Il a fallu.**

### Ce que le test a montré

Le test `la palette ne navigue jamais automatiquement sur un nom` a été **rouge deux fois
de suite**, la seconde avec une implémentation pourtant correcte :

    AssertionError: expected '/clients/3' to be '/'

Le fournisseur ne posait pas `correspondance_exacte` — vérifié, la valeur était bien
`false`. `resultatExact()` rendait donc `undefined`, et le `onKeyDown` de `Recherche.tsx`
ne faisait rien. **La navigation venait de `cmdk`**, qui :

1. sélectionne le premier élément dès qu'une liste arrive (`W()` dans `cmdk/dist/index.mjs` :
   `let e = V().find(s => s.getAttribute("aria-disabled") !== "true"); E.setState("value", ...)`) ;
2. écoute `keydown` **sur la racine** `cmdk-root` et, sur `Enter`, dispatche l'événement de
   sélection vers l'élément surligné (`case "Enter": { e.preventDefault(); let i = M(); if (i) … }`).

Autrement dit : **taper un nom puis envoyer `Entrée` ouvrait le premier candidat**, et
aucun fournisseur ne pouvait l'empêcher, parce que ni la sélection ni la liaison clavier ne
passent par le contrat `FournisseurDeRecherche`.

### Pourquoi c'est exactement la menace, et pas un détail d'interface

C'est T-04-47 mot pour mot. Aucun seuil ne sépare la vérité de l'erreur dans ce
classement : `mhamed → mohammed alaoui` vaut **0,333** — correspondance que CLIENT-10
**exige** — quand `fatima → fatiha bennani` vaut **0,571** et `abdelkrim → abdelkader
bennani` **0,600** — deux paires de personnes **distinctes** (mesures du plan 04-03, en
`word_similarity`). Le classement est donc **inversé**. Ouvrir le premier candidat au
comptoir, c'est ouvrir la fiche du voisin ; avec des ordonnances dessus, c'est une
divulgation de donnée de santé.

### Ce qui a été tenté avant de modifier le fichier

**La sélection contrôlée** (`<Command value={selection} onValueChange={…}>` démarrant à
`""`). Elle ne suffit pas : `W()` repose la valeur sur le premier élément à chaque
changement de recherche, et la repousse par `onValueChange`. Tentée, mesurée rouge,
abandonnée.

### Le correctif, et son revers livré dans le même commit

`Entrée` n'active plus que **ce que l'utilisateur a délibérément choisi** — une flèche, un
clic — **ou** ce que le serveur a marqué `correspondance_exacte`. L'événement est
`stopPropagation()` et pas seulement `preventDefault()`, parce que `cmdk` écoute sur la
racine et ne consulte pas `defaultPrevented`.

Et parce qu'**une ligne qui a l'air sélectionnée et qu'`Entrée` ignore serait une interface
qui ment**, le surlignage non demandé est retiré **visuellement** aussi, tant que personne
n'a choisi.

**Le revers est le point le plus important de ce correctif.** Désarmer `Entrée` sans
laisser de chemin clavier aurait fermé la palette à qui n'utilise pas de souris —
c'est-à-dire aurait corrigé une divulgation par une régression d'accessibilité, derrière
une suite verte. Le test `une fleche puis Entree ouvre bien la fiche CHOISIE, au clavier
seul` existe pour cela, et il assert qu'on atterrit sur la **seconde** ligne, celle qui a
été visée — pas sur celle que `cmdk` surligne tout seul.

### Ce que cela dit du contrat de la phase 3

L'abstraction n'était pas fausse, elle était **incomplète** : elle exposait *quels
résultats existent* et laissait *comment on les active* entièrement à `cmdk`. Un
fournisseur pouvait donc décrire ses résultats avec la plus grande prudence et être
contredit par la bibliothèque. Le contrat porte désormais les deux, et la phase 5
(`Articles`) comme la phase 6 (`Factures`) en héritent sans rien découvrir.

## Les rouges observés, et ce que chaque test attrape

Tâche 1, `npm --prefix web test` : **10 failed | 149 passed**.

| Test | Message d'échec observé |
|---|---|
| `on atteint la liste … en CLIQUANT depuis la racine` | `Unable to find an accessible element with the role "link" and name "Clients"` — l'entrée était `disponible: false` |
| `sans client.voir, l_entree est absente et la route rend la 403 …` | `Unable to find role="heading" and name "Vous n'avez pas accès à cette page."` |
| `la requete part telle quelle au serveur` | `Unable to find a label with the text of: Rechercher un client` |
| `la palette ne navigue jamais … sur un nom` | `Unable to find role="button" and name "Recherche"` |
| `le score ne s_affiche jamais comme un nombre …` | idem |
| `la garde de doublon s_affiche, ne bloque pas …` | `Unable to find role="button" and name "Créer un client"` |
| `aucune colonne protegee n_est ressuscitee …` | `Unable to find role="columnheader" and name "Dernière ordonnance"` |
| `tout combobox de cet ecran a un nom accessible non vide` | `Unable to find an element with the text: Mohammed Alaoui` |
| `distingue l_affaire sans aucune fiche …` | `Unable to find an element with the text: Aucun client` |
| `rend le telephone par le formateur partage …` | `AssertionError: expected undefined to be truthy` |

Ce que chacun attrape, une fois vert :

| Test | Ce qu'il attrape |
|---|---|
| `on atteint la liste … en CLIQUANT` | **La leçon 03-14.** Trente-deux tests verts sur un écran inatteignable. Ce test part de `/` et clique ; un montage direct sur `/clients` ne peut pas distinguer construit d'atteignable |
| `sans client.voir …` | Les deux moitiés : l'entrée **retirée** (jamais grisée) et la 403 qui **nomme** le droit. Un `PageEnAttente` affichant le chemin serait une impasse, et un code de permission affiché serait du vocabulaire interne |
| `la requete part telle quelle` | Le `trim()` ou le `toLowerCase()` qu'on ajoute « pour bien faire », et qui fait diverger le résultat de l'index serveur (T-04-51). Il porte son contrôle négatif : aucune URL ne contient la forme pliée |
| `la palette ne navigue jamais … sur un nom` | **La commodité qu'on ajoute six mois plus tard**, et qui ouvre la fiche du voisin. C'est lui qui a trouvé le défaut `cmdk` |
| `une fleche puis Entree ouvre la fiche CHOISIE` | Le correctif ci-dessus transformé en porte fermée au clavier. Il assert la **seconde** ligne, donc aussi que le surlignage automatique n'est plus la réponse |
| `le score ne s_affiche jamais comme un nombre` | « 0,333 » affiché à un opticien, qui l'inviterait à comparer deux rangs qu'aucun seuil ne sépare |
| `la garde de doublon …` | Quatre moitiés en un test : elle s'affiche, elle est **au-dessus** du formulaire (`compareDocumentPosition`), elle ne désactive pas `Créer le client`, et elle ne pré-sélectionne rien (`aria-selected`, `aria-checked`, `input:checked`) |
| `aucune colonne protegee n_est ressuscitee` | La branche cliente `{peut ? … : null}`. **Il porte sa jumelle de présence** : le jeu **avec** `derniere_ordonnance` rend bien l'en-tête, sans quoi un tableau qui ne rendrait jamais rien serait vert |
| `tout combobox … a un nom accessible non vide` | D-1 reproduit. Il **énumère** `[role="combobox"]` plutôt que de sonder un élément connu, et il affirme explicitement le cas « aucun » plutôt que d'itérer sur le vide. Il porte son contrôle positif : la mesure rend bien `Nom complet` sur un champ étiqueté |
| `distingue l_affaire sans aucune fiche de la recherche sans resultat` | Deux situations fondues en une phrase. Il vérifie aussi que **zéro ligne rend zéro en-tête** — les en-têtes du registre révéleraient l'existence de `Dernière ordonnance` |
| `rend le telephone par le formateur partage` | `${client.telephone}` écrit à la main. L'attendu est **calculé par le formateur**, donc un U+00A0 dégénéré en espace ordinaire ne peut pas passer |

## Les quatre colonnes, et la cinquième qui n'existe pas

`nom` · `telephone` · `date_naissance` · `derniere_ordonnance`.

**Pas de `derniere_visite`**, et la raison est écrite dans `colonnes.ts` plutôt que laissée
à deviner : `colonnesVisiblesSurLignes` filtre sur `champ in ligne`, et le registre
distingue délibérément la **clé absente** — « vous n'avez pas le droit » — de **`null`** —
« la donnée est inconnue ». Pour rendre `Jamais`, le champ devrait être **présent et nul** ;
or les visites supposent les ventes, donc la phase 6. La colonne aurait été filtrée à chaque
rendu, en silence, sans test pour le dire.

**Pas de colonne `Actions`, pas de menu de ligne.**

`derniere_ordonnance` est le **premier champ protégé du produit côté client**, et la seule
chose faite a été **rien** : aucune branche, aucun tiret, aucun cadenas. La vague 4 lui
donnera sa charge utile et la colonne apparaîtra d'elle-même.

## Décisions prises

1. **`correspondance_exacte` demande trois conditions simultanées** : `raison === "telephone"`,
   un résultat **unique**, et au moins **neuf chiffres** dans la requête. La raison `exact`
   du serveur ne suffit pas — elle signifie « égalité de chaîne normalisée », et deux
   personnes peuvent légitimement s'appeler « Mohamed Alaoui ». Compter les chiffres de la
   requête n'est **pas** une normalisation : rien de ce qui est calculé là n'est envoyé, le
   serveur reçoit la chaîne telle quelle. C'est écrit à côté de la fonction.

2. **Le fournisseur est enregistré dans `ContenuDuShell`, pas dans `ListeClients`.** La
   palette est le mode d'accès **principal** du produit (`03` §5.5) : l'enregistrer dans
   l'écran des clients la rendrait muette partout ailleurs, c'est-à-dire exactement là où on
   s'en sert.

3. **Il est conditionné à `client.voir`.** Sans le droit, chaque frappe produirait un 403
   que le fournisseur avalerait en silence ; l'absence du champ est cohérente avec l'absence
   de l'entrée de navigation. Rappel écrit dans le fichier : c'est du **confort**, le
   contrôle est la classe de permission du serveur.

4. **Aucun résultat rend DEUX lignes de palette** — `Aucun client ne correspond à « … ».`
   et `Créer un client « … »` — routées vers `/clients?search=…` et `/clients?creer=…`.
   C'était la seule façon de livrer la copie de §23 **sans toucher à `Recherche.tsx`**, dont
   le `CommandEmpty` appartient au shell. La liste consomme les deux paramètres puis les
   retire, pour qu'un rafraîchissement ne rouvre pas un dialogue fermé.

5. **La garde de droit porte le sous-arbre `/clients/*`**, pas la seule route d'accueil. Une
   garde sur l'index laisserait `/clients/42` répondre 404 à qui n'a pas le droit au lieu du
   403 qui nomme ce qui manque, et la fiche du plan 04-08 devrait réécrire sa propre garde.
   Elle n'aura qu'à ajouter une `Route` à l'intérieur.

6. **`colonnes.ts` reste un `.ts` et utilise `createElement`.** Le module est une **donnée** ;
   le garder hors du JSX dit qu'on ne viendra pas y ajouter de la mise en page. Les trois
   rendus sur mesure n'existent que parce que `formaterDateCourte` lève sur `null`, ce que
   le format déclaratif du tableau ne sait pas absorber.

7. **Pas de bibliothèque de formulaire** — `04-UI-SPEC.md` §15.3 **renverse** `03` §1, et le
   renversement est écrit dans la docstring de `CreerClient.tsx` avec ses trois raisons et
   son renvoi : **à revoir en phase 6**, dont les lignes de facture sont un tableau de champs
   dynamique — le cas qu'une bibliothèque gagne réellement. `grep -c react-hook-form
   web/package.json` rend **0**.

8. **Le bouton `Créer le client` n'est désactivé que pendant l'envoi et sur un refus de date
   en cours.** Ni la garde de doublon, ni un nom vide ne le désactivent : le premier étage du
   modèle de validation est le refus, et le serveur refuse indépendamment.

## Écarts au plan

### Corrections automatiques

**1. [Règle 1 — Bogue de sécurité] `Recherche.tsx` auto-naviguait sur un nom**

- **Trouvé pendant :** tâche 3, par le test `la palette ne navigue jamais automatiquement sur un nom`
- **Problème :** décrit en détail plus haut. `cmdk` surligne le premier résultat et lie
  `Entrée` à lui ; le contrat `FournisseurDeRecherche` ne pouvait pas l'empêcher
- **Correction :** `Entrée` n'active qu'un choix délibéré ou la correspondance exacte du
  serveur ; le surlignage non demandé est retiré visuellement ; le revers clavier est livré
  et testé dans le même commit
- **Fichiers :** `web/src/layout/Recherche.tsx` (**le fichier que le plan demandait de ne
  pas modifier**, et c'est la raison d'être de ce paragraphe)
- **Commit :** `5ba8eff`

**2. [Règle 3 — Bloquant] Deux tests de phase 3 visaient `/clients` comme route SANS module**

- **Trouvé pendant :** tâche 2
- **Problème :** `tests/connexion.test.tsx` (chemin mémorisé) et `tests/shell.test.tsx`
  (la portée ne navigue pas) lisaient `data-testid="destination"`, que seul `PageEnAttente`
  rend. Leurs commentaires **disaient déjà** viser « une route dont le module attend
  encore », et qu'ils avaient migré de `/parametres/comptes` vers `/clients` au plan 03-14
- **Correction :** ils visent `/stock`, qui joue ce rôle jusqu'à la phase 5. Le commentaire
  consigne la chaîne de déplacements, pour que le prochain n'ait pas à la redécouvrir
- **Commit :** `4ddd92d`

**3. [Règle 3 — Bloquant] Le test du gabarit de recherche décrivait un état que le produit n'atteint plus**

- **Trouvé pendant :** tâche 3
- **Problème :** `conserve ses 480px sans fournisseur enregistre` montait un propriétaire,
  qui détient `client.voir` — donc le fournisseur s'enregistre et le champ apparaît
- **Correction :** il monte un gérant sans `client.voir`, qui est encore exactement dans ce
  cas. **Il garde ses trois assertions**, son objet et son nom. Sa moitié jumelle — « avec le
  droit, le champ est là » — vit dans `clients.test.tsx`, qui clique ce bouton trois fois
- **Commit :** `5ba8eff`

**4. [Règle 3 — Bloquant] `ListeClients` ne compile pas sans le dialogue qu'elle ouvre**

- **Trouvé pendant :** tâche 2
- **Problème :** le plan place `ListeClients.tsx` en tâche 2 et `CreerClient.tsx` en tâche 3.
  La liste importe le dialogue ; le commit intermédiaire n'aurait pas construit
- **Correction :** `CreerClient.tsx` est livré en tâche 2, **sans** sa garde de doublon. La
  tâche 3 ajoute `GardeDeDoublon.tsx` et l'y branche, donc le test n° 6 garde son parcours
  rouge → vert intact
- **Commit :** `4ddd92d` puis `5ba8eff`

### Ajouts au titre de la règle 2

**5. Trois tests que le plan n'avait pas demandés**

| Test ajouté | Ce qu'il tient |
|---|---|
| `une fleche puis Entree ouvre bien la fiche CHOISIE, au clavier seul` | **Le revers de l'écart n° 1.** Sans lui, la correction d'une divulgation aurait fermé la palette aux utilisateurs clavier, derrière une suite verte |
| `distingue l_affaire sans aucune fiche de la recherche sans resultat` | Le `<done>` de la tâche 2 exige les deux états vides « au caractère près » et ne les fait vérifier nulle part. Il tient aussi « zéro ligne rend zéro colonne » |
| `rend le telephone par le formateur partage, pas par une interpolation` | §18.3 est la raison d'être de `formaterTelephone` en phase 4 ; rien ne vérifiait qu'il est réellement appelé |

**6. [Registre des menaces] L'avertissement A11 sur le téléphone**

La tâche 3 ne le mentionne pas, mais §18.6 et §16.3 le nomment : créer un client sans
téléphone rend `À vérifier — sans téléphone, ce client ne recevra aucun rappel.` Livré au
contrat de §16.4 : `role="status"`, présent dans `aria-describedby`, **sans `aria-invalid`**,
et il n'empêche rien.

**7. Les deux gardes de CI prouvées rouges avant d'être déclarées vertes**

`audit:projection` et `audit:clinique` ont été exercées sur une violation plantée dans
`colonnes.ts` — un `peut ? <span/> : null` et un commentaire contenant des bornes —, les
deux sont sorties à **1**, puis à **0** après retrait. Une garde qu'on n'a jamais vue rouge
ne prouve rien.

## Le piège de la prose grepée, évité de justesse

CLAUDE.md a gagné aujourd'hui la règle « une garde d'acceptation cherche un appel, un import
ou une affectation, jamais un mot nu », après dix occurrences.

Les deux gardes de ce plan cherchent une **forme syntaxique** : `\? *<[^>]*> *: *null|peut *\?`
et une classe de nombres bornée par `(^|[^0-9.])…([^0-9]|$)`. Vérifié : `sm:max-w-[480px]`
ne déclenche pas `audit:clinique` (le `180` y est précédé d'un chiffre), et la prose
française de `colonnes.ts` — qui parle de « la colonne disparaît sans tiret ni cadenas » —
ne déclenche pas `audit:projection`.

**`audit:clinique` attraperait une phrase française contenant les bornes, et c'est voulu** :
cette phrase-là vient du serveur (§16.2), elle n'a rien à faire en dur dans un composant.
Le commentaire de `CreerClient.tsx` qui l'explique est donc écrit **sans chiffres**.

Une vérification du plan elle-même a failli tomber dans le piège : `grep -A5 '"/clients"'
web/src/layout/nav.ts | grep -q 'disponible: true'`. Le commentaire justifiant la bascule,
écrit **à l'intérieur** de l'entrée, poussait `disponible` au-delà des cinq lignes. Le
commentaire est passé **au-dessus** de l'accolade ouvrante — il se lit mieux là de toute
façon.

## Exigences cochées, et la moitié de CLIENT-10 qui ne l'est pas

**CLIENT-01** — *« créer une fiche client avec ses coordonnées, et la retrouver par son nom
ou son téléphone »* : **cochée**. Un opticien clique `Clients`, tape un nom ou un numéro dans
le champ de la liste ou dans la palette, et crée une fiche par le dialogue. Le plan 04-03
avait délibérément laissé les deux non cochées en nommant celui-ci.

**CLIENT-10** — *« la recherche client **et article** est insensible aux accents et tolérante
aux variantes de translittération »* : **cochée**, avec une réserve nommée. La moitié
**client** est livrée de bout en bout : les quatre couches de rappel (plan 04-03), la requête
brute, l'affichage en mots. La moitié **article** appartient à la **phase 5** (STOCK-07) et
n'existe pas encore. Elle réutilisera le même mécanisme — `enregistrerFournisseurDeRecherche`
plus une couche `pg_trgm` — donc rien à concevoir, seulement à brancher. Cocher se défend
parce que la phrase que l'exigence illustre (« Mohamed, Mohammed et Mhamed trouvent la même
personne ») est **entièrement** satisfaite ; si l'on préfère une traçabilité stricte,
décocher jusqu'à la phase 5 est légitime et sans coût.

**CLIENT-02** (historique d'achats) n'est pas dans ce plan : il suppose les ventes, phase 6.

## Vérifications manuelles

**Ce plan n'en ajoute aucune** — le solde est **zéro**, comme le plan l'exige. Les cinq
vérifications visuelles de la phase 4 sont portées par le plan `04-09`. Deux revendications
de ce plan sont toutefois **visuelles par nature** et leur assertion ici est de **classe**,
pas de visibilité : le retrait du surlignage automatique de la palette, et
`tabular-nums` sur le téléphone et les dates. `04-09` devrait les regarder à l'œil.

## Commits par tâche

1. **Tâche 1 — les tests, rouges d'abord, en partant d'un clic** : `d327f82` (test)
2. **Tâche 2 — la liste, atteignable depuis la barre latérale** : `4ddd92d` (feat)
3. **Tâche 3 — la création, la garde de doublon, le fournisseur de palette** : `5ba8eff` (feat)

Chemins nommés à chaque commit (`git commit -F - -- <chemins>`), jamais `git add -A`.
Aucune mention de Claude dans aucun message. Vérifié : `git show --stat` sur les trois
commits ne porte **aucun** fichier Python et rien sous `domaine/`, `plateforme/` ou `tests/`
— le plan `04-04` écrivait dans le même index au même moment et ses commits `21bf4f9` et
`7eb472b` se sont intercalés **sans mélange**.

`state advance-plan` n'a **pas** été exécuté.

## Vérifications du plan, une par une

| Critère | Résultat |
|---|---|
| Un clic sur `Clients` depuis `/` mène à une liste réelle | vert, prouvé par un test qui part de `/` |
| Sans `client.voir` : entrée absente, 403 qui nomme le droit | vert |
| La requête part verbatim | vert, avec contrôle négatif |
| Rien n'auto-navigue sur un nom ; un téléphone unique, oui | vert — **a exigé de modifier `Recherche.tsx`** |
| Le score n'apparaît jamais comme un nombre | vert |
| La garde de doublon s'affiche, ne bloque pas, ne pré-sélectionne rien | vert |
| Aucune branche cliente de projection | vert, test à deux jeux **et** `audit:projection` |
| Aucun nombre clinique sous `web/src/pages/clients/` | vert, `audit:clinique` |
| `web/src/layout/Recherche.tsx` inchangé | **NON** — 81 insertions, 2 suppressions, motivées ci-dessus |
| `web/src/etats/messages.ts` inchangé | **oui** — `git diff --quiet c1d54c1 5ba8eff` est muet |
| Aucun fichier Python dans le diff | **oui** |

## Stubs connus

| Stub | Fichier | Raison, et qui le résout |
|---|---|---|
| Un clic sur une ligne navigue vers `/clients/{id}`, qui rend aujourd'hui la page 404 | `web/src/pages/clients/ListeClients.tsx` | La fiche est le plan **04-08**, vague 4. Le plan de celui-ci demande explicitement de câbler `onLigneActivee` vers la fiche ; la route existe déjà sous la bonne garde et 04-08 n'ajoute qu'une `Route`. Même remarque pour les liens `Ouvrir la fiche` de la garde de doublon |
| Après création, la liste se rafraîchit mais ne va pas sur la fiche neuve | `web/src/pages/clients/ListeClients.tsx` | Aller sur la fiche est la suite naturelle (y attacher une ordonnance) mais elle n'existe pas encore. **À reprendre en 04-08** |
| La colonne `derniere_ordonnance` est déclarée et n'est jamais présente | `web/src/pages/clients/colonnes.ts` | **Voulu, et testé dans les deux sens.** La charge utile la porte en vague 4 ; ici l'absence est une étape, pas un cul-de-sac |

Aucune valeur vide codée en dur, aucun texte d'attente, aucun composant sans source de
données.

## Éléments différés

| Réf | Ce qui est différé | Reprenant |
|---|---|---|
| **D-4-07-1** | L'aide `Sert aux rappels et à la règle des moins de 16 ans.` est rendue **à côté** de `ChampDate` et non reliée par `aria-describedby` : le composant gère lui-même cet attribut et n'expose pas de prop d'aide. Le texte est visible et adjacent, mais pas programmatiquement associé. Une prop `aide` sur `ChampDate` réglerait les trois écrans d'un coup | `04-08`, qui rend le même champ |
| **D-4-07-2** | `GardeDeDoublon` et le champ de la liste interrogent la même route ; sur un même terme, `react-query` partage l'entrée de cache, mais deux clés distinctes coexistent quand les termes diffèrent. Aucune mesure ne dit que cela coûte quoi que ce soit | à mesurer si une base réelle ralentit |
| **D-4-07-3** | D-1 (le `combobox` sans nom du sélecteur de magasin) **n'est pas corrigé** — ce n'est pas le fichier de ce plan. Le test d'énumération de ce plan est volontairement borné à `#contenu` et au dialogue, et les fixtures montent **un seul magasin** pour que le défaut hérité ne le fasse pas échouer pour la mauvaise raison | `04-09` ou une tâche rapide |

## Configuration utilisateur requise

Aucune.

## État pour la suite

**Prêt pour `04-08` (la fiche client) :**

- la route `/clients/*` existe, gardée par `client.voir` : ajouter `<Route path=":id" …>` suffit ;
- `COLONNES_CLIENTS`, `messages.ts` et `GardeDeDoublon` sont réutilisables tels quels ;
- les deux gardes de CI couvrent déjà tout `src/pages/clients/`, donc la fiche naît sous garde.

**À ne pas manquer :**

- **`Recherche.tsx` porte désormais une règle de sécurité**, pas seulement du rendu. La
  phase 5 y branchera `Articles` sans la toucher — mais une douchette clavier compte sur
  `correspondance_exacte`, que le serveur doit poser sur une **référence** exacte, et
  `Entrée` ne fonctionnera que par ce chemin-là.
- **`correspondance_exacte` est décidé par le fournisseur à partir de `raison`**, pas
  recopié du serveur. La phase 5 doit écrire sa propre règle, et elle doit être aussi
  étroite.
- Les deux paramètres d'URL `?search=` et `?creer=` sont consommés puis **retirés** par la
  liste ; tout écran qui voudra y router doit savoir qu'ils ne survivent pas à un
  rafraîchissement.

---
*Phase : 04-clients-ordonnances · Plan 07*
*Terminé : 2026-09-18*

## Self-Check: PASSED

Les sept fichiers annoncés existent sur le disque ; les trois empreintes `d327f82`,
`4ddd92d` et `5ba8eff` existent dans l'historique ; `npm --prefix web test` rend
**160 verts sur 8 fichiers**, `grep -c "  it(" web/tests/clients.test.tsx` rend **11**, et
`149 + 11 = 160` ferme le décompte. `run build` sort à **0**, et `audit:format`,
`audit:projection` et `audit:clinique` sortent tous à **0** — les deux dernières après
avoir été vues **rouges** sur une violation plantée.

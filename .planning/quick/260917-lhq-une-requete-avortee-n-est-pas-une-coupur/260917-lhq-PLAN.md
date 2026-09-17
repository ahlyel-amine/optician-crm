---
phase: quick
plan: 260917-lhq
type: execute
wave: 1
depends_on: []
files_modified:
  - web/tests/reseau.test.tsx
  - web/src/api/client.ts
autonomous: true
requirements: [APP-01]

must_haves:
  truths:
    - "Une requete avortee — `AbortError`, ou `request.signal.aborted` vrai — ne met JAMAIS l'application en etat de lien perdu : `useLienDisponible()` reste `true` et `BanniereDeLien` ne rend rien"
    - "Un echec de transport genuin (DNS, socket, TLS : `TypeError: Failed to fetch`) leve TOUJOURS la banniere — la correction ne doit pas devenir « ne plus jamais rien signaler »"
    - "Les deux formes d'abandon sont reconnues : `DOMException` nommee `AbortError` (navigateurs, undici) ET un `Error` simple nomme `AbortError` (environnements qui ne disposent pas de `DOMException`)"
    - "`request.signal.aborted` est consulte en premier : c'est le fait, la forme de l'exception n'en est que le symptome"
    - "Un abandon ne signale NI la panne NI le retablissement — il ne touche pas l'etat du lien, dans un sens comme dans l'autre"
    - "Le commentaire de `onError` enonce la distinction au lieu de repeter l'erreur : il listait `requete avortee` parmi les cas puis concluait que tout cas est une coupure"
    - "Aucun changement serveur : ni vue, ni serialiseur, ni route, donc `web/src/api/schema.yml` et `web/src/api/types.gen.ts` ne sont pas regeneres"
    - "Aucun seuil, aucun compteur, aucun delai de grace ajoute — voir la decision ci-dessous"
  artifacts:
    - path: "web/tests/reseau.test.tsx"
      provides: "les deux tests exiges (abandon muet / transport bruyant) plus les deux variantes de forme d'exception"
      contains: "test_app01_"
    - path: "web/src/api/client.ts"
      provides: "`estUneRequeteAvortee()` et un `onError` qui distingue l'abandon de la coupure"
      contains: "AbortError"
  key_links:
    - from: "web/src/api/client.ts"
      to: "web/src/etats/reseau.ts"
      via: "`signalerPanneDeLien()` n'est plus appele que sur un echec de transport reel"
      pattern: "signalerPanneDeLien"
    - from: "web/tests/reseau.test.tsx"
      to: "web/src/etats/BanniereDeLien.tsx"
      via: "le test monte la banniere et affirme sur le DOM, pas seulement sur le magasin d'etat"
      pattern: "BanniereDeLien"
---

<objective>
Cinquieme defaut de la phase trouve par le proprietaire **dans un vrai navigateur** pendant
que 306 tests etaient verts : la banniere `Connexion perdue. Vos modifications ne seront pas
enregistrées.` clignote a **chaque** rechargement de page et a **chaque** changement de route.

Le diagnostic est etabli, il n'est pas a refaire. `web/src/api/client.ts:175` :

```js
onError() {
  // `fetch` ne rejette que sur un echec de transport : DNS, socket, TLS,
  // requete avortee. Un 500 n'est PAS une erreur ici, c'est une reponse. Donc
  // arriver dans cette branche veut dire que le lien est tombe.
  signalerPanneDeLien();
  return undefined;
}
```

Le commentaire **enumere `requete avortee` parmi les cas** puis conclut qu'arriver la veut dire
que le lien est tombe. La conclusion contredit sa propre liste. **Une requete avortee n'est pas
une coupure de lien.**

Le chemin exact, verifie dans les paquets installes :

- `openapi-react-query` (`dist/index.mjs:10`) passe le `signal` de react-query dans l'`init` :
  `await fn(path, { signal, ...init })`.
- `openapi-fetch` 0.17.0 (`dist/index.mjs:78`) le pose sur la `Request` : `new Request(url,
  requestInit)`. Donc **le signal est joignable depuis l'intergiciel**.
- react-query annule la requete quand le dernier observateur se desabonne — c'est-a-dire au
  demontage, c'est-a-dire a chaque changement de route — et le navigateur annule au
  dechargement. `fetch` rejette alors avec un `AbortError`, `signalerPanneDeLien()` part, la
  banniere se peint, et la reponse suivante appelle `signalerLienRetabli()` qui la retire.
  D'ou le clignotement.
- `onError` recoit `{ request, error, ... }` (`dist/index.d.ts:158`), donc les deux sources de
  verite sont disponibles au meme endroit.

**Ce n'est pas cosmetique.** `03-UI-SPEC.md` 8.6 rend la banniere contractuelle : tant qu'elle
est levee, **tout controle d'ecriture est desactive**, et les phases 4 a 12 consultent toutes
`useLienDisponible()`. Donc aujourd'hui, brievement a chaque navigation, le produit entier se
croit hors ligne. Et une banniere qui crie au loup entraine l'utilisateur a ignorer la seule
fois ou elle dit vrai.
</objective>

<decision name="faut-il plus d'un point de mesure avant de lever la banniere ?">
**Non. La correction de l'abandon est toute la reponse.** Raisonne, pas esquive :

`clientDeRequetes` porte `retry: false` (`web/src/api/requetes.ts`) — decision deliberee du plan
03-12, parce que 8.6 veut qu'un echec soit VU tout de suite. Exiger deux echecs consecutifs
avant de lever la banniere aurait donc une consequence perverse : apres un unique appel echoue,
**aucune seconde requete ne part**. L'utilisateur au comptoir reste devant une interface qui a
l'air vivante, avec ses controles d'ecriture actifs, sur un lien mort. Un seuil rendrait la
banniere silencieuse exactement dans le cas le plus courant d'une vraie coupure.

Le bruit n'est pas cause par un manque de points de mesure — il est cause par **une mesure
fausse**. Un abandon n'est pas une observation du lien du tout : personne n'a mesure quoi que
ce soit, la mesure a ete annulee. On ne compense pas une mesure fausse en en exigeant deux ;
on la retire. Une fois l'abandon ecarte, il ne reste dans cette branche que des echecs de
transport reels, et un seul suffit.

Aucun compteur, aucune fenetre glissante, aucun delai de grace ne sont donc ajoutes.
</decision>

<task type="auto" tdd="true" name="1. Un abandon n'est pas une coupure">

<behavior>
`web/tests/reseau.test.tsx`, nouveau fichier. Quatre tests, tous rouges avant la correction
(les deux premiers uniquement — voir la note). Nommes d'apres APP-01 et le contrat 8.6.

1. `test_app01_une_requete_avortee_ne_leve_pas_la_banniere_de_lien_perdu`
   Monte `BanniereDeLien`. Double `fetch` : il avorte le `AbortController` fourni puis rejette
   avec `new DOMException("...", "AbortError")`. Appelle `clientApi.GET("/api/auth/moi/",
   { signal })`. Affirme `lienDisponible() === true` **et** l'absence du texte
   `MESSAGE_LIEN_PERDU` dans le DOM.

2. `test_app01_un_echec_de_transport_leve_bien_la_banniere`
   Le garde-fou qui interdit que la correction devienne « ne plus rien signaler ». Double
   `fetch` : rejette `new TypeError("Failed to fetch")`, **aucun signal avorte**. Affirme
   `lienDisponible() === false` **et** la presence du texte exact de `MESSAGE_LIEN_PERDU`.

3. `test_app01_un_abandon_sans_DOMException_est_reconnu_aussi`
   Certains environnements rejettent avec un `Error` simple nomme `AbortError`. Meme
   affirmation que 1.

4. `test_app01_un_abandon_ne_retablit_pas_un_lien_deja_tombe`
   Part de l'etat tombe (`signalerPanneDeLien()`), joue un abandon, affirme que la banniere est
   **toujours la**. Un abandon ne touche l'etat dans aucun des deux sens.

`beforeEach` remet `enLigne` a vrai par `signalerLienRetabli()` — le magasin est un module, son
etat survit d'un test a l'autre. `afterEach` fait `vi.unstubAllGlobals()`, comme les quatre
suites existantes.
</behavior>

<implementation>
`web/src/api/client.ts` — `estUneRequeteAvortee(error, request)` puis un `onError` qui s'en sert.

```ts
function estUneRequeteAvortee(erreur: unknown, requete: Request): boolean {
  if (requete.signal?.aborted === true) return true;                    // le fait
  return erreur instanceof Error && erreur.name === "AbortError";       // le symptome
}
```

`DOMException` herite de `Error` dans tous les environnements cibles (navigateurs, undici,
jsdom), donc le test `instanceof Error` couvre les deux formes en une ligne — a verifier
plutot qu'a supposer, c'est ce que fait le test 3.

`onError({ error, request })` : si la requete a ete avortee, **rendre `undefined` sans toucher
au lien**. Sinon `signalerPanneDeLien()` comme avant.

Le commentaire est reecrit. Il doit dire la distinction — mesure annulee contre mesure qui
echoue — et pourquoi le signal est consulte avant le nom de l'exception, pas re-enoncer la
phrase fausse.
</implementation>

<verification>
- `npm --prefix web test` : les 122 d'avant plus les 4 nouveaux, aucun regresse
- `npm --prefix web run build` : code 0
- `.venv/bin/pytest -q -m "not slow"` : 184 inchanges (aucun fichier serveur touche)
- `git diff --exit-code web/src/api/schema.yml web/src/api/types.gen.ts` : vide
</verification>

<done>
La phase RED est commitee separement et **observee rouge** avant que la correction n'existe ;
les deux commits nomment leurs chemins explicitement.
</done>

</task>

<success_criteria>
- [ ] Les tests 1 et 2 confirmes rouges contre le code d'avant, la sortie citee dans le SUMMARY
- [ ] Un abandon ne signale plus rien ; un echec de transport signale toujours
- [ ] Le commentaire trompeur reecrit
- [ ] Suites avant/apres avec des nombres reels, build a 0
- [ ] `ROADMAP.md` non touche, `state advance-plan` non execute
- [ ] Table `Quick Tasks Completed` de `STATE.md` mise a jour
</success_criteria>

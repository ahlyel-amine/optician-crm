import createClient from "openapi-fetch";
import type { Middleware } from "openapi-fetch";

import { signalerLienRetabli, signalerPanneDeLien } from "@/etats/reseau";

import type { paths } from "./types.gen";

/**
 * Le client d'API de la SPA. Types GENERES, jamais ecrits a la main.
 *
 * `paths` vient de `src/api/types.gen.ts`, produit par `npm run api:types`
 * depuis `src/api/schema.yml` — le contrat commite au plan 03-10. Un client
 * ecrit a la main serait un SECOND contrat, qui derive en silence du premier :
 * exactement le mode de defaillance que PERM-06 combat pour les champs, applique
 * cette fois aux types. La porte de CI est dans `docs/ci-schema.md` : toute
 * modification d'une vue, d'un serialiseur ou d'une route regenere le schema ET
 * ce fichier dans le meme changement.
 */

/**
 * **Aucun prefixe de chemin.** Les cles du schema portent deja `/api/...`
 * (`/api/auth/connexion/`, `/api/comptes/`), parce que drf-spectacular emet les
 * chemins tels que Django les route. Poser `baseUrl: "/api"` produirait
 * `/api/api/auth/connexion/` — un 404 sur chaque appel.
 *
 * Ce qui est pose, c'est **l'origine de la page elle-meme**, et c'est la
 * decision du plan 03-03 : le serveur de developpement proxifie `/api` vers
 * Django, donc le navigateur ne voit qu'une origine. Pas de CORS, pas de
 * prevol, `SameSite=Lax` suffit, et le cookie se comporte en developpement
 * exactement comme en production. L'ecrire plutot que de la laisser implicite
 * n'est pas cosmetique : `new Request()` refuse une URL relative hors d'un
 * document, donc une base vide casse des qu'on sort du navigateur.
 */
const RACINE = typeof window === "undefined" ? "" : window.location.origin;

/** Le nom du cookie pose par `GET /api/auth/csrf/`. */
const COOKIE_CSRF = "csrftoken";

/**
 * `CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"` cote Django, donc `X-CSRFToken` sur le
 * fil. Verifie contre `config/settings/base.py` au plan 03-08.
 */
export const EN_TETE_CSRF = "X-CSRFToken";

const METHODES_MUTANTES = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** 401 : la session est morte. Compare numeriquement, jamais affiche. */
const NON_AUTHENTIFIE = 401;

/**
 * Le seul endroit du code qui sait a quel nombre correspond « non authentifie ».
 *
 * L'amorcage en a besoin — un visiteur anonyme recoit ce statut sur
 * `/api/auth/moi/` et ce n'est pas une erreur — et le faire passer par une
 * fonction evite de semer des litteraux numeriques dans des composants, ou ils
 * finissent tot ou tard par etre affiches.
 */
export function estNonAuthentifie(reponse: Response): boolean {
  return reponse.status === NON_AUTHENTIFIE;
}

/**
 * Lit un cookie non `HttpOnly`.
 *
 * Le cookie `csrftoken` est lisible par le JS **par conception** : le motif
 * double-submit exige que le client le relise pour le renvoyer en en-tete. Ce
 * n'est pas un secret de session — le cookie de SESSION, lui, est `HttpOnly` et
 * reste illisible ici. La distinction est la raison pour laquelle aucun jeton
 * d'authentification n'est stocke cote client dans ce produit (menace T-03-83).
 */
export function lireCookie(nom: string): string | null {
  if (typeof document === "undefined") {
    return null;
  }
  const prefixe = `${nom}=`;
  for (const morceau of document.cookie.split(";")) {
    const candidat = morceau.trim();
    if (candidat.startsWith(prefixe)) {
      return decodeURIComponent(candidat.slice(prefixe.length));
    }
  }
  return null;
}

/**
 * L'echec du lien, remonte au composant appelant.
 *
 * Elle ne porte aucun message : la copie est dans `src/etats/messages.ts` et
 * c'est l'interface qui choisit laquelle afficher. Une exception qui porte sa
 * propre phrase finit par etre affichee telle quelle, et c'est ainsi qu'une
 * trace technique arrive a l'ecran.
 */
export class ServiceInjoignable extends Error {
  constructor() {
    super("service injoignable");
    this.name = "ServiceInjoignable";
  }
}

// --------------------------------------------------------------------------
// CSRF
// --------------------------------------------------------------------------

const intergicielCsrf: Middleware = {
  onRequest({ request }) {
    if (!METHODES_MUTANTES.has(request.method.toUpperCase())) {
      return undefined;
    }
    const jeton = lireCookie(COOKIE_CSRF);
    if (jeton !== null) {
      request.headers.set(EN_TETE_CSRF, jeton);
    }
    return request;
  },
};

// --------------------------------------------------------------------------
// La session, et le 401 global
// --------------------------------------------------------------------------

/**
 * Vrai entre un amorcage reussi et la fermeture de la session.
 *
 * Ce drapeau existe pour une raison precise et facile a manquer : `GET
 * /api/auth/moi/` repond 401 a un visiteur anonyme, ce qui est le cas NORMAL du
 * premier chargement. Sans ce drapeau, une premiere visite afficherait « votre
 * session a expire » a quelqu'un qui n'en a jamais ouvert — un message faux, et
 * inquietant sur un produit qui manipule de l'argent. Le message de session
 * n'appartient qu'a une session qui a REELLEMENT existe.
 */
let sessionOuverte = false;

const ecouteursDeSession = new Set<() => void>();

/** Appele par `AuthProvider` des que l'amorcage a reussi. */
export function declarerSessionOuverte(): void {
  sessionOuverte = true;
}

/** Appele a la deconnexion volontaire — aucun ecouteur n'est notifie. */
export function declarerSessionFermee(): void {
  sessionOuverte = false;
}

export function sessionEstOuverte(): boolean {
  return sessionOuverte;
}

/**
 * S'abonne a l'expiration de session. Rend la fonction de desabonnement.
 *
 * `AuthProvider` est le seul abonne : il vide le contexte, memorise le chemin
 * tente et route vers `/connexion`. Le client d'API ne connait donc ni le
 * routeur ni le contexte — il constate, il ne navigue pas.
 */
export function surSessionExpiree(ecouteur: () => void): () => void {
  ecouteursDeSession.add(ecouteur);
  return () => {
    ecouteursDeSession.delete(ecouteur);
  };
}

/**
 * L'appel a-t-il ete abandonne, plutot qu'echoue ?
 *
 * **Le signal d'abord, le nom de l'exception ensuite.** `request.signal.aborted`
 * est le FAIT — l'annulation a eu lieu, et `openapi-fetch` pose bien le signal
 * sur la `Request` (`new Request(url, requestInit)`), lui-meme fourni par
 * `openapi-react-query`, qui passe celui de react-query dans l'`init`. La forme
 * de l'exception n'en est que le symptome, et elle varie : les navigateurs et
 * `undici` rejettent une `DOMException` nommee `AbortError`, d'autres
 * environnements un `Error` simple portant le meme `name`. `DOMException`
 * heritant d'`Error`, un seul test couvre les deux — et une suite le verifie
 * plutot que de le supposer.
 *
 * Ce qui n'est PAS traite comme un abandon : tout le reste. Un `TypeError:
 * Failed to fetch` reste une coupure, et la banniere se leve des le premier —
 * `clientDeRequetes` porte `retry: false`, donc exiger un second echec avant de
 * parler laisserait l'utilisateur devant une interface active sur un lien mort.
 */
function estUneRequeteAvortee(erreur: unknown, requete: Request): boolean {
  if (requete.signal?.aborted === true) {
    return true;
  }
  return erreur instanceof Error && erreur.name === "AbortError";
}

const intergicielDeSession: Middleware = {
  onResponse({ response }) {
    signalerLienRetabli();
    if (response.status !== NON_AUTHENTIFIE || !sessionOuverte) {
      return undefined;
    }
    sessionOuverte = false;
    for (const ecouteur of [...ecouteursDeSession]) {
      ecouteur();
    }
    return undefined;
  },
  onError({ error, request }) {
    // Deux choses tres differentes arrivent ici, et les confondre a fait
    // clignoter la banniere de coupure a chaque navigation.
    //
    //   - un echec de transport — DNS, socket, TLS — est une mesure du lien
    //     qui ECHOUE : on a demande, rien n'est revenu, le lien est tombe ;
    //   - un abandon est une mesure QUI N'A PAS EU LIEU : nous avons nous-memes
    //     retire la question avant qu'elle n'ait une reponse.
    //
    // Un abandon ne dit donc rien de l'etat du lien, ni dans un sens ni dans
    // l'autre, et il est parfaitement ORDINAIRE : react-query annule une
    // requete des que son dernier observateur se desabonne — c'est-a-dire a
    // chaque changement de route — et le navigateur annule tout au
    // dechargement. Le compter comme une coupure levait la banniere a chaque
    // rechargement, donc desactivait brievement tout controle d'ecriture du
    // produit (`03-UI-SPEC.md` 8.6), et entrainait l'utilisateur a ignorer la
    // seule fois ou elle dit vrai.
    //
    // Un 500, lui, n'est toujours PAS une erreur ici : c'est une reponse, donc
    // une preuve que le lien tient, et il passe par `onResponse`.
    if (estUneRequeteAvortee(error, request)) {
      return undefined;
    }
    signalerPanneDeLien();
    return undefined;
  },
};

// --------------------------------------------------------------------------
// Le client
// --------------------------------------------------------------------------

export const clientApi = createClient<paths>({
  baseUrl: RACINE,
  credentials: "same-origin",
  // `openapi-fetch` capture `globalThis.fetch` UNE fois, a la creation du
  // client. Le reference ici a chaque appel : sinon aucune suite de tests ne
  // peut doubler le reseau sans doubler ce module entier, et un module double
  // est un module qu'on ne teste plus.
  fetch: (requete: Request) => globalThis.fetch(requete),
});

clientApi.use(intergicielCsrf, intergicielDeSession);

/**
 * Pose le cookie CSRF avant le premier POST.
 *
 * Appele au montage de `/connexion` (`03-UI-SPEC.md` 6). **Un echec ici se
 * presente comme l'etat d'erreur reseau**, jamais comme un envoi casse en
 * silence : sans cookie, le POST de connexion repondrait 403 et l'ecran
 * afficherait « identifiants incorrects » a quelqu'un qui a tape les bons.
 *
 * La promesse est memorisee pour qu'un double montage — `StrictMode` en
 * developpement en produit un — n'envoie pas deux requetes.
 */
let poseDuJeton: Promise<void> | null = null;

export function assurerJetonCsrf(): Promise<void> {
  if (lireCookie(COOKIE_CSRF) !== null) {
    return Promise.resolve();
  }
  if (poseDuJeton === null) {
    poseDuJeton = clientApi
      .GET("/api/auth/csrf/")
      .then(({ response }) => {
        if (!response.ok) {
          throw new ServiceInjoignable();
        }
      })
      .catch((cause: unknown) => {
        poseDuJeton = null;
        if (cause instanceof ServiceInjoignable) {
          throw cause;
        }
        throw new ServiceInjoignable();
      });
  }
  return poseDuJeton;
}

/** Remet le client a neuf. Reserve aux suites de tests. */
export function reinitialiserLeClient(): void {
  sessionOuverte = false;
  poseDuJeton = null;
  ecouteursDeSession.clear();
}

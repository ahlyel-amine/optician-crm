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
 * **Pas de prefixe.** Les cles de chemin du schema portent deja `/api/...`
 * (`/api/auth/connexion/`, `/api/comptes/`), parce que drf-spectacular emet les
 * chemins tels que Django les route. Poser `baseUrl: "/api"` produirait
 * `/api/api/auth/connexion/` — un 404 sur chaque appel.
 *
 * L'origine reste implicite, et c'est la decision du plan 03-03 : le serveur de
 * developpement proxifie `/api` vers Django, donc le navigateur ne voit qu'une
 * origine. Pas de CORS, pas de prevol, `SameSite=Lax` suffit, et le cookie se
 * comporte en developpement exactement comme en production.
 */
const RACINE = "";

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
  onError() {
    // `fetch` ne rejette que sur un echec de transport : DNS, socket, TLS,
    // requete avortee. Un 500 n'est PAS une erreur ici, c'est une reponse. Donc
    // arriver dans cette branche veut dire que le lien est tombe.
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

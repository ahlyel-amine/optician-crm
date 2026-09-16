import { QueryClient } from "@tanstack/react-query";
import createQueryClient from "openapi-react-query";

import { clientApi } from "./client";
import type { components } from "./types.gen";

/**
 * L'etat serveur de la SPA : react-query par-dessus le client genere.
 *
 * `openapi-react-query` ne reimplemente rien — il enveloppe `clientApi`, donc
 * les cles de requete sont les chemins du schema et les types des reponses sont
 * ceux de `types.gen.ts`. Une route absente du contrat n'est pas appelable, ce
 * qui est le but.
 */
export const $api = createQueryClient(clientApi);

/**
 * Les reglages par defaut, et pourquoi chacun.
 *
 * `retry: false` : le produit est en ligne uniquement (CLAUDE.md #1) et
 * `03-UI-SPEC.md` 8.6 veut qu'un echec de chargement soit VU, avec un bouton
 * « Réessayer » a portee de main. Trois tentatives silencieuses transforment un
 * echec net en trois secondes d'attente inexpliquee.
 *
 * `refetchOnWindowFocus: false` : au comptoir on bascule entre fenetres en
 * permanence ; recharger a chaque retour ferait clignoter l'ecran sans qu'on
 * l'ait demande.
 *
 * Aucune persistance, aucun `gcTime` allonge : rien de metier ne survit a la
 * fermeture de l'onglet. C'est la meme regle que « pas de stockage local ».
 */
export const clientDeRequetes = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
    mutations: {
      retry: false,
    },
  },
});

// --------------------------------------------------------------------------
// Les formes du contrat, nommees une fois
// --------------------------------------------------------------------------
//
// Des alias, pas des redeclarations : chacun pointe dans `components["schemas"]`
// du fichier genere. Si le serveur change la forme, ces noms changent de type
// sans que personne ne les touche, et le typecheck designe les appelants.

export type Amorcage = components["schemas"]["Amorcage"];
export type Utilisateur = components["schemas"]["Utilisateur"];
export type ClientDeLaffaire = components["schemas"]["Client"];
export type Magasin = components["schemas"]["Magasin"];
export type Catalogue = components["schemas"]["Catalogue"];
export type SectionCatalogue = components["schemas"]["SectionCatalogue"];
export type DroitCatalogue = components["schemas"]["DroitCatalogue"];

/** Les cinq routes d'authentification, nommees pour que personne ne les retape. */
export const ROUTE_CSRF = "/api/auth/csrf/" as const;
export const ROUTE_CONNEXION = "/api/auth/connexion/" as const;
export const ROUTE_DECONNEXION = "/api/auth/deconnexion/" as const;
export const ROUTE_MOI = "/api/auth/moi/" as const;
export const ROUTE_MOT_DE_PASSE = "/api/auth/mot-de-passe/" as const;

/**
 * Le corps d'une reponse d'erreur de DRF, tel que le plan 03-08 l'a fige.
 *
 * `reessayer_dans` n'accompagne que la limitation de debit : le delai part dans
 * un champ separe precisement pour que l'interface n'ait pas a extraire un
 * nombre d'une phrase francaise pour animer son compte a rebours.
 */
export type CorpsDerreur = {
  detail?: string;
  reessayer_dans?: number;
};

export function lireCorpsDerreur(corps: unknown): CorpsDerreur {
  if (typeof corps !== "object" || corps === null) {
    return {};
  }
  const { detail, reessayer_dans: delai } = corps as Record<string, unknown>;
  return {
    detail: typeof detail === "string" ? detail : undefined,
    reessayer_dans: typeof delai === "number" ? delai : undefined,
  };
}

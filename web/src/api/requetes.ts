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

// L'ecran `Comptes et droits` (plan 03-14), premier consommateur metier du
// client genere. Les noms pointent dans `components["schemas"]` : renommer un
// composant cote serveur casse le typecheck ici, ce qui est le but.
export type Compte = components["schemas"]["Compte"];
export type CatalogueOffrable = components["schemas"]["CatalogueOffrable"];
export type LigneDeDroit = components["schemas"]["LigneDeDroit"];
export type ResultatOctroi = components["schemas"]["ResultatOctroi"];

// Les ecrans clients (plans 04-07 a 04-09). Des ALIAS, jamais des
// redeclarations : le composant s'appelle `FicheClient` et non `Client` cote
// serveur parce que `Client` designait deja l'AFFAIRE — la collision est
// resolue au plan 04-03, avec sa raison ecrite au-dessus du serialiseur.
export type FicheClient = components["schemas"]["FicheClient"];
/**
 * Ce qu'un comptoir ENVOIE. **`version` n'y est pas, et c'est la garantie** :
 * le numero est emis par le serveur, sous verrou, dans la transaction
 * d'insertion. Le nommer dans un corps ne l'obtient pas.
 */
export type OrdonnanceASaisir = components["schemas"]["OrdonnanceASaisir"];

/**
 * Par quelle couche un resultat de recherche a ete trouve.
 *
 * **A dire en mots, jamais en chiffres.** Le `score` qui l'accompagne est la
 * pour que l'interface ORDONNE et EXPLIQUE ; « 0,333 » ne veut rien dire pour
 * un opticien, et l'afficher inviterait a comparer deux rangs qu'aucun seuil
 * ne separe (mesure du plan 04-03).
 */
export type RaisonDeCorrespondance = components["schemas"]["RaisonEnum"];

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

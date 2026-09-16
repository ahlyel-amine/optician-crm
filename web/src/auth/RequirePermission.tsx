// LE FILTRE DE PERMISSION DE L'INTERFACE EST UN CONFORT, JAMAIS UNE APPLICATION
// DE LA REGLE.
//
// `03-UI-SPEC.md` 5.3, encadre final, recopie ici mot pour mot parce que c'est
// le fichier ou quelqu'un viendra chercher « comment on cache une chose ». La
// restriction de queryset et la projection cote serveur SONT le controle ; ce
// composant ne fait que rendre l'application d'un gerant visiblement plus
// petite que celle du proprietaire. Aucune tache de plan, d'aucune phase, ne
// peut etre ecrite comme « masquer X dans l'interface » et marquee faite : elle
// doit nommer le queryset ou le serialiseur qui retire la donnee.
//
// Corollaire de rendu, et il est absolu : un code manquant fait DISPARAITRE
// l'element. Pas d'etat grise, pas d'infobulle « vous n'avez pas ce droit »,
// pas de petite serrure dessinee. Un element inerte apprend a l'utilisateur qu'un pouvoir
// existe et qu'il ne l'a pas — c'est une divulgation, et c'est un appel au
// support (menace T-03-85).

import type { ReactNode } from "react";

import { useAuth } from "./AuthProvider";

export type ProprietesRequirePermission = {
  /** Un code du catalogue, par exemple `caisse.voir`. */
  code: string;
  children: ReactNode;
};

/**
 * Rend son enfant si le code est detenu quelque part, et RIEN sinon.
 *
 * « Quelque part » est litteral : `permissions` est calcule cote serveur avec
 * `peut_quelque_part`, donc une entree apparait des que le droit est detenu
 * dans au moins un magasin. Sans cela, un gerant qui tient le stock du seul
 * magasin de Casablanca perdrait l'entree « Stock » des qu'il regarde
 * l'ensemble de l'affaire.
 */
export function RequirePermission({ code, children }: ProprietesRequirePermission) {
  const { permissions } = useAuth();
  if (!permissions.includes(code)) {
    return null;
  }
  return <>{children}</>;
}

// LA GARDE DE ROUTE — LE PENDANT DE `RequirePermission`, ET SON CONTRAIRE
// APPARENT.
//
// `RequirePermission` ne rend RIEN quand le code manque : c'est ce qu'il faut
// pour une entree de navigation ou un bouton, parce qu'un element inerte
// apprend a l'utilisateur qu'un pouvoir existe et qu'il ne l'a pas.
//
// Une ROUTE ne peut pas ne rien rendre. Quelqu'un a tape une adresse, ou suivi
// un lien colle par un collegue, et un ecran vide est une panne. Celle-ci rend
// donc le 403 pleine page de `03-UI-SPEC.md` 8.6, **qui nomme le droit
// manquant** — ce qui est possible precisement parce que le catalogue des
// droits est identique pour toutes les affaires du produit : le nommer ne
// divulgue rien d'un autre client, et cela transforme un appel de support en
// demande en libre service.
//
// Les deux ne se contredisent donc pas : l'element absent dit « ceci n'existe
// pas pour vous », la page 403 dit « cette adresse existe, ce droit vous
// manque, demandez-le a cette personne ». La difference est que l'adresse,
// elle, a deja ete divulguee par celui qui l'a collee.
//
// RAPPEL, absolu : cette garde est un CONFORT. Le serveur repond 403 a la
// requete, quoi que rende cette page ; c'est la restriction de queryset et la
// classe de permission qui sont le controle.

import type { ReactNode } from "react";

import { PageInterdite } from "@/etats/PageInterdite";

import { useAuth } from "./AuthProvider";
import type { Catalogue } from "@/api/requetes";

export type ProprietesRequireDroit = {
  /** Un code du catalogue, par exemple `compte.gerer`. */
  code: string;
  /**
   * Le proprietaire passe meme si le serveur ne lui liste pas le code.
   *
   * Vrai pour la seule surface des comptes, pour la meme raison que
   * `proprietaireToujours` dans `nav.ts` : c'est la porte par laquelle il
   * reprend la main, et se la fermer serait irrattrapable depuis l'interface.
   */
  proprietaireToujours?: true;
  children: ReactNode;
};

/**
 * Le libelle francais d'un code, tel que le SERVEUR le nomme.
 *
 * Jamais derive du code : `compte.gerer` ne devient pas « Gerer compte » par
 * une regle de typographie. Le catalogue est la seule source, ici comme sur
 * l'ecran de droits, et un code ajoute en phase 8 obtient son libelle sans
 * qu'une ligne de la SPA change.
 *
 * Rend `undefined` quand le code est inconnu — la page 403 se rend alors sans
 * sa seconde phrase, ce qui est moins bien qu'un libelle et beaucoup mieux
 * qu'un code de permission affiche a un opticien.
 */
export function libelleDuCode(
  catalogue: Catalogue | null,
  code: string,
): string | undefined {
  for (const section of catalogue?.sections ?? []) {
    const droit = section.droits.find((candidat) => candidat.code === code);
    if (droit) {
      return droit.libelle;
    }
  }
  return undefined;
}

export function RequireDroit({
  code,
  proprietaireToujours,
  children,
}: ProprietesRequireDroit) {
  const { permissions, utilisateur, catalogue } = useAuth();
  const autorise =
    permissions.includes(code) ||
    (proprietaireToujours === true && utilisateur?.est_proprietaire === true);

  if (!autorise) {
    return <PageInterdite libelleDuDroit={libelleDuCode(catalogue, code)} />;
  }
  return <>{children}</>;
}

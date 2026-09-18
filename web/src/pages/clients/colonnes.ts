import { createElement, type ReactNode } from "react";

import { formaterDateCourte, formaterTelephone } from "@/format";
import type { Colonne } from "@/tableau/registre";
import { Valeur } from "@/tableau/Valeur";

/**
 * Le registre des colonnes de la liste des clients — 04-UI-SPEC.md 18.2.
 *
 * **Declaratif pour le libelle, l'ordre et l'alignement ; pilote par la donnee
 * pour la PRESENCE.** C'est la separation posee par `src/tableau/registre.ts`
 * en phase 3, et ce fichier est son premier consommateur de phase 4.
 *
 * ---
 *
 * **Pourquoi `createElement` et non du JSX.** Ce module est une DONNEE : quatre
 * descriptions de colonnes. Le garder en `.ts` dit qu'il ne rend pas d'ecran et
 * qu'on ne viendra pas y ajouter de la mise en page. Les trois rendus
 * ci-dessous existent parce que le formateur du produit leve sur `null`, ce que
 * le format declaratif du tableau ne sait pas absorber.
 *
 * ---
 *
 * **Il n'y a PAS de colonne `derniere_visite`**, et son absence est une
 * decision datee du 2026-09-18 plutot qu'un oubli. `colonnesVisiblesSurLignes`
 * filtre sur `champ in ligne`, et le registre distingue deliberement la cle
 * ABSENTE — « vous n'avez pas le droit de voir ceci » — de la valeur `null` —
 * « la donnee est inconnue ». Pour afficher « Jamais », le champ devrait donc
 * etre PRESENT et nul. Or une visite suppose une vente, qui est la phase 6 :
 * aucun plan de la phase 4 n'ajoute ce champ, donc la colonne aurait ete
 * filtree a chaque rendu, en silence et sans aucun test pour le dire. Elle
 * revient avec le champ qui la porte.
 *
 * **Il n'y a pas non plus de colonne `Actions`, ni de menu de ligne.** Tout est
 * sur la fiche, a un clic.
 */

/** Une date, ou rien. Le formateur leve sur `null` ; la cellule, elle, se tait. */
function rendreUneDate(valeur: unknown): ReactNode {
  if (valeur === null || valeur === undefined || valeur === "") {
    return null;
  }
  return createElement(
    "span",
    { className: "tabular-nums" },
    formaterDateCourte(valeur as string),
  );
}

/**
 * Le telephone, par le formateur partage et jamais par une interpolation.
 *
 * `tabular-nums` pour que les chiffres s'alignent d'une ligne a l'autre, et
 * `Valeur` parce qu'un numero que le formateur ne reconnait pas est rendu
 * VERBATIM — c'est alors de la saisie utilisateur, qui a besoin de sa frontiere
 * d'isolation bidirectionnelle comme le reste.
 */
function rendreUnTelephone(valeur: unknown): ReactNode {
  if (valeur === null || valeur === undefined || valeur === "") {
    return null;
  }
  return createElement(
    "span",
    { className: "tabular-nums" },
    createElement(Valeur, null, formaterTelephone(valeur as string)),
  );
}

export const COLONNES_CLIENTS: readonly Colonne[] = [
  // `nom` n'a pas de rendu sur mesure : le tableau enveloppe deja toute valeur
  // utilisateur dans un `Valeur`, donc un nom en arabe s'affiche correctement
  // sans que cette ligne ait a le prevoir.
  { champ: "nom", libelle: "Nom", align: "left" },
  { champ: "telephone", libelle: "Téléphone", align: "left", rendu: rendreUnTelephone },
  {
    champ: "date_naissance",
    libelle: "Date de naissance",
    align: "left",
    rendu: rendreUneDate,
  },
  /*
    LE PREMIER CHAMP PROTEGE DU PRODUIT COTE CLIENT, et la seule chose a faire
    ici est... RIEN.

    Le serveur retire la cle de la charge utile quand `ordonnance.voir` manque
    (04-UI-SPEC.md 15.5). `colonnesVisiblesSurLignes` filtre sur `champ in
    ligne`, et la colonne disparait alors entierement : sans en-tete, sans
    tiret, sans cadenas, sans infobulle. Chacun de ces substituts revelerait
    l'existence et la position du champ, ce qui est une divulgation plus
    discrete mais pas plus benigne.

    C'est ici que quelqu'un aura envie d'ecrire une branche cliente. Il n'y en a
    pas, il n'y en aura pas, et une garde de CI le verifie sur tout ce dossier.
  */
  {
    champ: "derniere_ordonnance",
    libelle: "Dernière ordonnance",
    align: "left",
    rendu: rendreUneDate,
  },
];

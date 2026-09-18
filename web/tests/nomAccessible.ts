import { computeAccessibleName } from "dom-accessibility-api";
import { expect } from "vitest";

/**
 * La MESURE du nom accessible, partagee par toute la phase 4.
 *
 * Ce fichier n'est pas une suite : c'est un utilitaire importe par les ecrans
 * des plans 04-07, 04-08 et 04-09. Il n'existe que pour transformer une
 * relecture en assertion.
 *
 * **Sa raison d'etre est deja consignee.** `03.1/deferred-items.md` D-1 : le
 * selecteur de magasin du shell n'a AUCUN nom accessible, parce que
 * `combobox` est un role dont le nom vient de l'auteur — sa prose visible ne
 * devient jamais son nom. Trente-deux tests verts ne l'ont pas vu, parce
 * qu'aucun ne mesurait.
 *
 * **Cette phase ne corrige pas D-1** — ce n'est pas son fichier. Elle pose la
 * mesure qui rendra le correctif trivial (04-UI-SPEC.md 15.2, 25.2, 28-Q6), et
 * elle s'interdit d'introduire un seul nouveau role de ce genre sans nom.
 *
 * `dom-accessibility-api` est declare en `devDependencies` a la version deja
 * installee dans l'arbre. Il y etait par hissage transitif, tire par
 * `@testing-library/dom` ; s'en servir sans le declarer casserait au premier
 * `npm install` qui reorganise l'arbre.
 */

/** Le nom accessible calcule d'un element, espaces de bord retires. */
export function nomAccessible(element: Element): string {
  return computeAccessibleName(element).trim();
}

/**
 * Affirme que l'element PORTE un nom accessible, et le nom attendu s'il est
 * fourni.
 *
 * Le message d'echec nomme le piege plutot que de dire « attendu non vide » :
 * c'est exactement l'information qui manquait a la revue qui a laisse passer
 * D-1.
 */
export function attendUnNomAccessible(element: Element, attendu?: string): void {
  const nom = nomAccessible(element);

  expect(
    nom,
    `l'element <${element.tagName.toLowerCase()} role="${element.getAttribute("role") ?? ""}"> ` +
      "n'a aucun nom accessible : son texte visible ne devient pas son nom, " +
      "il lui faut une etiquette designee par l'auteur",
  ).not.toBe("");

  if (attendu !== undefined) {
    expect(nom).toBe(attendu);
  }
}

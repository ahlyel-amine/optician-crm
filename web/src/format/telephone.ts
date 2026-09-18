/**
 * Le TROISIEME format du produit, apres le montant et la date.
 *
 * Il vit ici, avec `montant.ts` et `date.ts`, non parce que formater un numero
 * serait difficile — cela tient en quinze lignes — mais parce que
 * `${client.telephone}` ecrit en ligne dans trois composants est EXACTEMENT la
 * divergence que la fixture monetaire existe pour empecher
 * (04-UI-SPEC.md 18.3, 03-UI-SPEC.md 8.1). Le jour ou la liste affiche
 * `0612345678` et la fiche `06 12 34 56 78`, le coupable est un composant qui a
 * formate sur place.
 *
 * `Intl` n'intervient pas, et AUCUNE etiquette de locale non plus. L'exemption
 * de `npm run audit:format` couvre deja `src/format/`, donc elle ne s'elargit
 * pas d'une ligne : ce module se contente de decouper des chiffres.
 *
 * L'espace entre les paires est un U+00A0, pour la meme raison que celui des
 * milliers : un espace ordinaire laisse la ligne se couper au milieu d'une
 * paire, et un numero coupe est un numero qu'on recopie faux.
 *
 * **Trois formes, et rien d'autre.** Ce qui n'est pas reconnu est rendu
 * VERBATIM : jamais de refus a l'affichage, jamais d'exception. Une fiche
 * importee d'un tableur porte n'importe quoi, et un formateur qui leverait
 * mettrait la liste entiere en erreur pour une seule fiche mal saisie.
 */

/** Separateur entre deux paires de chiffres : U+00A0, espace insecable. */
export const SEPARATEUR_PAIRES = "\u00a0";

/** Dix chiffres commencant par zero : la forme nationale marocaine. */
const NATIONAL = /^0\d{9}$/;
/** Douze chiffres commencant par l'indicatif : la forme internationale. */
const INTERNATIONAL = /^212(\d)(\d{8})$/;

const parPaires = (chiffres: string): string =>
  (chiffres.match(/\d{2}/g) ?? []).join(SEPARATEUR_PAIRES);

/**
 * Rend `06 12 34 56 78` ou `+212 6 12 34 56 78`, avec des espaces insecables.
 *
 * Tout le reste — un numero fixe mal saisi, une note glissee dans le champ, une
 * chaine vide — ressort tel quel, a rendre dans un `<bdi>` comme toute valeur
 * fournie par l'utilisateur (03-UI-SPEC.md 8.5).
 */
export function formaterTelephone(valeur: string): string {
  if (NATIONAL.test(valeur)) {
    return parPaires(valeur);
  }

  const international = INTERNATIONAL.exec(valeur);
  if (international) {
    const [, isole, suite] = international;
    return `+212${SEPARATEUR_PAIRES}${isole}${SEPARATEUR_PAIRES}${parPaires(suite)}`;
  }

  return valeur;
}

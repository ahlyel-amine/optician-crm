import type { ReactNode } from "react";

/**
 * `Valeur` — toute valeur fournie par l'utilisateur, isolee bidirectionnellement.
 *
 * 03-UI-SPEC.md 8.5. L'interface est en francais et `dir="ltr"` sur `<html>` est
 * permanent : il n'y a pas d'interface arabe, et BRAND-04 concerne du CONTENU
 * arabe dans des documents imprimes, pas une INTERFACE arabe. Mais les noms, les
 * adresses et les enseignes en arabe doivent s'y afficher correctement.
 *
 * Le probleme n'est pas la police, c'est l'algorithme bidirectionnel d'Unicode.
 * Un nom arabe voisin de ponctuation ou de chiffres dans une cellule fait migrer
 * les caracteres neutres qui l'entourent — la parenthese se retrouve du mauvais
 * cote, le numero passe avant le nom — et la ligne SE LIT FAUX sans qu'aucun
 * caractere n'ait change. `<bdi>` pose une frontiere d'isolation : le contenu se
 * reordonne a l'interieur et n'affecte plus rien au-dehors.
 *
 * Ce composant coute une balise et regle le probleme une fois pour neuf phases.
 * La regle qui va avec : TOUTE valeur venue de l'utilisateur passe par ici — nom,
 * prenom, raison sociale, adresse, texte libre, reference saisie a la main. Un
 * montant ou une date, eux, sont produits par `src/format/` et n'en ont pas
 * besoin.
 *
 * ---
 *
 * L'EXIGENCE JUMELLE, COTE SAISIE (03-UI-SPEC.md 5.5), consignee ici parce que
 * c'est la meme exigence vue de l'autre bout et qu'elle sera lue en phase 4 :
 *
 * la recherche envoie la requete BRUTE et ne filtre JAMAIS cote client. Pas de
 * retrait de caracteres, pas de normalisation Unicode, pas de translitteration,
 * pas de longueur minimale au-dela de deux caracteres. Une saisie arabe passee a
 * la moulinette d'un `normalize()` ou d'un `replace(/[^a-z]/g, "")` cote client
 * ne trouve plus son propre client. La normalisation est cote serveur, y compris
 * la tolerance aux variantes de translitteration (`Mohamed`, `Mohammed`,
 * `Mhamed`), qui est l'affaire de CLIENT-10 en phase 4.
 */
export type ProprietesValeur = {
  children: ReactNode;
  /**
   * Etiquette de langue de la VALEUR, quand elle est connue — `"ar"` pour un nom
   * saisi en arabe. Elle sert la synthese vocale et le choix de fonte, pas
   * l'alignement : voir ci-dessous.
   */
  langue?: string;
};

/**
 * Enveloppe une valeur fournie par l'utilisateur dans un `<bdi>`.
 *
 * Aucun `dir` n'est pose ici, et c'est deliberé : `<bdi>` vaut deja
 * `dir="auto"` isole, donc le sens d'ecriture est deduit du contenu A
 * L'INTERIEUR de la frontiere. L'ALIGNEMENT de la colonne, lui, reste celui du
 * registre — une colonne de noms reste alignee a gauche meme si le nom est
 * arabe, sinon le tableau cesse d'etre une grille et l'oeil ne peut plus
 * balayer la colonne.
 */
export function Valeur({ children, langue }: ProprietesValeur) {
  return <bdi lang={langue}>{children}</bdi>;
}

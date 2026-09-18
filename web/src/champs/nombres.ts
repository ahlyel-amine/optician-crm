/**
 * La saisie numerique clinique, en fonctions PURES et sans un seul chiffre.
 *
 * Trois regles portent ce module, et chacune a coute quelque chose a
 * quelqu'un.
 *
 * **1. Aucune borne, aucun pas n'est ecrit ici.** Q1 et D-4b : les bornes
 * vivent a UN endroit nomme, et le serveur les sert (plan 04-04). Une constante
 * TypeScript en serait un second endroit, les deux derivent, et le proprietaire
 * a deja change ces chiffres une fois. Tout ce qui ressemble a une valeur
 * clinique arrive donc en ARGUMENT, y compris dans les messages : le gabarit de
 * refus recoit les bornes recues et n'en ecrit aucune.
 *
 * **2. Rien n'est jamais arrondi en silence.** Une valeur hors de la grille du
 * pas est REFUSEE, telle qu'elle a ete tapee. Un arrondi silencieux est un
 * nombre faux sans message d'erreur, ce que la couche ORM refuse deja un etage
 * plus bas. Pour la meme raison, une saisie plus precise que le champ est
 * refusee et non tronquee.
 *
 * **3. L'arithmetique est ENTIERE, jamais flottante.** `0.1 + 0.2 !== 0.3`
 * produirait un refus sur une valeur correcte. Les comparaisons passent par
 * `BigInt` sur les chiffres mis a la meme echelle, comme l'arrondi de
 * `format/montant.ts` travaille sur les chiffres de la chaine.
 *
 * Le signe negatif affiche est U+2212 et non le trait d'union : a 14px, a cote
 * d'un `+`, un trait d'union est ambigu sur une grille dense.
 */

import { SEPARATEUR_DECIMAL } from "@/format";

/** Le vrai signe moins, U+2212. Jamais U+002D a l'affichage. */
export const SIGNE_MOINS = "\u2212";
/** Le signe plus, rendu explicitement partout ou le signe est porteur. */
export const SIGNE_PLUS = "+";

/**
 * Comment le signe se comporte sur un champ donne (04-UI-SPEC.md 20.4).
 *
 * - `requis` : il doit etre TAPE. C'est le cas de la sphere, ou les deux signes
 *   designent des verres opposes ;
 * - `fourni-negatif` : il est pose par le champ, et un signe contraire est
 *   refuse plutot que retourne en silence ;
 * - `fourni-positif` : idem, dans l'autre sens ;
 * - `aucun` : le champ ne porte pas de signe.
 */
export type SigneAttendu = "requis" | "fourni-positif" | "fourni-negatif" | "aucun";

/** Les regles de forme d'un champ. Le nombre de decimales vient de l'appelant. */
export type ReglesNombre = {
  decimales: 0 | 1 | 2;
  /** Defaut : `aucun`. */
  signe?: SigneAttendu;
};

/** L'objet servi par le serveur pour un champ. Aucune valeur par defaut ici. */
export type Bornes = { min: string; max: string; pas: string };

/** Ce dont la verification de bornes a besoin, et rien de plus. */
export type BornesMinMax = Pick<Bornes, "min" | "max">;

/* ---------------------------------------------------------------------------
 * Les refus, en constantes nommees A COTE du module.
 *
 * Ils ne vont PAS dans `src/etats/messages.ts`, qui ne porte que les cinq etats
 * globaux herites de la phase 3. Les chaines sont celles de
 * `04-UI-SPEC.md` 23, au caractere pres — chaque refus nomme la correction,
 * jamais la regle.
 * ------------------------------------------------------------------------- */

/** Le seul champ ou le signe doit etre tape : les deux designent des verres opposes. */
export const REFUS_SIGNE_MANQUANT = `Indiquez le signe : ${SIGNE_PLUS}2,00 ou ${SIGNE_MOINS}2,00.`;

/** La convention est enoncee la ou elle est enfreinte. */
export const REFUS_CYLINDRE_POSITIF =
  "En cylindre négatif, le cylindre ne peut pas être positif. " +
  "Basculez la notation ci-dessus si l'ordonnance est en cylindre positif.";

/** Le sujet du refus de bornes quand l'appelant n'en fournit pas. */
export const SUJET_GENERIQUE = "Cette valeur";

/** `Les valeurs vont par pas de X.` — le pas vient de l'objet servi. */
export const messagePas = (pasRendu: string): string =>
  `Les valeurs vont par pas de ${pasRendu}.`;

/** `La sphère va de A à B.` — le sujet et les deux bornes viennent de l'appelant. */
export const messageBornes = (sujet: string, minRendu: string, maxRendu: string): string =>
  `${sujet} va de ${minRendu} à ${maxRendu}.`;

/**
 * Rend une borne de transport (`-9.50`) dans la forme francaise (`−9,50`).
 *
 * Volontairement mecanique : c'est un affichage de borne, pas une
 * normalisation de saisie. L'ecran qui veut une forme particuliere — une borne
 * nulle rendue nue, par exemple — passe son propre rendu.
 */
export const rendreBorne = (borne: string): string =>
  borne.replace("-", SIGNE_MOINS).replace(".", SEPARATEUR_DECIMAL);

/** De quoi rediger le refus de bornes sans qu'un chiffre soit ecrit ici. */
export type PresentationBornes = { sujet: string; rendre: (borne: string) => string };

const PRESENTATION_PAR_DEFAUT: PresentationBornes = {
  sujet: SUJET_GENERIQUE,
  rendre: rendreBorne,
};

/* ---------------------------------------------------------------------------
 * L'arithmetique, entiere.
 * ------------------------------------------------------------------------- */

type Piece = {
  negatif: boolean;
  /** Vrai si l'utilisateur a TAPE un signe, quel qu'il soit. */
  signeExplicite: boolean;
  entier: string;
  fraction: string;
};

/** Un signe optionnel, des chiffres, et un separateur decimal au choix. */
const SAISIE = /^([+\-\u2212]?)(\d*)(?:[.,](\d*))?$/;

const decomposer = (saisi: string): Piece | null => {
  const brut = saisi.replace(/[\s\u00a0]/g, "");
  const morceaux = SAISIE.exec(brut);
  if (!morceaux) {
    return null;
  }

  const [, signe, entier, fraction = ""] = morceaux;
  if (entier === "" && fraction === "") {
    return null;
  }

  return {
    negatif: signe === "-" || signe === SIGNE_MOINS,
    signeExplicite: signe !== "",
    entier: entier === "" ? "0" : entier,
    fraction,
  };
};

/** Met deux pieces a la meme echelle et les compare en entiers. */
const comparer = (gauche: Piece, droite: Piece): number => {
  const echelle = Math.max(gauche.fraction.length, droite.fraction.length);
  const entier = (piece: Piece): bigint => {
    const chiffres = BigInt(`${piece.entier}${piece.fraction.padEnd(echelle, "0")}`);
    return piece.negatif ? -chiffres : chiffres;
  };
  const a = entier(gauche);
  const b = entier(droite);
  return a < b ? -1 : a > b ? 1 : 0;
};

/* ---------------------------------------------------------------------------
 * Les trois fonctions publiques.
 * ------------------------------------------------------------------------- */

/**
 * Rend la forme d'affichage d'une saisie, ou `null` si elle est irrecevable.
 *
 * La virgule et le point sont acceptes indifferemment : le pave numerique du
 * comptoir emet un point et l'opticien ecrit une virgule. Un champ vide reste
 * vide et ne devient JAMAIS zero — `0,00` et « non mesure » sont deux faits
 * differents, et le serveur stocke `null` pour le second.
 *
 * Elle ne consulte ni borne ni pas : ce sont deux verdicts separes, rendus par
 * les deux fonctions suivantes a partir de l'objet servi.
 */
export function normaliserNombre(saisi: string, regles: ReglesNombre): string | null {
  const piece = decomposer(saisi);
  if (!piece) {
    return null;
  }

  // Plus precis que le champ : refuse, jamais tronque.
  if (piece.fraction.length > regles.decimales) {
    return null;
  }

  const signe = regles.signe ?? "aucun";
  if (signe === "requis" && !piece.signeExplicite) {
    return null;
  }
  // Un signe contraire a la convention est refuse, jamais retourne en silence.
  if (signe === "fourni-negatif" && piece.signeExplicite && !piece.negatif) {
    return null;
  }
  if (signe === "fourni-positif" && piece.signeExplicite && piece.negatif) {
    return null;
  }
  if (signe === "aucun" && piece.negatif) {
    return null;
  }

  const entier = piece.entier.replace(/^0+(?=\d)/, "");
  const fraction = piece.fraction.padEnd(regles.decimales, "0");
  const estZero = /^0*$/.test(entier) && /^0*$/.test(fraction);

  const negatif =
    signe === "fourni-negatif" ? true : signe === "fourni-positif" ? false : piece.negatif;

  let prefixe = "";
  if (!estZero) {
    if (negatif) {
      prefixe = SIGNE_MOINS;
    } else if (signe === "requis" || signe === "fourni-positif") {
      prefixe = SIGNE_PLUS;
    }
  }

  const corps =
    regles.decimales === 0 ? entier : `${entier}${SEPARATEUR_DECIMAL}${fraction}`;
  return `${prefixe}${corps}`;
}

/**
 * Le refus de signe qui correspond a la saisie, ou `null`.
 *
 * `normaliserNombre` rend `null` pour plusieurs raisons ; celle-ci dit
 * laquelle, pour que l'ecran n'ait pas a la rededuire — et pour que la phrase
 * de 04-UI-SPEC.md 23 soit ecrite une seule fois dans le produit.
 */
export function fauteDeSigne(saisi: string, regles: ReglesNombre): string | null {
  const piece = decomposer(saisi);
  if (!piece) {
    return null;
  }
  if ((regles.signe ?? "aucun") === "requis" && !piece.signeExplicite) {
    return REFUS_SIGNE_MANQUANT;
  }
  if (regles.signe === "fourni-negatif" && piece.signeExplicite && !piece.negatif) {
    return REFUS_CYLINDRE_POSITIF;
  }
  return null;
}

/**
 * Rend le refus de bornes, ou `null`. Les bornes viennent de l'objet SERVI.
 *
 * Ce controle est une commodite qui evite un aller-retour au comptoir. Le
 * serveur refuse independamment : aucune tache de plan ne peut lire
 * « valider X dans l'interface » et se croire quitte.
 */
export function verifierBornes(
  valeur: string,
  bornes: BornesMinMax,
  presentation: PresentationBornes = PRESENTATION_PAR_DEFAUT,
): string | null {
  const piece = decomposer(valeur);
  const min = decomposer(bornes.min);
  const max = decomposer(bornes.max);
  if (!piece || !min || !max) {
    return null;
  }

  if (comparer(piece, min) < 0 || comparer(piece, max) > 0) {
    return messageBornes(
      presentation.sujet,
      presentation.rendre(bornes.min),
      presentation.rendre(bornes.max),
    );
  }
  return null;
}

/**
 * Rend le refus de pas, ou `null`. Le pas vient de l'objet SERVI.
 *
 * Il REFUSE et ne modifie rien. C'est la moitie qui compte : une
 * implementation qui ramenerait la valeur sur la grille rendrait un nombre faux
 * sans erreur, et l'ordonnance porterait une correction que personne n'a
 * prescrite.
 */
export function verifierPas(
  valeur: string,
  pas: string,
  rendre: (borne: string) => string = rendreBorne,
): string | null {
  const piece = decomposer(valeur);
  const grille = decomposer(pas);
  if (!piece || !grille) {
    return null;
  }

  const echelle = Math.max(piece.fraction.length, grille.fraction.length);
  const enEntier = (morceau: Piece): bigint =>
    BigInt(`${morceau.entier}${morceau.fraction.padEnd(echelle, "0")}`);

  const denominateur = enEntier(grille);
  if (denominateur === 0n) {
    return null;
  }

  return enEntier(piece) % denominateur === 0n ? null : messagePas(rendre(pas));
}

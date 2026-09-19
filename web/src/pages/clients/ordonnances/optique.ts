/**
 * L'arithmetique clinique cote client : transposer, canonicaliser un axe, et
 * les deux helpers decimaux dont la verification a besoin.
 *
 * ---
 *
 * **Le serveur possede la MEME fonction et c'est lui qui fait foi.**
 * `domaine/ordonnances/optique.py` (plan 04-04) transpose a l'enregistrement et
 * refuse tout ce qui n'est pas du cylindre negatif. Cette copie n'existe que
 * pour un **affichage immediat pendant la frappe** : basculer la notation doit
 * transposer les valeurs deja tapees SUR PLACE et VISIBLEMENT, sans
 * aller-retour, sinon l'opticien transpose de tete — et une transposition
 * mentale passe toutes les bornes (20.3).
 *
 * **Consequence, et c'est la ligne qui compte : ce qui part au serveur est
 * TOUJOURS du cylindre negatif**, quelle que soit la bascule, et il n'existe
 * aucune seconde representation rangee quelque part. Une seconde colonne serait
 * une seconde source de verite, et les deux divergeraient le jour ou une
 * correction n'en met a jour qu'une.
 *
 * **Deux implementations de la meme formule doivent etre eprouvees par la meme
 * table de cas.** `tests/ordonnance-saisie.test.tsx` reprend les cas de
 * `tests/test_optique.py`, deliberement. Deux tables divergent, et personne ne
 * le sait avant la premiere paire de verres fausse.
 *
 * ---
 *
 * **Aucun chiffre clinique n'est ecrit ici, y compris le tour de l'axe.** La
 * periode de l'axe est la borne haute SERVIE (`bornes.axe.max`), passee en
 * argument. Le jumeau serveur peut se permettre une constante nommee : il est
 * le proprietaire de la valeur. Le client ne l'est pas, et `audit:clinique`
 * fait rougir la CI pour cette raison exacte.
 *
 * **L'arithmetique est ENTIERE, jamais flottante.** `0.1 + 0.2 !== 0.3`
 * produirait une transposition hors de la grille du pas, donc un refus sur un
 * champ correctement rempli. Meme regle que CLAUDE.md #7 pour l'argent,
 * appliquee a une valeur qui decide d'une paire de verres.
 */

import { SEPARATEUR_DECIMAL } from "@/format";
import { SIGNE_MOINS, SIGNE_PLUS } from "@/champs/nombres";

/** La borne d'un champ entier, telle que l'amorcage la sert. L'axe, en degres. */
export type BorneAxe = { min: number; max: number; pas: number };

/** Une correction d'un oeil, dans la forme d'AFFICHAGE : `+2,00`, `−1,00`, `90`. */
export type Correction = { sphere: string; cylindre: string; axe: string };

/** L'echelle entiere commune : le millieme. Aucune valeur clinique n'a trois decimales. */
const ECHELLE = 3;

const CHIFFRES = /^([+\-−]?)(\d*)(?:[.,](\d*))?$/;

/**
 * Rend une saisie decimale en milliemes entiers, ou `null` si elle n'en est
 * pas une. La virgule et le point sont acceptes, comme le signe moins typographique.
 */
export function enMilliemes(valeur: string): bigint | null {
  const morceaux = CHIFFRES.exec(valeur.replace(/[\s ]/g, ""));
  if (!morceaux) {
    return null;
  }
  const [, signe, entier, fraction = ""] = morceaux;
  if (entier === "" && fraction === "") {
    return null;
  }
  if (fraction.length > ECHELLE) {
    return null;
  }
  const brut = BigInt(`${entier === "" ? "0" : entier}${fraction.padEnd(ECHELLE, "0")}`);
  return signe === "-" || signe === SIGNE_MOINS ? -brut : brut;
}

/**
 * L'inverse : des milliemes vers la forme francaise affichee.
 *
 * `avecSigne` rend le `+` explicite — la sphere, le cylindre transpose et
 * l'addition le portent toujours, un ecart pupillaire jamais.
 */
export function rendreMilliemes(
  milliemes: bigint,
  decimales: 0 | 1 | 2,
  avecSigne = false,
): string {
  const negatif = milliemes < 0n;
  const absolu = negatif ? -milliemes : milliemes;
  const diviseur = 10n ** BigInt(ECHELLE);
  const entier = (absolu / diviseur).toString();
  const fraction = (absolu % diviseur).toString().padStart(ECHELLE, "0").slice(0, decimales);

  let prefixe = "";
  if (negatif) {
    prefixe = SIGNE_MOINS;
  } else if (avecSigne && absolu !== 0n) {
    prefixe = SIGNE_PLUS;
  }

  return decimales === 0
    ? `${prefixe}${entier}`
    : `${prefixe}${entier}${SEPARATEUR_DECIMAL}${fraction}`;
}

/**
 * 0 et le tour complet sont le MEME meridien. **On rend le tour, jamais 0.**
 *
 * CLIENT-07 ecrit la plage en partant de zero, donc zero est ACCEPTE a la
 * saisie ; mais admettre les deux encodages rendrait deux ordonnances portant
 * le meme meridien incomparables. La periode vient de la borne servie : ce
 * module n'en connait pas la valeur, et `audit:clinique` s'assure qu'il ne
 * l'apprend pas — pas meme dans un commentaire.
 */
export function canonicaliserAxe(axe: number, borne: BorneAxe): number {
  const tour = borne.max;
  const reste = ((axe % tour) + tour) % tour;
  return reste === 0 ? tour : reste;
}

/**
 * La transposition de 04-RESEARCH.md 6.1 :
 * `sphere' = sphere + cylindre`, `cylindre' = −cylindre`,
 * `axe' = axe + un quart de tour`, canonicalise.
 *
 * Le quart de tour est la MOITIE de la periode servie — pas un second chiffre
 * ecrit ici, mais la geometrie de la periode elle-meme.
 *
 * Sans cylindre il n'y a rien a transposer : la saisie revient intacte.
 */
export function transposer(valeur: Correction, borne: BorneAxe): Correction {
  const sphere = enMilliemes(valeur.sphere);
  const cylindre = enMilliemes(valeur.cylindre);
  if (sphere === null || cylindre === null || cylindre === 0n) {
    return valeur;
  }

  const axe = Number.parseInt(valeur.axe, 10);
  const axeTranspose = Number.isNaN(axe)
    ? valeur.axe
    : String(canonicaliserAxe(axe + borne.max / 2, borne));

  return {
    sphere: rendreMilliemes(sphere + cylindre, 2, true),
    cylindre: rendreMilliemes(-cylindre, 2, true),
    axe: axeTranspose,
  };
}

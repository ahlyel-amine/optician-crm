/**
 * Le formateur de monnaie du client, ecrit a la main.
 *
 * CLAUDE.md #14 et 03-UI-SPEC.md 8.1 : l'argent rend `1 800,00 MAD`, avec un
 * U+00A0 entre les groupes de milliers ET avant le sigle, une virgule decimale
 * et toujours deux decimales.
 *
 * `Intl.NumberFormat` et `toLocaleString` sont INTERDITS ici, et l'interdiction
 * est verifiee par `tests/format.test.ts` puis par `npm run audit:format`. La
 * raison n'est pas le gout : leur sortie depend de la version d'ICU du
 * navigateur, que personne ne controle, et les trois sources plausibles sont en
 * desaccord — Django `fr` rend U+00A0, l'ICU `fr-FR` rend U+202F, et
 * l'etiquette marocaine rend un point. Chercher une locale EST le bogue. La
 * facture PDF (WeasyPrint, phase 9) et l'ecran doivent rendre le meme
 * caractere, donc le format est epingle depuis `tests/fixtures/formats_mad.json`
 * — une seule specification, deux implementations testees contre elle.
 *
 * AUCUNE ARITHMETIQUE MONETAIRE N'EXISTE DANS LA SPA, et ce n'est pas une regle
 * de lint mais une regle de conception d'API : chaque total affiche est un champ
 * fourni par le serveur, calcule en `Decimal` cote Python (CLAUDE.md #7). Le
 * client n'a donc jamais besoin d'additionner deux montants, et ne le peut donc
 * jamais. Ce module n'expose ni somme, ni produit, ni conversion.
 *
 * Le transport est une CHAINE (`COERCE_DECIMAL_TO_STRING` est vrai cote DRF).
 * L'arrondi ci-dessous travaille sur les chiffres de cette chaine et ne passe
 * jamais par un flottant binaire : `999.995` vaut 999.99499999999997 en double,
 * donc un `Math.round(valeur * 100)` rendrait `999,99` la ou la fixture — et le
 * `ROUND_HALF_UP` du serveur — exigent `1 000,00`.
 */

/** Separateur de groupes de milliers : U+00A0, espace insecable. */
export const SEPARATEUR_MILLIERS = "\u00a0";
/** Separateur decimal. */
export const SEPARATEUR_DECIMAL = ",";
/** Separateur entre le nombre et le sigle : U+00A0, pour que la ligne ne coupe jamais. */
export const SEPARATEUR_AVANT_DEVISE = "\u00a0";
/** Nombre de decimales, toujours affichees, y compris `,00`. */
export const DECIMALES = 2;
/** Sigle monetaire. */
export const DEVISE = "MAD";

/** Un montant tel que l'API le livre : une chaine. Un `number` n'est tolere que pour les litteraux. */
export type MontantBrut = string | number;

const DECIMAL_BRUT = /^([+-]?)(\d+)(?:\.(\d*))?$/;

/** Ajoute 1 a une chaine de chiffres, sans jamais passer par un nombre. */
const incrementer = (chiffres: string): string => {
  const digits = [...chiffres];
  let i = digits.length - 1;
  while (i >= 0) {
    if (digits[i] === "9") {
      digits[i] = "0";
      i -= 1;
    } else {
      digits[i] = String(Number(digits[i]) + 1);
      return digits.join("");
    }
  }
  return `1${digits.join("")}`;
};

/** Groupe les milliers par trois, de droite a gauche, avec l'espace insecable. */
const grouperMilliers = (entier: string): string =>
  entier.replace(/\B(?=(\d{3})+(?!\d))/g, SEPARATEUR_MILLIERS);

/**
 * `ROUND_HALF_UP` sur les chiffres de la chaine, comme `Decimal.quantize` cote
 * serveur. Rend le couple (partie entiere, partie decimale sur `DECIMALES`).
 */
const arrondirDemiSuperieur = (entier: string, fraction: string): [string, string] => {
  const complete = fraction.padEnd(DECIMALES + 1, "0");
  const conserve = `${entier}${complete.slice(0, DECIMALES)}`;
  const premierRejete = complete[DECIMALES];
  const arrondi = premierRejete >= "5" ? incrementer(conserve) : conserve;
  const rembourre = arrondi.padStart(DECIMALES + 1, "0");
  const coupe = rembourre.length - DECIMALES;
  return [rembourre.slice(0, coupe), rembourre.slice(coupe)];
};

/**
 * Rend un montant MAD : `1 800,00 MAD`.
 *
 * Le negatif porte un `-` en tete. La couleur destructive du rendu vient EN PLUS
 * du signe, jamais a sa place (03-UI-SPEC.md 8.1) : une ligne lue en noir et
 * blanc, ou par un daltonien, doit rester juste.
 */
export function formaterMontant(valeur: MontantBrut): string {
  const brut = String(valeur).trim();
  const correspondance = DECIMAL_BRUT.exec(brut);
  if (!correspondance) {
    throw new TypeError(
      `formaterMontant attend un decimal en chaine tel que l'API le livre, recu ${JSON.stringify(brut)}`,
    );
  }

  const [, signe, entierBrut, fractionBrute = ""] = correspondance;
  const [entier, fraction] = arrondirDemiSuperieur(entierBrut, fractionBrute);

  // `-0,001` arrondi a deux decimales vaut zero : un `-0,00 MAD` affiche serait
  // un signe sans montant.
  const estZero = /^0*$/.test(entier) && /^0*$/.test(fraction);
  const prefixe = signe === "-" && !estZero ? "-" : "";

  return `${prefixe}${grouperMilliers(entier)}${SEPARATEUR_DECIMAL}${fraction}${SEPARATEUR_AVANT_DEVISE}${DEVISE}`;
}

/** Vrai si le montant livre par l'API est strictement negatif — pour la couleur, EN PLUS du signe. */
export function estMontantNegatif(valeur: MontantBrut): boolean {
  return formaterMontant(valeur).startsWith("-");
}

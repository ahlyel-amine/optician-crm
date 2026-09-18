/**
 * La saisie d'une date, en fonctions PURES.
 *
 * 04-UI-SPEC.md 15.4 : la phase 4 livre le masque et PAS le calendrier — voir
 * la docstring de `ChampDate.tsx`, qui porte la raison. Ici il n'y a que le
 * masque, la normalisation au blur, et les deux traductions de transport.
 *
 * **L'annee de reference est un ARGUMENT.** Un module pur dont le verdict
 * depend de `new Date()` est un test qui vire rouge un 1er janvier. Le defaut
 * existe pour le confort de l'appelant ; les tests passent l'annee.
 *
 * **`versISO` est la seule forme qui quitte le navigateur, `depuisISO` la seule
 * qui entre.** L'ecran n'affiche jamais d'ISO : c'est la ligne `Transport` de
 * 15.4, et c'est aussi ce qui evite qu'un `2026-09-14` se lise un jour comme
 * un 9 septembre.
 *
 * Aucune de ces fonctions ne construit un `Date` pour juger : la validite du
 * quantieme se calcule sur les nombres, ce qui la met hors d'atteinte de tout
 * fuseau horaire.
 */

/** Le placeholder du champ. Il n'est PAS le label (03-UI-SPEC.md 10). */
export const GABARIT_DATE = "jj/mm/aaaa";

/** 04-UI-SPEC.md 15.4 et 23, au caractere pres. */
export const FAUTE_DATE_INCOMPLETE = `Date incomplète. Écrivez ${GABARIT_DATE}.`;
/** Idem. */
export const FAUTE_DATE_INEXISTANTE = "Cette date n'existe pas.";

/** Le verdict d'une normalisation : une valeur, ou une faute. Jamais les deux. */
export type VerdictDate = { valeur: string } | { faute: string };

const SAISIE_COMPLETE = /^(\d{1,2})\/(\d{1,2})\/(\d{2}|\d{4})$/;
const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;
const AFFICHEE = /^(\d{2})\/(\d{2})\/(\d{4})$/;

const surDeuxChiffres = (nombre: number): string => String(nombre).padStart(2, "0");

const bissextile = (annee: number): boolean =>
  (annee % 4 === 0 && annee % 100 !== 0) || annee % 400 === 0;

const joursDuMois = (mois: number, annee: number): number =>
  [31, bissextile(annee) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mois - 1];

/**
 * Insere le slash apres le deuxieme et le quatrieme chiffre, et ne recrit RIEN
 * d'autre en cours de frappe.
 *
 * Le piege que cette fonction evite : un masque qui extrairait « les chiffres
 * seuls » puis les redecouperait mutile la saisie de l'opticien qui tape
 * lui-meme ses slashes — `14/9/2026` deviendrait `14/92/026` sous ses doigts.
 * Les segments deja separes sont donc respectes, et un slash efface n'est
 * jamais reinsere.
 */
export function masquerDate(saisi: string): string {
  const brut = saisi.replace(/[^\d/]/g, "");
  const morceaux = brut.split("/");

  // Les chiffres CASCADENT d'un segment plein vers le suivant. Sans cela, le
  // troisieme chiffre du mois — la premiere frappe de l'annee — tombe dans le
  // vide : `14/09` puis `2` rendait `14/09`, et le chiffre etait perdu sous les
  // doigts de l'opticien. C'est ce que le test de frappe chiffre a chiffre a
  // attrape ; une seule frappe de la chaine complete ne l'aurait jamais vu.
  const jour = morceaux[0].slice(0, 2);
  const debordJour = morceaux[0].slice(2);

  const moisEtendu = `${debordJour}${morceaux[1] ?? ""}`;
  const mois = moisEtendu.slice(0, 2);
  const debordMois = moisEtendu.slice(2);

  const annee = `${debordMois}${morceaux.slice(2).join("")}`.slice(0, 4);

  const slashApresJour = morceaux.length > 1 || debordJour !== "";
  const slashApresMois = morceaux.length > 2 || debordMois !== "";

  let sortie = jour;
  if (slashApresJour || mois !== "") {
    sortie += `/${mois}`;
  }
  if (slashApresMois || annee !== "") {
    sortie += `/${annee}`;
  }
  return sortie;
}

/**
 * Deplie une annee a deux chiffres.
 *
 * La regle de 15.4 : deux chiffres inferieurs ou egaux a l'annee de reference
 * plus un donnent le siecle courant, sinon le precedent. Une ordonnance se date
 * dans le passe proche, une naissance loin dans le passe, et le « plus un »
 * laisse passer une date de validite.
 */
const deplierAnnee = (deuxChiffres: number, anneeCourante: number): number => {
  const siecle = Math.floor(anneeCourante / 100) * 100;
  const seuil = (anneeCourante + 1) % 100;
  return deuxChiffres <= seuil ? siecle + deuxChiffres : siecle - 100 + deuxChiffres;
};

/**
 * Complete et valide une saisie AU BLUR : `14/9/26` devient `14/09/2026`.
 *
 * Rien de tout cela n'arrive en cours de frappe — un refus qui apparait a la
 * troisieme touche apprend a l'opticien a ignorer les refus.
 */
export function normaliserDate(
  saisi: string,
  anneeCourante: number = new Date().getFullYear(),
): VerdictDate {
  const morceaux = SAISIE_COMPLETE.exec(saisi.trim());
  if (!morceaux) {
    return { faute: FAUTE_DATE_INCOMPLETE };
  }

  const jour = Number(morceaux[1]);
  const mois = Number(morceaux[2]);
  const annee =
    morceaux[3].length === 4
      ? Number(morceaux[3])
      : deplierAnnee(Number(morceaux[3]), anneeCourante);

  if (mois < 1 || mois > 12 || jour < 1 || jour > joursDuMois(mois, annee)) {
    return { faute: FAUTE_DATE_INEXISTANTE };
  }

  return { valeur: `${surDeuxChiffres(jour)}/${surDeuxChiffres(mois)}/${annee}` };
}

/** `14/09/2026` vers `2026-09-14`. La seule forme qui quitte le navigateur. */
export function versISO(jjmmaaaa: string): string {
  const morceaux = AFFICHEE.exec(jjmmaaaa);
  if (!morceaux) {
    throw new TypeError(
      `versISO attend une date normalisee ${GABARIT_DATE}, recu ${JSON.stringify(jjmmaaaa)}`,
    );
  }
  const [, jour, mois, annee] = morceaux;
  return `${annee}-${mois}-${jour}`;
}

/** `2026-09-14` vers `14/09/2026`. La seule forme qui entre. Le vide reste vide. */
export function depuisISO(iso: string): string {
  if (iso === "") {
    return "";
  }
  const morceaux = ISO.exec(iso);
  if (!morceaux) {
    throw new TypeError(
      `depuisISO attend une date ISO AAAA-MM-JJ, recu ${JSON.stringify(iso)}`,
    );
  }
  const [, annee, mois, jour] = morceaux;
  return `${jour}/${mois}/${annee}`;
}

/**
 * Vrai si la date affichee est posterieure a la reference, toutes deux en ISO.
 *
 * La comparaison est LEXICOGRAPHIQUE sur deux chaines ISO rembourrees de zeros,
 * donc exacte et sans fuseau. Le jour de reference est un argument : le
 * composant ne lit pas l'horloge lui-meme.
 */
export function estDansLeFutur(jjmmaaaa: string, referenceISO: string): boolean {
  return versISO(jjmmaaaa) > referenceISO;
}

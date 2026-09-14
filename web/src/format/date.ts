/**
 * Les dates du client.
 *
 * C'est la moitie facile, et elle est facile pour une raison precise : ici les
 * sources s'accordent. `Intl.DateTimeFormat("fr-FR")` rend `14/09/2026`, tout
 * comme le `SHORT_DATE_FORMAT` du locale `fr` de Django. `Intl` est donc
 * AUTORISE ici, et SEULEMENT ici — jamais pour l'argent, ou les memes sources
 * sont en desaccord (voir `montant.ts`).
 *
 * L'etiquette est epinglee sur `fr-FR` et non sur l'etiquette marocaine :
 * celle-ci s'accorde aujourd'hui et se trouve a une mise a jour d'ICU de ne plus
 * s'accorder, ce qui ferait diverger l'ecran de la facture sans qu'une seule
 * ligne de ce depot ne change.
 *
 * Le fuseau d'affichage est applique DANS ces fonctions, jamais dans les
 * reglages : `TIME_ZONE = "UTC"` cote serveur porte PgBouncer et ne doit pas
 * bouger. Le serveur livre de l'UTC, le client affiche l'heure de Casablanca.
 *
 * Les chaines sont assemblees a partir de `formatToParts` plutot que prises
 * telles quelles : une sortie d'ICU peut glisser d'un U+0020 a un U+202F entre
 * deux versions de navigateur, et le test de la fixture compare les POINTS DE
 * CODE. Assembler nous-memes rend ce glissement impossible.
 */

/** La seule etiquette de locale de la SPA, et uniquement pour les dates. */
const LOCALE_DATE = "fr-FR";

/** Le fuseau d'affichage, celui de la fixture partagee. */
export const FUSEAU_AFFICHAGE = "Africa/Casablanca";

/** Ce que l'API livre : une chaine ISO 8601 en UTC. Un `Date` est tolere. */
export type DateBrute = string | Date;

const enDate = (valeur: DateBrute): Date => {
  const date = valeur instanceof Date ? valeur : new Date(valeur);
  if (Number.isNaN(date.getTime())) {
    throw new TypeError(
      `formatage de date : horodatage ISO invalide, recu ${JSON.stringify(String(valeur))}`,
    );
  }
  return date;
};

const formatDate = new Intl.DateTimeFormat(LOCALE_DATE, {
  timeZone: FUSEAU_AFFICHAGE,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

const formatHeure = new Intl.DateTimeFormat(LOCALE_DATE, {
  timeZone: FUSEAU_AFFICHAGE,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const morceaux = (format: Intl.DateTimeFormat, date: Date): Record<string, string> =>
  Object.fromEntries(
    format.formatToParts(date).map((morceau) => [morceau.type, morceau.value]),
  );

/** Rend `14/09/2026`, heure de Casablanca. */
export function formaterDateCourte(valeur: DateBrute): string {
  const { day, month, year } = morceaux(formatDate, enDate(valeur));
  return `${day}/${month}/${year}`;
}

/** Rend `10:14`, heure de Casablanca, sur 24 heures. */
export function formaterHeure(valeur: DateBrute): string {
  const { hour, minute } = morceaux(formatHeure, enDate(valeur));
  return `${hour}:${minute}`;
}

/**
 * Rend `14/09/2026 à 10:14`, heure de Casablanca.
 *
 * Les deux espaces autour du `à` sont des U+0020 ordinaires — la fixture le dit,
 * et le test le verifie point de code par point de code. L'espace insecable est
 * la convention de la MONNAIE, pas celle des dates.
 */
export function formaterDateHeure(valeur: DateBrute): string {
  const date = enDate(valeur);
  return `${formaterDateCourte(date)} à ${formaterHeure(date)}`;
}

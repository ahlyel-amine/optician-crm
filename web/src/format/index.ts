/**
 * Le seul endroit de la SPA ou un format est decide.
 *
 * `src/format/` est l'unique dossier exempte de l'audit anti-`Intl` de
 * `tests/format.test.ts` et de `npm run audit:format`, et cette exemption ne
 * vaut que pour les dates. Tout le reste de la SPA importe depuis ici plutot que
 * de formater sur place : un `${montant} MAD` ecrit a la main dans un composant
 * est exactement la divergence que la fixture partagee existe pour empecher.
 */

export {
  DECIMALES,
  DEVISE,
  SEPARATEUR_AVANT_DEVISE,
  SEPARATEUR_DECIMAL,
  SEPARATEUR_MILLIERS,
  estMontantNegatif,
  formaterMontant,
} from "./montant";
export type { MontantBrut } from "./montant";

export { FUSEAU_AFFICHAGE, formaterDateCourte, formaterDateHeure, formaterHeure } from "./date";
export type { DateBrute } from "./date";

/**
 * La copie francaise des etats globaux — ecrite UNE fois, heritee par neuf phases.
 *
 * `03-UI-SPEC.md` 8.6 et 9.1. Trois regles y sont absolues et se verifient par
 * lecture de ce fichier :
 *
 *   - jamais un code de statut a l'ecran ;
 *   - jamais une trace de pile ;
 *   - jamais un mot d'anglais.
 *
 * Un code de statut affiche est une fuite doublee d'une impasse : il ne dit rien
 * a un opticien au comptoir et il decrit notre mecanique a qui la sonde. La
 * phrase affichee dit ce qui s'est passe et l'action suivante, jamais autre
 * chose (voix : `03-UI-SPEC.md` 9.2 — vouvoiement, present, aucune excuse).
 *
 * Ces chaines vivent ici et NULLE PART AILLEURS. Une copie recopiee dans un
 * composant est une divergence en attente : l'un des deux exemplaires sera
 * corrige un jour et pas l'autre.
 */

/**
 * 401. Le seul cas ou le message parle de la session : elle existait et elle est
 * morte. Une premiere visite anonyme ne le voit PAS — voir le commentaire de
 * `sessionOuverte` dans `src/api/client.ts`.
 */
export const MESSAGE_SESSION_EXPIREE = "Votre session a expiré. Reconnectez-vous.";

/** Reseau injoignable ou 5xx. Aucun code, aucune cause, une action. */
export const MESSAGE_SERVICE_INDISPONIBLE =
  "Le service est momentanément indisponible. Réessayez dans quelques instants.";

/**
 * La banniere persistante de coupure du lien (`03-UI-SPEC.md` 8.6, derniere
 * ligne). Elle est destructive et elle ne disparait pas toute seule : le produit
 * est en ligne uniquement (CLAUDE.md #1), donc la seule chose honnete a faire
 * d'une coupure est de la dire.
 */
export const MESSAGE_LIEN_PERDU =
  "Connexion perdue. Vos modifications ne seront pas enregistrées.";

/** 403, premiere phrase. */
export const MESSAGE_ACCES_REFUSE = "Vous n'avez pas accès à cette page.";

/**
 * 403, seconde phrase. **Nommer le droit manquant est delibere** : le catalogue
 * des droits est identique pour chaque affaire du produit, donc le nommer ne
 * divulgue rien d'un autre client, et cela transforme un appel de support en
 * demande en libre service — le cout de support est le cout dominant par client
 * (`research/FEATURES.md`).
 */
export function messageDroitManquant(libelleDuDroit: string): string {
  return `Il vous manque le droit « ${libelleDuDroit} ». Demandez-le au propriétaire.`;
}

/** 404. */
export const MESSAGE_PAGE_INEXISTANTE = "Cette page n'existe pas.";

/** 404, l'issue. */
export const LIEN_VERS_LE_TABLEAU_DE_BORD = "Aller au tableau de bord";

/**
 * Echec de chargement. Rendu en carte EN LIGNE dans la zone de contenu, jamais
 * en toast : un toast d'echec de chargement disparait et laisse un ecran blanc
 * que l'utilisateur ne sait plus interpreter.
 */
export function messageChargementImpossible(quoi: string): string {
  return `Impossible de charger ${quoi}. Vérifiez votre connexion.`;
}

/** L'action de la carte ci-dessus. */
export const ACTION_REESSAYER = "Réessayer";

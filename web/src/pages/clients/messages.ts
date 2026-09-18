/**
 * La copie francaise des ecrans clients — 04-UI-SPEC.md 23, au caractere pres.
 *
 * Elle vit ICI, a cote des composants qui l'affichent, et **pas** dans
 * `src/etats/messages.ts`. Ce dernier ne porte que les cinq etats globaux —
 * 401, 403, 404, lien perdu, echec de chargement — que neuf phases se
 * partagent. Un ecran qui y deposerait sa propre copie ferait de ce fichier un
 * depotoir ou personne ne retrouverait la phrase globale qu'il vient corriger.
 *
 * Des constantes nommees plutot que des litteraux dans le JSX : c'est ce qui
 * rend une phrase corrigible en un endroit, et grepable depuis un test.
 */

// --------------------------------------------------------------------------
// La liste
// --------------------------------------------------------------------------

export const TITRE_LISTE = "Clients";
export const ACTION_CREER = "Créer un client";
export const LABEL_RECHERCHE = "Rechercher un client";
export const QUOI_CHARGER = "les clients";
export const MESSAGE_CHARGEMENT = "Chargement…";
export const LEGENDE_TABLEAU =
  "Les clients de l'entreprise, leurs coordonnées et leur dernière ordonnance";

/**
 * L'etat vide d'une affaire le jour de son arrivee.
 *
 * La seconde phrase est DELIBEREE, comme la ligne sur les vendeurs de `03` 7.2 :
 * elle dit a l'opticien que la tolerance aux graphies existe, au moment exact
 * ou il se demande s'il doit s'inquieter de l'orthographe.
 */
export const VIDE_SANS_FICHE_TITRE = "Aucun client";
export const VIDE_SANS_FICHE_CORPS =
  "Créez une fiche pour chaque personne qui achète. Vous la retrouverez ensuite par son nom ou par son téléphone, même écrit autrement.";

export const VIDE_SANS_RESULTAT_TITRE = "Aucun résultat";
export const VIDE_SANS_RESULTAT_CORPS =
  "Vérifiez l'orthographe, essayez le numéro de téléphone, ou créez la fiche.";

/** `Créer un client « mohamed b »` — la requete est echouee VERBATIM. */
export const creerAvecCeNom = (terme: string): string => `Créer un client « ${terme} »`;

// --------------------------------------------------------------------------
// La palette
// --------------------------------------------------------------------------

/** `Aucun client ne correspond à « mohamed b ».` — verbatim, encore. */
export const aucuneCorrespondance = (terme: string): string =>
  `Aucun client ne correspond à « ${terme} ».`;

/**
 * `Mohammed Alaoui · proche de « mhamed »`.
 *
 * La raison se dit EN MOTS. Le rang que le serveur calcule ne dit rien a un
 * opticien, et l'afficher inviterait a le comparer d'une ligne a l'autre alors
 * qu'aucun seuil ne separe une bonne d'une mauvaise correspondance.
 */
export const procheDe = (nom: string, terme: string): string =>
  `${nom} · proche de « ${terme} »`;

/** `Mohammed Alaoui — 06 12 34 56 78`, le telephone deja formate. */
export const nomEtTelephone = (nom: string, telephone: string): string =>
  telephone === "" ? nom : `${nom} — ${telephone}`;

// --------------------------------------------------------------------------
// Le dialogue de creation
// --------------------------------------------------------------------------

export const TITRE_CREATION = "Créer un client";
export const ACTION_CONFIRMER = "Créer le client";
/** `Retour` ferme, `Annuler` defait. La regle des trois mots de `03` 7.10. */
export const ACTION_RETOUR = "Retour";

export const LABEL_NOM = "Nom complet";
export const LABEL_TELEPHONE = "Téléphone";
export const LABEL_DATE_NAISSANCE = "Date de naissance";
export const AIDE_DATE_NAISSANCE = "Sert aux rappels et à la règle des moins de 16 ans.";
export const LABEL_ADRESSE = "Adresse";
export const LABEL_NOTES = "Notes";
/**
 * `notes` est classe PUBLIC au registre de projection. Cette aide est ce qui
 * rend cette decision honnete vis-a-vis de celui qui ecrit dedans : sans elle,
 * un gerant y consignerait un detail qu'il croit confidentiel.
 */
export const AIDE_NOTES = "Visible par toute personne qui peut voir ce client.";
export const MESSAGE_NAISSANCE_FUTURE = "Cette date de naissance est dans le futur.";

// --------------------------------------------------------------------------
// La garde de doublon
// --------------------------------------------------------------------------

export const GARDE_TITRE = "Clients existants";
export const GARDE_ACTION = "Ouvrir la fiche";

export const gardeDecompte = (nombre: number): string =>
  nombre === 1 ? "1 fiche porte un nom proche." : `${nombre} fiches portent un nom proche.`;

/**
 * A11 de 04-UI-SPEC.md 16.3 — un AVERTISSEMENT, pas un refus.
 *
 * Il se dit au blur, il ne porte pas `aria-invalid`, et il n'empeche rien : un
 * client de passage qui ne laisse pas son numero doit pouvoir etre enregistre.
 * Il relie cet ecran a la phase 10, ou les rappels partiront par ce numero.
 */
export const AVERTISSEMENT_SANS_TELEPHONE =
  "À vérifier — sans téléphone, ce client ne recevra aucun rappel.";

/** Le nom du groupe de la palette du shell. Il s'affiche en en-tete de groupe. */
export const GROUPE_PALETTE = "Clients";

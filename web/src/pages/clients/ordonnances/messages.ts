/**
 * La copie francaise de l'ecran de saisie — 04-UI-SPEC.md 23, au caractere pres.
 *
 * Elle vit ICI, a cote des composants qui l'affichent, et **pas** dans
 * `src/etats/messages.ts`, qui ne porte que les cinq etats globaux que neuf
 * phases se partagent.
 *
 * **Aucune borne clinique n'est ecrite dans ce fichier.** Les phrases de refus
 * qui en citent une sont des GABARITS : elles recoivent les bornes servies par
 * l'amorcage. C'est la meme regle que `src/champs/nombres.ts`, et
 * `npm run audit:clinique` la fait tenir.
 */

// --------------------------------------------------------------------------
// L'ecran
// --------------------------------------------------------------------------

export const TITRE_SAISIE = "Nouvelle ordonnance";
export const ACTION_ENREGISTRER = "Enregistrer l'ordonnance";
/** `Fermer` ferme, `Retour` revient, `Annuler` DEFAIT. La regle des trois mots de `03` 7.10. */
export const ACTION_FERMER = "Fermer";
export const ACTION_RETOUR = "Retour";
export const ACTION_QUITTER = "Quitter";

// --------------------------------------------------------------------------
// La grille et la notation
// --------------------------------------------------------------------------

/** `Nouvelle ordonnance` a un sous-titre : le nom du client, dans un `<bdi>`. */
export const LEGENDE_NOTATION = "Notation :";
export const NOTATION_NEGATIVE = "Cylindre négatif";
export const NOTATION_POSITIVE = "Cylindre positif";

/**
 * La convention est enoncee A L'ECRAN, et pas seulement dans le code.
 *
 * `04-CONTEXT.md` le demande explicitement : une erreur de convention doit se
 * voir a la premiere saisie, pas a la premiere paire de verres fausse.
 */
export const LIGNE_CONVENTION = "Les valeurs sont enregistrées en cylindre négatif.";

export const ENTETE_SPHERE = "Sphère";
export const ENTETE_CYLINDRE = "Cylindre";
export const ENTETE_AXE = "Axe";
export const ENTETE_ADDITION = "Addition";
export const SUFFIXE_DEGRE = "°";

export const OEIL_DROIT = "œil droit";
export const OEIL_GAUCHE = "œil gauche";

/** `Sphère de l'œil droit` — un VRAI label, masque visuellement (25.3). */
export const labelDeGrille = (champ: string, oeil: string): string =>
  `${champ} de l'${oeil}`;

/** `Transposé en cylindre négatif : OD +2,00 (−1,00 à 90°).` */
export const annonceTransposition = (notation: string, ligne: string): string =>
  `Transposé en ${notation.toLocaleLowerCase("fr")} : ${ligne}.`;

// --------------------------------------------------------------------------
// L'ecart pupillaire
// --------------------------------------------------------------------------

export const LEGENDE_EP = "Écart pupillaire :";
/**
 * Le nom du champ, seul, pour composer les labels masques de 25.3 par
 * `labelDeGrille` : `Écart pupillaire de l'œil droit`. Il ne porte pas les deux
 * points de la legende, qui appartiennent au groupe et non au champ.
 */
export const CHAMP_EP = "Écart pupillaire";
export const LABEL_EP_BINOCULAIRE = `${CHAMP_EP} binoculaire`;
export const EP_BINOCULAIRE = "binoculaire";
export const EP_MONOCULAIRE = "monoculaire";
export const EP_LES_DEUX = "les deux";
export const UNITE_MM = "mm";

/** `somme : 62,0 mm` — un AFFICHAGE. Jamais un champ range, jamais soumis. */
export const sommeEp = (somme: string): string => `somme : ${somme} ${UNITE_MM}`;

/**
 * La phrase que `04-RESEARCH.md` 6.5 demande au plan de trancher, rendue
 * VISIBLE dans le composant plutot que cachee dans un commentaire.
 *
 * Diviser un binoculaire en deux presuppose la symetrie a laquelle les verres
 * progressifs sont exactement sensibles.
 */
export const REGLE_EP =
  "On enregistre ce qui a été saisi ; la somme binoculaire s'affiche comme contrôle " +
  "quand les deux monoculaires existent ; on ne calcule jamais un monoculaire.";

// --------------------------------------------------------------------------
// Source, prescripteur, date, magasin, type de saisie
// --------------------------------------------------------------------------

export const LEGENDE_SOURCE = "Source :";
export const SOURCE_MEDICALE = "Ordonnance médicale";
export const SOURCE_OPTICIEN = "Réfraction opticien";
export const AIDE_OPTICIEN =
  "La réfraction a été faite au magasin. Aucun prescripteur à indiquer.";

export const LABEL_PRESCRIPTEUR = "Prescripteur";
export const LABEL_DATE_PRESCRIPTION = "Date de prescription";
export const MESSAGE_PRESCRIPTION_FUTURE =
  "Une ordonnance ne peut pas être datée dans le futur.";

export const LABEL_MAGASIN = "Magasin qui enregistre";
export const AIDE_MAGASIN =
  "Sert à la traçabilité. L'ordonnance reste visible depuis tous les magasins.";

export const LEGENDE_TYPE_SAISIE = "Type de saisie :";
export const TYPE_RENOUVELLEMENT = "Renouvellement";
export const TYPE_CORRECTION = "Correction d'une saisie précédente";
export const LABEL_MOTIF = "Motif";
export const AIDE_MOTIF = "Dites ce qui était faux. Cela restera lisible.";

export const ACTION_REPRENDRE = "Reprendre la précédente";
/** `Valeurs du 14/03/2025 reprises. Vérifiez-les sur l'ordonnance.` */
export const annonceReprise = (date: string): string =>
  `Valeurs du ${date} reprises. Vérifiez-les sur l'ordonnance.`;

// --------------------------------------------------------------------------
// Le panneau de relecture
// --------------------------------------------------------------------------

export const TITRE_RELECTURE = "Relecture";
/** Le separateur du panneau : `Ordonnance médicale · Dr. Bennani · 14/03/2025 · Anfa`. */
export const SEPARATEUR_RELECTURE = " · ";
/** `monoculaire — OD 31,5 mm · OG 30,5 mm` : la forme SAISIE, puis ce qui a ete saisi. */
export const detailEp = (forme: string, valeurs: string): string =>
  valeurs === "" ? forme : `${forme} — ${valeurs}`;
export const ETIQUETTE_EP = "EP";
export const ETIQUETTE_SAISI_POSITIF = "Saisi en cylindre positif :";

/** `Dernière ordonnance — 14/03/2025` */
export const referencePrecedente = (date: string): string =>
  `Dernière ordonnance — ${date}`;

/**
 * `2 points à vérifier.` — le compteur `role="status"` de 16.4.
 *
 * Zero avertissement ne rend AUCUNE ligne, et surtout pas « 0 point à
 * vérifier » : un compteur a zero est du bruit permanent.
 */
export const pointsAVerifier = (nombre: number): string =>
  nombre === 1 ? "1 point à vérifier." : `${nombre} points à vérifier.`;

// --------------------------------------------------------------------------
// L'enregistrement
// --------------------------------------------------------------------------

export const AIDE_LIEN_COUPE = "Enregistrement impossible tant que la connexion est coupée.";

/** `Ordonnance enregistrée — version 2.` — le toast, SANS action. */
export const toastEnregistree = (version: number): string =>
  `Ordonnance enregistrée — version ${String(version)}.`;

/** `Enregistrer malgré 2 points à vérifier ?` */
export const titreConfirmationAvertissements = (nombre: number): string =>
  nombre === 1
    ? "Enregistrer malgré 1 point à vérifier ?"
    : `Enregistrer malgré ${String(nombre)} points à vérifier ?`;

/**
 * La seconde phrase enonce CE QUI SURVIT, comme `03` 7.9 l'exige de toute
 * confirmation de ce produit. Ici ce qui survit est le fond meme de CLIENT-06.
 */
export const CORPS_CONFIRMATION_AVERTISSEMENTS =
  "Vous pourrez corriger par une nouvelle version : celle-ci restera lisible telle " +
  "qu'elle a été saisie.";

export const TITRE_QUITTER = "Quitter sans enregistrer ?";
export const CORPS_QUITTER =
  "Les valeurs saisies seront perdues. L'ordonnance n'a pas été enregistrée.";

// --------------------------------------------------------------------------
// Les refus (23, bloc « Refusals ») — gabarits, jamais de chiffre ecrit
// --------------------------------------------------------------------------

export const REFUS_CYLINDRE_SANS_AXE = (oeil: string): string =>
  `Le cylindre de l'${oeil} demande un axe.`;
export const REFUS_AXE_SANS_CYLINDRE =
  "Un axe sans cylindre n'a pas de sens. Saisissez le cylindre, ou effacez l'axe.";
export const REFUS_SOURCE =
  "Indiquez la source : ordonnance médicale ou réfraction opticien.";
export const REFUS_PRESCRIPTEUR = "Qui a prescrit ? Indiquez le médecin.";
export const REFUS_MAGASIN = "Indiquez le magasin qui enregistre cette ordonnance.";

/**
 * L'annonce de canonicalisation de 20.4. **Le tour est SERVI**, jamais ecrit —
 * y compris ici : `audit:clinique` lit aussi les commentaires, et c'est voulu.
 */
export const annonceAxeCanonicalise = (tour: number): string =>
  `Un axe de 0° et de ${String(tour)}° est le même axe. Enregistré comme ${String(tour)}°.`;

// --------------------------------------------------------------------------
// Les avertissements (16.3) — onze lignes, toutes prefixees
// --------------------------------------------------------------------------

/**
 * **La marque qui distingue un avertissement d'un refus, et la seule.**
 *
 * 16.4 : un avertissement ne porte AUCUNE couleur. Ce sont ces trois mots qui
 * portent le sens, parce que `03` 10 interdit la couleur comme unique
 * vecteur — et parce qu'un avertissement qui ressemble a une erreur entraine
 * l'opticien a ecarter les deux.
 */
export const PREFIXE_AVERTISSEMENT = "À vérifier — ";

const prefixer = (phrase: string): string => `${PREFIXE_AVERTISSEMENT}${phrase}`;

export const A1_ADDITIONS_DIFFERENTES = (od: string, og: string): string =>
  prefixer(
    `l'addition est normalement identique aux deux yeux. OD ${od}, OG ${og}.`,
  );

export const A2_SPHERE_FORTE = (sphere: string): string =>
  prefixer(`une sphère de ${sphere} est forte. Confirmez-la sur l'ordonnance.`);

export const A3_ECART_ENTRE_LES_YEUX = (ecart: string): string =>
  prefixer(`${ecart} d'écart entre les deux yeux. Vérifiez les signes.`);

export const A4_AXE_A_BOUGE = (
  oeil: string,
  avant: string,
  apres: string,
  date: string,
): string =>
  prefixer(`l'axe ${oeil} passe de ${avant}° à ${apres}° depuis le ${date}.`);

export const A5_SPHERE_A_BOUGE = (
  oeil: string,
  avant: string,
  apres: string,
  date: string,
): string =>
  prefixer(`la sphère ${oeil} passe de ${avant} à ${apres} depuis le ${date}.`);

export const A6_ADDITION_DIMINUE = (date: string): string =>
  prefixer(`l'addition diminue par rapport au ${date}.`);

export const A7_SOMME_INCOHERENTE = (
  bino: string,
  od: string,
  og: string,
  somme: string,
): string =>
  prefixer(
    "l'écart binoculaire ne correspond pas à la somme des monoculaires : " +
      `${bino} contre ${od} + ${og} = ${somme}.`,
  );

/**
 * A8 et A9 SONT les deux discriminants, depuis l'amendement du 2026-09-18
 * (04-CONTEXT.md Q4). Ils les ABSORBENT au lieu de s'y ajouter : onze lignes
 * avant, onze apres, et pas de douzieme.
 *
 * **La moitie « … est inhabituel. » de ces deux lignes a disparu, et c'est une
 * suppression raisonnee, pas un oubli.** Les deux formes partagent un champ, et
 * sa borne de refus est l'UNION des deux plages servies ; la region que
 * l'ancienne phrase decrivait — au-dessus du plafond binoculaire, sous le
 * plancher monoculaire — est exactement la region deja REFUSEE. La garder
 * produirait un avertissement qui ne peut apparaitre qu'accompagne d'un refus,
 * c'est-a-dire du bruit, que 16.3 interdit explicitement.
 *
 * Les phrases sont celles de 20.5 mot pour mot, avec deux changements
 * mecaniques et aucun changement de mot : le prefixe d'avertissement, et
 * l'initiale mise en bas de casse parce qu'elle suit desormais un tiret. Elles
 * nomment la CORRECTION — « choisissez monoculaire » — et jamais la regle.
 *
 * **Elles n'empechent rien.** Un refus fonde sur un seuil devine bloquerait une
 * saisie legitime au comptoir ; le cout d'un faux refus est un opticien qui ne
 * peut pas enregistrer une ordonnance reelle, celui d'un faux avertissement est
 * une phrase a lire. La severite redevient un refus en une ligne le jour ou un
 * opticien confirme le seuil (28-Q4).
 */
export const A8_BINOCULAIRE_EST_MONOCULAIRE = (valeur: string): string =>
  prefixer(
    `un écart binoculaire de ${valeur} ${UNITE_MM} est un écart monoculaire. ` +
      "Choisissez « monoculaire » ci-dessus.",
  );

export const A9_MONOCULAIRE_EST_BINOCULAIRE = (valeur: string): string =>
  prefixer(
    `un écart monoculaire de ${valeur} ${UNITE_MM} est un écart binoculaire. ` +
      "Choisissez « binoculaire » ci-dessus.",
  );

export const A10_MOINS_DE_SEIZE_ANS = (age: number): string =>
  prefixer(
    `moins de ${String(age)} ans : la correction doit venir d'une ordonnance médicale.`,
  );

// --------------------------------------------------------------------------
// Les SUJETS des refus de bornes
// --------------------------------------------------------------------------
//
// `messageBornes` de `src/champs/nombres.ts` ecrit `{sujet} va de {min} à {max}.`
// Le sujet est de la copie, les deux bornes viennent de l'amorcage : les trois
// se rencontrent au moment du refus et nulle part ailleurs.

export const SUJET_SPHERE = "La sphère";
export const SUJET_CYLINDRE = "Le cylindre";
export const SUJET_AXE = "L'axe";
export const SUJET_ADDITION = "L'addition";
export const SUJET_EP = "L'écart pupillaire";

// --------------------------------------------------------------------------
// L'historique des versions (21) et la carte de version
// --------------------------------------------------------------------------

export const TITRE_HISTORIQUE = "Ordonnances";
export const ACTION_SAISIR = "Saisir une ordonnance";
export const ACTION_VOIR_HISTORIQUE = "Voir l'historique";
export const TITRE_DERNIERE = "Dernière ordonnance";
export const QUOI_CHARGER_LES_ORDONNANCES = "les ordonnances";

export const VIDE_TITRE = "Aucune ordonnance";
export const VIDE_CORPS =
  "Saisissez l'ordonnance du client pour commander ses verres et déclencher ses rappels.";

/**
 * Les badges de 21.1 — **neutres, et porteurs du MOT** (`03` 4).
 *
 * **Rien n'est rouge ici.** Une version remplacee n'est pas une erreur : c'est
 * la forme normale d'une correction dans un modele ou l'on n'efface jamais. La
 * phase 4 n'introduit aucune couleur, et c'est la revendication verifiable de
 * toute la conception de l'avertissement (17.3).
 */
export const BADGE_EN_COURS = "Version en cours";
export const BADGE_REMPLACEE = "Remplacée";
export const BADGE_CORRECTION = "Correction";
export const BADGE_RENOUVELLEMENT = "Renouvellement";

/** `Version 3 — 12/02/2026` */
export const titreDeVersion = (version: number, date: string): string =>
  `Version ${String(version)} — ${date}`;

/** `Ordonnance médicale · Dr. Bennani · prescrite le 10/02/2026` */
export const prescriteLe = (date: string): string => `prescrite le ${date}`;

/** `Remplace la version 2` — un lien qui defile jusqu'a cette carte et la focalise. */
export const remplaceLaVersion = (version: number): string =>
  `Remplace la version ${String(version)}`;

/** `motif : « axe OD saisi 90 au lieu de 9 »` — il restera lisible, comme promis. */
export const motifDit = (motif: string): string => `motif : « ${motif} »`;

/**
 * `Saisie au magasin Anfa par Karim Benali le 12/02/2026 à 09:14`.
 *
 * Le magasin est de la PROVENANCE, jamais un filtre (D-4a) : un gerant qui voit
 * le client voit tout son historique, quel que soit le comptoir.
 */
export const saisieAu = (magasin: string, par: string, quand: string): string =>
  `Saisie au magasin ${magasin} par ${par} le ${quand}`;

export const ACTION_IMPRIMER = "Imprimer";

// --------------------------------------------------------------------------
// La feuille imprimee (21.5)
// --------------------------------------------------------------------------

/**
 * **Le pied de la feuille imprimee.** Une correction imprimee sans convention
 * enoncee est la mauvaise paire de verres en attente d'etre commandee.
 */
export const PIED_IMPRESSION = "Cylindre négatif.";

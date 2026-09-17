/**
 * Le registre de colonnes — la moitie cliente de PERM-06.
 *
 * 03-UI-SPEC.md 8.3. Le serveur retire un champ qu'un gerant n'a pas le droit de
 * voir. Le client ne doit pas le ressusciter en colonne vide, en tiret, en
 * infobulle ou en zero. « Absent, pas grise » ne se maintient pas par
 * discipline : un tableau de colonnes code en dur dans un composant rendrait
 * `prix_achat: undefined` comme une colonne vide surmontee d'un en-tete, et
 * personne ne le verrait a la relecture.
 *
 * D'ou la separation faite ici :
 *
 * - DECLARATIF pour le libelle, l'ordre et l'alignement, qui sont des decisions
 *   humaines explicites et doivent le rester ;
 * - PILOTE PAR LA DONNEE pour la PRESENCE, qui n'en est pas une.
 *
 * Le filtre est `champ in ligne`, et le choix de `in` plutot que
 * `ligne[champ] !== undefined` est le sujet meme : le serveur RETIRE la cle
 * quand le droit manque, et la laisse a `null` quand la donnee est simplement
 * inconnue. Tester la valeur confondrait « tu n'as pas le droit de voir ce
 * champ » avec « ce champ n'est pas renseigne », et ces deux phrases ne
 * s'affichent pas de la meme facon.
 *
 * RAPPEL — et il vaut pour tout fichier frontend de cette phase : ce filtre est
 * un CONFORT, jamais une application de la regle. Le controle est la restriction
 * de queryset et la projection cote serveur. Un champ deja present dans la
 * charge utile est deja divulgue, quoi que fasse ce module. Aucune tache ne peut
 * etre ecrite « masquer X dans l'interface » puis marquee faite.
 */

/** Alignement de la colonne. Jamais deduit du sens d'ecriture du contenu — voir `Valeur.tsx`. */
export type AlignementColonne = "left" | "right";

/** Formatage applique a la valeur. Toujours celui de `src/format/`, jamais une locale. */
export type FormatColonne = "montant" | "date" | "dateheure";

/**
 * Le rendu d'une cellule, quand la valeur n'est ni un montant, ni une date, ni
 * du texte.
 *
 * Ajoute au plan 03-14, et la raison merite d'etre ecrite : la liste des
 * comptes porte un tableau de magasins, un compte de droits assorti d'un badge
 * et un booleen d'activite. Aucun des trois ne se rend en `<bdi>`.
 *
 * L'alternative etait de composer les chaines d'affichage AVANT d'appeler le
 * tableau, et elle est fausse : le filtre de presence s'appliquerait alors a
 * des cles inventees par la page au lieu de celles du serveur, ce qui est
 * exactement la reconstruction cliente que PERM-06 ferme. Le rendu change, la
 * PRESENCE reste pilotee par la charge utile.
 *
 * `ligne` est fourni parce qu'une cellule depend parfois d'un second champ — le
 * badge « Personnalisé par magasin » se lit sur `personnalise` et s'affiche
 * dans la colonne `nombre_de_droits`. Un champ absent y vaut `undefined`, donc
 * l'absence reste fail-closed sans branche a ecrire.
 */
export type RenduCellule = (
  valeur: unknown,
  ligne: Record<string, unknown>,
) => import("react").ReactNode;

/** Une colonne, clee par le NOM DE CHAMP DE L'API — c'est ce qui rend le filtre mecanique. */
export type Colonne = {
  champ: string;
  libelle: string;
  align?: AlignementColonne;
  format?: FormatColonne;
  rendu?: RenduCellule;
};

/** Le contrat minimal qu'une colonne doit remplir pour etre filtrable. */
type ColonneFiltrable = { champ: string };

/**
 * Les colonnes reellement rendues pour UNE ligne : celles dont le champ est
 * present dans la charge utile.
 *
 * C'est la formule de 03-UI-SPEC.md 8.3, et elle tient en une ligne exprès.
 */
export const colonnesVisibles = <C extends ColonneFiltrable>(
  colonnes: readonly C[],
  ligne: object,
): C[] => colonnes.filter((colonne) => colonne.champ in ligne);

/**
 * Les colonnes rendues pour un JEU de lignes : celles presentes dans CHACUNE.
 *
 * Deux cas limites, et les deux sont voulus.
 *
 * 1. Une seule ligne sans la cle suffit a retirer la colonne. La projection du
 *    serveur est uniforme pour une requete donnee, donc une ligne discordante
 *    signale un bogue ; retirer la colonne echoue du cote sur.
 * 2. **Zero ligne rend zero colonne.** C'est le cas le plus sournois : une
 *    recherche sans resultat. Rendre les en-tetes du registre revelerait a un
 *    gerant sans le droit que la colonne « Prix d'achat » existe — la position et
 *    l'existence d'un champ sont elles-memes une divulgation. L'etat vide se dit
 *    avec une phrase, au-dessus ou a cote du tableau, pas avec des en-tetes.
 */
export const colonnesVisiblesSurLignes = <C extends ColonneFiltrable>(
  colonnes: readonly C[],
  lignes: readonly object[],
): C[] =>
  lignes.length === 0
    ? []
    : colonnes.filter((colonne) => lignes.every((ligne) => colonne.champ in ligne));

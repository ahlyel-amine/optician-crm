/**
 * Les refus et les ONZE avertissements de la saisie, purs et sans rendu.
 *
 * ---
 *
 * **La position de la phase, et tout ce fichier en decoule.** La validation
 * attrape l'impossible ; seul l'ecran attrape l'invraisemblable. Un axe de 90
 * tape pour 9 passe toutes les bornes. Ce module porte donc DEUX severites qui
 * ne doivent jamais se confondre :
 *
 * - un **refus** dit que la valeur est fausse. Il porte `aria-invalid`, il
 *   prend la couleur destructive, il bloque l'enregistrement ;
 * - un **avertissement** dit seulement que la valeur est inhabituelle. Il ne
 *   porte PAS `aria-invalid`, il n'a AUCUNE couleur, il ne bloque rien, et il
 *   n'est jamais annonce de maniere assertive (16.4).
 *
 * Melanger les deux defait toute la conception en un attribut : un
 * avertissement deviendrait indiscernable d'une erreur pour exactement
 * l'utilisateur qui ne voit pas la difference de couleur.
 *
 * ---
 *
 * **Les BORNES viennent de l'amorcage** — `Amorcage["bornes_ordonnance"]`,
 * servi par `domaine/ordonnances/bornes.py`. Aucune n'est ecrite ici, y compris
 * dans un commentaire, et `npm run audit:clinique` fait rougir la CI si l'une
 * reapparait. La preuve vivante est
 * `client07_deux_jeux_de_bornes_rendent_deux_verdicts_sur_la_MEME_valeur` :
 * seule la donnee change, et le verdict change avec elle.
 *
 * **Les SEUILS D'AVERTISSEMENT sont d'une autre nature, et le melange serait
 * dangereux s'il n'etait pas ecrit.** Ce ne sont pas des bornes : le serveur ne
 * les applique pas, aucune contrainte n'en depend, et 16.3 les marque
 * `[JUGEMENT]` precisement pour qu'en supprimer un coute une ligne et aucune
 * discussion. Ils vivent donc a UN endroit nomme ci-dessous, marques, plutot
 * que d'etre disperses dans des conditions.
 */

import type { Amorcage } from "@/api/requetes";
import {
  fauteDeSigne,
  messageBornes,
  messagePas,
  normaliserNombre,
  verifierBornes,
  verifierPas,
  type Bornes,
  type PresentationBornes,
  type ReglesNombre,
} from "@/champs/nombres";
import { estDansLeFutur, versISO } from "@/champs/dates";

import { canonicaliserAxe, enMilliemes, rendreMilliemes } from "./optique";
import {
  A10_MOINS_DE_SEIZE_ANS,
  A1_ADDITIONS_DIFFERENTES,
  A2_SPHERE_FORTE,
  A3_ECART_ENTRE_LES_YEUX,
  A4_AXE_A_BOUGE,
  A5_SPHERE_A_BOUGE,
  A6_ADDITION_DIMINUE,
  A7_SOMME_INCOHERENTE,
  A8_BINOCULAIRE_EST_MONOCULAIRE,
  A9_MONOCULAIRE_EST_BINOCULAIRE,
  MESSAGE_PRESCRIPTION_FUTURE,
  OEIL_DROIT,
  OEIL_GAUCHE,
  REFUS_AXE_SANS_CYLINDRE,
  REFUS_CYLINDRE_SANS_AXE,
  REFUS_MAGASIN,
  REFUS_PRESCRIPTEUR,
  REFUS_SOURCE,
  SUJET_ADDITION,
  SUJET_AXE,
  SUJET_CYLINDRE,
  SUJET_EP,
  SUJET_SPHERE,
} from "./messages";
import { AVERTISSEMENT_SANS_TELEPHONE } from "../messages";

/* ---------------------------------------------------------------------------
 * Les formes
 * ------------------------------------------------------------------------- */

/** Les bornes SERVIES, prises sur l'amorcage. Jamais redeclarees. */
export type BornesServies = Amorcage["bornes_ordonnance"];

export type Notation = "negatif" | "positif";
export type EpSaisi = "binoculaire" | "monoculaire" | "les_deux";
export type Source = "" | "ordonnance_medicale" | "refraction_opticien";
export type TypeRevision = "" | "renouvellement" | "correction";

/**
 * L'etat plat du formulaire — une vingtaine de champs, tous en forme
 * d'AFFICHAGE francaise (`+2,00`, `−1,00`, `31,5`, `14/03/2025`).
 *
 * Plat plutot qu'imbrique parce que la grille tabule en LIGNES : un etat
 * imbrique par oeil obligerait chaque champ a connaitre son chemin, pour ne
 * rien rendre de plus lisible.
 */
export type Ordonnance = {
  notation: Notation;
  sphere_od: string;
  sphere_og: string;
  cylindre_od: string;
  cylindre_og: string;
  axe_od: string;
  axe_og: string;
  addition_od: string;
  addition_og: string;
  ep_saisi: EpSaisi;
  ep_binoculaire: string;
  ep_mono_od: string;
  ep_mono_og: string;
  source: Source;
  prescripteur: string;
  date_prescription: string;
  magasin: string;
  type_revision: TypeRevision;
  motif_revision: string;
};

/**
 * Le formulaire a l'ouverture.
 *
 * `notation` vaut **negatif, toujours** : c'est la convention de stockage.
 * `source` n'a **aucun defaut** — une source pre-selectionnee est une
 * affirmation clinique que personne n'a faite.
 */
export const ORDONNANCE_VIDE: Ordonnance = {
  notation: "negatif",
  sphere_od: "",
  sphere_og: "",
  cylindre_od: "",
  cylindre_og: "",
  axe_od: "",
  axe_og: "",
  addition_od: "",
  addition_og: "",
  ep_saisi: "binoculaire",
  ep_binoculaire: "",
  ep_mono_od: "",
  ep_mono_og: "",
  source: "",
  prescripteur: "",
  date_prescription: "",
  magasin: "",
  type_revision: "",
  motif_revision: "",
};

export type Severite = "refus" | "avertissement";

export type Remarque = {
  /** La cle du champ concerne, ou `""` pour une remarque de formulaire. */
  champ: string;
  texte: string;
  severite: Severite;
};

export type ContexteVerification = {
  bornes: BornesServies;
  /** La derniere version du client. **A4, A5 et A6 n'existent que si elle est la.** */
  precedente?: Ordonnance;
  /** `jj/mm/aaaa`. Sert a A10, et a rien d'autre. */
  dateNaissance?: string;
  /** Le jour de reference, en ISO. Requis pour refuser une date future. */
  aujourdhui?: string;
};

/* ---------------------------------------------------------------------------
 * Les seuils de JUGEMENT — un endroit, marques comme tels
 * ------------------------------------------------------------------------- */

/**
 * Les six seuils qui ne sont PAS des bornes.
 *
 * 16.3 marque A3, A5, A6, A8 et A9 `[JUGEMENT]` pour qu'en supprimer un coute
 * une ligne et aucun argument. Les voici, a cet endroit-la. Le serveur ne les
 * connait pas et ne les applique pas : les recevoir de l'amorcage donnerait
 * l'illusion qu'ils ont la meme autorite que les bornes, alors qu'ils n'en ont
 * aucune.
 */
export const SEUILS = {
  /** A2 — au-dela, une sphere est forte. `[JUGEMENT]`, 04-RESEARCH.md 6.3 */
  sphereForte: "10",
  /** A3 — au-dela, l'ecart entre les deux yeux est suspect. `[JUGEMENT — sans source]` */
  ecartEntreLesYeux: "4",
  /** A4 — en degres, depuis la version precedente. `[JUGEMENT]` */
  deriveDeLaxe: 30,
  /** A5 — en dioptries, depuis la version precedente. `[JUGEMENT]` */
  deriveDeLaSphere: "2",
  /** A7 — l'ecart tolere entre le binoculaire et la somme. 04-RESEARCH.md 6.5 */
  ecartDeLaSomme: "1",
  /** A10 — PITFALLS.md 18, `[source secondaire]` */
  ageDeLordonnanceMedicale: 16,
} as const;

/* ---------------------------------------------------------------------------
 * La table des ONZE — 16.3, amendee le 2026-09-18 (04-CONTEXT.md Q4)
 * ------------------------------------------------------------------------- */

export type ArgumentsDavertissement = {
  oeil?: string;
  avant?: string;
  apres?: string;
  date?: string;
  od?: string;
  og?: string;
  bino?: string;
  somme?: string;
  valeur?: string;
  ecart?: string;
  sphere?: string;
  age?: number;
};

export type LigneDavertissement = {
  readonly condition: string;
  readonly jugement: boolean;
  readonly texte: (arguments_: ArgumentsDavertissement) => string;
};

/**
 * **ONZE lignes. Pas douze.**
 *
 * 16.3 se clot par « ne pas ajouter un douzieme avertissement sans en
 * supprimer un », parce que la valeur de la table s'effondre des qu'une saisie
 * normale en produit deux — et que le suivant sera alors ignore. Le test
 * `client07_une_saisie_normale_complete_ne_rend_AUCUNE_remarque` est ce qui
 * tient cette promesse.
 *
 * **L'amendement du 2026-09-18 aurait pu en faire treize.** Promouvoir les deux
 * discriminants d'ecart pupillaire en avertissements les aurait AJOUTES a A8 et
 * A9. La resolution retenue respecte la regle au lieu de la contourner : les
 * deux discriminants **absorbent** A8 et A9. Onze avant, onze apres.
 *
 * **A11 ne porte pas sur une ordonnance** : elle vit sur le dialogue de
 * creation d'un client, ou elle est deja rendue (plan 04-07). Elle figure ici
 * pour que la table de 16.3 soit COMPLETE et comptable a un seul endroit, et
 * son texte pointe sur la constante unique plutot que de la recopier.
 */
export const AVERTISSEMENTS: Record<string, LigneDavertissement> = {
  A1: {
    condition: "les deux additions different",
    jugement: false,
    texte: ({ od = "", og = "" }) => A1_ADDITIONS_DIFFERENTES(od, og),
  },
  A2: {
    condition: "une sphere depasse le seuil de sphere forte",
    jugement: false,
    texte: ({ sphere = "" }) => A2_SPHERE_FORTE(sphere),
  },
  A3: {
    condition: "l'ecart entre les deux spheres depasse le seuil",
    jugement: true,
    texte: ({ ecart = "" }) => A3_ECART_ENTRE_LES_YEUX(ecart),
  },
  A4: {
    condition: "un axe a bouge de plus du seuil depuis la version precedente",
    jugement: true,
    texte: ({ oeil = "", avant = "", apres = "", date = "" }) =>
      A4_AXE_A_BOUGE(oeil, avant, apres, date),
  },
  A5: {
    condition: "une sphere a bouge de plus du seuil depuis la version precedente",
    jugement: true,
    texte: ({ oeil = "", avant = "", apres = "", date = "" }) =>
      A5_SPHERE_A_BOUGE(oeil, avant, apres, date),
  },
  A6: {
    condition: "l'addition a diminue depuis la version precedente",
    jugement: true,
    texte: ({ date = "" }) => A6_ADDITION_DIMINUE(date),
  },
  A7: {
    condition: "le binoculaire ne correspond pas a la somme des monoculaires",
    jugement: false,
    texte: ({ bino = "", od = "", og = "", somme = "" }) =>
      A7_SOMME_INCOHERENTE(bino, od, og, somme),
  },
  A8: {
    condition:
      "l'ecart binoculaire passe sous le plancher binoculaire servi : c'est un " +
      "ecart monoculaire",
    jugement: true,
    texte: ({ valeur = "" }) => A8_BINOCULAIRE_EST_MONOCULAIRE(valeur),
  },
  A9: {
    condition:
      "l'ecart monoculaire passe au-dessus du plafond monoculaire servi : c'est " +
      "un ecart binoculaire",
    jugement: true,
    texte: ({ valeur = "" }) => A9_MONOCULAIRE_EST_BINOCULAIRE(valeur),
  },
  A10: {
    condition: "le client est mineur et la source est une refraction opticien",
    jugement: false,
    texte: ({ age = SEUILS.ageDeLordonnanceMedicale }) => A10_MOINS_DE_SEIZE_ANS(age),
  },
  A11: {
    condition: "un client est cree sans telephone — porte par l'ecran de creation",
    jugement: true,
    texte: () => AVERTISSEMENT_SANS_TELEPHONE,
  },
};

/* ---------------------------------------------------------------------------
 * Les bornes derivees — derivees, jamais reecrites
 * ------------------------------------------------------------------------- */

const opposer = (borne: string): string => {
  if (borne.startsWith("-")) {
    return borne.slice(1);
  }
  return enMilliemes(borne) === 0n ? borne : `-${borne}`;
};

/**
 * Les bornes du champ cylindre pour la notation COURANTE.
 *
 * En notation positive, la plage acceptee est l'OPPOSEE de la plage servie —
 * derivee, jamais reecrite. Ce que le formulaire enverra reste du cylindre
 * negatif dans tous les cas (20.3).
 */
export function bornesDuCylindre(bornes: BornesServies, notation: Notation): Bornes {
  if (notation === "negatif") {
    return bornes.cylindre;
  }
  return {
    min: opposer(bornes.cylindre.max),
    max: opposer(bornes.cylindre.min),
    pas: bornes.cylindre.pas,
  };
}

/**
 * La borne de REFUS du champ d'ecart pupillaire : l'UNION des deux plages
 * servies.
 *
 * **C'est la consequence mecanique de l'amendement Q4.** Les deux formes
 * partagent un meme type de champ, et depuis que le discriminant de 45 mm est
 * un avertissement, la plage propre a chaque forme ne peut plus servir de
 * refus — sinon le refus reviendrait par la porte des bornes, ce que la
 * decision du proprietaire ecarte explicitement. Ce qui reste refuse est
 * l'impossible : une valeur hors de l'union des deux plages.
 */
export function bornesDeLecartPupillaire(bornes: BornesServies): Bornes {
  return {
    min: bornes.ep_monoculaire.min,
    max: bornes.ep_binoculaire.max,
    pas: bornes.ep_monoculaire.pas,
  };
}

/** Le nombre de decimales d'un champ, LU sur son pas servi. */
export function decimalesDuPas(pas: string | number): 0 | 1 | 2 {
  const texte = String(pas);
  const point = texte.indexOf(".");
  if (point === -1) {
    return 0;
  }
  return Math.min(texte.length - point - 1, 2) as 0 | 1 | 2;
}

/** De quoi rediger `{sujet} va de {min} à {max}.` sans ecrire un chiffre. */
export function presentationDe(
  sujet: string,
  pas: string | number,
  avecSigne: boolean,
): PresentationBornes {
  const decimales = decimalesDuPas(pas);
  return {
    sujet,
    rendre: (borne: string) => {
      const milliemes = enMilliemes(borne);
      if (milliemes === null) {
        return borne;
      }
      // Une borne nulle se rend nue : `Le cylindre va de … à 0.`
      return milliemes === 0n ? "0" : rendreMilliemes(milliemes, decimales, avecSigne);
    },
  };
}

/* ---------------------------------------------------------------------------
 * La verification
 * ------------------------------------------------------------------------- */

const OEILS = [
  { suffixe: "od", court: "OD", long: OEIL_DROIT },
  { suffixe: "og", court: "OG", long: OEIL_GAUCHE },
] as const;

const vide = (valeur: string): boolean => valeur.trim() === "";

const absolu = (valeur: bigint): bigint => (valeur < 0n ? -valeur : valeur);

const enEntier = (valeur: string): number | null => {
  const nombre = Number.parseInt(valeur.trim(), 10);
  return Number.isNaN(nombre) ? null : nombre;
};

/**
 * L'ecart le plus court entre deux axes, sur un cercle d'un demi-tour.
 *
 * Un axe de 175° et un axe de 5° sont a dix degres l'un de l'autre, pas a cent
 * soixante-dix. Sans cette periode, A4 hurlerait a chaque renouvellement d'un
 * astigmatisme proche de l'horizontale — et une table qui hurle est une table
 * qu'on cesse de lire.
 */
function ecartAngulaire(gauche: number, droite: number, tour: number): number {
  const brut = Math.abs(gauche - droite) % tour;
  return Math.min(brut, tour - brut);
}

/** L'age au jour de la prescription, ou `null` si l'une des deux dates manque. */
function ageALaPrescription(naissance: string, prescription: string): number | null {
  const isoNaissance = versISO(naissance);
  const isoPrescription = versISO(prescription);
  if (isoNaissance === "" || isoPrescription === "") {
    return null;
  }
  const [anneeN, moisN, jourN] = isoNaissance.split("-").map(Number);
  const [anneeP, moisP, jourP] = isoPrescription.split("-").map(Number);
  let age = anneeP - anneeN;
  if (moisP < moisN || (moisP === moisN && jourP < jourN)) {
    age -= 1;
  }
  return age;
}

/**
 * Le verdict complet du formulaire : les refus de 20.4, 20.8 et 20.9, puis les
 * onze avertissements de 16.3.
 *
 * **Pure, et c'est ce qui la rend eprouvable.** L'ecran n'evalue rien : il
 * appelle cette fonction et rend ce qu'elle dit. Un module de verification
 * melange a du rendu se teste par le DOM, donc mal, donc peu.
 */
export function verifierOrdonnance(
  valeur: Ordonnance,
  contexte: ContexteVerification,
): Remarque[] {
  const { bornes, precedente } = contexte;
  const remarques: Remarque[] = [];
  const refuser = (champ: string, texte: string | null) => {
    if (texte !== null) {
      remarques.push({ champ, texte, severite: "refus" });
    }
  };
  const avertir = (champ: string, texte: string) => {
    remarques.push({ champ, texte, severite: "avertissement" });
  };

  const bornesCylindre = bornesDuCylindre(bornes, valeur.notation);
  const bornesEp = bornesDeLecartPupillaire(bornes);
  const tour = bornes.axe.max;

  const reglesSphere: ReglesNombre = { decimales: 2, signe: "requis" };
  const reglesCylindre: ReglesNombre = {
    decimales: 2,
    signe: valeur.notation === "negatif" ? "fourni-negatif" : "fourni-positif",
  };
  const reglesAddition: ReglesNombre = { decimales: 2, signe: "fourni-positif" };
  const reglesEp: ReglesNombre = { decimales: decimalesDuPas(bornesEp.pas) };

  /** Un champ decimal : forme, puis bornes, puis pas. Dans cet ordre. */
  const verifierDecimal = (
    champ: string,
    brut: string,
    regles: ReglesNombre,
    bornesDuChamp: Bornes,
    presentation: PresentationBornes,
  ): string | null => {
    if (vide(brut)) {
      return null;
    }
    // **Le PAS ne porte jamais de signe**, meme sur un champ qui en exige un.
    // `Les valeurs vont par pas de +0,25.` est faux : le pas est un ecart, pas
    // une valeur signee. Le rendu de borne et le rendu de pas sont donc deux
    // rendus differents du meme objet servi — une sonde de test l'a montre.
    const rendrePas = presentationDe("", bornesDuChamp.pas, false).rendre;
    const normalise = normaliserNombre(brut, regles);
    if (normalise === null) {
      const faute = fauteDeSigne(brut, regles);
      refuser(champ, faute ?? messagePas(rendrePas(bornesDuChamp.pas)));
      return null;
    }
    const faute =
      verifierBornes(normalise, bornesDuChamp, presentation) ??
      verifierPas(normalise, bornesDuChamp.pas, rendrePas);
    refuser(champ, faute);
    return faute === null ? normalise : null;
  };

  // ---- Les refus, oeil par oeil -----------------------------------------
  const spheres: Record<string, bigint | null> = {};
  const additions: Record<string, bigint | null> = {};

  for (const oeil of OEILS) {
    const sphere = verifierDecimal(
      `sphere_${oeil.suffixe}`,
      valeur[`sphere_${oeil.suffixe}`],
      reglesSphere,
      bornes.sphere,
      presentationDe(SUJET_SPHERE, bornes.sphere.pas, true),
    );
    spheres[oeil.suffixe] = sphere === null ? null : enMilliemes(sphere);

    const cylindreBrut = valeur[`cylindre_${oeil.suffixe}`];
    verifierDecimal(
      `cylindre_${oeil.suffixe}`,
      cylindreBrut,
      reglesCylindre,
      bornesCylindre,
      presentationDe(SUJET_CYLINDRE, bornesCylindre.pas, true),
    );

    const addition = verifierDecimal(
      `addition_${oeil.suffixe}`,
      valeur[`addition_${oeil.suffixe}`],
      reglesAddition,
      bornes.addition,
      presentationDe(SUJET_ADDITION, bornes.addition.pas, true),
    );
    additions[oeil.suffixe] = addition === null ? null : enMilliemes(addition);

    // L'axe : 0 est ACCEPTE et canonicalise avant d'etre confronte a la borne.
    const axeBrut = valeur[`axe_${oeil.suffixe}`];
    const champAxe = `axe_${oeil.suffixe}`;
    if (!vide(axeBrut)) {
      const axe = enEntier(axeBrut);
      const presentationAxe = presentationDe(SUJET_AXE, bornes.axe.pas, false);
      if (axe === null) {
        refuser(
          champAxe,
          messageBornes(
            SUJET_AXE,
            presentationAxe.rendre(String(bornes.axe.min)),
            presentationAxe.rendre(String(bornes.axe.max)),
          ),
        );
      } else {
        const canonique = axe === 0 ? canonicaliserAxe(axe, bornes.axe) : axe;
        if (canonique < bornes.axe.min || canonique > bornes.axe.max) {
          refuser(
            champAxe,
            messageBornes(
              SUJET_AXE,
              presentationAxe.rendre(String(bornes.axe.min)),
              presentationAxe.rendre(String(bornes.axe.max)),
            ),
          );
        }
      }
    }

    // La classe croisee qu'aucun controle de plage n'attrape, DANS LES DEUX SENS.
    const cylindrePose = !vide(cylindreBrut) && enMilliemes(cylindreBrut) !== 0n;
    if (cylindrePose && vide(axeBrut)) {
      refuser(champAxe, REFUS_CYLINDRE_SANS_AXE(oeil.long));
    }
    if (!cylindrePose && !vide(axeBrut)) {
      refuser(champAxe, REFUS_AXE_SANS_CYLINDRE);
    }
  }

  // ---- Les refus d'ecart pupillaire -------------------------------------
  const presentationEp = presentationDe(SUJET_EP, bornesEp.pas, false);
  const champsEp: string[] =
    valeur.ep_saisi === "binoculaire"
      ? ["ep_binoculaire"]
      : valeur.ep_saisi === "monoculaire"
        ? ["ep_mono_od", "ep_mono_og"]
        : ["ep_binoculaire", "ep_mono_od", "ep_mono_og"];

  for (const champ of champsEp) {
    verifierDecimal(
      champ,
      valeur[champ as keyof Ordonnance] as string,
      reglesEp,
      bornesEp,
      presentationEp,
    );
  }

  // ---- Les refus de formulaire ------------------------------------------
  if (valeur.source === "") {
    refuser("source", REFUS_SOURCE);
  }
  if (valeur.source === "ordonnance_medicale" && vide(valeur.prescripteur)) {
    refuser("prescripteur", REFUS_PRESCRIPTEUR);
  }
  if (vide(valeur.magasin)) {
    refuser("magasin", REFUS_MAGASIN);
  }
  if (
    !vide(valeur.date_prescription) &&
    contexte.aujourdhui !== undefined &&
    estDansLeFutur(valeur.date_prescription, contexte.aujourdhui)
  ) {
    refuser("date_prescription", MESSAGE_PRESCRIPTION_FUTURE);
  }

  // ---- A1 : les deux additions different ---------------------------------
  if (additions.od !== null && additions.og !== null && additions.od !== additions.og) {
    avertir(
      "addition_og",
      AVERTISSEMENTS.A1.texte({
        od: valeur.addition_od,
        og: valeur.addition_og,
      }),
    );
  }

  // ---- A2 : une sphere forte ---------------------------------------------
  const sphereForte = enMilliemes(SEUILS.sphereForte);
  for (const oeil of OEILS) {
    const sphere = spheres[oeil.suffixe];
    if (sphere !== null && sphereForte !== null && absolu(sphere) > sphereForte) {
      avertir(
        `sphere_${oeil.suffixe}`,
        AVERTISSEMENTS.A2.texte({ sphere: valeur[`sphere_${oeil.suffixe}`] }),
      );
    }
  }

  // ---- A3 : l'ecart entre les deux yeux -----------------------------------
  const seuilEcart = enMilliemes(SEUILS.ecartEntreLesYeux);
  if (spheres.od !== null && spheres.og !== null && seuilEcart !== null) {
    const ecart = absolu(spheres.od - spheres.og);
    if (ecart > seuilEcart) {
      avertir("sphere_og", AVERTISSEMENTS.A3.texte({ ecart: rendreMilliemes(ecart, 2) }));
    }
  }

  // ---- A4, A5, A6 : ce que la version PRECEDENTE ajoute, et rien d'autre --
  if (precedente !== undefined) {
    const date = precedente.date_prescription;
    const seuilAxe = SEUILS.deriveDeLaxe;
    const seuilSphere = enMilliemes(SEUILS.deriveDeLaSphere);

    for (const oeil of OEILS) {
      const avantAxe = enEntier(precedente[`axe_${oeil.suffixe}`]);
      const apresAxe = enEntier(valeur[`axe_${oeil.suffixe}`]);
      if (avantAxe !== null && apresAxe !== null) {
        if (ecartAngulaire(avantAxe, apresAxe, tour) > seuilAxe) {
          avertir(
            `axe_${oeil.suffixe}`,
            AVERTISSEMENTS.A4.texte({
              oeil: oeil.court,
              avant: String(avantAxe),
              apres: String(apresAxe),
              date,
            }),
          );
        }
      }

      const avantSphere = enMilliemes(precedente[`sphere_${oeil.suffixe}`]);
      const apresSphere = spheres[oeil.suffixe];
      if (
        avantSphere !== null &&
        apresSphere !== null &&
        seuilSphere !== null &&
        absolu(apresSphere - avantSphere) > seuilSphere
      ) {
        avertir(
          `sphere_${oeil.suffixe}`,
          AVERTISSEMENTS.A5.texte({
            oeil: oeil.court,
            avant: precedente[`sphere_${oeil.suffixe}`],
            apres: valeur[`sphere_${oeil.suffixe}`],
            date,
          }),
        );
      }
    }

    const diminue = OEILS.some((oeil) => {
      const avant = enMilliemes(precedente[`addition_${oeil.suffixe}`]);
      const apres = additions[oeil.suffixe];
      return avant !== null && apres !== null && apres < avant;
    });
    if (diminue) {
      avertir("addition_od", AVERTISSEMENTS.A6.texte({ date }));
    }
  }

  // ---- A7 : la somme des monoculaires -------------------------------------
  const bino = enMilliemes(valeur.ep_binoculaire);
  const monoOd = enMilliemes(valeur.ep_mono_od);
  const monoOg = enMilliemes(valeur.ep_mono_og);
  const seuilSomme = enMilliemes(SEUILS.ecartDeLaSomme);
  if (
    valeur.ep_saisi === "les_deux" &&
    bino !== null &&
    monoOd !== null &&
    monoOg !== null &&
    seuilSomme !== null &&
    absolu(bino - (monoOd + monoOg)) > seuilSomme
  ) {
    const decimalesEp = decimalesDuPas(bornesEp.pas);
    avertir(
      "ep_binoculaire",
      AVERTISSEMENTS.A7.texte({
        bino: valeur.ep_binoculaire,
        od: valeur.ep_mono_od,
        og: valeur.ep_mono_og,
        somme: rendreMilliemes(monoOd + monoOg, decimalesEp),
      }),
    );
  }

  // ---- A8 et A9 : les deux discriminants, absorbes (amendement Q4) --------
  // Un avertissement ne double JAMAIS un refus : la valeur hors de l'union est
  // deja refusee, et 16.3 refuse le bruit avant de refuser le douzieme.
  const aDejaUnRefus = (champ: string) =>
    remarques.some((r) => r.champ === champ && r.severite === "refus");

  const planchierBino = enMilliemes(bornes.ep_binoculaire.min);
  if (
    champsEp.includes("ep_binoculaire") &&
    bino !== null &&
    planchierBino !== null &&
    bino < planchierBino &&
    !aDejaUnRefus("ep_binoculaire")
  ) {
    avertir(
      "ep_binoculaire",
      AVERTISSEMENTS.A8.texte({ valeur: valeur.ep_binoculaire }),
    );
  }

  const plafondMono = enMilliemes(bornes.ep_monoculaire.max);
  for (const oeil of OEILS) {
    const champ = `ep_mono_${oeil.suffixe}`;
    if (!champsEp.includes(champ)) {
      continue;
    }
    const mono = enMilliemes(valeur[champ as keyof Ordonnance] as string);
    if (mono === null || plafondMono === null || mono <= plafondMono) {
      continue;
    }
    if (!aDejaUnRefus(champ)) {
      avertir(
        champ,
        AVERTISSEMENTS.A9.texte({ valeur: valeur[champ as keyof Ordonnance] as string }),
      );
    }
  }

  // ---- A10 : moins de seize ans, et une refraction au magasin -------------
  if (
    contexte.dateNaissance !== undefined &&
    valeur.source === "refraction_opticien" &&
    !vide(valeur.date_prescription)
  ) {
    const age = ageALaPrescription(contexte.dateNaissance, valeur.date_prescription);
    if (age !== null && age < SEUILS.ageDeLordonnanceMedicale) {
      avertir(
        "source",
        AVERTISSEMENTS.A10.texte({ age: SEUILS.ageDeLordonnanceMedicale }),
      );
    }
  }

  return remarques;
}

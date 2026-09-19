import { ChampNombre } from "@/champs/ChampNombre";
import type { Bornes, ReglesNombre } from "@/champs/nombres";
import { cn } from "cn";

import {
  ENTETE_ADDITION,
  ENTETE_AXE,
  ENTETE_CYLINDRE,
  ENTETE_SPHERE,
  LEGENDE_NOTATION,
  LIGNE_CONVENTION,
  NOTATION_NEGATIVE,
  NOTATION_POSITIVE,
  OEIL_DROIT,
  OEIL_GAUCHE,
  SUFFIXE_DEGRE,
  SUJET_ADDITION,
  SUJET_AXE,
  SUJET_CYLINDRE,
  SUJET_SPHERE,
  labelDeGrille,
  referencePrecedente,
} from "./messages";
import { LigneDeCorrection } from "./LigneDeCorrection";
import {
  bornesDuCylindre,
  presentationDe,
  type BornesServies,
  type Notation,
  type Ordonnance,
} from "./verifier";

/**
 * La grille OD/OG — **le tableau du papier**, en CSS grid et non en `table`.
 *
 * Une ordonnance marocaine ou francaise s'ecrit en table : lignes OD/OG,
 * colonnes Sphere · Cylindre · Axe · Addition. Le formulaire EST cette table,
 * et la tabulation la parcourt **en lignes** (20.2). L'ordre du DOM est donc
 * l'ordre visuel et l'ordre de tabulation a la fois — ce qui n'est vrai que
 * parce qu'il n'existe **aucun `tabindex` positif** ici ni ailleurs (`03` 5.7).
 *
 * **CSS grid et non un `table` HTML, et c'est de l'accessibilite, pas du gout.**
 * (Le symbole est ecrit sans ses chevrons a dessein : la garde d'acceptation de
 * ce plan cherche l'element, et dix fois dans les phases 3 et 4 un critere a
 * echoue sur la prose qui l'expliquait — CLAUDE.md, « Testing ».) Une
 * table de champs fait annoncer des coordonnees de cellule au lecteur d'ecran
 * au lieu du sens ; c'est un formulaire, et 25.3 le tranche.
 *
 * Chaque entree porte un **vrai `<label>` visuellement masque** portant tout le
 * sens (`Sphère de l'œil droit`) plutot qu'un `aria-label` : un `<label>`
 * agrandit aussi la cible de clic, ce qu'un attribut ne fait pas. Les en-tetes
 * visibles sont `aria-hidden` pour ne pas etre lus deux fois, et le `°` est
 * **hors** de l'entree, `aria-hidden` lui aussi — le label masque dit deja
 * « Axe ».
 *
 * **La colonne de reference** (20.7) est `aria-hidden` : son contenu est repris
 * mot pour mot dans le texte accessible du panneau de relecture, et le lire
 * deux fois en ferait du bruit.
 */

/** Le zero de l'axe est ACCEPTE a la saisie puis canonicalise (20.4). Ce n'est pas une borne. */
const ZERO = "0";

const OEILS = [
  { suffixe: "od" as const, court: "OD" as const, long: OEIL_DROIT },
  { suffixe: "og" as const, court: "OG" as const, long: OEIL_GAUCHE },
];

const ENTETES = [ENTETE_SPHERE, ENTETE_CYLINDRE, ENTETE_AXE, ENTETE_ADDITION];

export type RemarquesDuChamp = { faute?: string; avertissement?: string };

export type ProprietesGrilleOdOg = {
  valeur: Ordonnance;
  bornes: BornesServies;
  surChamp: (champ: keyof Ordonnance, valeur: string) => void;
  /** Appele au blur d'une entree : c'est LA que les remarques se calculent (16.4). */
  surSortieDeChamp: () => void;
  surNotation: (notation: Notation) => void;
  remarquesDe: (champ: string) => RemarquesDuChamp;
  /** La derniere version du client, deja chargee pour 19.3. */
  precedente?: Ordonnance | null;
  dateDeLaPrecedente?: string;
};

/** Les bornes de l'axe telles que le CHAMP les accepte : le zero en plus, canonicalise ensuite. */
export function bornesDeSaisieDeLaxe(bornes: BornesServies): Bornes {
  return {
    min: ZERO,
    max: String(bornes.axe.max),
    pas: String(bornes.axe.pas),
  };
}

export function GrilleOdOg({
  valeur,
  bornes,
  surChamp,
  surSortieDeChamp,
  surNotation,
  remarquesDe,
  precedente = null,
  dateDeLaPrecedente = "",
}: ProprietesGrilleOdOg) {
  const bornesCylindre = bornesDuCylindre(bornes, valeur.notation);
  const bornesAxe = bornesDeSaisieDeLaxe(bornes);

  const reglesSphere: ReglesNombre = { decimales: 2, signe: "requis" };
  const reglesCylindre: ReglesNombre = {
    decimales: 2,
    signe: valeur.notation === "negatif" ? "fourni-negatif" : "fourni-positif",
  };
  const reglesAddition: ReglesNombre = { decimales: 2, signe: "fourni-positif" };
  const reglesAxe: ReglesNombre = { decimales: 0 };

  const colonnes = [
    {
      champ: "sphere",
      sujet: SUJET_SPHERE,
      entete: ENTETE_SPHERE,
      bornes: bornes.sphere,
      regles: reglesSphere,
      signe: true,
      suffixe: undefined as string | undefined,
    },
    {
      champ: "cylindre",
      sujet: SUJET_CYLINDRE,
      entete: ENTETE_CYLINDRE,
      bornes: bornesCylindre,
      regles: reglesCylindre,
      signe: true,
      suffixe: undefined,
    },
    {
      champ: "axe",
      sujet: SUJET_AXE,
      entete: ENTETE_AXE,
      bornes: bornesAxe,
      regles: reglesAxe,
      signe: false,
      suffixe: SUFFIXE_DEGRE,
    },
    {
      champ: "addition",
      sujet: SUJET_ADDITION,
      entete: ENTETE_ADDITION,
      bornes: bornes.addition,
      regles: reglesAddition,
      signe: true,
      suffixe: undefined,
    },
  ];

  return (
    <div data-testid="bloc-grille" className="flex flex-col gap-4">
      {/*
        La bascule de notation, en tete de grille. Un `radiogroup` et non un
        combobox : les deux options sont visibles, la navigation aux fleches est
        native, et un groupe de radios tire son nom d'un `<legend>` reel — donc
        le piege *name from author* qui a produit D-1 ne peut pas s'y produire.
      */}
      <fieldset role="radiogroup" aria-labelledby="ord-notation-legende">
        <legend id="ord-notation-legende" className="text-sm font-medium">
          {LEGENDE_NOTATION}
        </legend>
        <div className="mt-2 flex flex-wrap items-center gap-6">
          {[
            { code: "negatif" as const, libelle: NOTATION_NEGATIVE },
            { code: "positif" as const, libelle: NOTATION_POSITIVE },
          ].map((option) => (
            <label key={option.code} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="ord-notation"
                value={option.code}
                checked={valeur.notation === option.code}
                onChange={() => surNotation(option.code)}
              />
              {option.libelle}
            </label>
          ))}
        </div>
      </fieldset>

      {/*
        `data-testid` porte le TABLEAU seul, et non la bascule de notation qui
        le surmonte. C'est ce qui rend « la tabulation parcourt la grille en
        lignes » verifiable : une assertion sur les entrees du bloc entier
        compterait les deux radios de notation et ne dirait plus rien de
        l'ordre du papier.
      */}
      <div
        data-testid="grille-od-og"
        className="grid grid-cols-[3rem_repeat(4,minmax(0,1fr))_auto] items-start gap-x-3 gap-y-2"
      >
        <span aria-hidden="true" />
        {ENTETES.map((entete) => (
          <span key={entete} aria-hidden="true" className="text-xs text-muted-foreground">
            {entete}
          </span>
        ))}
        <span aria-hidden="true" className="text-xs text-muted-foreground">
          {precedente === null ? "" : referencePrecedente(dateDeLaPrecedente)}
        </span>

        {OEILS.map((oeil) => (
          <GroupeDeLigne
            key={oeil.suffixe}
            oeil={oeil}
            colonnes={colonnes}
            valeur={valeur}
            surChamp={surChamp}
            surSortieDeChamp={surSortieDeChamp}
            remarquesDe={remarquesDe}
            precedente={precedente}
          />
        ))}
      </div>

      {/*
        LA CONVENTION, A L'ECRAN. `04-CONTEXT.md` le demande explicitement :
        une erreur de convention doit se voir a la premiere saisie, et non a la
        premiere paire de verres fausse.
      */}
      <p className="text-xs text-muted-foreground">{LIGNE_CONVENTION}</p>
    </div>
  );
}

type Colonne = {
  champ: string;
  sujet: string;
  entete: string;
  bornes: Bornes;
  regles: ReglesNombre;
  signe: boolean;
  suffixe: string | undefined;
};

/**
 * Une ligne de la grille : le libelle d'oeil, ses quatre entrees, sa reference.
 *
 * Les quatre entrees sont des enfants DIRECTS de la grille — un `<div>`
 * enveloppant par ligne casserait l'alignement des colonnes en CSS grid, et
 * c'est ce qui rendrait le tableau du papier illisible.
 */
function GroupeDeLigne({
  oeil,
  colonnes,
  valeur,
  surChamp,
  surSortieDeChamp,
  remarquesDe,
  precedente,
}: {
  oeil: { suffixe: "od" | "og"; court: "OD" | "OG"; long: string };
  colonnes: Colonne[];
  valeur: Ordonnance;
  surChamp: (champ: keyof Ordonnance, valeur: string) => void;
  surSortieDeChamp: () => void;
  remarquesDe: (champ: string) => RemarquesDuChamp;
  precedente: Ordonnance | null;
}) {
  return (
    <>
      <span className="pt-8 text-sm font-semibold">
        {oeil.court}
        {/* Un lecteur d'ecran qui epelle `OD` ne dit rien a personne (25.3). */}
        <span className="sr-only"> {oeil.long}</span>
      </span>

      {colonnes.map((colonne) => {
        const cle = `${colonne.champ}_${oeil.suffixe}` as keyof Ordonnance;
        const remarques = remarquesDe(cle);
        return (
          <ChampNombre
            key={cle}
            identifiant={`ord-${colonne.champ}-${oeil.suffixe}`}
            label={labelDeGrille(colonne.entete, oeil.long)}
            labelMasque
            largeur="w-full"
            valeur={valeur[cle] as string}
            surChangement={(saisie) => surChamp(cle, saisie)}
            surVerdict={() => surSortieDeChamp()}
            bornes={colonne.bornes}
            regles={colonne.regles}
            suffixe={colonne.suffixe}
            presentation={presentationDe(colonne.sujet, colonne.bornes.pas, colonne.signe)}
            faute={remarques.faute}
            avertissement={remarques.avertissement}
          />
        );
      })}

      {/*
        La colonne de reference (20.7), `aria-hidden` : un secours pour l'oeil,
        repris dans le texte du panneau de relecture pour l'oreille.
      */}
      <span aria-hidden="true" className={cn("pt-8 text-xs text-muted-foreground")}>
        {precedente === null ? null : (
          <LigneDeCorrection
            oeil={oeil.court}
            sphere={precedente[`sphere_${oeil.suffixe}`]}
            cylindre={precedente[`cylindre_${oeil.suffixe}`]}
            axe={precedente[`axe_${oeil.suffixe}`]}
            addition={precedente[`addition_${oeil.suffixe}`]}
          />
        )}
      </span>
    </>
  );
}

import { Badge } from "@/components/ui/badge";
import { cn } from "cn";
import { formaterDateCourte, formaterDateHeure } from "@/format";

import { LigneDeCorrection } from "./LigneDeCorrection";
import { afficherTelQuel } from "./optique";
import {
  BADGE_CORRECTION,
  BADGE_EN_COURS,
  BADGE_REMPLACEE,
  BADGE_RENOUVELLEMENT,
  EP_BINOCULAIRE,
  EP_LES_DEUX,
  EP_MONOCULAIRE,
  ETIQUETTE_EP,
  SEPARATEUR_RELECTURE,
  SOURCE_MEDICALE,
  SOURCE_OPTICIEN,
  UNITE_MM,
  detailEp,
  motifDit,
  prescriteLe,
  remplaceLaVersion,
  saisieAu,
  titreDeVersion,
} from "./messages";

/**
 * UNE VERSION STOCKEE, RENDUE TELLE QU'ELLE A ETE SAISIE — 04-UI-SPEC.md 21.1.
 *
 * ---
 *
 * **La phrase qui gouverne ce fichier, et la seule raison pour laquelle il
 * existe separement du formulaire de saisie :**
 *
 * > Une version enregistree se rend telle qu'elle a ete saisie. L'affichage ne
 * > la revalide JAMAIS.
 *
 * Les bornes cliniques vivent a un endroit servi et le proprietaire les a deja
 * changees une fois. Une version portant une valeur que les bornes
 * d'aujourd'hui refuseraient s'affiche donc **sans avertissement, sans badge
 * d'erreur, sans annotation** — sinon les anciennes fiches paraitraient
 * fausses parce que la regle a bouge, ce qui detruit exactement la garantie
 * que CLIENT-06 achete. Les notes « A verifier » sont une propriete du
 * FORMULAIRE DE SAISIE, jamais d'une ordonnance stockee.
 *
 * Consequence mecanique, et elle est verifiee par un grep du plan autant que
 * par un test : **ce module n'importe pas le verificateur clinique**, et il n'a
 * besoin d'aucune borne pour rendre une valeur — `afficherTelQuel` compte les
 * decimales de la CHAINE recue.
 *
 * ---
 *
 * **Aucun controle de modification, aucun controle de suppression.** Ni menu de
 * ligne, ni icone crayon, ni corbeille (T-04-64). Le serveur rend 405 de toute
 * facon (plan 04-05), donc ceci est une defense en profondeur et non la
 * garantie. Corriger, c'est `Saisir une ordonnance` → `Correction d'une saisie
 * precedente` → un `Motif`.
 *
 * **Rien n'est rouge.** Une version remplacee n'est pas une erreur : c'est la
 * forme normale d'une correction dans un modele ou l'on n'efface jamais. Les
 * badges sont neutres et portent LE MOT (`03` 4).
 *
 * **Pas de vue de difference retrospective entre deux versions en phase 4**, et
 * la raison est ecrite plutot que l'omission : le moment ou une comparaison
 * evite une erreur est PENDANT la saisie, et il est couvert par le panneau de
 * relecture et la colonne de reference. Un diff est un confort ; differe avec
 * sa raison.
 */

/** Les quatre valeurs d'un oeil, dans la forme SERVIE : point decimal, axe entier. */
export type OeilServi = {
  sphere: string | null;
  cylindre: string | null;
  axe: number | null;
  addition: string | null;
};

/** L'ecart pupillaire servi, dans la forme SAISIE — jamais recalcule. */
export type EcartServi = {
  ep_saisi: string;
  ep_binoculaire: string | null;
  ep_mono_od: string | null;
  ep_mono_og: string | null;
};

const LIBELLE_SOURCE: Record<string, string> = {
  ordonnance_medicale: SOURCE_MEDICALE,
  refraction_opticien: SOURCE_OPTICIEN,
};

const LIBELLE_EP: Record<string, string> = {
  binoculaire: EP_BINOCULAIRE,
  monoculaire: EP_MONOCULAIRE,
  les_deux: EP_LES_DEUX,
};

const LIBELLE_TYPE: Record<string, string> = {
  correction: BADGE_CORRECTION,
  renouvellement: BADGE_RENOUVELLEMENT,
};

function texte(brut: Record<string, unknown>, cle: string): string {
  const valeur = brut[cle];
  return typeof valeur === "string" ? valeur : "";
}

function nombre(brut: Record<string, unknown>, cle: string): number | null {
  const valeur = brut[cle];
  return typeof valeur === "number" ? valeur : null;
}

function decimal(brut: Record<string, unknown>, cle: string): string | null {
  const valeur = brut[cle];
  return typeof valeur === "string" ? valeur : null;
}

/** Les quatre valeurs d'un oeil, extraites d'une version servie a plat. */
export function oeilDeLaVersion(
  brut: Record<string, unknown>,
  oeil: "od" | "og",
): OeilServi {
  return {
    sphere: decimal(brut, `sphere_${oeil}`),
    cylindre: decimal(brut, `cylindre_${oeil}`),
    axe: nombre(brut, `axe_${oeil}`),
    addition: decimal(brut, `addition_${oeil}`),
  };
}

export function ecartDeLaVersion(brut: Record<string, unknown>): EcartServi {
  return {
    ep_saisi: texte(brut, "ep_saisi"),
    ep_binoculaire: decimal(brut, "ep_binoculaire"),
    ep_mono_od: decimal(brut, "ep_mono_od"),
    ep_mono_og: decimal(brut, "ep_mono_og"),
  };
}

/**
 * LES TROIS LIGNES D'UNE CORRECTION : OD, OG, puis l'ecart pupillaire.
 *
 * **Un composant rend une correction, partout** — `LigneDeCorrection`, et
 * celui-ci ne fait que l'appeler deux fois. La fiche client (19.3),
 * l'historique (21.1), la version seule (21.4) et la feuille imprimee (21.5)
 * passent toutes par ici : une correction rendue de deux facons finirait par
 * etre rendue de deux facons DIFFERENTES, et le lecteur n'aurait aucun moyen de
 * savoir laquelle correspond au papier. Meme regle de source unique que le
 * formateur monetaire.
 */
export function BlocCorrection({
  od,
  og,
  ecart,
  className,
}: {
  od: OeilServi;
  og: OeilServi;
  ecart: EcartServi;
  className?: string;
}) {
  const valeursEp = [
    ecart.ep_binoculaire === null
      ? ""
      : `${afficherTelQuel(ecart.ep_binoculaire)} ${UNITE_MM}`,
    ecart.ep_mono_od === null
      ? ""
      : `OD ${afficherTelQuel(ecart.ep_mono_od)} ${UNITE_MM}`,
    ecart.ep_mono_og === null
      ? ""
      : `OG ${afficherTelQuel(ecart.ep_mono_og)} ${UNITE_MM}`,
  ]
    .filter((morceau) => morceau !== "")
    .join(SEPARATEUR_RELECTURE);

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <LigneDeCorrection
        oeil="OD"
        sphere={afficherTelQuel(od.sphere, true)}
        cylindre={afficherTelQuel(od.cylindre, true)}
        axe={od.axe === null ? "" : String(od.axe)}
        addition={afficherTelQuel(od.addition, true)}
      />
      <LigneDeCorrection
        oeil="OG"
        sphere={afficherTelQuel(og.sphere, true)}
        cylindre={afficherTelQuel(og.cylindre, true)}
        axe={og.axe === null ? "" : String(og.axe)}
        addition={afficherTelQuel(og.addition, true)}
      />
      <p className="flex items-baseline gap-2 text-sm tabular-nums">
        <span className="font-semibold">{ETIQUETTE_EP}</span>
        <span>{detailEp(LIBELLE_EP[ecart.ep_saisi] ?? "", valeursEp)}</span>
      </p>
    </div>
  );
}

export type ProprietesCarteVersion = {
  /** La version servie, telle quelle. Aucune normalisation, aucune revalidation. */
  version: Record<string, unknown>;
  /** Vrai pour la plus recente. Le badge porte le MOT, jamais une seule couleur. */
  enCours: boolean;
  /** Le nom du magasin de provenance, resolu par l'appelant depuis l'amorcage. */
  nomDuMagasin: string;
  /** Ce que l'appelant place sous la correction : la photo, l'impression. */
  children?: React.ReactNode;
};

export function CarteVersion({
  version,
  enCours,
  nomDuMagasin,
  children,
}: ProprietesCarteVersion) {
  const numero = nombre(version, "version") ?? 0;
  const remplacee = nombre(version, "supersede");
  const motif = texte(version, "motif_revision");
  const type = LIBELLE_TYPE[texte(version, "type_revision")] ?? "";
  const source = LIBELLE_SOURCE[texte(version, "source")] ?? "";
  const prescripteur = texte(version, "prescripteur");
  const prescrite = texte(version, "date_prescription");
  const creeeLe = texte(version, "created_at");
  const par = texte(version, "created_par");

  const entete = [source, prescripteur, prescriteLe(formaterDateCourte(prescrite))]
    .filter((morceau) => morceau !== "")
    .join(SEPARATEUR_RELECTURE);

  const origine = [
    remplacee === null ? "" : remplaceLaVersion(remplacee),
    motif === "" ? "" : motifDit(motif),
  ]
    .filter((morceau) => morceau !== "")
    .join(SEPARATEUR_RELECTURE);

  return (
    <article
      // Le lien `Remplace la version 2` defile jusqu'a cette carte ET lui donne
      // le focus : `tabIndex={-1}` la rend focalisable au programme sans
      // l'ajouter a l'ordre de tabulation, qui appartient aux controles.
      id={`version-${String(numero)}`}
      tabIndex={-1}
      data-testid={`version-${String(numero)}`}
      className="rounded-lg border border-border p-6"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold tabular-nums">
          {titreDeVersion(numero, formaterDateCourte(creeeLe))}
        </h2>
        <div className="flex flex-wrap gap-2">
          {/*
            Le badge dit l'ETAT avec un mot. Une version remplacee n'est pas une
            erreur, donc aucune variante d'alerte n'est employee ici — et la
            phase 4 n'introduit aucune couleur (17.3).
          */}
          <Badge variant="outline">{enCours ? BADGE_EN_COURS : BADGE_REMPLACEE}</Badge>
          {type === "" ? null : <Badge variant="outline">{type}</Badge>}
        </div>
      </div>

      {entete === "" ? null : (
        <p className="mt-1 text-sm text-muted-foreground">{entete}</p>
      )}

      {origine === "" ? null : (
        <p className="mt-1 text-sm text-muted-foreground">
          {remplacee === null ? null : (
            <a
              className="underline underline-offset-4"
              href={`#version-${String(remplacee)}`}
              onClick={(evenement) => {
                // DEFILER NE SUFFIT PAS : le lecteur au clavier doit ARRIVER
                // sur la carte, sans quoi il defile la page sans deplacer son
                // point de lecture (25.4).
                const cible = document.getElementById(`version-${String(remplacee)}`);
                if (cible !== null) {
                  evenement.preventDefault();
                  cible.scrollIntoView();
                  cible.focus();
                }
              }}
            >
              {remplaceLaVersion(remplacee)}
            </a>
          )}
          {motif === "" ? null : (
            <span>
              {remplacee === null ? "" : SEPARATEUR_RELECTURE}
              {motifDit(motif)}
            </span>
          )}
        </p>
      )}

      <BlocCorrection
        className="mt-4 text-base"
        od={oeilDeLaVersion(version, "od")}
        og={oeilDeLaVersion(version, "og")}
        ecart={ecartDeLaVersion(version)}
      />

      {creeeLe === "" ? null : (
        <p className="mt-4 text-xs text-muted-foreground">
          {/*
            LA PROVENANCE, jamais un filtre (D-4a) : un gerant qui voit le
            client voit tout son historique, quel que soit le comptoir qui l'a
            saisi.
          */}
          {saisieAu(nomDuMagasin, par, formaterDateHeure(creeeLe))}
        </p>
      )}

      {children}
    </article>
  );
}

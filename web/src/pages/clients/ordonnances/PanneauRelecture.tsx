import { LigneDeCorrection } from "./LigneDeCorrection";
import { enMilliemes, rendreMilliemes, transposer } from "./optique";
import {
  ETIQUETTE_EP,
  ETIQUETTE_SAISI_POSITIF,
  EP_BINOCULAIRE,
  EP_LES_DEUX,
  EP_MONOCULAIRE,
  LIGNE_CONVENTION,
  SEPARATEUR_RELECTURE,
  SOURCE_MEDICALE,
  SOURCE_OPTICIEN,
  TITRE_RELECTURE,
  UNITE_MM,
  detailEp,
  pointsAVerifier,
  sommeEp,
} from "./messages";
import {
  decimalesDuPas,
  bornesDeLecartPupillaire,
  type BornesServies,
  type Ordonnance,
} from "./verifier";

/**
 * Le panneau de relecture — **le jugement central de cet ecran, et il est
 * signale comme tel.**
 *
 * Un dialogue de confirmation qui restituerait les memes chiffres dans la meme
 * disposition demanderait au lecteur de **comparer une chose a elle-meme**, et
 * serait clique au travers. Relire dans une **autre notation** est le seul
 * mecanisme de cet ecran qui attrape reellement `90` tape pour `9` : aucune
 * borne ne le refuse, aucun validateur ne le voit, et un axe de 90 saisi pour
 * 9 sort une paire de verres fausse.
 *
 * Le panneau rend donc la prescription dans **la notation du papier** — une
 * phrase continue, avec la parenthese cylindre-axe — quand la grille, elle, est
 * quatre cases alignees. **C'est la difference de FORME qui fait relire**, et
 * c'est elle que le test mesure, pas la presence des chiffres.
 *
 * Il rend **en continu**, a cote du papier, et non a la soumission : le moment
 * ou une comparaison evite une erreur est *pendant* la saisie.
 *
 * Deux details qui ne sont pas cosmetiques :
 *
 * - **Formulaire vide, le panneau rend ses intitules sans valeurs** plutot que
 *   de disparaitre. Un panneau qui apparait a mi-frappe deplace la mise en page
 *   sous les doigts de quelqu'un qui tape en lisant du papier.
 * - **Zero avertissement ne rend AUCUNE ligne**, et surtout pas « 0 point à
 *   vérifier » : un compteur a zero est du bruit permanent, et le bruit est
 *   exactement ce qui fait cesser de lire la onzieme remarque.
 */
export type ProprietesPanneauRelecture = {
  valeur: Ordonnance;
  bornes: BornesServies;
  /** Le nombre d'AVERTISSEMENTS en cours. Les refus ne se comptent pas ici. */
  avertissements: number;
  /** Le nom du magasin qui enregistre, pour la ligne de provenance. */
  nomDuMagasin?: string;
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

export function PanneauRelecture({
  valeur,
  bornes,
  avertissements,
  nomDuMagasin = "",
}: ProprietesPanneauRelecture) {
  // CE QUI SERA STOCKE : toujours du cylindre negatif, quelle que soit la
  // bascule. Sous `positif`, le panneau montre les deux — l'opticien voit ce
  // qu'il a tape ET ce qui partira.
  const enPositif = valeur.notation === "positif";
  const stocke = enPositif ? transposerLesDeuxYeux(valeur, bornes) : valeur;

  const decimalesEp = decimalesDuPas(bornesDeLecartPupillaire(bornes).pas);
  const od = enMilliemes(valeur.ep_mono_od);
  const og = enMilliemes(valeur.ep_mono_og);
  const somme = od === null || og === null ? "" : rendreMilliemes(od + og, decimalesEp);

  const valeursEp = [
    valeur.ep_binoculaire === "" ? "" : `${valeur.ep_binoculaire} ${UNITE_MM}`,
    valeur.ep_mono_od === "" ? "" : `OD ${valeur.ep_mono_od} ${UNITE_MM}`,
    valeur.ep_mono_og === "" ? "" : `OG ${valeur.ep_mono_og} ${UNITE_MM}`,
  ]
    .filter((morceau) => morceau !== "")
    .join(SEPARATEUR_RELECTURE);

  const provenance = [
    LIBELLE_SOURCE[valeur.source] ?? "",
    valeur.prescripteur,
    valeur.date_prescription,
    nomDuMagasin,
  ]
    .filter((morceau) => morceau !== "")
    .join(SEPARATEUR_RELECTURE);

  return (
    <aside
      data-testid="panneau-relecture"
      className="flex w-[320px] shrink-0 flex-col gap-3 self-start rounded-lg border border-border p-4"
    >
      <h2 className="text-lg font-semibold">{TITRE_RELECTURE}</h2>

      {avertissements === 0 ? null : (
        <p role="status" className="text-sm text-foreground">
          {pointsAVerifier(avertissements)}
        </p>
      )}

      {enPositif ? (
        <div className="flex flex-col gap-1 border-b border-border pb-3">
          <p className="text-xs text-muted-foreground">{ETIQUETTE_SAISI_POSITIF}</p>
          <LigneDeCorrection
            oeil="OD"
            sphere={valeur.sphere_od}
            cylindre={valeur.cylindre_od}
            axe={valeur.axe_od}
            addition={valeur.addition_od}
            className="text-lg font-semibold"
          />
          <LigneDeCorrection
            oeil="OG"
            sphere={valeur.sphere_og}
            cylindre={valeur.cylindre_og}
            axe={valeur.axe_og}
            addition={valeur.addition_og}
            className="text-lg font-semibold"
          />
        </div>
      ) : null}

      <LigneDeCorrection
        oeil="OD"
        sphere={stocke.sphere_od}
        cylindre={stocke.cylindre_od}
        axe={stocke.axe_od}
        addition={stocke.addition_od}
        className="text-lg font-semibold"
      />
      <LigneDeCorrection
        oeil="OG"
        sphere={stocke.sphere_og}
        cylindre={stocke.cylindre_og}
        axe={stocke.axe_og}
        addition={stocke.addition_og}
        className="text-lg font-semibold"
      />

      <p className="flex items-baseline gap-2 text-sm tabular-nums">
        <span className="font-semibold">{ETIQUETTE_EP}</span>
        <span>{detailEp(LIBELLE_EP[valeur.ep_saisi] ?? "", valeursEp)}</span>
        {somme === "" ? null : (
          <span className="text-muted-foreground">({sommeEp(somme)})</span>
        )}
      </p>

      {provenance === "" ? null : (
        <p className="text-sm text-muted-foreground">{provenance}</p>
      )}

      <p className="text-xs text-muted-foreground">{LIGNE_CONVENTION}</p>
    </aside>
  );
}

/** Les deux yeux transposes d'un coup — la meme fonction pure que la bascule. */
function transposerLesDeuxYeux(valeur: Ordonnance, bornes: BornesServies): Ordonnance {
  const od = transposer(
    { sphere: valeur.sphere_od, cylindre: valeur.cylindre_od, axe: valeur.axe_od },
    bornes.axe,
  );
  const og = transposer(
    { sphere: valeur.sphere_og, cylindre: valeur.cylindre_og, axe: valeur.axe_og },
    bornes.axe,
  );
  return {
    ...valeur,
    sphere_od: od.sphere,
    cylindre_od: od.cylindre,
    axe_od: od.axe,
    sphere_og: og.sphere,
    cylindre_og: og.cylindre,
    axe_og: og.axe,
  };
}

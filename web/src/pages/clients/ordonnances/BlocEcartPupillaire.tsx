import { ChampNombre } from "@/champs/ChampNombre";
import type { ReglesNombre } from "@/champs/nombres";

import type { RemarquesDuChamp } from "./GrilleOdOg";
import { enMilliemes, rendreMilliemes } from "./optique";
import {
  CHAMP_EP,
  EP_BINOCULAIRE,
  EP_LES_DEUX,
  EP_MONOCULAIRE,
  LABEL_EP_BINOCULAIRE,
  LEGENDE_EP,
  OEIL_DROIT,
  OEIL_GAUCHE,
  REGLE_EP,
  SUJET_EP,
  UNITE_MM,
  labelDeGrille,
  sommeEp,
} from "./messages";
import {
  bornesDeLecartPupillaire,
  decimalesDuPas,
  presentationDe,
  type BornesServies,
  type EpSaisi,
  type Ordonnance,
} from "./verifier";

/**
 * L'ecart pupillaire — un `radiogroup` qui ECRIT `ep_saisi`, et trois champs.
 *
 * **La forme est stockee, jamais deduite de ce qui est nul** (04-RESEARCH.md
 * 3.2). Deduire « monoculaire » de deux colonnes remplies confondrait une
 * mesure monoculaire avec un binoculaire qu'on aurait divise.
 *
 * **La phrase que la recherche demande de trancher est RENDUE, pas commentee :**
 * on enregistre ce qui a ete saisi, la somme s'affiche comme controle, et on ne
 * calcule jamais un monoculaire. Diviser un binoculaire en deux presuppose la
 * symetrie a laquelle les verres progressifs sont exactement sensibles — et un
 * commentaire dans le code ne protege personne au comptoir.
 *
 * `somme : 62,0 mm` est donc **un affichage**. Elle n'a pas de `<label>`, elle
 * n'entre dans aucun etat range, et elle ne part jamais au serveur.
 *
 * Les deux discriminants de 20.5 sont depuis l'amendement Q4 des
 * **avertissements** : ils n'empechent pas l'enregistrement, et ils ne posent
 * pas `aria-invalid` — c'est `ChampNombre` qui tient ce contrat, pas ce
 * fichier, et c'est pour cela qu'il n'y a ici aucun attribut a lire.
 */
export type ProprietesBlocEcartPupillaire = {
  valeur: Ordonnance;
  bornes: BornesServies;
  surChamp: (champ: keyof Ordonnance, valeur: string) => void;
  surSortieDeChamp: () => void;
  surForme: (forme: EpSaisi) => void;
  remarquesDe: (champ: string) => RemarquesDuChamp;
};

const FORMES: { code: EpSaisi; libelle: string }[] = [
  { code: "binoculaire", libelle: EP_BINOCULAIRE },
  { code: "monoculaire", libelle: EP_MONOCULAIRE },
  { code: "les_deux", libelle: EP_LES_DEUX },
];

export function BlocEcartPupillaire({
  valeur,
  bornes,
  surChamp,
  surSortieDeChamp,
  surForme,
  remarquesDe,
}: ProprietesBlocEcartPupillaire) {
  const bornesEp = bornesDeLecartPupillaire(bornes);
  const decimales = decimalesDuPas(bornesEp.pas);
  const regles: ReglesNombre = { decimales };
  const presentation = presentationDe(SUJET_EP, bornesEp.pas, false);

  const avecBinoculaire = valeur.ep_saisi !== "monoculaire";
  const avecMonoculaires = valeur.ep_saisi !== "binoculaire";

  // La somme n'existe QUE si les deux monoculaires existent. C'est un controle
  // offert, et il ne remplit aucun champ.
  const od = enMilliemes(valeur.ep_mono_od);
  const og = enMilliemes(valeur.ep_mono_og);
  const somme = od === null || og === null ? null : rendreMilliemes(od + og, decimales);

  const entree = (champ: "ep_binoculaire" | "ep_mono_od" | "ep_mono_og", label: string) => {
    const remarques = remarquesDe(champ);
    return (
      <ChampNombre
        identifiant={`ord-${champ.replace(/_/g, "-")}`}
        label={label}
        labelMasque
        largeur="w-[88px]"
        valeur={valeur[champ]}
        surChangement={(saisie) => surChamp(champ, saisie)}
        surVerdict={() => surSortieDeChamp()}
        bornes={bornesEp}
        regles={regles}
        suffixe={UNITE_MM}
        presentation={presentation}
        faute={remarques.faute}
        avertissement={remarques.avertissement}
      />
    );
  };

  return (
    <fieldset
      data-testid="bloc-ecart-pupillaire"
      role="radiogroup"
      aria-labelledby="ord-ep-legende"
      className="flex flex-col gap-3"
    >
      <legend id="ord-ep-legende" className="text-sm font-medium">
        {LEGENDE_EP}
      </legend>

      <div className="flex flex-wrap items-center gap-6">
        {FORMES.map((forme) => (
          <label key={forme.code} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="ord-ep-forme"
              value={forme.code}
              checked={valeur.ep_saisi === forme.code}
              onChange={() => surForme(forme.code)}
            />
            {forme.libelle}
          </label>
        ))}
      </div>

      <div className="flex flex-wrap items-start gap-6">
        {avecBinoculaire ? entree("ep_binoculaire", LABEL_EP_BINOCULAIRE) : null}
        {avecMonoculaires
          ? entree("ep_mono_od", labelDeGrille(CHAMP_EP, OEIL_DROIT))
          : null}
        {avecMonoculaires
          ? entree("ep_mono_og", labelDeGrille(CHAMP_EP, OEIL_GAUCHE))
          : null}
        {somme === null ? null : (
          <p className="pt-2 text-sm tabular-nums text-muted-foreground">
            {sommeEp(somme)}
          </p>
        )}
      </div>

      <p className="max-w-prose text-xs text-muted-foreground">{REGLE_EP}</p>
    </fieldset>
  );
}

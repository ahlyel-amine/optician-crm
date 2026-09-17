import { useEffect, useId, useState } from "react";

import { ChevronsUpDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/**
 * `03-UI-SPEC.md` 7.5, amende le 2026-09-17 — **le selecteur de magasin des
 * droits**, en tete de la section C.
 *
 * Il REMPLACE l'ouverture ligne par ligne : le bouton `Par magasin`, sa
 * sous-liste, son etat `deplie` et le bouton `Uniformiser` qui en dependait ont
 * disparu dans le meme changement. Une seule facon de faire, pas deux — c'est
 * la decision 1 du proprietaire, prise l'ecran sous les yeux, et la
 * coexistence des deux mecanismes est precisement ce qu'elle refuse.
 *
 * **Ce n'est pas le selecteur du shell** (`layout/SelecteurMagasin.tsx`), et il
 * ne le reutilise pas : celui-la lit `useAuth()`, ecrit dans l'URL et dans
 * `localStorage`, parce qu'il est une portee de DONNEES. Celui-ci est un
 * reglage d'EDITION, local a une fiche et a une session d'edition.
 *
 * **Consequence : la selection ne persiste nulle part** — ni `localStorage`,
 * ni URL, ni contexte. La persister rendrait fausse la garantie « le defaut est
 * `Tous` » des la seconde visite, et ferait d'un choix vieux de trois jours le
 * mode dans lequel le proprietaire croit regler tous les magasins.
 */

/** Le defaut, et il est nomme autrement que `Tous les magasins` de 5.4. */
export const TOUS_LES_MAGASINS_DU_COMPTE = "Tous les magasins de ce compte";

/** Le nom accessible, distinct de celui du selecteur du shell. */
export const ETIQUETTE_SELECTEUR = "Régler les droits pour";

/**
 * La question tranchee du plan `03.1-01`. Une seule ligne a changer si elle se
 * rouvre.
 *
 * `null` veut dire `Tous`, et **CLAUDE.md #13 n'est pas amende** : le defaut
 * reste une liste uniforme sur les magasins accordes, et choisir un magasin
 * nomme EST la granularite par magasin faite surgir a la demande. Ouvrir sur un
 * magasin nomme transformerait chaque premier clic en personnalisation
 * accidentelle, donc en sous-octroi silencieux — le proprietaire croirait avoir
 * accorde partout. L'argument complet est au plan, section « la question
 * tranchee », et le resume au contrat `03-UI-SPEC.md` 7.5.
 */
export const MODE_PAR_DEFAUT: string | null = null;

/** Palier `Chaine` : au-dela, la liste se cherche au lieu de se parcourir. */
const SEUIL_DE_RECHERCHE = 10;

export type ProprietesSelecteurDeMagasinDesDroits = {
  /**
   * Les magasins **accordes a la cible**, et rien d'autre.
   *
   * Jamais `catalogue.magasins` (T-03.1-02) : le catalogue porte les magasins
   * de l'APPELANT, qui ne sont pas ceux de la cible. `magasins_accordes` est
   * deja intersecte aux deux par `services.etat_des_droits`. Offrir une portee
   * que le serveur refusera est une impasse, et proposer un magasin que la
   * cible n'a pas ferait echouer chaque clic contre `_magasins_vises`.
   */
  magasins: readonly { code: string; nom: string }[];
  /** `null` === `Tous les magasins de ce compte`. */
  choisi: string | null;
  surChoix: (code: string | null) => void;
};

export function SelecteurDeMagasinDesDroits({
  magasins,
  choisi,
  surChoix,
}: ProprietesSelecteurDeMagasinDesDroits) {
  const [ouvert, setOuvert] = useState(false);
  const etiquette = useId();
  const declencheur = useId();

  /*
    **La selection est revalidee a chaque rendu** (menace T-03.1-04).

    Retirer un magasin du compte pendant qu'il est choisi laisserait une portee
    perimee : chaque clic suivant partirait vers un magasin que la cible ne
    detient plus, echouerait contre `_magasins_vises`, et poserait une erreur
    sur chaque ligne sans rien expliquer d'utile. On retombe donc sur `Tous`,
    exactement comme 5.4 revalide le code lu dans `localStorage`.

    Dans un effet, jamais pendant le rendu : remonter un etat du parent au
    milieu du rendu de l'enfant est un avertissement React, et ici cela ferait
    diverger l'ecran de la requete qu'il s'apprete a envoyer.
  */
  const perime = choisi !== null && !magasins.some((magasin) => magasin.code === choisi);
  useEffect(() => {
    if (perime) {
      surChoix(null);
    }
  }, [perime, surChoix]);

  /*
    **Moins de deux magasins : aucun controle.** La regle de 5.4 et de 7.3 B, et
    c'est ELLE — non une revelation au survol — qui protege l'ecran de
    l'encombrement. Le cas frequent est l'affaire mono-magasin, qui ne doit rien
    gagner de cet ecran.

    Le composant est monte quand meme par `SectionDroits`, pour que l'effet de
    revalidation ci-dessus continue de tourner quand le compte tombe a un seul
    magasin.
  */
  if (magasins.length < 2) {
    return null;
  }

  const libelle =
    choisi === null
      ? TOUS_LES_MAGASINS_DU_COMPTE
      : (magasins.find((magasin) => magasin.code === choisi)?.nom ??
        TOUS_LES_MAGASINS_DU_COMPTE);

  const choisir = (code: string | null) => {
    setOuvert(false);
    surChoix(code);
  };

  return (
    <div data-testid="selecteur-droits" className="mt-3 flex items-center gap-2">
      {/*
        Un `<label>` VISIBLE, pas un `aria-label` seul : le shell monte deja un
        `combobox` de magasin, et deux controles homonymes sur un ecran sont
        ambigus a l'oeil comme au lecteur d'ecran (section 10). Le libelle porte
        le nom accessible, le declencheur porte la valeur.
      */}
      <label id={etiquette} htmlFor={declencheur} className="text-sm">
        {ETIQUETTE_SELECTEUR}
      </label>
      <Popover open={ouvert} onOpenChange={setOuvert}>
        <PopoverTrigger asChild>
          <Button
            id={declencheur}
            variant="outline"
            size="sm"
            role="combobox"
            aria-expanded={ouvert}
            aria-labelledby={etiquette}
            className="h-8 justify-between gap-2"
          >
            {libelle}
            <ChevronsUpDown aria-hidden="true" className="size-4 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-72 p-0">
          <Command>
            {magasins.length >= SEUIL_DE_RECHERCHE ? (
              <CommandInput placeholder="Chercher un magasin" />
            ) : null}
            <CommandList>
              <CommandEmpty>Aucun magasin.</CommandEmpty>
              <CommandGroup>
                <CommandItem
                  value={TOUS_LES_MAGASINS_DU_COMPTE}
                  onSelect={() => choisir(null)}
                >
                  {TOUS_LES_MAGASINS_DU_COMPTE}
                </CommandItem>
                {magasins.map((magasin) => (
                  <CommandItem
                    key={magasin.code}
                    value={magasin.nom}
                    onSelect={() => choisir(magasin.code)}
                  >
                    {magasin.nom}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}

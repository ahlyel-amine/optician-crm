import { useCallback, useEffect, useState } from "react";

import { useQueryClient } from "@tanstack/react-query";
import { ChevronsUpDown } from "lucide-react";
import { useLocation, useSearchParams } from "react-router-dom";

import { useAuth, type SelectionMagasin } from "@/auth/AuthProvider";
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
import type { Magasin } from "@/api/requetes";

import { entreePourChemin } from "./nav";

/**
 * Le selecteur de magasin : **un filtre de portee, jamais un contexte de
 * connexion** (03-UI-SPEC.md 5.4). Les phases 5, 6, 7, 8 et 10 en dependent.
 *
 * Il ne reauthentifie pas et il ne navigue pas. Trois consequences se tiennent
 * ensemble :
 *
 *   1. les options viennent de `acces.magasins`, deja restreints par le
 *      serveur, et de rien d'autre. Offrir une portee que le serveur refusera
 *      est une divulgation doublee d'une impasse (T-03-88) ;
 *   2. **un utilisateur a exactement un magasin ne voit aucun controle.** Pas
 *      de liste deroulante desactivee, pas de menu a une option : il n'y a pas
 *      de decision, donc il n'y a pas de commande. C'est la plus grosse
 *      simplification disponible et elle couvre tout le palier `Essentiel` ;
 *   3. changer de portee invalide les requetes qui portent un magasin et
 *      annonce le changement. **Cela ne change jamais de route.**
 */

export const LIBELLE_TOUS = "Tous les magasins";

/** Palier `Chaine` : au-dela, la liste se cherche au lieu de se parcourir. */
const SEUIL_DE_RECHERCHE = 10;

function libelleDeLaPortee(selection: SelectionMagasin, magasins: readonly Magasin[]): string {
  if (selection === null) {
    return LIBELLE_TOUS;
  }
  return magasins.find((magasin) => magasin.code === selection)?.nom ?? LIBELLE_TOUS;
}

/**
 * Une cle de requete « porte un magasin » si le code ou le mot y apparait.
 *
 * Le test se fait sur la cle SERIALISEE parce qu'une cle react-query est un
 * tableau de n'importe quoi : `["/api/caisse/", { magasin: "ANFA" }]` autant
 * que `["caisse", "ANFA"]`. Inspecter la forme obligerait chaque phase a
 * declarer ses cles d'une seule facon, et la premiere qui l'oublierait
 * afficherait un solde du mauvais magasin sans aucune erreur.
 *
 * Le defaut choisi est donc d'invalider un peu trop plutot qu'un peu trop peu.
 * Une requete rejouee pour rien coute un aller-retour ; une requete non
 * rejouee affiche un nombre faux.
 */
export function cleConcerneUnMagasin(cle: readonly unknown[], codes: readonly string[]): boolean {
  const serialisee = JSON.stringify(cle);
  if (serialisee === undefined) {
    return false;
  }
  if (serialisee.includes("magasin")) {
    return true;
  }
  return codes.some((code) => serialisee.includes(`"${code}"`));
}

export function SelecteurMagasin() {
  const { magasins, magasinSelectionne, choisirMagasin } = useAuth();
  const requetes = useQueryClient();
  const emplacement = useLocation();
  const [parametres, setParametres] = useSearchParams();
  const [ouvert, setOuvert] = useState(false);
  const [annonce, setAnnonce] = useState("");

  const routeAPorteeMagasin = entreePourChemin(emplacement.pathname)?.portee === "magasin";

  /**
   * L'URL l'emporte sur `localStorage` au chargement (03-UI-SPEC.md 5.4).
   *
   * Un lien partage doit ouvrir le magasin qu'il nomme, pas celui que le
   * navigateur du destinataire avait retenu. Le code est revalide contre
   * `acces.magasins` — un `?magasin=` fabrique a la main ne donne donc aucune
   * portee, et le serveur filtrerait de toute facon.
   *
   * L'effet converge : il n'ecrit que lorsque l'URL et la portee divergent, et
   * apres l'ecriture elles concordent.
   */
  useEffect(() => {
    const code = parametres.get("magasin");
    if (code === null || code === magasinSelectionne) {
      return;
    }
    if (!magasins.some((magasin) => magasin.code === code)) {
      return;
    }
    choisirMagasin(code);
  }, [choisirMagasin, magasinSelectionne, magasins, parametres]);

  const changerDePortee = useCallback(
    (selection: SelectionMagasin) => {
      setOuvert(false);
      choisirMagasin(selection);

      // Chaque cle qui porte un magasin est invalidee. Les autres ne le sont
      // pas : tout invalider ferait clignoter l'ecran entier a chaque
      // changement de portee.
      const codes = magasins.map((magasin) => magasin.code);
      void requetes.invalidateQueries({
        predicate: (requete) => cleConcerneUnMagasin(requete.queryKey, codes),
      });

      // Le miroir dans l'URL n'existe que sur une route a portee magasin : un
      // `?magasin=` traine sur le tableau de bord ne voudrait rien dire.
      if (routeAPorteeMagasin) {
        const suivants = new URLSearchParams(parametres);
        if (selection === null) {
          suivants.delete("magasin");
        } else {
          suivants.set("magasin", selection);
        }
        setParametres(suivants, { replace: true });
      }

      setAnnonce(`Magasin : ${libelleDeLaPortee(selection, magasins)}`);
    },
    [choisirMagasin, magasins, parametres, requetes, routeAPorteeMagasin, setParametres],
  );

  if (magasins.length === 0) {
    return null;
  }

  const libelle = libelleDeLaPortee(magasinSelectionne, magasins);

  // UN SEUL MAGASIN : un libelle statique, et aucun controle.
  if (magasins.length === 1) {
    return (
      <p data-testid="portee-magasin" className="text-sm text-[#52525B]">
        <span className="sr-only">Magasin : </span>
        {magasins[0].nom}
      </p>
    );
  }

  return (
    <div data-testid="portee-magasin" className="flex items-center gap-2">
      <Popover open={ouvert} onOpenChange={setOuvert}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            role="combobox"
            aria-expanded={ouvert}
            className="h-8 justify-between gap-2"
          >
            {libelle}
            <ChevronsUpDown aria-hidden="true" className="size-4 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-64 p-0">
          <Command>
            {magasins.length >= SEUIL_DE_RECHERCHE ? (
              <CommandInput placeholder="Chercher un magasin" />
            ) : null}
            <CommandList>
              <CommandEmpty>Aucun magasin.</CommandEmpty>
              <CommandGroup>
                {/* « Tous les magasins » n'existe qu'a partir de deux. */}
                <CommandItem value={LIBELLE_TOUS} onSelect={() => changerDePortee(null)}>
                  {LIBELLE_TOUS}
                </CommandItem>
                {magasins.map((magasin) => (
                  <CommandItem
                    key={magasin.code}
                    value={magasin.nom}
                    onSelect={() => changerDePortee(magasin.code)}
                  >
                    {magasin.nom}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {/* Polie : l'utilisateur vient de demander ce changement. */}
      <p data-testid="annonce-magasin" role="status" aria-live="polite" className="sr-only">
        {annonce}
      </p>
    </div>
  );
}

/**
 * L'invite de choix — ce qu'une route a portee magasin rend quand la portee
 * active est « Tous les magasins ».
 *
 * **Jamais une supposition silencieuse.** Choisir le premier magasin et
 * afficher son solde de caisse produirait un nombre faux sans aucune erreur,
 * exactement ce que la couche ORM refuse deja (T-03-89). Le prix a payer est un
 * clic ; le prix de l'autre option est une caisse qu'on croit lue.
 */
export function InviteChoixMagasin({ explication }: { explication?: string }) {
  const { magasins, choisirMagasin } = useAuth();
  const [, setParametres] = useSearchParams();

  const choisir = (code: string) => {
    choisirMagasin(code);
    const suivants = new URLSearchParams(window.location.search);
    suivants.set("magasin", code);
    setParametres(suivants, { replace: true });
  };

  return (
    <div className="max-w-prose">
      <h1 className="text-2xl font-semibold">Choisissez un magasin</h1>
      <p className="mt-4 text-sm text-[#52525B]">
        {explication ?? "Cette page est propre à chaque magasin."} Sélectionnez-en un pour
        continuer.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        {magasins.map((magasin) => (
          <Button key={magasin.code} variant="outline" onClick={() => choisir(magasin.code)}>
            {magasin.nom}
          </Button>
        ))}
      </div>
    </div>
  );
}

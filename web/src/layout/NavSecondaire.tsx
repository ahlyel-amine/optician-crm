import { NavLink } from "react-router-dom";

import { useAuth } from "@/auth/AuthProvider";
import { cn } from "@/lib/utils";

import { sousEntreesVisibles, type EntreeNav } from "./nav";

/**
 * LA NAVIGATION DE SECOND NIVEAU — une rangee de liens DANS la zone de contenu.
 *
 * `03-UI-SPEC.md` 5.3 : « Second-level navigation renders as a row of section
 * links inside the content area, **not** as a sidebar accordion — an accordion
 * at this size becomes a tree the user re-navigates on every visit. »
 *
 * Elle n'existait pas jusqu'au point de controle du plan 03-14, et son absence
 * n'etait pas cosmetique : cliquer `Parametres` menait au titre d'attente, et
 * `/parametres/comptes` — le seul ecran metier de la phase — n'etait
 * atteignable qu'en TAPANT son adresse. Un ecran inatteignable n'est pas un
 * ecran.
 *
 * **Toutes ses entrees viennent de `nav.ts`**, comme celles de la barre
 * laterale, et par le meme filtre : une entree dont le code n'est pas detenu
 * est retiree, pas grisee. La phase 9 (Personnalisation) et la phase 12
 * (Abonnement) y ajoutent leur ecran en ajoutant une DONNEE a `sousEntrees`,
 * sans toucher a ce fichier ni faire grossir la barre laterale.
 *
 * Rendue meme a une seule entree. Elle est l'ancrage de l'ecran — elle dit
 * « vous etes dans les parametres, voici ce qu'ils contiennent » — et une
 * rangee qui apparaitrait au deuxieme ecran deplacerait tout le contenu le
 * jour ou la phase 9 atterrit.
 */
export function NavSecondaire({ entree }: { entree: EntreeNav }) {
  const { permissions, utilisateur } = useAuth();
  const sous = sousEntreesVisibles(entree, {
    permissions,
    proprietaire: utilisateur?.est_proprietaire ?? false,
  });

  if (sous.length === 0) {
    return null;
  }

  return (
    <nav
      // Le nom accessible est celui de l'entree parente : un lecteur d'ecran
      // qui liste les reperes doit distinguer cette navigation de la
      // principale sans avoir a la parcourir.
      aria-label={entree.libelle}
      className="mb-6 flex gap-1 border-b border-border"
    >
      {sous.map((lien) => (
        <NavLink
          key={lien.route}
          to={lien.route}
          className={({ isActive }) =>
            cn(
              "-mb-px border-b-2 px-3 py-2 text-sm transition-colors",
              "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
              isActive
                ? "border-primary font-semibold text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )
          }
        >
          {lien.libelle}
        </NavLink>
      ))}
    </nav>
  );
}

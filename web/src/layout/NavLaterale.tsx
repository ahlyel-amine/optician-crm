import { NavLink, useLocation } from "react-router-dom";

import { useAuth } from "@/auth/AuthProvider";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

import { entreePourChemin, entreesVisibles } from "./nav";

/**
 * La barre laterale : 240px, repliable en rail de 56px.
 *
 * **Toutes ses entrees viennent de `nav.ts` et d'aucune autre source.** Un
 * `NavLink` vers une route de module ecrit ailleurs echapperait au filtrage par
 * droits ; le test de comptage de `tests/shell.test.tsx` compare les entrees
 * rendues au tableau filtre precisement pour que cela redevienne rouge.
 *
 * Une entree dont le code manque n'est pas rendue — pas d'etat grise, pas
 * d'infobulle, pas de cadenas (03-UI-SPEC.md 5.3). L'application d'un gerant
 * est genuinement plus petite.
 *
 * Dans le rail replie, le libelle devient une infobulle **et** un `aria-label`.
 * Jamais une infobulle seule : elle n'existe pas pour un lecteur d'ecran et
 * elle n'existe pas au clavier tant qu'on n'a pas devine ou pointer.
 */
export function NavLaterale() {
  const { permissions, utilisateur } = useAuth();
  const emplacement = useLocation();
  const active = entreePourChemin(emplacement.pathname);

  const entrees = entreesVisibles({
    permissions,
    proprietaire: utilisateur?.est_proprietaire ?? false,
  });

  return (
    <nav aria-label="Navigation principale" className="flex-1 overflow-y-auto p-2">
      <SidebarMenu>
        {entrees.map((entree) => {
          const Icone = entree.icone;
          const estActive = active?.route === entree.route;
          return (
            <SidebarMenuItem key={entree.route}>
              <SidebarMenuButton asChild isActive={estActive} tooltip={entree.libelle}>
                <NavLink
                  to={entree.route}
                  end={entree.route === "/"}
                  // L'infobulle du rail ne suffit pas : le nom accessible doit
                  // exister meme quand le libelle est masque.
                  aria-label={entree.libelle}
                  className={cn("entree-nav", estActive && "entree-nav-active")}
                >
                  {/* 16px, decoratives : le libelle porte deja le sens. */}
                  <Icone aria-hidden="true" className="size-4 shrink-0" />
                  <span>{entree.libelle}</span>
                </NavLink>
              </SidebarMenuButton>
            </SidebarMenuItem>
          );
        })}
      </SidebarMenu>
    </nav>
  );
}

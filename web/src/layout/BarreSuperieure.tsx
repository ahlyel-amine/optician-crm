import { useNavigate } from "react-router-dom";

import { ChevronDown } from "lucide-react";

import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SidebarTrigger } from "@/components/ui/sidebar";

/**
 * La barre superieure, 56px, fixe (03-UI-SPEC.md 5.1 et 5.2).
 *
 * L'EMPLACEMENT DE MARQUE reserve **24 par 24 px des maintenant**, vide. La
 * phase 9 y posera le logo du client (BRAND-01) et ne provoquera aucun reflux :
 * la place est deja prise. Reserver un carre vide coute une ligne aujourd'hui
 * et evite de rejouer la mise en page de toute la barre quand l'image arrive.
 *
 * L'ordre est contractuel : marque, portee de magasin, recherche. La recherche
 * garde ses 480px meme sans fournisseur enregistre, pour la meme raison.
 */
export function BarreSuperieure() {
  const { affaire, utilisateur, seDeconnecter } = useAuth();
  const naviguer = useNavigate();

  return (
    <header className="sticky top-0 z-30 flex h-14 w-full shrink-0 items-center gap-4 border-b border-border bg-background px-4">
      <SidebarTrigger className="cible-44" />

      <div className="flex min-w-0 items-center gap-2">
        {/* Le carre reserve. Vide en phase 3, image en phase 9, meme boite. */}
        <div aria-hidden="true" data-testid="emplacement-logo" className="size-6 shrink-0" />
        <span className="truncate text-sm font-semibold">
          {affaire?.raison_sociale ?? ""}
        </span>
      </div>

      {/* Le selecteur de portee et l'emplacement de recherche arrivent a la
          tache 2 de ce plan, exactement ici. */}

      <div className="ml-auto">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="h-8 gap-1">
              <span className="max-w-40 truncate">{utilisateur?.nom_complet ?? ""}</span>
              <ChevronDown aria-hidden="true" className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Mon compte</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => naviguer("/mot-de-passe")}>
              Changer mon mot de passe
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => void seDeconnecter()}>
              Se déconnecter
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { useLocation } from "react-router-dom";

import { useAuth } from "@/auth/AuthProvider";
import { Sidebar, SidebarContent, SidebarProvider } from "@/components/ui/sidebar";

import { BarreSuperieure } from "./BarreSuperieure";
import { NavLaterale } from "./NavLaterale";
import { InviteChoixMagasin } from "./SelecteurMagasin";
import { entreePourChemin } from "./nav";

/**
 * L'app shell — l'artefact a plus fort effet de levier de la phase.
 *
 * Neuf phases s'y accrochent sans redesign, donc tout ce qui est ici est un
 * contrat et non une suggestion (03-UI-SPEC.md 5).
 *
 * Trois decisions de mise en page, et leurs raisons :
 *
 *   1. **Aucune largeur maximale sur la zone de contenu.** Le tableau de stock
 *      de la phase 5 et les lignes de document de la phase 6 ont besoin de
 *      toute la fenetre. Ce sont les FORMULAIRES qui plafonnent — a 640px, via
 *      `.colonne-formulaire` — et les colonnes de lecture a 80 caracteres. Un
 *      champ de 14px etire sur 1600px est inutilisable ; un tableau tronque a
 *      1024px l'est aussi, et pour la moitie de la journee.
 *   2. **Le contenu defile seul.** La barre superieure et la barre laterale ne
 *      defilent pas : au comptoir, la portee de magasin et la navigation
 *      doivent rester atteignables sans remonter.
 *   3. **Le focus suit la route.** Sans cela, un utilisateur de lecteur d'ecran
 *      n'entend rien apres avoir clique une entree : la page a change, sa
 *      position n'a pas bouge. C'est 03-UI-SPEC.md section 10, et c'est la
 *      seule partie du clavier que vitest peut reellement affirmer.
 */

const LARGEUR_BARRE = "240px";
const LARGEUR_RAIL = "56px";

function cleDeLaBarre(identifiant: number): string {
  return `optique.barre-laterale.${identifiant}`;
}

/**
 * L'etat replie/deplie, persiste **par utilisateur**.
 *
 * Par utilisateur et non par navigateur : un poste de comptoir est partage, et
 * la preference de l'un ne doit pas s'imposer a l'autre. Meme cle de forme que
 * la preference de magasin, pour qu'il n'y ait qu'un seul motif a connaitre.
 */
function lireEtatDeLaBarre(identifiant: number | undefined): boolean {
  if (identifiant === undefined) {
    return true;
  }
  try {
    return localStorage.getItem(cleDeLaBarre(identifiant)) !== "repliee";
  } catch {
    return true;
  }
}

/**
 * Le rail automatique de 1024 a 1279px (03-UI-SPEC.md 5.6).
 *
 * En dessous de 1024px, le bloc `sidebar` bascule tout seul en tiroir
 * hors-canevas. Au-dessus de 1280px, la barre reste depliee. Entre les deux,
 * elle se replie en rail : c'est la seule chose a faire pour que le contenu
 * garde une largeur utile, et cela ne change rien d'autre.
 */
function useRailAutomatique(): boolean {
  const [serre, setSerre] = useState(false);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") {
      return;
    }
    const requete = window.matchMedia("(max-width: 1279px)");
    const surChangement = () => setSerre(requete.matches);
    surChangement();
    requete.addEventListener("change", surChangement);
    return () => requete.removeEventListener("change", surChangement);
  }, []);
  return serre;
}

export function AppShell({ children }: { children: ReactNode }) {
  const { utilisateur, magasinSelectionne } = useAuth();
  const emplacement = useLocation();
  const railAutomatique = useRailAutomatique();

  /**
   * La declaration de portee de route, appliquee (03-UI-SPEC.md 5.4).
   *
   * Quand la portee active est « Tous les magasins » et que la route en exige
   * un, la zone de contenu rend l'invite de choix — **jamais** le contenu du
   * premier magasin. Un solde de caisse affiche pour un magasin que personne
   * n'a designe est un nombre faux sans erreur, et c'est la categorie de panne
   * la plus couteuse de ce produit.
   */
  const entree = entreePourChemin(emplacement.pathname);
  const porteeManquante = entree?.portee === "magasin" && magasinSelectionne === null;

  const [depliee, setDepliee] = useState(() => lireEtatDeLaBarre(utilisateur?.id));
  const [annonce, setAnnonce] = useState("");

  const changerLetat = useCallback(
    (ouverte: boolean) => {
      setDepliee(ouverte);
      if (utilisateur === null) {
        return;
      }
      try {
        localStorage.setItem(cleDeLaBarre(utilisateur.id), ouverte ? "depliee" : "repliee");
      } catch {
        // Un navigateur en navigation privee peut refuser d'ecrire. Une
        // preference d'affichage perdue n'est pas une panne.
      }
    },
    [utilisateur],
  );

  /**
   * Le focus, et l'annonce, a chaque changement de route.
   *
   * Pas au premier rendu : un autofocus au chargement n'est demande nulle part
   * (03-UI-SPEC.md 5.7, « Autofocus : … Nowhere else »), et il volerait le
   * curseur a quelqu'un qui tape deja.
   */
  const dernierChemin = useRef(emplacement.pathname);
  useEffect(() => {
    if (dernierChemin.current === emplacement.pathname) {
      return;
    }
    dernierChemin.current = emplacement.pathname;
    const titre = document.querySelector<HTMLElement>("#contenu h1");
    if (titre === null) {
      return;
    }
    // `-1` : focalisable par programme, absent de l'ordre de tabulation. Jamais
    // un tabindex positif, nulle part.
    titre.setAttribute("tabindex", "-1");
    titre.focus();
    setAnnonce(titre.textContent ?? "");
  }, [emplacement.pathname]);

  return (
    <SidebarProvider
      className="flex-col"
      open={depliee && !railAutomatique}
      onOpenChange={changerLetat}
      style={
        {
          "--sidebar-width": LARGEUR_BARRE,
          "--sidebar-width-icon": LARGEUR_RAIL,
        } as React.CSSProperties
      }
    >
      {/*
        Le lien d'evitement est le PREMIER element de l'ordre de tabulation, et
        il devient visible au focus. `sr-only` plutot que `display: none` :
        masque visuellement, jamais retire de l'ordre de tabulation — un lien
        d'evitement inatteignable au clavier est une case cochee pour rien.
      */}
      <a
        href="#contenu"
        className="sr-only rounded-md bg-background px-4 py-2 text-sm font-semibold focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50"
      >
        Aller au contenu
      </a>

      <BarreSuperieure />

      <div className="flex w-full flex-1">
        <Sidebar
          collapsible="icon"
          className="top-14 h-[calc(100svh-3.5rem)] border-r border-border"
        >
          <SidebarContent className="bg-[#F4F4F5]">
            <NavLaterale />
          </SidebarContent>
        </Sidebar>

        {/*
          `min-w-0` : sans lui, un tableau large de la phase 5 pousserait le
          conteneur flex au lieu de defiler dans sa propre boite, et la barre
          laterale se ferait chasser hors de l'ecran.
        */}
        <div className="flex min-w-0 flex-1 flex-col">
          <main id="contenu" className="flex-1 p-6">
            {porteeManquante ? (
              <InviteChoixMagasin explication={entree?.explicationPortee} />
            ) : (
              children
            )}
          </main>
        </div>
      </div>

      {/*
        La region d'annonce polie. `sr-only` : elle ne s'affiche pas, elle se
        dit. Polie et non assertive — l'utilisateur vient de demander ce
        changement, l'interrompre serait brutal.
      */}
      <p
        data-testid="annonce-de-route"
        role="status"
        aria-live="polite"
        className="sr-only"
      >
        {annonce}
      </p>
    </SidebarProvider>
  );
}

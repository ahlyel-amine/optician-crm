import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
import { reinitialiserLeClient } from "@/api/client";
import { NAV, PLAFOND_NAV, entreesVisibles, navCompletActif } from "@/layout/nav";

/* ---------------------------------------------------------------------------
 * L'app shell — l'artefact a plus fort effet de levier de la phase 3.
 *
 * Neuf phases s'y accrochent sans redesign, donc ce fichier teste des CONTRATS
 * et non des pixels : d'ou viennent les entrees de navigation, ce qu'une entree
 * non detenue produit (rien), ce qu'un utilisateur mono-magasin voit (aucun
 * controle), et ce qu'une route a portee magasin fait quand la portee est
 * « tous » (elle demande, elle ne devine pas).
 *
 * Rappel qui vaut pour tout le fichier : le filtre de permission de l'interface
 * est un CONFORT, jamais une application de la regle. Ces tests verifient qu'un
 * noeud n'existe pas ; l'autorisation, elle, est la restriction de queryset et
 * la projection cote serveur.
 * ------------------------------------------------------------------------- */

const CATALOGUE = {
  sections: [
    {
      titre: "Caisse",
      droits: [
        {
          code: "caisse.voir",
          libelle: "Consulter la caisse",
          explication: "Voir le journal de caisse du magasin.",
        },
      ],
    },
  ],
  prerequis: { "caisse.saisir": ["caisse.voir"] },
};

/** Les huit codes du contrat de navigation, plus le droit du widget de CA. */
const TOUS_LES_CODES = [
  "client.voir",
  "stock.voir",
  "vente.voir",
  "caisse.voir",
  "fournisseur.voir",
  "rappel.voir",
  "compte.gerer",
  "dashboard.voir_ca_global",
];

const ANFA = { id: 1, code: "ANFA", nom: "Anfa" };
const MAARIF = { id: 2, code: "MAARIF", nom: "Maârif" };

function amorcageDe(options: {
  proprietaire?: boolean;
  permissions?: string[];
  magasins?: { id: number; code: string; nom: string }[];
}) {
  return {
    utilisateur: {
      id: 7,
      email: options.proprietaire ? "amine@optiqueanfa.ma" : "karim@optiqueanfa.ma",
      nom_complet: options.proprietaire ? "Amine El Fassi" : "Karim Benali",
      est_proprietaire: options.proprietaire ?? false,
      doit_changer_mot_de_passe: false,
    },
    client: { code: "anfa", raison_sociale: "Optique Anfa" },
    permissions: options.permissions ?? TOUS_LES_CODES,
    magasins: options.magasins ?? [ANFA, MAARIF],
    catalogue: CATALOGUE,
  };
}

const PROPRIETAIRE = amorcageDe({ proprietaire: true });

function json(corps: unknown, statut = 200): Response {
  return new Response(JSON.stringify(corps), {
    status: statut,
    headers: { "Content-Type": "application/json" },
  });
}

function vide(statut: number): Response {
  return new Response(null, { status: statut });
}

function poserLesReponses(table: Record<string, () => Response | Promise<Response>>): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (requete: Request) => {
      const chemin = new URL(requete.url, "http://localhost").pathname;
      const reponse = table[chemin];
      if (!reponse) {
        throw new Error(`Aucune reponse de test posee pour ${chemin}`);
      }
      return reponse();
    }),
  );
}

/**
 * Le shell complet, monte sur l'application reelle.
 *
 * On monte `App` et non `AppShell` isole : ce qui est verifie ici est justement
 * que rien, nulle part dans l'arbre reel, ne rend une entree de navigation en
 * dehors du tableau `NAV`. Un montage isole ne pourrait pas le dire.
 */
function rendreShell(amorcage: unknown = PROPRIETAIRE, chemin = "/") {
  poserLesReponses({
    "/api/auth/csrf/": () => vide(204),
    "/api/auth/moi/": () => json(amorcage),
  });
  const requetes = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const rendu = render(
    <MemoryRouter initialEntries={[chemin]}>
      <QueryClientProvider client={requetes}>
        <App />
      </QueryClientProvider>
    </MemoryRouter>,
  );
  return { ...rendu, requetes };
}

function barreDeNavigation(): HTMLElement {
  return screen.getByRole("navigation", { name: "Navigation principale" });
}

beforeEach(() => {
  localStorage.clear();
  reinitialiserLeClient();
  document.cookie = "csrftoken=jeton-de-test; path=/";
  // `matchMedia` vient de tests/setup.ts, en mode « large ecran ».
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

/* =========================================================================
 * Le tableau de navigation — le contrat de neuf phases
 * ======================================================================= */

describe("le contrat de navigation", () => {
  it("compte exactement huit entrees, sous le plafond dur de neuf", () => {
    // Un dixieme module entre dans une section existante ou en remplace une.
    // Il n'obtient pas une dixieme ligne : ce test est la ou cette decision est
    // gardee, parce que c'est le seul endroit qui redeviendra rouge.
    expect(NAV).toHaveLength(8);
    expect(NAV.length).toBeLessThanOrEqual(PLAFOND_NAV);
    expect(PLAFOND_NAV).toBe(9);
  });

  it("transcrit les routes et les codes du contrat, dans l'ordre", () => {
    expect(NAV.map((entree) => [entree.route, entree.code])).toEqual([
      ["/", null],
      ["/clients", "client.voir"],
      ["/stock", "stock.voir"],
      ["/ventes", "vente.voir"],
      ["/caisse", "caisse.voir"],
      ["/achats", "fournisseur.voir"],
      ["/rappels", "rappel.voir"],
      ["/parametres", "compte.gerer"],
    ]);
  });

  it("une entree non construite est absente en production et presente derriere le drapeau", () => {
    const contexte = { permissions: TOUS_LES_CODES, proprietaire: true };
    const enProduction = entreesVisibles({ ...contexte, complet: false });
    const enDensitePleine = entreesVisibles({ ...contexte, complet: true });

    // Le drapeau existe pour que la mise en page soit exercee A PLEINE DENSITE
    // des la phase 3, et que personne ne decouvre en phase 8 que huit entrees
    // debordent.
    expect(enDensitePleine).toHaveLength(8);
    expect(enProduction.length).toBeLessThan(enDensitePleine.length);
    expect(enProduction.every((entree) => entree.disponible)).toBe(true);
  });

  it("le drapeau ne s'arme qu'en developpement, et seulement a « 1 »", () => {
    vi.stubEnv("VITE_NAV_COMPLET", "");
    expect(navCompletActif()).toBe(false);

    vi.stubEnv("VITE_NAV_COMPLET", "1");
    expect(navCompletActif()).toBe(true);

    // Une construction de production n'expose JAMAIS un module non construit,
    // meme si la variable trainait dans l'environnement de construction.
    vi.stubEnv("DEV", false);
    expect(navCompletActif()).toBe(false);
  });

  it("une entree dont le code manque est retiree, sans aucune trace", () => {
    const visibles = entreesVisibles({
      permissions: ["client.voir"],
      proprietaire: false,
      complet: true,
    });
    expect(visibles.map((entree) => entree.route)).toEqual(["/", "/clients"]);
  });

  it("le proprietaire garde Parametres meme si le code ne lui est pas liste", () => {
    const visibles = entreesVisibles({ permissions: [], proprietaire: true, complet: true });
    expect(visibles.map((entree) => entree.route)).toEqual(["/", "/parametres"]);
  });
});

/* =========================================================================
 * Le rendu de la navigation — rien hors du tableau
 * ======================================================================= */

describe("la navigation rendue", () => {
  it("ne rend aucune entree en dehors du tableau NAV", async () => {
    rendreShell();
    await screen.findByRole("navigation", { name: "Navigation principale" });

    const attendues = entreesVisibles({
      permissions: TOUS_LES_CODES,
      proprietaire: true,
      complet: navCompletActif(),
    });
    const rendues = within(barreDeNavigation()).getAllByRole("link");

    // Comptage, pas echantillonnage : si un composant se met a rendre une
    // neuvieme entree « juste pour ce module-la », ce nombre le dit.
    expect(rendues).toHaveLength(attendues.length);
    expect(rendues.map((lien) => lien.getAttribute("href"))).toEqual(
      attendues.map((entree) => entree.route),
    );
  });

  it("l'application d'un gerant est genuinement plus petite que celle du proprietaire", async () => {
    const { unmount } = rendreShell();
    await screen.findByRole("navigation", { name: "Navigation principale" });
    const chezLeProprietaire = within(barreDeNavigation()).getAllByRole("link").length;
    unmount();

    rendreShell(amorcageDe({ permissions: ["client.voir"] }));
    await screen.findByRole("navigation", { name: "Navigation principale" });
    const chezLeGerant = within(barreDeNavigation()).getAllByRole("link").length;

    expect(chezLeGerant).toBeLessThan(chezLeProprietaire);
  });

  it("une entree dont le code manque ne produit AUCUN noeud DOM", async () => {
    rendreShell(amorcageDe({ permissions: ["client.voir"] }));
    await screen.findByRole("navigation", { name: "Navigation principale" });

    const navigation = barreDeNavigation();
    // Ni libelle, ni etat desactive, ni infobulle, ni cadenas. Un element inerte
    // apprend a un gerant qu'un module existe et qu'il n'y a pas droit : c'est
    // une divulgation (T-03-90), et c'est un appel au support.
    expect(within(navigation).queryByText("Caisse")).toBeNull();
    expect(within(navigation).queryByText("Stock")).toBeNull();
    expect(navigation.querySelector("[disabled]")).toBeNull();
    expect(navigation.querySelector("[aria-disabled]")).toBeNull();
    expect(navigation.querySelector("[title]")).toBeNull();
  });
});

/* =========================================================================
 * Reperes, lien d'evitement, focus — 03-UI-SPEC.md section 10
 * ======================================================================= */

describe("la mise en page et le clavier", () => {
  it("expose exactement un header, un nav et un main, dans cet ordre", async () => {
    const { container } = rendreShell();
    await screen.findByRole("navigation", { name: "Navigation principale" });

    expect(container.querySelectorAll("header")).toHaveLength(1);
    expect(container.querySelectorAll("nav")).toHaveLength(1);
    expect(container.querySelectorAll("main")).toHaveLength(1);

    const reperes = Array.from(container.querySelectorAll("header, nav, main")).map(
      (noeud) => noeud.tagName,
    );
    expect(reperes).toEqual(["HEADER", "NAV", "MAIN"]);
  });

  it("le lien d'evitement ouvre l'ordre de tabulation et devient visible au focus", async () => {
    const { container } = rendreShell();
    await screen.findByRole("navigation", { name: "Navigation principale" });

    const evitement = screen.getByRole("link", { name: "Aller au contenu" });
    const focalisables = Array.from(
      container.querySelectorAll<HTMLElement>("a[href], button, input, select, textarea"),
    );
    expect(focalisables[0]).toBe(evitement);
    expect(evitement.getAttribute("href")).toBe("#contenu");
    expect(container.querySelector("#contenu")).not.toBeNull();

    // Visible au focus : la classe `sr-only` est retiree par `focus:not-sr-only`,
    // jamais par un `display: none` qui le sortirait de l'ordre de tabulation.
    expect(evitement.className).toContain("sr-only");
    expect(evitement.className).toContain("focus:not-sr-only");
  });

  it("aucun tabindex positif nulle part dans le shell", async () => {
    const { container } = rendreShell();
    await screen.findByRole("navigation", { name: "Navigation principale" });

    const positifs = Array.from(container.querySelectorAll("[tabindex]")).filter(
      (noeud) => Number(noeud.getAttribute("tabindex")) > 0,
    );
    expect(positifs).toHaveLength(0);
  });

  it("un changement de route porte le focus sur le h1 de la nouvelle page et l'annonce", async () => {
    rendreShell();
    await screen.findByRole("navigation", { name: "Navigation principale" });

    // « Parametres » plutot que « Clients » : sans `VITE_NAV_COMPLET`, seules
    // les entrees des modules CONSTRUITS sont rendues, ce qui est exactement le
    // comportement qu'affirme la suite du contrat de navigation.
    const versParametres = within(barreDeNavigation()).getByRole("link", {
      name: "Paramètres",
    });
    fireEvent.click(versParametres);

    // Sans cela, un utilisateur de lecteur d'ecran n'entend RIEN apres avoir
    // clique une entree : la page a change, sa position n'a pas bouge.
    await waitFor(() => {
      const titre = screen.getByRole("heading", { level: 1 });
      expect(titre.textContent).toBe("Paramètres");
      expect(document.activeElement).toBe(titre);
    });
    await waitFor(() => {
      expect(screen.getByTestId("annonce-de-route").textContent).toBe("Paramètres");
    });
  });
});

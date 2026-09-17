import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
import { reinitialiserLeClient } from "@/api/client";
import { NAV, PLAFOND_NAV, entreesVisibles, navCompletActif } from "@/layout/nav";
import {
  MAX_PAR_GROUPE,
  enregistrerFournisseurDeRecherche,
  grouperResultats,
  resultatExact,
} from "@/layout/Recherche";

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

/* =========================================================================
 * Le selecteur de magasin — un filtre de portee, jamais un contexte de
 * connexion (03-UI-SPEC.md 5.4)
 * ======================================================================= */

function declencheurDePortee(): HTMLElement {
  return screen.getByRole("combobox");
}

async function ouvrirLeSelecteur(): Promise<void> {
  fireEvent.click(declencheurDePortee());
  await screen.findByRole("option", { name: "Anfa" });
}

describe("le selecteur de magasin", () => {
  it("test_perm04_les_options_viennent_des_magasins_accordes_et_de_rien_dautre", async () => {
    // Le serveur a deja restreint `acces.magasins` (plan 03-08). L'interface ne
    // doit JAMAIS offrir une portee que le serveur refusera : une option
    // Californie ici serait une divulgation (T-03-88) doublee d'une impasse.
    rendreShell(amorcageDe({ proprietaire: true, magasins: [ANFA, MAARIF] }));
    await screen.findByRole("navigation", { name: "Navigation principale" });
    await ouvrirLeSelecteur();

    const options = screen.getAllByRole("option").map((option) => option.textContent);
    expect(options).toEqual(["Tous les magasins", "Anfa", "Maârif"]);
    expect(document.body.textContent).not.toContain("Californie");
  });

  it("un utilisateur a UN SEUL magasin ne voit aucun controle, seulement un libelle", async () => {
    rendreShell(amorcageDe({ magasins: [ANFA] }));
    await screen.findByRole("navigation", { name: "Navigation principale" });

    const portee = screen.getByTestId("portee-magasin");
    expect(portee.textContent).toContain("Anfa");
    // Il n'y a pas de decision, donc il n'y a pas de commande. Ni liste
    // deroulante desactivee, ni menu a une option : cela couvre tout le palier
    // Essentiel et la plupart des gerants, qui ne rencontrent jamais ce
    // controle.
    expect(portee.querySelector("button")).toBeNull();
    expect(portee.querySelector("select")).toBeNull();
    expect(portee.querySelector('[role="combobox"]')).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByText("Tous les magasins")).toBeNull();
  });

  it("« Tous les magasins » n'apparait qu'a partir de deux magasins detenus", async () => {
    rendreShell(amorcageDe({ proprietaire: true, magasins: [ANFA, MAARIF] }));
    await screen.findByRole("navigation", { name: "Navigation principale" });
    await ouvrirLeSelecteur();

    expect(screen.getByRole("option", { name: "Tous les magasins" })).toBeTruthy();
  });

  it("changer de portee invalide les requetes du magasin, l'annonce, et NE CHANGE PAS de route", async () => {
    const { requetes } = rendreShell(amorcageDe({ proprietaire: true }), "/parametres/comptes");
    await screen.findByRole("navigation", { name: "Navigation principale" });

    const clePortante = ["/api/caisse/journal/", { magasin: "ANFA" }];
    const cleNeutre = ["/api/comptes/"];
    requetes.setQueryData(clePortante, { solde: "0,00" });
    requetes.setQueryData(cleNeutre, []);

    const routeAvant = screen.getByTestId("destination").textContent;

    await ouvrirLeSelecteur();
    fireEvent.click(screen.getByRole("option", { name: "Anfa" }));

    await waitFor(() => {
      expect(requetes.getQueryState(clePortante)?.isInvalidated).toBe(true);
    });
    // Une requete sans magasin dans sa cle n'a aucune raison d'etre rejouee :
    // tout invalider ferait clignoter l'ecran entier a chaque changement de
    // portee.
    expect(requetes.getQueryState(cleNeutre)?.isInvalidated).toBe(false);

    // La portee est un FILTRE. Elle ne navigue pas, elle ne reauthentifie pas.
    expect(screen.getByTestId("destination").textContent).toBe(routeAvant);
    await waitFor(() => {
      expect(screen.getByTestId("annonce-magasin").textContent).toBe("Magasin : Anfa");
    });
  });

  it("l'URL l'emporte sur la preference memorisee au chargement", async () => {
    // Un lien partage doit ouvrir le magasin qu'il nomme, pas celui que le
    // navigateur du destinataire avait retenu. C'est ce qui rend un lien
    // reellement partageable et un rechargement stable.
    localStorage.setItem("optique.magasin.7", "ANFA");
    rendreShell(amorcageDe({ proprietaire: true }), "/caisse?magasin=MAARIF");
    await screen.findByRole("navigation", { name: "Navigation principale" });

    await waitFor(() => {
      expect(declencheurDePortee().textContent).toContain("Maârif");
    });
  });
});

/* =========================================================================
 * La portee de route — demander, jamais deviner (03-UI-SPEC.md 5.4)
 * ======================================================================= */

describe("la portee de route", () => {
  it("une route a portee magasin DEMANDE lequel au lieu de deviner", async () => {
    // Choisir silencieusement le premier magasin et afficher son solde de
    // caisse est le « nombre faux sans erreur » que la couche ORM refuse deja
    // (T-03-89). L'interface le refuse aussi.
    rendreShell(amorcageDe({ proprietaire: true }), "/caisse");
    await screen.findByRole("navigation", { name: "Navigation principale" });

    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Choisissez un magasin",
    );
    expect(screen.queryByTestId("destination")).toBeNull();
    expect(screen.getByRole("button", { name: "Anfa" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Maârif" })).toBeTruthy();
  });

  it("choisir dans l'invite rend enfin le contenu de la route", async () => {
    rendreShell(amorcageDe({ proprietaire: true }), "/caisse");
    await screen.findByRole("navigation", { name: "Navigation principale" });

    fireEvent.click(screen.getByRole("button", { name: "Anfa" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Caisse");
    });
    expect(screen.getByTestId("destination").textContent).toBe("/caisse");
  });

  it("une route a portee multi ne demande rien", async () => {
    rendreShell(amorcageDe({ proprietaire: true }), "/parametres");
    await screen.findByRole("navigation", { name: "Navigation principale" });

    expect(screen.queryByText("Choisissez un magasin")).toBeNull();
    expect(screen.getByTestId("destination").textContent).toBe("/parametres");
  });
});

/* =========================================================================
 * L'emplacement de recherche (03-UI-SPEC.md 5.5)
 * ======================================================================= */

describe("l'emplacement de recherche", () => {
  it("conserve ses 480px sans fournisseur enregistre, et ne rend aucun champ", async () => {
    rendreShell();
    await screen.findByRole("navigation", { name: "Navigation principale" });

    // La phase 3 n'a rien a chercher. L'emplacement existe quand meme, pour que
    // la barre superieure ne se reflue pas quand la phase 4 enregistre son
    // premier fournisseur.
    const emplacement = screen.getByTestId("emplacement-recherche");
    expect(emplacement.className).toContain("480");
    expect(emplacement.querySelector("input")).toBeNull();
    expect(emplacement.querySelector("button")).toBeNull();
  });

  it("regroupe par type et n'en garde que cinq par groupe", () => {
    const beaucoup = Array.from({ length: 8 }, (_, rang) => ({
      id: `c${rang}`,
      groupe: "Clients",
      libelle: `Client ${rang}`,
      route: `/clients/${rang}`,
    }));
    const groupes = grouperResultats([
      ...beaucoup,
      { id: "a1", groupe: "Articles", libelle: "Monture", route: "/stock/1" },
    ]);

    expect(groupes.map((groupe) => groupe.nom)).toEqual(["Clients", "Articles"]);
    expect(groupes[0].resultats).toHaveLength(MAX_PAR_GROUPE);
    expect(MAX_PAR_GROUPE).toBe(5);
  });

  it("un resultat marque exact court-circuite la liste", () => {
    const resultats = [
      { id: "a1", groupe: "Articles", libelle: "Autre", route: "/stock/1" },
      {
        id: "a2",
        groupe: "Articles",
        libelle: "REF-4471",
        route: "/stock/2",
        correspondance_exacte: true,
      },
    ];
    // Une douchette clavier tape une reference puis envoie Entree. Cela doit
    // atterrir sur l'article, sans liste intermediaire (STOCK-07, phase 5).
    expect(resultatExact(resultats)?.route).toBe("/stock/2");
    expect(resultatExact(resultats.slice(0, 1))).toBeUndefined();
  });

  it("la requete part BRUTE : aucune normalisation cliente", async () => {
    const recues: string[] = [];
    const retirer = enregistrerFournisseurDeRecherche({
      nom: "Clients",
      chercher: async (requete) => {
        recues.push(requete);
        return [];
      },
    });
    try {
      rendreShell();
      await screen.findByRole("navigation", { name: "Navigation principale" });

      fireEvent.click(screen.getByRole("button", { name: "Recherche" }));
      const champ = await screen.findByPlaceholderText("Recherche");
      // Arabe, accents, casse : la normalisation est cote serveur (CLIENT-10).
      // Un `toLowerCase` ou un retrait d'accent ici altererait une saisie arabe
      // ou une reference de douchette (T-03-92).
      fireEvent.change(champ, { target: { value: "Bénali محمد" } });

      await waitFor(() => expect(recues).toContain("Bénali محمد"), { timeout: 2000 });
    } finally {
      retirer();
    }
  });
});

/* =========================================================================
 * La feuille d'impression (03-UI-SPEC.md 8.4)
 *
 * Elle se verifie en lisant le fichier : jsdom ne met pas en page, ne pagine
 * pas et n'a pas de media `print`. Ce qui EST verifiable — et ce que la phase 9
 * heritera — c'est que la geometrie de page existe, que le chrome est masque,
 * et qu'aucun gabarit de document ne s'est glisse ici.
 * ======================================================================= */

describe("la feuille d'impression", () => {
  // `process.cwd()` et non `import.meta.url` : sous vitest, l'URL d'un module
  // est une URL http servie par vite, que `node:fs` ne sait pas lire. Meme
  // motif que tests/format.test.ts.
  const feuille = readFileSync(resolve(process.cwd(), "src/print.css"), "utf8");

  it("pose la geometrie A4 et repete les en-tetes de tableau", () => {
    expect(feuille).toContain("@page");
    expect(feuille).toContain("size: A4");
    expect(feuille).toContain("margin: 15mm");
    // Sans cela, la page 2 d'un tableau est une colonne de nombres sans
    // legende.
    expect(feuille).toContain("display: table-header-group");
  });

  it("masque le chrome du shell", () => {
    for (const repere of ["header", "nav", '[data-slot="sidebar"]', '[data-sonner-toaster]']) {
      expect(feuille).toContain(repere);
    }
  });

  it("ne contient aucun gabarit de document ni ressource externe", () => {
    // La phase 6 possede le modele de document, la phase 9 l'impression. Ce qui
    // est livre ici est la COUTURE : aucune mise en forme d'un document
    // commercial, aucun bloc d'adresse, aucun tableau de lignes.
    expect(feuille.toLowerCase()).not.toMatch(/factur|devis|avoir\s*:/);
    // Aucune ressource externe : une police ou une image telechargee a
    // l'impression ne se charge pas toujours, et le document sort faux.
    expect(feuille).not.toContain("url(");
  });

  it("n'imprime rien en couleur de fond, et ne retire aucun anneau de focus", () => {
    // `print-color-adjust: exact` n'est declare nulle part : les documents sont
    // noirs sur blanc pour que le budget toner d'une boutique survive.
    expect(feuille).not.toMatch(/^\s*print-color-adjust/m);
    expect(feuille).not.toMatch(/outline:\s*none/);
  });
});

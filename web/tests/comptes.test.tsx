import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
import { reinitialiserLeClient } from "@/api/client";

/* ---------------------------------------------------------------------------
 * `Comptes et droits` — la surface difficile de la phase 3.
 *
 * Vingt et une permissions, N magasins, et un opticien qui ne doit pas avoir
 * besoin de formation. `03-UI-SPEC.md` 7.1 nomme les trois conceptions naives
 * qui echouent ici ; ce fichier teste que la quatrieme est bien celle qui est
 * livree.
 *
 * Ce qui est verifie ici, et qui merite d'etre dit une fois pour tout le
 * fichier :
 *
 *   - **la copie exacte** de l'etat vide, des deux dialogues destructifs et de
 *     la ligne de temporalite. Une phrase manquante dans un dialogue destructif
 *     est un appel de support, voire une action legitime evitee a tort ;
 *   - **l'absence** de tout preset, palier, `Tout cocher` ou `Copier les droits
 *     de` — CLAUDE.md #6, et point de revue explicite ;
 *   - **l'absence au niveau du fil** : la SPA rend ce que le catalogue serveur
 *     lui donne et n'a aucune branche de filtrage. Le test du catalogue tronque
 *     est celui qui le dit ;
 *   - **le tri-etat annonce**, pas seulement dessine : `aria-checked="mixed"`.
 *
 * Rappel qui vaut pour tout le fichier : masquer une ligne dans l'interface
 * n'est pas un controle. Le catalogue pre-intersecte du plan 03-09 et le
 * service d'octroi SONT le controle.
 * ------------------------------------------------------------------------- */

const ANFA = { id: 1, code: "ANFA", nom: "Anfa" };
const MAARIF = { id: 2, code: "MAARIF", nom: "Maârif" };
const CALIFORNIE = { id: 3, code: "CALIFORNIE", nom: "Californie" };

/** Le catalogue de `/api/auth/moi/` : les 21 codes existent pour tout le monde. */
const CATALOGUE_COMPLET = {
  sections: [
    {
      titre: "Comptes",
      droits: [
        {
          code: "compte.gerer",
          libelle: "Gérer les comptes et les droits",
          explication: "Créer des comptes gérants et leur accorder des droits.",
        },
      ],
    },
  ],
  prerequis: {},
};

/**
 * Le catalogue **offrable**, celui de `GET /api/comptes/catalogue/`.
 *
 * Trois sections seulement, parce que ce fichier n'a pas besoin des sept pour
 * verifier une regle — et parce qu'un catalogue tronque est precisement ce que
 * le test d'absence exerce : la SPA rend ce qu'elle recoit, donc un catalogue
 * court produit un ecran court, sans branche cliente.
 */
function catalogueOffrable(magasins = [ANFA, MAARIF]) {
  return {
    sections: [
      {
        titre: "Stock",
        droits: [
          {
            code: "stock.voir",
            libelle: "Consulter le stock",
            explication: "Voir les articles et les quantités disponibles.",
          },
          {
            code: "stock.ajuster",
            libelle: "Ajuster le stock / inventaire",
            explication: "Corriger une quantité après un inventaire.",
          },
        ],
      },
      {
        titre: "Caisse",
        droits: [
          {
            code: "caisse.voir",
            libelle: "Consulter la caisse",
            explication: "Voir le journal de caisse du magasin.",
          },
          {
            code: "caisse.saisir",
            libelle: "Saisir en caisse",
            explication: "Enregistrer une entrée ou une sortie d'espèces.",
          },
        ],
      },
      {
        titre: "Comptes",
        droits: [
          {
            code: "compte.gerer",
            libelle: "Gérer les comptes et les droits",
            explication: "Créer des comptes gérants et leur accorder des droits.",
          },
        ],
      },
    ],
    prerequis: { "stock.ajuster": ["stock.voir"], "caisse.saisir": ["caisse.voir"] },
    magasins,
  };
}

const PROPRIETAIRE = {
  utilisateur: {
    id: 1,
    email: "amine@optiqueanfa.ma",
    nom_complet: "Amine El Fassi",
    est_proprietaire: true,
    doit_changer_mot_de_passe: false,
  },
  client: { code: "anfa", raison_sociale: "Optique Anfa" },
  permissions: ["compte.gerer"],
  magasins: [ANFA, MAARIF],
  catalogue: CATALOGUE_COMPLET,
};

/** Un gerant sans `compte.gerer` : la route doit lui repondre par le 403 pleine page. */
const GERANT_SANS_DROIT = {
  ...PROPRIETAIRE,
  utilisateur: {
    id: 9,
    email: "nadia@optiqueanfa.ma",
    nom_complet: "Nadia Chraibi",
    est_proprietaire: false,
    doit_changer_mot_de_passe: false,
  },
  permissions: ["stock.voir"],
  magasins: [ANFA],
};

function ligneProprietaire(surcharge: Record<string, unknown> = {}) {
  return {
    id: 1,
    nom_complet: "Amine El Fassi",
    email: "amine@optiqueanfa.ma",
    est_proprietaire: true,
    actif: true,
    doit_changer_mot_de_passe: false,
    derniere_connexion: "2026-09-14T08:14:00Z",
    magasins: [ANFA, MAARIF],
    nombre_de_droits: 21,
    personnalise: false,
    ...surcharge,
  };
}

function ligneKarim(surcharge: Record<string, unknown> = {}) {
  return {
    id: 2,
    nom_complet: "Karim Benali",
    email: "karim.benali@optiqueanfa.ma",
    est_proprietaire: false,
    actif: true,
    doit_changer_mot_de_passe: false,
    derniere_connexion: null,
    magasins: [ANFA],
    nombre_de_droits: 3,
    personnalise: false,
    ...surcharge,
  };
}

function json(corps: unknown, statut = 200): Response {
  return new Response(JSON.stringify(corps), {
    status: statut,
    headers: { "Content-Type": "application/json" },
  });
}

function vide(statut: number): Response {
  return new Response(null, { status: statut });
}

type Reponse = Response | Promise<Response>;
type Table = Record<string, (requete: Request) => Reponse>;

/** Les appels observes, pour les assertions « ce qui est parti sur le fil ». */
let appels: { methode: string; chemin: string; corps: unknown }[] = [];

function poserLesReponses(table: Table): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (requete: Request) => {
      const chemin = new URL(requete.url, "http://localhost").pathname;
      const clef = `${requete.method} ${chemin}`;
      const texte = ["POST", "PATCH", "PUT"].includes(requete.method)
        ? await requete.clone().text()
        : "";
      appels.push({
        methode: requete.method,
        chemin,
        corps: texte === "" ? undefined : JSON.parse(texte),
      });
      const reponse = table[clef] ?? table[chemin];
      if (!reponse) {
        throw new Error(`Aucune reponse de test posee pour ${clef}`);
      }
      return reponse(requete);
    }),
  );
}

function rendre(table: Table, chemin: string, amorcage: unknown = PROPRIETAIRE) {
  poserLesReponses({
    "/api/auth/csrf/": () => vide(204),
    "/api/auth/moi/": () => json(amorcage),
    ...table,
  });
  const requetes = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={[chemin]}>
      <QueryClientProvider client={requetes}>
        <App />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

/** La liste, montee sur l'application reelle, a sa vraie route. */
function rendreLaListe(comptes: unknown[], amorcage: unknown = PROPRIETAIRE) {
  return rendre(
    { "/api/comptes/": () => json(comptes) },
    "/parametres/comptes",
    amorcage,
  );
}

beforeEach(() => {
  appels = [];
  localStorage.clear();
  reinitialiserLeClient();
  document.cookie = "csrftoken=jeton-de-test; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

/* =========================================================================
 * 7.2 — la liste des comptes
 * ======================================================================= */

describe("la liste des comptes", () => {
  it("rend l'etat vide avec sa phrase sur les vendeurs, en entier", async () => {
    // La seconde phrase pre-empte le malentendu le plus probable de
    // CLAUDE.md #6 — « il me faut un compte par vendeur » — et elle coute une
    // ligne au lieu d'un appel telephonique. Un etat vide qui dirait seulement
    // « Aucun compte » laisserait l'opticien creer huit comptes inutiles.
    rendreLaListe([]);

    expect(
      await screen.findByRole("heading", { name: "Aucun compte gérant" }),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Créez un compte pour chaque personne qui tient un magasin. Les vendeurs n'ont pas besoin de compte — ils sont enregistrés sur la vente.",
      ),
    ).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Créer un compte gérant" }).length)
      .toBeGreaterThan(0);

    // Zero ligne rend zero colonne (plan 03-11) : un etat vide ne doit pas
    // laisser derriere lui une rangee d'en-tetes.
    expect(screen.queryByRole("columnheader")).toBeNull();
  });

  it("place la ligne du proprietaire en premier, et la marque", async () => {
    rendreLaListe([ligneProprietaire(), ligneKarim()]);

    const lignes = await screen.findAllByRole("row");
    // `lignes[0]` est la rangee d'en-tetes.
    expect(within(lignes[1]).getByText("Amine El Fassi")).toBeTruthy();
    expect(within(lignes[1]).getByText("Propriétaire")).toBeTruthy();
    expect(within(lignes[2]).getByText("Karim Benali")).toBeTruthy();
  });

  it("n'ouvre aucun editeur de droits sur le compte du proprietaire", async () => {
    // 7.7 : « No droits section is rendered at all ». Pas une section grisee,
    // pas une section en lecture seule — absente. Le proprietaire detient tout
    // par construction (`Acces` materialise, plan 03-05) : une case a cocher y
    // serait un mensonge, et un mensonge qu'on peut cliquer.
    rendre(
      {
        "/api/comptes/1/": () =>
          json({ ...ligneProprietaire(), droits: [], magasins_accordes: ["ANFA", "MAARIF"] }),
        "/api/comptes/catalogue/": () => json(catalogueOffrable()),
      },
      "/parametres/comptes/1",
    );

    expect(
      await screen.findByText(
        "Propriétaire — accès complet à tous les magasins. Ces droits ne se modifient pas.",
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("switch")).toBeNull();
    expect(screen.queryByRole("region", { name: "Droits" })).toBeNull();
  });

  it("passe par le registre de colonnes, donc un champ absent ne fait pas d'en-tete", async () => {
    // La moitie cliente de PERM-06 (plan 03-11), exercee sur le premier ecran
    // metier du produit. `champ in ligne` et rien d'autre : le serveur retire
    // la cle, l'en-tete disparait avec elle. Un `<th>` litteral serait
    // inconditionnel, et c'est exactement la fuite que PERM-06 ferme.
    const sansDerniereConnexion = ligneKarim();
    delete (sansDerniereConnexion as Record<string, unknown>).derniere_connexion;
    rendreLaListe([sansDerniereConnexion]);

    await screen.findByRole("columnheader", { name: "Nom" });
    expect(screen.queryByRole("columnheader", { name: "Dernière connexion" })).toBeNull();
    expect(
      screen.getAllByRole("columnheader").map((entete) => entete.getAttribute("data-champ")),
    ).toEqual(["nom_complet", "email", "magasins", "nombre_de_droits", "actif"]);
  });

  it("isole chaque nom dans un bdi", async () => {
    // Un nom arabe voisin de ponctuation fait migrer les caracteres neutres qui
    // l'entourent : la ligne se lit faux sans qu'aucun caractere n'ait change.
    // `Valeur` pose la frontiere, et ce test verifie qu'on y est passe plutot
    // que d'avoir ecrit `{ligne.nom_complet}`.
    rendreLaListe([ligneKarim({ nom_complet: "كريم بنعلي" })]);

    const cellule = await screen.findByText("كريم بنعلي");
    expect(cellule.closest("bdi")).not.toBeNull();
  });

  it("va droit au detail apres une creation", async () => {
    // Un compte neuf n'a ni droit ni magasin : le detail EST la prochaine
    // chose a faire. Rester sur la liste demanderait a l'opticien de retrouver
    // la ligne qu'il vient de creer pour finir ce qu'il a commence.
    let comptes = [ligneProprietaire()];
    rendre(
      {
        "GET /api/comptes/": () => json(comptes),
        "POST /api/comptes/": () => {
          comptes = [ligneProprietaire(), ligneKarim({ nombre_de_droits: 0, magasins: [] })];
          return json(
            {
              compte: ligneKarim({ nombre_de_droits: 0, magasins: [] }),
              mot_de_passe_provisoire: "Anfa-2026-provisoire",
            },
            201,
          );
        },
        "/api/comptes/2/": () =>
          json({
            ...ligneKarim({ nombre_de_droits: 0, magasins: [] }),
            droits: [],
            magasins_accordes: [],
          }),
        "/api/comptes/catalogue/": () => json(catalogueOffrable()),
      },
      "/parametres/comptes",
    );

    fireEvent.click(await screen.findByRole("button", { name: "Créer un compte gérant" }));
    fireEvent.change(screen.getByLabelText("Nom complet"), {
      target: { value: "Karim Benali" },
    });
    fireEvent.change(screen.getByLabelText("Adresse e-mail"), {
      target: { value: "karim.benali@optiqueanfa.ma" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Générer un mot de passe" }));
    fireEvent.click(screen.getByRole("button", { name: "Créer le compte" }));

    expect(
      await screen.findByRole("heading", { name: "Karim Benali", level: 1 }),
    ).toBeTruthy();
  });

  it("n'envoie jamais le client dans le corps de la creation", async () => {
    // Le `client` est pose par le SERVEUR (menace T-03-57). La SPA ne le
    // connait pas et ne doit pas apprendre a l'envoyer : le jour ou elle
    // l'enverrait, le refus serveur serait la seule chose entre un opticien et
    // un compte cree chez un concurrent.
    rendre(
      {
        "GET /api/comptes/": () => json([ligneProprietaire()]),
        "POST /api/comptes/": () =>
          json({ compte: ligneKarim(), mot_de_passe_provisoire: "x" }, 201),
        "/api/comptes/2/": () =>
          json({ ...ligneKarim(), droits: [], magasins_accordes: ["ANFA"] }),
        "/api/comptes/catalogue/": () => json(catalogueOffrable()),
      },
      "/parametres/comptes",
    );

    fireEvent.click(await screen.findByRole("button", { name: "Créer un compte gérant" }));
    fireEvent.change(screen.getByLabelText("Nom complet"), { target: { value: "K" } });
    fireEvent.change(screen.getByLabelText("Adresse e-mail"), {
      target: { value: "k@optiqueanfa.ma" },
    });
    fireEvent.change(screen.getByLabelText("Mot de passe provisoire"), {
      target: { value: "Anfa-2026-provisoire" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Créer le compte" }));

    await waitFor(() => {
      const creation = appels.find(
        (appel) => appel.methode === "POST" && appel.chemin === "/api/comptes/",
      );
      expect(creation).toBeTruthy();
      expect(Object.keys(creation?.corps as object).sort()).toEqual([
        "email",
        "mot_de_passe_provisoire",
        "nom_complet",
      ]);
    });
  });

  it("repond par le 403 pleine page a un gerant sans le droit, en le nommant", async () => {
    // Le 403 NOMME le droit manquant : le catalogue est identique pour toutes
    // les affaires du produit, donc le nommer ne divulgue rien d'un autre
    // client, et cela transforme un appel de support en demande en libre
    // service. C'est le premier ecran de la phase a porter de la donnee reelle,
    // donc c'est ici que la garde de route commence (le plan 03-13 l'avait
    // differee pour cette raison).
    rendreLaListe([], GERANT_SANS_DROIT);

    expect(
      await screen.findByRole("heading", { name: "Vous n'avez pas accès à cette page." }),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Il vous manque le droit « Gérer les comptes et les droits ». Demandez-le au propriétaire.",
      ),
    ).toBeTruthy();
    // Et rien de la liste n'a ete demande : un ecran refuse ne fait pas la
    // requete qu'il refuse d'afficher.
    expect(appels.some((appel) => appel.chemin === "/api/comptes/")).toBe(false);
  });
});

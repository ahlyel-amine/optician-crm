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

function ligneProprietaire(surcharge: Record<string, unknown> = {}): Record<string, unknown> {
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

function ligneKarim(surcharge: Record<string, unknown> = {}): Record<string, unknown> {
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

/* =========================================================================
 * 7.3, 7.4 et 7.7 — la fiche, les magasins, et la liste des droits
 * ======================================================================= */

/** La fiche d'un compte, avec son etat de droits et le catalogue de l'appelant. */
function rendreLaFiche(options: {
  compte?: Record<string, unknown>;
  droits?: { code: string; etat: string; magasins: string[] }[];
  magasinsAccordes?: string[];
  catalogue?: unknown;
  amorcage?: unknown;
  surDroits?: (requete: Request) => Response | Promise<Response>;
  surMagasins?: (requete: Request) => Response | Promise<Response>;
  surUniformiser?: (requete: Request) => Response | Promise<Response>;
  surStatut?: (requete: Request) => Response | Promise<Response>;
  surJournal?: (requete: Request) => Response | Promise<Response>;
} = {}) {
  const compte = options.compte ?? ligneKarim();
  const table: Table = {
    "/api/comptes/2/": () =>
      json({
        ...compte,
        droits: options.droits ?? [],
        magasins_accordes: options.magasinsAccordes ?? ["ANFA", "MAARIF"],
      }),
    "/api/comptes/catalogue/": () => json(options.catalogue ?? catalogueOffrable()),
  };
  if (options.surDroits) {
    table["POST /api/comptes/2/droits/"] = options.surDroits;
  }
  if (options.surUniformiser) {
    table["POST /api/comptes/2/droits/uniformiser/"] = options.surUniformiser;
  }
  if (options.surMagasins) {
    table["POST /api/comptes/2/magasins/"] = options.surMagasins;
  }
  if (options.surStatut) {
    table["POST /api/comptes/2/statut/"] = options.surStatut;
  }
  table["/api/comptes/2/journal/"] = options.surJournal ?? (() => json([]));
  return rendre(table, "/parametres/comptes/2", options.amorcage ?? PROPRIETAIRE);
}

describe("la fiche d'un compte", () => {
  it("place les magasins AVANT les droits, et l'historique en dernier", async () => {
    // L'ordre est porteur, pas esthetique : un droit sans magasin n'accorde
    // rien. Poser les droits d'abord produit l'appel « je lui ai tout donne et
    // il ne voit rien », qui est le plus cher des appels evitables.
    rendreLaFiche();

    await screen.findByRole("region", { name: "Droits" });
    expect(
      screen.getAllByRole("heading", { level: 2 }).map((titre) => titre.textContent),
    ).toEqual(["Identité", "Magasins", "Droits", "Historique des droits"]);
  });

  it("rend une ligne statique, et aucune case, pour une entreprise mono-magasin", async () => {
    // Zero decision la ou une seule reponse est possible. C'est la plus grosse
    // simplification disponible et elle couvre tout le palier `Essentiel`.
    rendreLaFiche({
      catalogue: catalogueOffrable([ANFA]),
      magasinsAccordes: ["ANFA"],
      compte: ligneKarim({ magasins: [ANFA] }),
    });

    // Le nom du magasin est dans un `bdi` (8.5), donc la phrase est coupee en
    // deux noeuds : l'assertion porte sur le texte complet du paragraphe, ce
    // qui est bien la copie, et non sur un noeud de texte isole.
    await screen.findByRole("region", { name: "Magasins" });
    expect(
      screen.getByText(
        (_contenu, element) =>
          element?.tagName === "P" && element.textContent === "Magasin : Anfa",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText("Ce compte a accès au seul magasin de l'entreprise."),
    ).toBeTruthy();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("refuse en ligne de decocher le dernier magasin, et propose la desactivation", async () => {
    rendreLaFiche({
      magasinsAccordes: ["ANFA"],
      compte: ligneKarim({ magasins: [ANFA] }),
    });

    const anfa = await screen.findByRole("checkbox", { name: /Anfa/ });
    fireEvent.click(anfa);

    expect(
      screen.getByText(/Un compte doit avoir accès à au moins un magasin\./),
    ).toBeTruthy();
    // La derniere proposition est un LIEN qui ouvre le dialogue de
    // desactivation : une phrase qui dit « desactivez plutot » sans donner le
    // moyen de le faire renvoie l'utilisateur chercher le bouton lui-meme.
    expect(
      screen.getByRole("button", { name: "Désactivez plutôt le compte." }),
    ).toBeTruthy();
    // Et rien n'est parti sur le fil : le refus est cote interface parce que le
    // serveur, lui, accepte zero magasin (un compte neuf en a zero).
    expect(appels.some((appel) => appel.chemin === "/api/comptes/2/magasins/")).toBe(false);
  });

  it("rend les sections et les libelles du catalogue SERVEUR, dans son ordre", async () => {
    // Les libelles, les explications, les sections et les prerequis viennent
    // tous du serveur. Un code ajoute en phase 8 apparait ici sans changement
    // cote SPA, et un libelle ne peut jamais deriver de son code.
    rendreLaFiche();

    await screen.findByRole("region", { name: "Droits" });
    const droits = screen.getByRole("region", { name: "Droits" });
    expect(
      within(droits)
        .getAllByRole("heading", { level: 3 })
        .map((titre) => titre.textContent),
    ).toEqual(["Stock", "Caisse", "Comptes"]);
    expect(within(droits).getByText("Ajuster le stock / inventaire")).toBeTruthy();
  });

  it("ne rend aucune ligne absente du catalogue, sans branche cliente", async () => {
    // Le test d'absence, et il porte sur la SPA : rendue avec un catalogue
    // tronque, elle rend un ecran tronque. Une liste de codes ecrite cote
    // client produirait ici des lignes que le serveur n'a pas servies.
    rendreLaFiche({
      catalogue: {
        sections: [
          {
            titre: "Stock",
            droits: [
              {
                code: "stock.voir",
                libelle: "Consulter le stock",
                explication: "Voir les articles et les quantités disponibles.",
              },
            ],
          },
        ],
        prerequis: {},
        magasins: [ANFA, MAARIF],
      },
    });

    await screen.findByRole("switch", { name: "Consulter le stock" });
    expect(screen.queryByText("Saisir en caisse")).toBeNull();
    expect(screen.queryByText("Ajuster le stock / inventaire")).toBeNull();
    expect(screen.getAllByRole("switch")).toHaveLength(1);
  });

  it("affiche l'explication de chaque ligne en texte visible, jamais en infobulle", async () => {
    // Une infobulle est invisible a qui balaie l'ecran, et cette ligne EST le
    // levier de cout de support de l'ecran : elle nomme la consequence.
    rendreLaFiche();

    const explication = await screen.findByText(
      "Corriger une quantité après un inventaire.",
    );
    expect(explication.getAttribute("title")).toBeNull();
    expect(explication.closest("[role='tooltip']")).toBeNull();
  });

  it("n'offre aucun preset, aucun palier, aucune copie de droits", async () => {
    // CLAUDE.md #6 : les permissions sont accordees individuellement, comme des
    // donnees, jamais par paliers de role. `Tout cocher`, `Gerant standard` et
    // `Copier les droits de` sont les trois memes paliers sous un nom
    // sympathique. Point de revue explicite, pas affaire de gout.
    rendreLaFiche();

    await screen.findByRole("region", { name: "Droits" });
    for (const interdit of [/tout cocher/i, /gérant standard/i, /copier les droits/i]) {
      expect(screen.queryByText(interdit)).toBeNull();
    }
  });

  it("annonce qu'un compte neuf ne verra rien, en le nommant", async () => {
    rendreLaFiche({
      droits: [],
      magasinsAccordes: [],
      compte: ligneKarim({ nombre_de_droits: 0, magasins: [] }),
    });

    expect(
      await screen.findByText(
        "Ce compte n'a encore aucun droit. Karim pourra se connecter, mais ne verra rien.",
      ),
    ).toBeTruthy();
  });

  it("porte la ligne de temporalite en permanence au pied de la section", async () => {
    // Elle repond a la question de support la plus previsible de l'ecran, et
    // elle est VRAIE : les droits sont relus depuis le plan de controle a
    // chaque requete (plan 03-05).
    rendreLaFiche({
      droits: [{ code: "stock.voir", etat: "actif", magasins: ["ANFA", "MAARIF"] }],
    });

    expect(
      await screen.findByText(
        "Les changements prennent effet immédiatement, dès l'action suivante de l'utilisateur. Il n'a pas besoin de se reconnecter.",
      ),
    ).toBeTruthy();
  });

  it("nomme les magasins de portee plutot que de les compter, jusqu'a quatre", async () => {
    rendreLaFiche({
      magasinsAccordes: ["ANFA", "MAARIF"],
      compte: ligneKarim({ magasins: [ANFA, MAARIF] }),
    });

    expect(
      await screen.findByText(
        "Ces droits s'appliquent à tous les magasins de ce compte (Anfa, Maârif).",
      ),
    ).toBeTruthy();
  });
});

/* =========================================================================
 * 7.5, 7.8, 7.9 et 7.10 — surcharge par magasin, annulation, dialogues
 * ======================================================================= */

const CALIFORNIE = { id: 3, code: "CALIFORNIE", nom: "Californie" };

/** Karim a deux magasins ; `caisse.saisir` n'est detenu qu'a Anfa : mixte. */
const DROITS_MIXTES = [
  { code: "stock.voir", etat: "actif", magasins: ["ANFA", "MAARIF"] },
  { code: "caisse.voir", etat: "actif", magasins: ["ANFA", "MAARIF"] },
  { code: "caisse.saisir", etat: "mixte", magasins: ["ANFA"] },
];

function resultat(surcharge: Record<string, unknown> = {}) {
  return {
    code: "caisse.saisir",
    action: "accorde",
    lignes: [],
    cascade: [],
    magasins_accordes: ["ANFA", "MAARIF"],
    magasins_etendus: [],
    ...surcharge,
  };
}

describe("la surcharge par magasin", () => {
  it("n'offre `Par magasin` qu'a partir de deux magasins", async () => {
    rendreLaFiche({
      catalogue: catalogueOffrable([ANFA]),
      magasinsAccordes: ["ANFA"],
      droits: [{ code: "stock.voir", etat: "actif", magasins: ["ANFA"] }],
    });

    await screen.findByRole("switch", { name: "Consulter le stock" });
    // Invisible pour toute entreprise mono-magasin : la grille n'existe que la
    // ou le proprietaire l'a demandee, et il ne peut pas la demander ici.
    expect(screen.queryByRole("button", { name: "Par magasin" })).toBeNull();
  });

  it("annonce le tri-etat plutot que de seulement le dessiner", async () => {
    rendreLaFiche({ droits: DROITS_MIXTES });

    const parent = await screen.findByRole("switch", { name: "Saisir en caisse" });
    expect(parent.getAttribute("aria-checked")).toBe("mixed");
    expect(screen.getByText("Personnalisé : 1 magasin sur 2")).toBeTruthy();
  });

  it("deplie une seule ligne, et nomme le magasin dans chaque sous-interrupteur", async () => {
    rendreLaFiche({ droits: DROITS_MIXTES });

    await screen.findByRole("switch", { name: "Saisir en caisse" });
    // Une ligne personnalisee est depliee d'emblee ; dans le cas attendu —
    // aucune personnalisation — zero ligne l'est.
    expect(screen.getByRole("switch", { name: "Saisir en caisse — Anfa" })).toBeTruthy();
    expect(screen.getByRole("switch", { name: "Saisir en caisse — Maârif" })).toBeTruthy();
    expect(screen.queryByRole("switch", { name: "Consulter le stock — Anfa" })).toBeNull();
  });

  it("garde le badge `Personnalise` une fois la ligne repliee", async () => {
    rendreLaFiche({ droits: DROITS_MIXTES });

    fireEvent.click(await screen.findByRole("button", { name: "Uniformiser" }));
    // Le dialogue s'interpose ; on revient en arriere, la ligne se replie.
    fireEvent.click(screen.getByRole("button", { name: "Retour" }));

    expect(screen.queryByRole("switch", { name: "Saisir en caisse — Anfa" })).toBeNull();
    expect(screen.getByText("Personnalisé")).toBeTruthy();
  });

  it("allume TOUS les magasins au clic sur un parent mixte, et le toast le dit", async () => {
    rendreLaFiche({
      droits: DROITS_MIXTES,
      surDroits: () =>
        json(
          resultat({
            lignes: [
              { code: "caisse.saisir", etat: "actif", magasins: ["ANFA", "MAARIF"] },
            ],
          }),
        ),
    });

    fireEvent.click(await screen.findByRole("switch", { name: "Saisir en caisse" }));

    await waitFor(() => {
      const envoi = appels.find(
        (appel) => appel.chemin === "/api/comptes/2/droits/" && appel.methode === "POST",
      );
      expect(envoi?.corps).toEqual({
        code: "caisse.saisir",
        accorde: true,
        magasins: ["ANFA", "MAARIF"],
      });
    });
    expect(
      await screen.findByText("Droit accordé dans tous les magasins : « Saisir en caisse »."),
    ).toBeTruthy();
  });

  it("demande avant d'uniformiser une ligne dont les magasins divergent", async () => {
    rendreLaFiche({ droits: DROITS_MIXTES });

    fireEvent.click(await screen.findByRole("button", { name: "Uniformiser" }));

    expect(
      screen.getByRole("heading", { name: "Appliquer le même droit à tous les magasins ?" }),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Les réglages par magasin de « Saisir en caisse » seront remplacés. Karim aura ce droit dans les 2 magasins.",
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retour" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Annuler" })).toBeNull();
  });

  it("etend les lignes uniformes a un magasin ajoute, et pas les personnalisees", async () => {
    // L'extension silencieuse d'une ligne personnalisee distribuerait une
    // permission que le proprietaire avait deliberement refusee, a l'occasion
    // d'une action sans rapport (menace T-03-62). La regle est appliquee par le
    // serveur ; l'interface la RACONTE, et c'est la note qui evite qu'elle
    // passe inapercue.
    rendreLaFiche({
      catalogue: catalogueOffrable([ANFA, MAARIF, CALIFORNIE]),
      droits: [
        { code: "stock.voir", etat: "actif", magasins: ["ANFA", "MAARIF"] },
        { code: "caisse.voir", etat: "mixte", magasins: ["ANFA"] },
        { code: "caisse.saisir", etat: "mixte", magasins: ["ANFA"] },
      ],
      surMagasins: () =>
        json(
          resultat({
            code: "CALIFORNIE",
            lignes: [
              {
                code: "stock.voir",
                etat: "actif",
                magasins: ["ANFA", "CALIFORNIE", "MAARIF"],
              },
            ],
            magasins_accordes: ["ANFA", "CALIFORNIE", "MAARIF"],
            magasins_etendus: ["stock.voir"],
          }),
        ),
    });

    fireEvent.click(await screen.findByRole("checkbox", { name: /Californie/ }));

    expect(
      await screen.findByText(
        "Californie a été ajouté. Vérifiez les 2 droits personnalisés par magasin.",
      ),
    ).toBeTruthy();
    // La ligne personnalisee n'a pas bouge : toujours mixte, toujours le seul Anfa.
    expect(
      screen.getByRole("switch", { name: "Saisir en caisse" }).getAttribute("aria-checked"),
    ).toBe("mixed");
  });
});

describe("l'annulation, les echecs et les dialogues", () => {
  it("offre `Annuler` sur un toast de revocation, et un seul pour toute la cascade", async () => {
    let appelsDroits = 0;
    rendreLaFiche({
      droits: [
        { code: "stock.voir", etat: "actif", magasins: ["ANFA", "MAARIF"] },
        { code: "stock.ajuster", etat: "actif", magasins: ["ANFA", "MAARIF"] },
      ],
      surDroits: () => {
        appelsDroits += 1;
        return json(
          resultat({
            code: "stock.voir",
            action: "revoque",
            lignes: [
              { code: "stock.voir", etat: "inactif", magasins: [] },
              { code: "stock.ajuster", etat: "inactif", magasins: [] },
            ],
            cascade: ["stock.ajuster"],
          }),
        );
      },
    });

    fireEvent.click(await screen.findByRole("switch", { name: "Consulter le stock" }));

    expect(
      await screen.findByText('Droit retiré : « Consulter le stock ».'),
    ).toBeTruthy();
    // La note symetrique de la cascade, en ligne sous la ligne emportee (7.6).
    expect(
      screen.getByText(
        '« Ajuster le stock / inventaire » a été retiré : il dépend de « Consulter le stock ».',
      ),
    ).toBeTruthy();
    // UN SEUL toast, et donc un seul `Annuler`, pour toute la cascade.
    expect(screen.getAllByRole("button", { name: "Annuler" })).toHaveLength(1);
    expect(appelsDroits).toBe(1);
  });

  it("affiche l'echec d'un octroi SUR LA LIGNE, jamais en toast", async () => {
    // Un toast d'echec se rate en regardant ailleurs, et ce qui reste alors a
    // l'ecran est un interrupteur qui ment sur l'etat reel (menace T-03-101).
    rendreLaFiche({
      droits: [{ code: "stock.voir", etat: "inactif", magasins: [] }],
      surDroits: () =>
        json(
          { detail: "Vous ne pouvez accorder qu'un droit que vous détenez vous-même." },
          403,
        ),
    });

    const interrupteur = await screen.findByRole("switch", { name: "Consulter le stock" });
    fireEvent.click(interrupteur);

    const message = await screen.findByText(
      "Vous ne pouvez accorder qu'un droit que vous détenez vous-même.",
    );
    // Sur la ligne, donc dans le meme `li` que l'interrupteur.
    expect(message.closest("li")).toBe(interrupteur.closest("li"));
    // Et l'interrupteur est revenu en arriere.
    await waitFor(() => {
      expect(
        screen.getByRole("switch", { name: "Consulter le stock" }).getAttribute("aria-checked"),
      ).toBe("false");
    });
  });

  it("porte la copie exacte du dialogue de desactivation, seconde phrase comprise", async () => {
    rendreLaFiche({ droits: DROITS_MIXTES });

    const statut = await screen.findByLabelText("Statut");
    fireEvent.change(statut, { target: { value: "inactif" } });

    expect(
      screen.getByRole("heading", { name: "Désactiver le compte de Karim Benali ?" }),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Il sera déconnecté dès sa prochaine action. Ses ventes et ses saisies restent enregistrées à son nom. Vous pourrez réactiver ce compte plus tard.",
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retour" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Désactiver le compte" })).toBeTruthy();
    // `Annuler` ne veut JAMAIS dire « fermer ce dialogue » (7.10).
    expect(screen.queryByRole("button", { name: "Annuler" })).toBeNull();
  });

  it("porte la copie exacte du dialogue de retrait d'un magasin", async () => {
    rendreLaFiche({
      droits: [
        { code: "caisse.voir", etat: "mixte", magasins: ["MAARIF"] },
        { code: "caisse.saisir", etat: "mixte", magasins: ["MAARIF"] },
      ],
    });

    fireEvent.click(await screen.findByRole("checkbox", { name: /Maârif/ }));

    expect(
      screen.getByRole("heading", { name: "Retirer l'accès au magasin Maârif ?" }),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Karim ne verra plus les clients, le stock, les ventes ni la caisse de Maârif. Les réglages par magasin de 2 droits pour ce magasin seront supprimés.",
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retour" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retirer l'accès" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Annuler" })).toBeNull();
    // Rien n'est parti avant la confirmation.
    expect(appels.some((appel) => appel.chemin === "/api/comptes/2/magasins/")).toBe(false);
  });

  it("deroule l'historique du plus recent au plus ancien, a l'ouverture seulement", async () => {
    rendreLaFiche({
      droits: DROITS_MIXTES,
      surJournal: () =>
        json([
          {
            le: "2026-09-14T08:14:00Z",
            action: "accorde",
            nature: "droit",
            cible: "caisse.saisir",
            libelle: "Saisir en caisse",
            par: "Amine El Fassi",
          },
          {
            le: "2026-09-13T15:02:00Z",
            action: "revoque",
            nature: "magasin",
            cible: "MAARIF",
            libelle: "Maârif",
            par: "Amine El Fassi",
          },
        ]),
    });

    await screen.findByRole("region", { name: "Historique des droits" });
    // Ferme par defaut : un repli ferme qui charge quand meme fait payer a
    // chaque fiche un aller-retour que presque personne ne demande.
    expect(appels.some((appel) => appel.chemin === "/api/comptes/2/journal/")).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Afficher l'historique" }));

    const premiere = await screen.findByText(/Saisir en caisse/, { selector: "li" });
    expect(premiere.textContent).toBe(
      "14/09/2026 à 09:14 — Amine El Fassi a accordé « Saisir en caisse »",
    );
    expect(
      screen.getByText(/Maârif/, { selector: "li" }).textContent,
    ).toBe("13/09/2026 à 16:02 — Amine El Fassi a retiré l'accès au magasin Maârif");
  });
});

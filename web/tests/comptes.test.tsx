import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { toast } from "sonner";
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
  // Les toasts survivent au demontage : `sonner` rend dans une couche haute
  // ajoutee a `document.body`, que le nettoyage de Testing Library ne possede
  // pas. Sans cette purge, le `Annuler` d'un test se compte dans le suivant —
  // et les tests qui affirment son ABSENCE dans un dialogue deviennent faux
  // pour une raison qui n'a rien a voir avec le code teste.
  toast.dismiss();
  for (const reste of document.querySelectorAll("[data-sonner-toaster]")) {
    reste.remove();
  }
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
 * 5.3 — atteindre l'ecran, ce qui precede tout le reste
 * ======================================================================= */

describe("l'acces a l'ecran depuis la navigation (PERM-02)", () => {
  it("atteint la liste depuis la barre laterale, sans jamais taper d'adresse", async () => {
    // LE TEST QUI MANQUAIT. Les trois ecrans de ce fichier etaient montes
    // directement sur `/parametres/comptes`, donc tous verts pendant que
    // l'ecran etait INATTEIGNABLE par l'interface : `Parametres` menait au
    // titre d'attente, et rien dans le produit ne liait vers la liste.
    //
    // Monter a la racine et cliquer est la seule forme qui l'aurait dit.
    rendre({ "/api/comptes/": () => json([ligneProprietaire(), ligneKarim()]) }, "/");

    const barre = await screen.findByRole("navigation", {
      name: "Navigation principale",
    });
    fireEvent.click(within(barre).getByRole("link", { name: "Paramètres" }));

    // Un seul clic : l'accueil des parametres redirige vers la premiere entree
    // que l'appelant peut voir, plutot que de le deposer sur une page vide.
    expect(
      await screen.findByRole("heading", { name: "Comptes et droits", level: 1 }),
    ).toBeTruthy();
    expect(await screen.findByText("Karim Benali")).toBeTruthy();

    // Et la rangee de second niveau est la, dans le contenu, pour que les
    // phases 9 et 12 y ajoutent leurs ecrans sans toucher a la barre laterale.
    const secondNiveau = screen.getByRole("navigation", { name: "Paramètres" });
    expect(
      within(secondNiveau).getByRole("link", { name: "Comptes et droits" }),
    ).toBeTruthy();
  });

  it("ne depose personne sur une impasse quand aucune entree de parametres n'est visible", async () => {
    // Le cas ne s'atteint qu'en TAPANT l'adresse : la barre laterale retire
    // deja `Parametres` a qui n'a pas `compte.gerer`. Il doit quand meme avoir
    // une issue, et la 403 pleine page de 8.6 en est une — un `PageEnAttente`
    // affichant `/parametres` n'en est pas une.
    //
    // Le droit n'est PAS nomme ici, et c'est delibere : aucun droit unique ne
    // possede `/parametres`. La phase 9 y ajoute un ecran sous un autre code,
    // et nommer `compte.gerer` enverrait alors demander le mauvais droit.
    rendre({}, "/parametres", GERANT_SANS_DROIT);

    expect(
      await screen.findByRole("heading", { name: "Vous n'avez pas accès à cette page." }),
    ).toBeTruthy();
    expect(screen.queryByTestId("destination")).toBeNull();
  });
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
  surStatut?: (requete: Request) => Response | Promise<Response>;
  surMotDePasse?: (requete: Request) => Response | Promise<Response>;
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
  if (options.surMagasins) {
    table["POST /api/comptes/2/magasins/"] = options.surMagasins;
  }
  if (options.surStatut) {
    table["POST /api/comptes/2/statut/"] = options.surStatut;
  }
  if (options.surMotDePasse) {
    table["POST /api/comptes/2/mot-de-passe/"] = options.surMotDePasse;
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

/** Le nom accessible du selecteur des droits, distinct de celui du shell (5.4). */
const ETIQUETTE_DES_DROITS = /Régler les droits pour/;

describe("le sélecteur de magasin des droits (PERM-03, PERM-04)", () => {
  it("rend le sélecteur sans survol ni focus, et ouvre sur « Tous les magasins de ce compte » (PERM-03)", async () => {
    // Le remplacant du test caduc de la tache rapide `260917-l7l`, dont il
    // reprend la discipline d'assertion. Le defaut d'origine : le controle par
    // ligne existait a deux magasins mais etait rendu `opacity-0` jusqu'au
    // survol de sa ligne. Indecouvrable — il fallait pointer exactement la
    // bonne ligne pour apprendre qu'il existait — et purement absent au
    // toucher, donc absent de la tablette du comptoir. Le proprietaire en a
    // conclu que l'octroi par magasin n'existait pas, puis a demande un
    // selecteur en tete de section a la place. C'est ce selecteur-la qui doit
    // desormais se voir sans rien survoler.
    //
    // **Pourquoi une assertion de CLASSES et non de visibilite.** jsdom ne
    // calcule pas le CSS : `getComputedStyle` n'y resout ni Tailwind ni une
    // feuille externe, donc `toBeVisible()` rend vrai sur un `opacity-0`. Ce
    // test attrape la regression exacte ; il ne prouve pas une visibilite
    // reelle. Cette preuve-la reste humaine — etape 1 du plan `03.1-04`.
    rendreLaFiche({
      droits: [
        { code: "stock.voir", etat: "actif", magasins: ["ANFA", "MAARIF"] },
        { code: "caisse.voir", etat: "actif", magasins: ["ANFA", "MAARIF"] },
      ],
    });

    await screen.findByRole("switch", { name: "Consulter le stock" });
    // Aucun `mouseOver`, aucun `focus` : l'ecran tel qu'il est rendu.
    const selecteur = screen.getByRole("combobox", { name: ETIQUETTE_DES_DROITS });
    expect(selecteur.textContent).toContain("Tous les magasins de ce compte");

    const classes = selecteur.className.split(/\s+/);
    expect(classes).not.toContain("opacity-0");
    expect(
      classes.filter(
        (classe) =>
          classe.startsWith("group-hover:") ||
          classe.startsWith("group-focus-within:") ||
          classe.startsWith("focus:opacity"),
      ),
    ).toEqual([]);

    // Le shell monte deja un selecteur de magasin (5.4). Deux `combobox`
    // homonymes sur un ecran sont ambigus a l'oeil comme au lecteur d'ecran,
    // et rendent chaque requete de test equivoque : celui des droits porte un
    // nom accessible a lui, et le libelle de son option `Tous` differe aussi
    // de `Tous les magasins` du shell.
    const duShell = within(screen.getByTestId("portee-magasin")).getByRole("combobox");
    expect(duShell).not.toBe(selecteur);
    expect(duShell.textContent).toContain("Tous les magasins");
    expect(duShell.textContent).not.toContain("Tous les magasins de ce compte");
    expect(screen.getAllByRole("combobox", { name: ETIQUETTE_DES_DROITS })).toHaveLength(1);
  });

  it("n'offre aucun sélecteur a une entreprise mono-magasin", async () => {
    // **Une garde de predicat se teste par paire.** Seule, l'assertion
    // d'absence serait verte contre un ecran qui ne porte aucun selecteur du
    // tout — c'est-a-dire contre le code d'avant ce plan. Le cas a deux
    // magasins est donc rendu d'abord, et c'est lui qui donne du mordant au
    // second.
    rendreLaFiche({
      droits: [{ code: "stock.voir", etat: "actif", magasins: ["ANFA", "MAARIF"] }],
    });
    expect(
      await screen.findByRole("combobox", { name: ETIQUETTE_DES_DROITS }),
    ).toBeTruthy();

    cleanup();
    appels = [];

    // Le cas frequent : une affaire a un magasin, ou un gerant-gestionnaire
    // reduit a un seul. Aucune decision, donc aucun controle (5.4, 7.3 B).
    // La source est `magasins_accordes`, jamais le catalogue de l'appelant
    // (T-03.1-02) : offrir une portee que le serveur refusera est une impasse.
    rendreLaFiche({
      catalogue: catalogueOffrable([ANFA]),
      magasinsAccordes: ["ANFA"],
      droits: [{ code: "stock.voir", etat: "actif", magasins: ["ANFA"] }],
    });
    await screen.findByRole("switch", { name: "Consulter le stock" });
    expect(screen.queryByRole("combobox", { name: ETIQUETTE_DES_DROITS })).toBeNull();
    expect(screen.queryByText("Tous les magasins de ce compte")).toBeNull();
  });

  it("ne laisse subsister ni « Par magasin », ni sous-liste, ni « Uniformiser » — une seule facon de faire", async () => {
    // Une ligne MIXTE est le seul cas ou l'ancien ecran depliait d'emblee :
    // c'est donc la fiche sur laquelle les trois absences veulent dire
    // quelque chose. La decision 1 du CONTEXT refuse la coexistence des deux
    // mecanismes, pas seulement l'ancien.
    rendreLaFiche({ droits: DROITS_MIXTES });

    await screen.findByRole("switch", { name: "Saisir en caisse" });
    expect(screen.queryAllByRole("button", { name: "Par magasin" })).toHaveLength(0);
    expect(screen.queryAllByRole("button", { name: "Uniformiser" })).toHaveLength(0);
    // Le tiret cadratin etait ce que la sous-liste mettait dans le nom
    // accessible de chaque sous-interrupteur.
    expect(screen.queryAllByRole("switch", { name: /—/ })).toHaveLength(0);
  });

  it("regle un seul magasin quand un magasin est choisi, et n'annonce jamais « mixed »", async () => {
    rendreLaFiche({
      droits: DROITS_MIXTES,
      surDroits: () =>
        json(
          resultat({
            action: "revoque",
            lignes: [{ code: "caisse.saisir", etat: "inactif", magasins: [] }],
          }),
        ),
    });

    fireEvent.click(await screen.findByRole("combobox", { name: ETIQUETTE_DES_DROITS }));
    fireEvent.click(await screen.findByRole("option", { name: "Anfa" }));

    // (a) **Un magasin unique ne peut pas etre mixte.** C'est l'invariant qui
    // interdit une quatrieme variante de `services.etat_de` : en mode nomme,
    // l'etat d'une ligne est une APPARTENANCE a `lignes[].magasins`, pas un
    // etat calcule.
    for (const interrupteur of screen.getAllByRole("switch")) {
      expect(interrupteur.getAttribute("aria-checked")).not.toBe("mixed");
    }

    // (b) `caisse.saisir` est detenu a Anfa, et a Anfa seulement.
    const saisir = screen.getByRole("switch", { name: "Saisir en caisse" });
    expect(saisir.getAttribute("aria-checked")).toBe("true");

    // (c) Exactement un code de magasin sur le fil, celui choisi (T-03.1-06).
    fireEvent.click(saisir);
    await waitFor(() => {
      const envoi = appels.find(
        (appel) => appel.chemin === "/api/comptes/2/droits/" && appel.methode === "POST",
      );
      expect(envoi?.corps).toEqual({
        code: "caisse.saisir",
        accorde: false,
        magasins: ["ANFA"],
      });
    });
  });

  it("porte TOUS les magasins accordes sur le fil tant que le mode est « Tous »", async () => {
    // La garde contre le **sous-octroi silencieux** (T-03.1-03) : un corps
    // reduit au magasin choisi alors que le mode est `Tous` ferait croire au
    // proprietaire qu'il a accorde partout. Elle vaut pour le defaut ET pour
    // un retour explicite sur `Tous` apres un detour par un magasin nomme.
    rendreLaFiche({
      droits: DROITS_MIXTES,
      surDroits: () => json(resultat({ action: "revoque", lignes: [] })),
    });

    // Sans toucher au selecteur.
    fireEvent.click(await screen.findByRole("switch", { name: "Consulter le stock" }));
    // **Apres un tour de boucle d'evenements**, jamais juste apres le clic :
    // `mutate()` rend la main avant d'appeler `fetch`, donc une assertion
    // immediate serait verte au-dessus du defaut.
    await waitFor(() => {
      const envoi = appels.find(
        (appel) => appel.chemin === "/api/comptes/2/droits/" && appel.methode === "POST",
      );
      expect(envoi?.corps).toEqual({
        code: "stock.voir",
        accorde: false,
        magasins: ["ANFA", "MAARIF"],
      });
    });

    fireEvent.click(screen.getByRole("combobox", { name: ETIQUETTE_DES_DROITS }));
    fireEvent.click(await screen.findByRole("option", { name: "Anfa" }));
    fireEvent.click(screen.getByRole("combobox", { name: ETIQUETTE_DES_DROITS }));
    fireEvent.click(
      await screen.findByRole("option", { name: "Tous les magasins de ce compte" }),
    );

    appels = [];
    fireEvent.click(screen.getByRole("switch", { name: "Consulter la caisse" }));
    await waitFor(() => {
      const envoi = appels.find(
        (appel) => appel.chemin === "/api/comptes/2/droits/" && appel.methode === "POST",
      );
      expect(envoi?.corps).toEqual({
        code: "caisse.voir",
        accorde: false,
        magasins: ["ANFA", "MAARIF"],
      });
    });
  });

  it("garde le badge « Personnalisé » dans les deux modes, pilote par l'etat serveur", async () => {
    // Le successeur de `garde le badge « Personnalise » une fois la ligne
    // repliee` : il n'y a plus de repliement, mais la propriete qu'il gardait
    // — l'etat personnalise n'est JAMAIS cache — reste et doit rester tenue.
    // Le badge dit « ce droit n'est pas le meme partout », et cette phrase
    // reste vraie quand on n'en regarde qu'un.
    rendreLaFiche({ droits: DROITS_MIXTES });

    await screen.findByRole("switch", { name: "Saisir en caisse" });
    expect(screen.getByText("Personnalisé")).toBeTruthy();

    fireEvent.click(screen.getByRole("combobox", { name: ETIQUETTE_DES_DROITS }));
    fireEvent.click(await screen.findByRole("option", { name: "Anfa" }));

    expect(screen.getByText("Personnalisé")).toBeTruthy();
  });

  it("retombe sur « Tous » quand le magasin choisi est retire du compte", async () => {
    // Menace T-03.1-04 : une selection perimee ferait echouer chaque clic
    // suivant contre `_magasins_vises`, avec une erreur sur chaque ligne et
    // aucune explication utile. La revalidation est la regle de 5.4,
    // appliquee ici.
    rendreLaFiche({
      droits: DROITS_MIXTES,
      surMagasins: () =>
        json(
          resultat({
            code: "MAARIF",
            action: "revoque",
            lignes: [{ code: "caisse.saisir", etat: "actif", magasins: ["ANFA"] }],
            magasins_accordes: ["ANFA"],
          }),
        ),
      surDroits: () => json(resultat({ action: "revoque", lignes: [] })),
    });

    fireEvent.click(await screen.findByRole("combobox", { name: ETIQUETTE_DES_DROITS }));
    fireEvent.click(await screen.findByRole("option", { name: "Maârif" }));

    fireEvent.click(screen.getByRole("checkbox", { name: /Maârif/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Retirer l'accès" }));

    // Un seul magasin restant : il n'y a plus de decision, donc plus de
    // controle.
    await waitFor(() => {
      expect(screen.queryByRole("combobox", { name: ETIQUETTE_DES_DROITS })).toBeNull();
    });

    appels = [];
    fireEvent.click(screen.getByRole("switch", { name: "Consulter le stock" }));
    await waitFor(() => {
      expect(
        appels.some((appel) => appel.chemin === "/api/comptes/2/droits/"),
      ).toBe(true);
    });
    // Aucune requete ulterieure ne porte le magasin retire.
    for (const appel of appels) {
      expect(JSON.stringify(appel.corps ?? null)).not.toContain("MAARIF");
    }
  });

  it("annonce le tri-etat plutot que de seulement le dessiner", async () => {
    rendreLaFiche({ droits: DROITS_MIXTES });

    const parent = await screen.findByRole("switch", { name: "Saisir en caisse" });
    expect(parent.getAttribute("aria-checked")).toBe("mixed");
    expect(screen.getByText("Personnalisé : 1 magasin sur 2")).toBeTruthy();
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

  it("ne reinitialise aucun mot de passe avant confirmation, et le `Retour` laisse le compte intact (PERM-02)", async () => {
    // La seule action de cet ecran qui soit a la fois immediate et sans
    // retour. Les vingt et une bascules ont leur toast `Annuler` (7.8), la
    // desactivation et le retrait de magasin ont leur confirmation ; celle-ci
    // n'avait ni l'un ni l'autre, et partait depuis le `onClick`. Un clic par
    // megarde coupait l'acces d'un gerant en plein service.
    //
    // `DialogueMotDePasse` n'est pas une confirmation : il AFFICHE un mot de
    // passe deja genere, c'est-a-dire un degat deja fait.
    rendreLaFiche({
      surMotDePasse: () => json({ mot_de_passe_provisoire: "Tr0is-Mots-Ici" }),
    });

    fireEvent.click(
      await screen.findByRole("button", { name: "Réinitialiser le mot de passe" }),
    );

    // **Vider la file avant d'affirmer l'absence.** `mutate()` rend la main
    // avant d'appeler `fetch`, donc `appels` est encore vide une ligne apres
    // le clic — meme au-dessus du code fautif. Une assertion posee la serait
    // verte contre le defaut qu'elle est censee attraper, ce qui est
    // exactement le piege que `.planning/TESTING.md` nomme. Un tour de boucle
    // d'evenements suffit a laisser partir la requete si elle doit partir.
    await new Promise((resoudre) => {
      setTimeout(resoudre, 0);
    });

    // L'assertion qui mord : rien n'est parti sur le fil.
    expect(appels.some((appel) => appel.chemin === "/api/comptes/2/mot-de-passe/")).toBe(
      false,
    );

    expect(
      screen.getByRole("heading", {
        name: "Réinitialiser le mot de passe de Karim ?",
      }),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Son mot de passe actuel cessera immédiatement de fonctionner. Vous devrez lui communiquer le nouveau.",
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retour" })).toBeTruthy();
    // `Annuler` ne veut JAMAIS dire « fermer ce dialogue » (7.10).
    expect(screen.queryByRole("button", { name: "Annuler" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Retour" }));

    await new Promise((resoudre) => {
      setTimeout(resoudre, 0);
    });
    expect(appels.some((appel) => appel.chemin === "/api/comptes/2/mot-de-passe/")).toBe(
      false,
    );
    expect(screen.queryByText("Tr0is-Mots-Ici")).toBeNull();
  });

  it("reinitialise apres confirmation, et montre le mot de passe provisoire (PERM-02)", async () => {
    rendreLaFiche({
      surMotDePasse: () => json({ mot_de_passe_provisoire: "Tr0is-Mots-Ici" }),
    });

    fireEvent.click(
      await screen.findByRole("button", { name: "Réinitialiser le mot de passe" }),
    );
    // Le nom accessible est EXACT en Testing Library : `Réinitialiser` ne
    // designe que l'action du dialogue, jamais le bouton de la fiche qui
    // s'appelle `Réinitialiser le mot de passe`.
    fireEvent.click(screen.getByRole("button", { name: "Réinitialiser" }));

    await waitFor(() => {
      expect(
        appels.some(
          (appel) =>
            appel.chemin === "/api/comptes/2/mot-de-passe/" && appel.methode === "POST",
        ),
      ).toBe(true);
    });
    // Apres confirmation, le comportement est exactement celui d'avant.
    expect(await screen.findByText("Tr0is-Mots-Ici")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Fermer" })).toBeTruthy();
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

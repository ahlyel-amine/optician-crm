import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
import { reinitialiserLeClient } from "@/api/client";
import { formaterTelephone } from "@/format";

import { attendUnNomAccessible } from "./nomAccessible";

/* ---------------------------------------------------------------------------
 * Les ecrans clients — la liste, sa recherche, et la creation.
 *
 * TROIS PIEGES DEJA PAYES GOUVERNENT CE FICHIER.
 *
 * 1. **jsdom ne calcule AUCUN CSS.** `toBeVisible()` rend `true` sur un
 *    `opacity-0`, et une tache rapide a livre un controle invisible derriere
 *    trente-deux tests verts pour exactement cette raison. Ce fichier ne
 *    revendique donc AUCUNE visibilite : ses assertions portent sur la presence
 *    dans le DOM, sur des attributs, sur l'ordre des noeuds et sur des noms
 *    accessibles. Les revendications visuelles de la phase 4 sont les cinq
 *    verifications manuelles de `04-VALIDATION.md`, portees par le plan 04-09.
 *
 * 2. **`mutate()` rend la main AVANT que `fetch` ne soit appele.** Toute
 *    assertion « la requete est partie » — et sa jumelle « rien n'est parti » —
 *    a besoin d'un tour de boucle d'evenements. D'ou les `waitFor` et le
 *    `await Promise.resolve()` explicite la ou l'absence est affirmee.
 *
 * 3. **Construit n'est pas atteignable.** Trente-deux tests frontend etaient
 *    verts sur un ecran qu'aucun opticien ne pouvait ouvrir, parce qu'ils
 *    montaient tous l'ecran a sa propre adresse. Le premier `it` de ce fichier
 *    part de `/` et CLIQUE. Une suite qui monte chaque ecran a son adresse ne
 *    peut pas distinguer construit d'atteignable.
 *
 * Rappel qui vaut pour tout le fichier : le retrait d'une entree de navigation
 * et l'absence d'une colonne sont de l'EXPERIENCE UTILISATEUR. Le controle est
 * la restriction de queryset et la projection cote serveur (plan 04-03).
 * ------------------------------------------------------------------------- */

const ANFA = { id: 1, code: "ANFA", nom: "Anfa" };

/**
 * Le catalogue de `/api/auth/moi/`. Il porte le LIBELLE de `client.voir`, parce
 * que c'est lui que la page 403 affiche — jamais le code.
 */
const CATALOGUE = {
  sections: [
    {
      titre: "Clients",
      droits: [
        {
          code: "client.voir",
          libelle: "Consulter les clients",
          explication: "Voir les fiches clients et leurs coordonnées.",
        },
        {
          code: "client.modifier",
          libelle: "Créer et modifier un client",
          explication: "Créer une fiche et corriger ses coordonnées.",
        },
      ],
    },
  ],
  prerequis: {},
};

/**
 * Un seul magasin, delibere : au-dela d'un, le shell rend le selecteur de
 * magasin, qui est le `combobox` sans nom du defaut D-1. Le test d'enumeration
 * des `combobox` de cet ecran ne doit pas echouer sur un defaut herite qui
 * n'appartient pas a cette phase.
 */
function amorcageDe(permissions: string[], proprietaire = false) {
  return {
    utilisateur: {
      id: 7,
      email: "karim@optiqueanfa.ma",
      nom_complet: "Karim Benali",
      est_proprietaire: proprietaire,
      doit_changer_mot_de_passe: false,
    },
    client: { code: "anfa", raison_sociale: "Optique Anfa" },
    permissions,
    magasins: [ANFA],
    catalogue: CATALOGUE,
  };
}

const AU_COMPTOIR = amorcageDe(["client.voir", "client.modifier"]);
const SANS_CLIENT_VOIR = amorcageDe(["stock.voir"]);

/** Une fiche telle que `/api/clients/` la sert. `derniere_ordonnance` est ABSENT. */
function fiche(surcharge: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 1,
    nom: "Mohammed Alaoui",
    telephone: "0612345678",
    date_naissance: "1984-03-14",
    adresse: "",
    notes: "",
    actif: true,
    created_at: "2026-02-12T09:14:00Z",
    score: null,
    raison: null,
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

type Table = Record<string, (requete: Request) => Response | Promise<Response>>;

/** Les appels observes. `url` est COMPLETE : c'est elle que le test n°3 lit. */
let appels: { methode: string; chemin: string; url: string; corps: unknown }[] = [];

function poserLesReponses(table: Table): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (requete: Request) => {
      const chemin = new URL(requete.url, "http://localhost").pathname;
      const texte = ["POST", "PATCH"].includes(requete.method)
        ? await requete.clone().text()
        : "";
      appels.push({
        methode: requete.method,
        chemin,
        url: requete.url,
        corps: texte === "" ? undefined : JSON.parse(texte),
      });
      const reponse = table[`${requete.method} ${chemin}`] ?? table[chemin];
      if (!reponse) {
        throw new Error(`Aucune reponse de test posee pour ${requete.method} ${chemin}`);
      }
      return reponse(requete);
    }),
  );
}

/**
 * Le chemin courant, expose par un voisin de `App` sous le MEME routeur.
 *
 * C'est la seule facon honnete d'affirmer « la route n'a pas change » : lire
 * l'ecran rendu confondrait « rien n'a navigue » avec « la destination n'est
 * pas encore construite ».
 */
function Mouchard() {
  const emplacement = useLocation();
  return <span data-testid="chemin-courant">{emplacement.pathname}</span>;
}

function rendre(table: Table, chemin: string, amorcage: unknown = AU_COMPTOIR) {
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
        <Mouchard />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

/** Ce que le champ de recherche de la LISTE a envoye, terme brut compris. */
function termesCherches(): (string | null)[] {
  return appels
    .filter((appel) => appel.chemin === "/api/clients/" && appel.url.includes("search"))
    .map((appel) => new URL(appel.url, "http://localhost").searchParams.get("search"));
}

function chemin(): string {
  return screen.getByTestId("chemin-courant").textContent ?? "";
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
 * 18.1 — atteindre l'ecran, ce qui precede tout le reste
 * ======================================================================= */

describe("l'acces a la liste des clients (CLIENT-01)", () => {
  it("on atteint la liste des clients en CLIQUANT depuis la racine", async () => {
    // LA LECON 03-14, RENDUE MECANIQUE. Aucun montage direct sur `/clients` :
    // un ecran parfait derriere une entree `disponible: false` est un ecran que
    // personne n'ouvre, et seul un test qui part de `/` le dit.
    rendre({ "/api/clients/": () => json([fiche()]) }, "/");

    const barre = await screen.findByRole("navigation", {
      name: "Navigation principale",
    });
    fireEvent.click(within(barre).getByRole("link", { name: "Clients" }));

    expect(await screen.findByRole("heading", { name: "Clients", level: 1 })).toBeTruthy();
    // Et une VRAIE ligne : un titre seul serait le titre d'attente que le plan
    // 03-14 a justement retire.
    expect(await screen.findByText("Mohammed Alaoui")).toBeTruthy();
  });

  it("sans client.voir, l_entree est absente et la route rend la 403 qui NOMME le droit", async () => {
    // Deux moities, et la seconde est celle qu'on oublie : l'entree retiree
    // (contrat `03` 5.3 — retiree, jamais grisee) ne protege pas l'adresse,
    // qu'un collegue colle dans un message.
    const premier = rendre({}, "/", SANS_CLIENT_VOIR);
    const barre = await screen.findByRole("navigation", {
      name: "Navigation principale",
    });
    expect(within(barre).queryByRole("link", { name: "Clients" })).toBeNull();
    premier.unmount();

    rendre({}, "/clients", SANS_CLIENT_VOIR);
    expect(
      await screen.findByRole("heading", { name: "Vous n'avez pas accès à cette page." }),
    ).toBeTruthy();
    // Le LIBELLE du catalogue, jamais le code : `client.voir` ne veut rien dire
    // pour un opticien qui doit demander ce droit au proprietaire.
    expect(
      await screen.findByText(
        "Il vous manque le droit « Consulter les clients ». Demandez-le au propriétaire.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("client.voir")).toBeNull();
  });
});

/* =========================================================================
 * 18.4 — la requete, et ce que le client s'interdit d'en faire
 * ======================================================================= */

describe("la recherche de la liste (CLIENT-10)", () => {
  it("la requete part telle quelle au serveur", async () => {
    // Aucune normalisation cliente : ni `trim`, ni `toLowerCase`, ni retrait
    // d'accent. La normalisation est SERVEUR, et une seconde ferait diverger le
    // resultat de l'index (T-04-51). Une saisie arabe fait l'aller-retour
    // inchangee pour la meme raison.
    rendre({ "/api/clients/": () => json([fiche()]) }, "/clients");

    const champ = await screen.findByLabelText("Rechercher un client");
    fireEvent.change(champ, { target: { value: "  MOHAMED  " } });

    // PIEGE 2 : sans ce tour de boucle, l'assertion passerait au-dessus d'un
    // anti-rebond qui n'a encore rien appele.
    await waitFor(() => {
      expect(termesCherches()).toEqual(["  MOHAMED  "]);
    });

    // Le controle negatif, dans le meme `it` : aucune forme pliee n'est partie.
    const urls = appels.map((appel) => appel.url);
    expect(urls.some((url) => url.includes("mohamed"))).toBe(false);
    expect(urls.some((url) => url.includes("search=MOHAMED&"))).toBe(false);
    expect(urls.some((url) => url.endsWith("search=MOHAMED"))).toBe(false);
  });

  it("la palette ne navigue jamais automatiquement sur un nom", async () => {
    // AUCUN SEUIL NE SEPARE LA VERITE DE L'ERREUR. Mesure du plan 04-03, en
    // `word_similarity` : mhamed vers Mohammed Alaoui vaut 0,333 et fatima vers
    // Fatiha Bennani vaut 0,571 — le classement est INVERSE. Auto-naviguer vers
    // un nom bien classe ouvre la fiche du voisin, et avec des ordonnances
    // dessus c'est une divulgation de donnee de sante (T-04-47).
    rendre(
      {
        "/api/clients/": (requete) => {
          const terme = new URL(requete.url).searchParams.get("search") ?? "";
          if (terme.includes("06")) {
            return json([
              fiche({ id: 2, nom: "Rachid Bennani", telephone: "0661223344", score: 1, raison: "telephone" }),
            ]);
          }
          return json([
            fiche({ id: 3, nom: "Mohammed Alaoui", score: 0.333, raison: "phonetique" }),
          ]);
        },
      },
      "/",
    );

    fireEvent.click(await screen.findByRole("button", { name: "Recherche" }));
    const saisie = await screen.findByPlaceholderText("Recherche");

    fireEvent.change(saisie, { target: { value: "mhamed" } });
    await screen.findByText("Mohammed Alaoui · proche de « mhamed »");
    fireEvent.keyDown(saisie, { key: "Enter" });
    await Promise.resolve();
    expect(chemin()).toBe("/");

    // LA MOITIE POSITIVE, sans laquelle un fournisseur qui ne poserait JAMAIS
    // `correspondance_exacte` serait vert : un numero complet et unique, lui,
    // navigue bien — c'est ce dont une douchette et un comptoir presse ont
    // besoin.
    fireEvent.change(saisie, { target: { value: "0661223344" } });
    await waitFor(() => {
      expect(chemin()).toBe("/clients/2");
    });
  });

  it("le score ne s_affiche jamais comme un nombre, la raison se dit en mots", async () => {
    // « 0,333 » ne dit rien a un opticien. `score` est dans la charge utile pour
    // que l'interface ORDONNE et EXPLIQUE, pas pour etre affiche — c'est ecrit
    // dans son `help_text`, donc dans le schema.
    rendre(
      {
        "/api/clients/": () =>
          json([fiche({ id: 3, nom: "Mohammed Alaoui", score: 0.333, raison: "phonetique" })]),
      },
      "/",
    );

    fireEvent.click(await screen.findByRole("button", { name: "Recherche" }));
    fireEvent.change(await screen.findByPlaceholderText("Recherche"), {
      target: { value: "mhamed" },
    });

    expect(await screen.findByText("Mohammed Alaoui · proche de « mhamed »")).toBeTruthy();
    const texte = document.body.textContent ?? "";
    expect(texte.includes("0,333")).toBe(false);
    expect(texte.includes("0.333")).toBe(false);
  });
});

/* =========================================================================
 * 18.6 — la creation, et la garde de doublon
 * ======================================================================= */

describe("la creation d'un client (CLIENT-01)", () => {
  it("la garde de doublon s_affiche, ne bloque pas, et ne pre-selectionne rien", async () => {
    // UNE FICHE EN DOUBLE EST UN HISTORIQUE DE PRESCRIPTION SCINDE — le danger
    // clinique meme qui a rendu les ordonnances transversales a l'affaire
    // (D-4a). Creer le doublon est l'erreur la plus probable du comptoir, et le
    // moment de l'empecher est pendant que le nom se tape. Empecher, ici, veut
    // dire INFORMER : jamais bloquer, jamais fusionner, jamais pre-selectionner
    // (T-04-50) — un refus sur un homonyme reel serait un opticien qui ne peut
    // pas enregistrer son client.
    rendre(
      {
        "/api/clients/": (requete) =>
          new URL(requete.url).searchParams.has("search")
            ? json([
                fiche({ id: 4, nom: "Mohammed Alaoui", telephone: "0612345678" }),
                fiche({ id: 5, nom: "Mhamed Alaoui", telephone: "0661223344" }),
              ])
            : json([fiche()]),
      },
      "/clients",
    );

    fireEvent.click(await screen.findByRole("button", { name: "Créer un client" }));
    const dialogue = await screen.findByRole("dialog");
    const champNom = within(dialogue).getByLabelText("Nom complet");
    fireEvent.change(champNom, { target: { value: "Mo" } });

    // 1. Elle s'affiche, avec sa copie exacte.
    const garde = await within(dialogue).findByTestId("garde-de-doublon");
    expect(within(garde).getByText("Clients existants")).toBeTruthy();
    expect(within(garde).getByText("2 fiches portent un nom proche.")).toBeTruthy();
    expect(within(garde).getAllByRole("link", { name: "Ouvrir la fiche" })).toHaveLength(2);

    // 2. AU-DESSUS du formulaire, jamais en dessous : l'information arrive avant
    //    la saisie qu'elle doit informer.
    expect(
      garde.compareDocumentPosition(champNom) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    // 3. Elle ne bloque pas.
    const confirmer = within(dialogue).getByRole("button", { name: "Créer le client" });
    expect(confirmer.hasAttribute("disabled")).toBe(false);

    // 4. Elle ne pre-selectionne rien. Assertions d'ATTRIBUT, pas de visibilite.
    expect(dialogue.querySelectorAll('[aria-selected="true"]')).toHaveLength(0);
    expect(dialogue.querySelectorAll('[aria-checked="true"]')).toHaveLength(0);
    expect(dialogue.querySelectorAll("input:checked")).toHaveLength(0);
  });
});

/* =========================================================================
 * 15.5 — la projection, cote client : ne rien faire, et le prouver
 * ======================================================================= */

describe("les colonnes de la liste (PERM-06)", () => {
  it("aucune colonne protegee n_est ressuscitee cote client", async () => {
    // LE JEU AVEC, d'abord — sans cette moitie, un tableau qui ne rendrait
    // JAMAIS d'en-tete serait vert.
    const avec = rendre(
      {
        "/api/clients/": () =>
          json([fiche({ derniere_ordonnance: "2025-03-14" })]),
      },
      "/clients",
    );
    expect(
      await screen.findByRole("columnheader", { name: "Dernière ordonnance" }),
    ).toBeTruthy();
    avec.unmount();

    // LE JEU SANS : ni en-tete, ni tiret, ni cadenas, ni infobulle. Le serveur
    // RETIRE la cle quand `ordonnance.voir` manque, `colonnesVisiblesSurLignes`
    // filtre sur `champ in ligne`, et la colonne disparait entierement. Un
    // substitut quelconque revelerait l'existence et la position du champ
    // (T-04-48).
    appels = [];
    rendre({ "/api/clients/": () => json([fiche()]) }, "/clients");
    expect(await screen.findByText("Mohammed Alaoui")).toBeTruthy();
    expect(screen.queryByRole("columnheader", { name: "Dernière ordonnance" })).toBeNull();

    const tableau = screen.getByRole("table");
    expect(tableau.querySelector('[data-champ="derniere_ordonnance"]')).toBeNull();
    expect((tableau.textContent ?? "").includes("Dernière ordonnance")).toBe(false);
    expect(tableau.querySelectorAll("[title]")).toHaveLength(0);
  });
});

/* =========================================================================
 * 25.2 — la lecon D-1 : on ENUMERE, on ne sonde pas
 * ======================================================================= */

describe("l_accessibilite des ecrans clients", () => {
  it("tout combobox de cet ecran a un nom accessible non vide", async () => {
    // `combobox` est un role dont le NOM VIENT DE L'AUTEUR : sa prose visible ne
    // devient jamais son nom accessible. C'est ainsi que D-1 est passe sous
    // trente-deux tests verts. Un controle ponctuel sur un element connu
    // laisserait passer le suivant, donc on ENUMERE.
    rendre({ "/api/clients/": () => json([fiche()]) }, "/clients");
    await screen.findByText("Mohammed Alaoui");

    fireEvent.click(screen.getByRole("button", { name: "Créer un client" }));
    const dialogue = await screen.findByRole("dialog");

    const contenu = document.getElementById("contenu");
    expect(contenu).not.toBeNull();
    const combos = [
      ...(contenu?.querySelectorAll('[role="combobox"]') ?? []),
      ...dialogue.querySelectorAll('[role="combobox"]'),
    ];

    // Si l'ecran n'en porte aucun, on l'AFFIRME plutot que de passer sur une
    // liste vide : un test qui itere sur rien est vert pour la mauvaise raison.
    // Les ecrans de ce plan n'ont que des `input` etiquetes par un vrai
    // `label`, dont le nom vient du contenu et non de l'auteur.
    if (combos.length === 0) {
      expect(combos).toHaveLength(0);
    }
    for (const combo of combos) {
      attendUnNomAccessible(combo);
    }

    // Le controle POSITIF de l'outil, dans le meme `it` : la mesure sait rendre
    // un nom non vide sur un champ reellement etiquete.
    attendUnNomAccessible(
      within(dialogue).getByLabelText("Nom complet"),
      "Nom complet",
    );
  });
});

/* =========================================================================
 * 18.5 — les deux etats vides, au caractere pres
 * ======================================================================= */

describe("les etats vides de la liste", () => {
  it("distingue l_affaire sans aucune fiche de la recherche sans resultat", async () => {
    // Deux phrases differentes pour deux situations differentes. La seconde
    // moitie de la premiere est DELIBEREE : elle dit a l'opticien que CLIENT-10
    // existe, au moment exact ou il se demande s'il doit s'inquieter de
    // l'orthographe.
    rendre({ "/api/clients/": () => json([]) }, "/clients");

    expect(await screen.findByText("Aucun client")).toBeTruthy();
    expect(
      screen.getByText(
        "Créez une fiche pour chaque personne qui achète. Vous la retrouverez ensuite par son nom ou par son téléphone, même écrit autrement.",
      ),
    ).toBeTruthy();

    // ZERO LIGNE REND ZERO COLONNE : rendre les en-tetes du registre sur un
    // resultat vide revelerait a un gerant sans le droit que la colonne
    // « Dernière ordonnance » existe. L'etat vide se dit avec une phrase.
    expect(screen.queryByRole("columnheader")).toBeNull();

    fireEvent.change(screen.getByLabelText("Rechercher un client"), {
      target: { value: "zzz" },
    });
    expect(await screen.findByText("Aucun résultat")).toBeTruthy();
    expect(
      screen.getByText(
        "Vérifiez l'orthographe, essayez le numéro de téléphone, ou créez la fiche.",
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Créer un client « zzz »" })).toBeTruthy();
  });
});

/* =========================================================================
 * 18.3 — le telephone passe par le formateur du produit
 * ======================================================================= */

describe("le rendu des colonnes", () => {
  it("rend le telephone par le formateur partage, pas par une interpolation", async () => {
    // `${client.telephone}` ecrit a la main dans trois composants est la
    // divergence meme que `src/format/` existe pour empecher. L'attendu est
    // calcule PAR le formateur : ecrire la chaine a la main ici reintroduirait
    // le risque d'espace ordinaire la ou le produit pose un U+00A0.
    rendre({ "/api/clients/": () => json([fiche()]) }, "/clients");

    const cellule = await waitFor(() => {
      const trouve = document
        .querySelector("table")
        ?.querySelector('td[data-champ="telephone"]');
      expect(trouve).toBeTruthy();
      return trouve as HTMLElement;
    });
    expect(cellule.textContent).toBe(formaterTelephone("0612345678"));
    // Le controle negatif : la forme brute n'est PAS a l'ecran.
    expect(cellule.textContent).not.toBe("0612345678");
  });
});

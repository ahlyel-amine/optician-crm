import { useContext } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { reinitialiserLeClient } from "@/api/client";
import { AuthProvider, ContexteAuth } from "@/auth/AuthProvider";
import { RequirePermission } from "@/auth/RequirePermission";

/* ---------------------------------------------------------------------------
 * Le contexte d'authentification, ses deux gardes, et l'ecran /connexion.
 *
 * `@testing-library/react` est importe STATIQUEMENT : sa purge entre deux tests
 * s'enregistre AU MOMENT DE L'IMPORT (voir la note de tests/colonnes.test.ts).
 *
 * Rappel qui vaut pour tout ce fichier, et que `RequirePermission` porte aussi
 * en tete de son module : le filtre de permission de l'interface est un
 * CONFORT, jamais une application de la regle. Ces tests verifient que rien
 * n'est rendu quand un droit manque ; ils ne verifient pas une autorisation.
 * L'autorisation est la restriction de queryset et la projection cote serveur.
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

const AMORCAGE = {
  utilisateur: {
    id: 7,
    email: "karim.benali@optiqueanfa.ma",
    nom_complet: "Karim Benali",
    est_proprietaire: false,
    doit_changer_mot_de_passe: false,
  },
  client: { code: "anfa", raison_sociale: "Optique Anfa" },
  permissions: ["client.voir", "caisse.voir"],
  magasins: [
    { id: 1, code: "ANFA", nom: "Anfa" },
    { id: 2, code: "MAARIF", nom: "Maârif" },
  ],
  catalogue: CATALOGUE,
};

type Appel = { url: string; methode: string; corps: string | null };

let appels: Appel[] = [];

/**
 * Remplace `fetch` par une table de reponses indexee par chemin.
 *
 * `openapi-fetch` appelle `fetch(request)` avec un objet `Request` : on lit donc
 * l'URL et la methode dessus, ce qui rend le comptage d'appels exact — c'est
 * l'assertion « l'amorcage tient en UNE requete ».
 */
function poserLesReponses(
  table: Record<string, () => Response | Promise<Response>>,
): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (requete: Request) => {
      const chemin = new URL(requete.url, "http://localhost").pathname;
      appels.push({
        url: chemin,
        methode: requete.method.toUpperCase(),
        corps: requete.body ? await requete.clone().text() : null,
      });
      const reponse = table[chemin];
      if (!reponse) {
        throw new Error(`Aucune reponse de test posee pour ${chemin}`);
      }
      return reponse();
    }),
  );
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

function amorcageReussi(charge: unknown = AMORCAGE) {
  return {
    "/api/auth/csrf/": () => vide(204),
    "/api/auth/moi/": () => json(charge),
  };
}

function rendre(enfant: React.ReactNode, chemin = "/") {
  const requetes = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={[chemin]}>
      <QueryClientProvider client={requetes}>
        <AuthProvider>{enfant}</AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

/** Affiche ce que le contexte expose, pour l'inspecter depuis un test. */
function Sonde({ surContexte }: { surContexte: (valeur: unknown) => void }) {
  const contexte = useContext(ContexteAuth);
  surContexte(contexte);
  return <span data-testid="sonde">{contexte.etat}</span>;
}

beforeEach(() => {
  appels = [];
  localStorage.clear();
  reinitialiserLeClient();
  document.cookie = "csrftoken=jeton-de-test; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("le contexte d'authentification", () => {
  it("l'amorcage se fait en une seule requete vers /api/auth/moi/", async () => {
    poserLesReponses(amorcageReussi());

    rendre(<Sonde surContexte={() => {}} />);
    await screen.findByText("connecte");

    const amorcages = appels.filter((appel) => appel.url === "/api/auth/moi/");
    expect(amorcages).toHaveLength(1);
  });

  it("le contexte expose le catalogue recu sans en reconstruire aucun", async () => {
    poserLesReponses(amorcageReussi());

    let vu: any = null;
    rendre(<Sonde surContexte={(valeur) => (vu = valeur)} />);
    await screen.findByText("connecte");

    // Egalite STRUCTURELLE avec ce que le serveur a envoye : pas un code de
    // plus, pas un libelle inventé, pas un ordre re-trié. Le catalogue est deja
    // intersecte cote serveur (plan 03-09) ; le reconstruire ici recreerait la
    // liste de codes que 7.7 interdit de tenir cote client.
    expect(vu.catalogue).toEqual(CATALOGUE);
    expect(vu.permissions).toEqual(["client.voir", "caisse.voir"]);
  });

  it("une selection de magasin absente des magasins accordes retombe sur le premier", async () => {
    localStorage.setItem("optique.magasin.7", "CALIFORNIE");
    poserLesReponses(amorcageReussi());

    let vu: any = null;
    rendre(<Sonde surContexte={(valeur) => (vu = valeur)} />);
    await screen.findByText("connecte");

    // Silencieusement : aucun message, aucune alerte. Le serveur filtre de
    // toute facon, donc une preference d'affichage perimee n'est pas un
    // incident — c'est un magasin retire par le proprietaire.
    expect(vu.magasinSelectionne).toBe("ANFA");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("une selection de magasin toujours accordee est conservee", async () => {
    localStorage.setItem("optique.magasin.7", "MAARIF");
    poserLesReponses(amorcageReussi());

    let vu: any = null;
    rendre(<Sonde surContexte={(valeur) => (vu = valeur)} />);
    await screen.findByText("connecte");

    expect(vu.magasinSelectionne).toBe("MAARIF");
  });
});

describe("RequirePermission", () => {
  it("un code absent des droits ne produit AUCUN noeud DOM", async () => {
    poserLesReponses(amorcageReussi());

    const { container } = rendre(
      <>
        <Sonde surContexte={() => {}} />
        <RequirePermission code="caisse.saisir">
          <button type="button">Saisir en caisse</button>
        </RequirePermission>
      </>,
    );
    await screen.findByText("connecte");

    // Pas d'etat desactive, pas d'infobulle, pas de cadenas : ABSENT.
    // Un element grise apprend a l'utilisateur qu'un droit existe et qu'il ne
    // l'a pas, ce qui est exactement la divulgation que 5.3 refuse.
    expect(screen.queryByText("Saisir en caisse")).toBeNull();
    expect(container.querySelector("button")).toBeNull();
    expect(container.querySelector("[disabled]")).toBeNull();
    expect(container.querySelector("[aria-disabled]")).toBeNull();
    expect(container.querySelector("[title]")).toBeNull();
  });

  it("un code detenu rend son enfant tel quel", async () => {
    poserLesReponses(amorcageReussi());

    rendre(
      <>
        <Sonde surContexte={() => {}} />
        <RequirePermission code="caisse.voir">
          <button type="button">Consulter la caisse</button>
        </RequirePermission>
      </>,
    );
    await screen.findByText("connecte");

    expect(screen.getByText("Consulter la caisse")).toBeTruthy();
  });
});

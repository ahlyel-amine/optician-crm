import { useContext } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
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

/* =========================================================================
 * Surface A — /connexion (03-UI-SPEC.md section 6)
 * ======================================================================= */

function rendreApplication(chemin = "/connexion") {
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

function champEmail(): HTMLInputElement {
  return screen.getByLabelText("Adresse e-mail") as HTMLInputElement;
}

function champMotDePasse(): HTMLInputElement {
  return screen.getByLabelText("Mot de passe") as HTMLInputElement;
}

async function saisirEtSoumettre(email: string, motDePasse: string) {
  fireEvent.change(champEmail(), { target: { value: email } });
  fireEvent.change(champMotDePasse(), { target: { value: motDePasse } });
  fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));
}

describe("/connexion", () => {
  it("un echec affiche exactement la phrase unique, vide le mot de passe et y ramene le focus", async () => {
    poserLesReponses({
      "/api/auth/csrf/": () => vide(204),
      "/api/auth/moi/": () => vide(401),
      "/api/auth/connexion/": () =>
        json({ detail: "Identifiant ou mot de passe incorrect." }, 400),
    });

    rendreApplication();
    await screen.findByLabelText("Adresse e-mail");
    await saisirEtSoumettre("karim.benali@optiqueanfa.ma", "mauvais");

    const alerte = await screen.findByRole("alert");
    expect(alerte.textContent).toBe("Identifiant ou mot de passe incorrect.");
    // L'e-mail survit : le refaire taper apres une faute de frappe sur le mot
    // de passe est la petite cruaute qui fait detester un outil de comptoir.
    expect(champEmail().value).toBe("karim.benali@optiqueanfa.ma");
    expect(champMotDePasse().value).toBe("");
    expect(document.activeElement).toBe(champMotDePasse());
    expect(champMotDePasse().getAttribute("aria-invalid")).toBe("true");
  });

  it("un compte desactive et un mot de passe faux donnent LA MEME phrase (T-03-80)", async () => {
    // Le serveur renvoie deja un corps unique (plan 03-08). Ce test verifie la
    // seconde moitie de la garantie : meme si un corps distinctif arrivait un
    // jour — nouvelle branche, nouveau middleware, proxy bavard — l'ecran
    // afficherait toujours la meme phrase, parce qu'il n'affiche jamais le
    // `detail` du serveur sur cette route.
    const phrases: string[] = [];
    for (const corps of [
      { detail: "Identifiant ou mot de passe incorrect." },
      { detail: "Ce compte a été désactivé le 14/09/2026." },
    ]) {
      poserLesReponses({
        "/api/auth/csrf/": () => vide(204),
        "/api/auth/moi/": () => vide(401),
        "/api/auth/connexion/": () => json(corps, 400),
      });
      const { unmount } = rendreApplication();
      await screen.findByLabelText("Adresse e-mail");
      await saisirEtSoumettre("karim.benali@optiqueanfa.ma", "x");
      phrases.push((await screen.findByRole("alert")).textContent ?? "");
      unmount();
    }
    expect(phrases[0]).toBe(phrases[1]);
    expect(phrases[0]).toBe("Identifiant ou mot de passe incorrect.");
  });

  it("la carte est decalee du haut, et l'apparition de l'erreur ne la deplace pas", async () => {
    poserLesReponses({
      "/api/auth/csrf/": () => vide(204),
      "/api/auth/moi/": () => vide(401),
      "/api/auth/connexion/": () => json({ detail: "x" }, 400),
    });

    rendreApplication();
    await screen.findByLabelText("Adresse e-mail");

    // jsdom ne fait aucune mise en page, donc `getBoundingClientRect()` rend
    // zero partout et ne prouverait rien. Ce qui est verifiable — et ce qui est
    // la VRAIE cause du saut — c'est le mecanisme de positionnement : un
    // decalage fixe depuis le haut, et aucun centrage vertical. Un centrage
    // vertical deplace la carte des que son contenu grandit.
    const scene = screen.getByTestId("scene-connexion");
    const avant = {
      paddingTop: scene.style.paddingTop,
      alignItems: getComputedStyle(scene).alignItems,
    };
    expect(avant.paddingTop).toBe("64px");
    expect(avant.alignItems).not.toBe("center");

    await saisirEtSoumettre("karim.benali@optiqueanfa.ma", "x");
    await screen.findByRole("alert");

    expect(scene.style.paddingTop).toBe(avant.paddingTop);
    expect(getComputedStyle(scene).alignItems).toBe(avant.alignItems);
  });

  it("le libelle du bouton ne change pas pendant l'attente", async () => {
    let debloquer!: () => void;
    const attente = new Promise<void>((resoudre) => {
      debloquer = resoudre;
    });
    poserLesReponses({
      "/api/auth/csrf/": () => vide(204),
      "/api/auth/moi/": () => vide(401),
      "/api/auth/connexion/": async () => {
        await attente;
        return json(AMORCAGE);
      },
    });

    rendreApplication();
    await screen.findByLabelText("Adresse e-mail");
    const bouton = screen.getByRole("button", { name: "Se connecter" });
    const libelleAuRepos = bouton.textContent;

    await saisirEtSoumettre("karim.benali@optiqueanfa.ma", "bon");

    await waitFor(() => expect(bouton.hasAttribute("disabled")).toBe(true));
    // Le libelle ne change pas, donc le bouton ne se redimensionne pas. Un
    // bouton qui passe de « Se connecter » a « Connexion... » saute de largeur
    // au moment ou l'utilisateur regarde exactement cet endroit.
    expect(bouton.textContent).toBe(libelleAuRepos);
    debloquer();
  });

  it("il n'y a ni lien de mot de passe oublie, ni case de session persistante", async () => {
    poserLesReponses({
      "/api/auth/csrf/": () => vide(204),
      "/api/auth/moi/": () => vide(401),
    });

    rendreApplication();
    await screen.findByLabelText("Adresse e-mail");

    // Aucun lien : il n'y a pas de fournisseur d'e-mail transactionnel, donc
    // une reinitialisation en libre service serait un lien mort. La ligne
    // d'aide dit qui contacter, en une phrase.
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(
      screen.getByText("Mot de passe oublié ? Contactez le propriétaire de votre magasin."),
    ).toBeTruthy();
  });

  it("une limite de debit affiche sa phrase et un compte a rebours dans la ligne d'aide", async () => {
    poserLesReponses({
      "/api/auth/csrf/": () => vide(204),
      "/api/auth/moi/": () => vide(401),
      "/api/auth/connexion/": () =>
        json({ detail: "Trop de tentatives. Réessayez dans une minute.", reessayer_dans: 42 }, 429),
    });

    rendreApplication();
    await screen.findByLabelText("Adresse e-mail");
    await saisirEtSoumettre("karim.benali@optiqueanfa.ma", "x");

    const alerte = await screen.findByRole("alert");
    expect(alerte.textContent).toBe("Trop de tentatives. Réessayez dans une minute.");
    expect(screen.getByTestId("ligne-daide").textContent).toContain("42");
    expect(
      screen.getByRole("button", { name: "Se connecter" }).hasAttribute("disabled"),
    ).toBe(true);
  });

  it("une panne du service affiche sa phrase, sans code ni anglais", async () => {
    poserLesReponses({
      "/api/auth/csrf/": () => vide(204),
      "/api/auth/moi/": () => vide(401),
      "/api/auth/connexion/": () => json({ detail: "boom" }, 503),
    });

    rendreApplication();
    await screen.findByLabelText("Adresse e-mail");
    await saisirEtSoumettre("karim.benali@optiqueanfa.ma", "x");

    const alerte = await screen.findByRole("alert");
    expect(alerte.textContent).toBe(
      "Le service est momentanément indisponible. Réessayez dans quelques instants.",
    );
    expect(alerte.textContent).not.toMatch(/[0-9]{3}/);
  });

  it("un echec du cookie CSRF se presente comme l'etat reseau, pas comme un envoi casse", async () => {
    document.cookie = "csrftoken=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    poserLesReponses({
      "/api/auth/csrf/": () => vide(503),
      "/api/auth/moi/": () => vide(401),
    });

    rendreApplication();
    const alerte = await screen.findByRole("alert");
    expect(alerte.textContent).toBe(
      "Le service est momentanément indisponible. Réessayez dans quelques instants.",
    );
  });

  it("le formulaire est un vrai form avec bouton de soumission, donc Entree soumet", async () => {
    poserLesReponses({
      "/api/auth/csrf/": () => vide(204),
      "/api/auth/moi/": () => vide(401),
      "/api/auth/connexion/": () => json(AMORCAGE),
    });

    rendreApplication();
    await screen.findByLabelText("Adresse e-mail");

    // jsdom n'implemente pas la soumission implicite du navigateur : on verifie
    // donc le MECANISME dont elle depend — un `form` reel contenant un bouton
    // de type `submit` — puis la soumission elle-meme.
    const formulaire = screen.getByTestId("formulaire-connexion") as HTMLFormElement;
    expect(formulaire.tagName).toBe("FORM");
    const soumettre = screen.getByRole("button", { name: "Se connecter" });
    expect(soumettre.getAttribute("type")).toBe("submit");
    expect(formulaire.contains(soumettre)).toBe(true);

    fireEvent.change(champEmail(), { target: { value: "karim.benali@optiqueanfa.ma" } });
    fireEvent.change(champMotDePasse(), { target: { value: "bon" } });
    fireEvent.submit(formulaire);
    await waitFor(() =>
      expect(appels.some((appel) => appel.url === "/api/auth/connexion/")).toBe(true),
    );
  });

  it("les champs portent aria-describedby et la bascule d'affichage porte aria-pressed", async () => {
    poserLesReponses({
      "/api/auth/csrf/": () => vide(204),
      "/api/auth/moi/": () => vide(401),
    });

    rendreApplication();
    await screen.findByLabelText("Adresse e-mail");

    expect(champEmail().getAttribute("autocomplete")).toBe("username");
    expect(champMotDePasse().getAttribute("autocomplete")).toBe("current-password");

    const bascule = screen.getByRole("button", { name: "Afficher le mot de passe" });
    expect(bascule.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(bascule);
    expect(champMotDePasse().getAttribute("type")).toBe("text");
    expect(
      screen.getByRole("button", { name: "Masquer le mot de passe" }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("une connexion reussie mene dans l'application et y revient par le chemin memorise", async () => {
    poserLesReponses({
      "/api/auth/csrf/": () => vide(204),
      "/api/auth/moi/": () => vide(401),
      "/api/auth/connexion/": () => json(AMORCAGE),
    });

    // Une route protegee visitee sans session : la garde memorise le chemin.
    // `/clients` plutot que `/parametres/comptes` depuis le plan 03-14, qui a
    // construit ce dernier : ce test parle du chemin memorise, pas de l'ecran
    // qui l'occupe, donc il vise une route dont le module attend encore.
    rendreApplication("/clients");
    await screen.findByLabelText("Adresse e-mail");
    await saisirEtSoumettre("karim.benali@optiqueanfa.ma", "bon");

    await screen.findByTestId("destination");
    expect(screen.getByTestId("destination").textContent).toBe("/clients");
  });
});

/* =========================================================================
 * /mot-de-passe — DEUX chemins, deux jeux de champs
 *
 * Le chemin FORCE (doit_changer_mot_de_passe) rend DEUX champs : la personne
 * vient de taper son mot de passe pour ouvrir la session, le lui redemander
 * revient a le lui faire repeter. Le chemin VOLONTAIRE, atteint depuis
 * `Changer mon mot de passe` du menu du compte, en rend TROIS : la, et
 * seulement la, le secret n'est connu que d'elle, et le champ est ce qui fait
 * qu'un poste deverrouille donne une session et non le compte.
 *
 * Tranche au point de controle du plan 03-13 le 2026-09-17, revenant sur la
 * decision du point de controle 03-12. `03-UI-SPEC.md` 9.4 decrit les deux.
 * ======================================================================= */

describe("/mot-de-passe", () => {
  const AVEC_DRAPEAU = {
    ...AMORCAGE,
    utilisateur: { ...AMORCAGE.utilisateur, doit_changer_mot_de_passe: true },
  };

  it("doit_changer_mot_de_passe mene a une page pleine, sans navigation de shell", async () => {
    poserLesReponses({
      "/api/auth/csrf/": () => vide(204),
      "/api/auth/moi/": () => json(AVEC_DRAPEAU),
    });

    rendreApplication("/parametres/comptes");

    expect(await screen.findByText("Choisissez votre mot de passe")).toBeTruthy();
    expect(
      screen.getByText(
        "Ce mot de passe vous a été communiqué par le propriétaire. Choisissez-en un que vous êtes seul à connaître.",
      ),
    ).toBeTruthy();
    // Non refermable : aucune navigation de shell, aucune issue.
    expect(document.querySelector("nav")).toBeNull();
    expect(screen.queryByRole("button", { name: "Fermer" })).toBeNull();
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeTruthy();
    // Deux champs, pas trois : le mot de passe actuel vient d'etre saisi.
    expect(screen.queryByLabelText("Mot de passe actuel")).toBeNull();
    expect(screen.getByLabelText("Nouveau mot de passe")).toBeTruthy();
    expect(screen.getByLabelText("Confirmer")).toBeTruthy();
  });

  it("deux saisies differentes sont refusees avant tout appel reseau", async () => {
    poserLesReponses({
      "/api/auth/csrf/": () => vide(204),
      "/api/auth/moi/": () => json(AVEC_DRAPEAU),
    });

    rendreApplication("/");
    await screen.findByText("Choisissez votre mot de passe");

    fireEvent.change(screen.getByLabelText("Nouveau mot de passe"), {
      target: { value: "un-mot-de-passe-long" },
    });
    fireEvent.change(screen.getByLabelText("Confirmer"), {
      target: { value: "un-mot-de-passe-lung" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    const alerte = await screen.findByRole("alert");
    expect(alerte.textContent).toBe("Les deux mots de passe ne sont pas identiques.");
    expect(appels.some((appel) => appel.url === "/api/auth/mot-de-passe/")).toBe(false);
  });

  it("un changement accepte libere l'application", async () => {
    poserLesReponses({
      "/api/auth/csrf/": () => vide(204),
      "/api/auth/moi/": () => json(AVEC_DRAPEAU),
      "/api/auth/mot-de-passe/": () => json(AMORCAGE),
    });

    rendreApplication("/");
    await screen.findByText("Choisissez votre mot de passe");

    fireEvent.change(screen.getByLabelText("Nouveau mot de passe"), {
      target: { value: "un-mot-de-passe-long" },
    });
    fireEvent.change(screen.getByLabelText("Confirmer"), {
      target: { value: "un-mot-de-passe-long" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await screen.findByTestId("destination");
    expect(screen.getByTestId("destination").textContent).toBe("/");

    const envoi = appels.find((appel) => appel.url === "/api/auth/mot-de-passe/");
    expect(envoi).toBeTruthy();
    expect(JSON.parse(envoi!.corps!)).toEqual({
      nouveau_mot_de_passe: "un-mot-de-passe-long",
    });
  });

  it("le chemin volontaire rend TROIS champs et sa propre copie", async () => {
    poserLesReponses({
      "/api/auth/csrf/": () => vide(204),
      "/api/auth/moi/": () => json(AMORCAGE),
      "/api/auth/mot-de-passe/": () => json(AMORCAGE),
    });

    rendreApplication("/mot-de-passe");

    expect(await screen.findByText("Changer mon mot de passe")).toBeTruthy();
    expect(
      screen.getByText(
        "Choisissez un nouveau mot de passe. Saisissez d'abord celui que vous utilisez aujourd'hui.",
      ),
    ).toBeTruthy();
    expect(screen.getByLabelText("Mot de passe actuel")).toBeTruthy();
    expect(screen.getByLabelText("Nouveau mot de passe")).toBeTruthy();
    expect(screen.getByLabelText("Confirmer")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Mot de passe actuel"), {
      target: { value: "celui-d-aujourd-hui" },
    });
    fireEvent.change(screen.getByLabelText("Nouveau mot de passe"), {
      target: { value: "un-mot-de-passe-long" },
    });
    fireEvent.change(screen.getByLabelText("Confirmer"), {
      target: { value: "un-mot-de-passe-long" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => {
      expect(appels.some((appel) => appel.url === "/api/auth/mot-de-passe/")).toBe(true);
    });
    const envoi = appels.find((appel) => appel.url === "/api/auth/mot-de-passe/");
    expect(JSON.parse(envoi!.corps!)).toEqual({
      mot_de_passe_actuel: "celui-d-aujourd-hui",
      nouveau_mot_de_passe: "un-mot-de-passe-long",
    });
  });

  it("le chemin volontaire a une issue, le chemin force n'en a aucune", async () => {
    poserLesReponses(amorcageReussi());
    rendreApplication("/mot-de-passe");
    await screen.findByText("Changer mon mot de passe");
    // `Retour` et non `Annuler` : le lexique reserve `Annuler` a l'annulation
    // d'une modification enregistree (`03-UI-SPEC.md` 7.10 et 9.3).
    expect(screen.getByRole("link", { name: "Retour" })).toBeTruthy();
  });
});

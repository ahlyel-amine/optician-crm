import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
import { reinitialiserLeClient } from "@/api/client";
// La feuille d'impression est LUE SUR LE DISQUE, pas decrite : jsdom
// n'applique aucune feuille `@media print`, donc la seule chose honnete a
// verifier ici est le TEXTE de la regle. **Pas `?raw`** : vitest neutralise les
// imports CSS et rendait une chaine VIDE, donc un test qui passait en ne
// regardant rien.
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

/* ---------------------------------------------------------------------------
 * Le dossier client en LECTURE : la fiche, l'historique des versions, la
 * feuille imprimee et la photo. Plan 04-09, 04-UI-SPEC.md 19, 21 et 22.
 *
 * DEUX PHRASES GOUVERNENT CE FICHIER, et les six premiers tests ne sont que
 * leur forme executable.
 *
 * 1. **Une version enregistree se rend telle qu'elle a ete saisie.
 *    L'affichage ne la revalide JAMAIS** (CLIENT-06). Les bornes vivent a un
 *    endroit servi et le proprietaire les a deja changees une fois : une
 *    version portant une valeur que les bornes d'aujourd'hui refuseraient doit
 *    s'afficher sans avertissement, sans badge d'erreur et sans annotation.
 *    Les notes « A verifier » sont une propriete du FORMULAIRE DE SAISIE.
 * 2. **Il n'existe aucun controle de modification et aucun controle de
 *    suppression sur une ordonnance, nulle part.** Corriger, c'est une
 *    nouvelle version avec son motif.
 *
 * TROIS PIEGES HERITES, et ils sont payes plutot que theoriques.
 *
 * - **jsdom ne calcule AUCUN CSS.** Aucune assertion d'apparence ici : ce qui
 *   est verifiable est la presence dans le DOM, un attribut, un nom accessible
 *   et une LISTE DE CLASSES. « Rien n'est rouge » est donc une revendication de
 *   JETON, pas de pixel, et les noms de tests le disent. La revendication
 *   visuelle est la verification manuelle n° 2 de `04-VALIDATION.md`.
 * - **Construit n'est pas atteignable.** Le premier `it` part de `/` et CLIQUE
 *   quatre fois. C'est le parcours le plus long de la phase, et le plan 04-08 a
 *   laisse ce dernier maillon ouvert EN LE NOMMANT.
 * - **Le magasin de `sonner` est module-global** : un toast survit d'un test au
 *   suivant s'il n'est pas congedie (mesure du plan 04-08).
 * ------------------------------------------------------------------------- */

const ANFA = { id: 1, code: "ANFA", nom: "Anfa" };

/** Les bornes SERVIES. Aucun chiffre clinique n'est compile dans l'interface. */
const BORNES = {
  sphere: { min: "-20.00", max: "20.00", pas: "0.25", signe_obligatoire: true },
  cylindre: { min: "-10.00", max: "0.00", pas: "0.25", convention: "negatif" },
  axe: { min: 1, max: 180, pas: 1 },
  addition: { min: "0.75", max: "4.00", pas: "0.25" },
  ep_binoculaire: { min: "45.0", max: "85.0", pas: "0.5" },
  ep_monoculaire: { min: "18.0", max: "44.5", pas: "0.5" },
};

/**
 * Le MEME contrat, avec d'autres chiffres — le proprietaire en a deja change
 * une fois. C'est cette paire de bornes qui rend le test de non-revalidation
 * honnete : la version stockee est hors de CELLES-CI.
 */
const BORNES_ETROITES = {
  ...BORNES,
  sphere: { min: "-6.00", max: "6.00", pas: "0.25", signe_obligatoire: true },
};

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
        {
          code: "ordonnance.voir",
          libelle: "Consulter les ordonnances",
          explication: "Voir les corrections et leur historique.",
        },
        {
          code: "ordonnance.saisir",
          libelle: "Saisir une ordonnance",
          explication: "Enregistrer une nouvelle version de la correction.",
        },
      ],
    },
  ],
  prerequis: {},
};

function amorcageDe(permissions: string[], bornes: unknown = BORNES) {
  return {
    utilisateur: {
      id: 7,
      email: "karim@optiqueanfa.ma",
      nom_complet: "Karim Tazi",
      est_proprietaire: false,
      doit_changer_mot_de_passe: false,
    },
    client: { code: "anfa", raison_sociale: "Optique Anfa" },
    permissions,
    magasins: [ANFA],
    catalogue: CATALOGUE,
    bornes_ordonnance: bornes,
  };
}

const AU_COMPTOIR = amorcageDe([
  "client.voir",
  "client.modifier",
  "ordonnance.voir",
  "ordonnance.saisir",
]);

const SANS_ORDONNANCE_VOIR = amorcageDe(["client.voir", "client.modifier"]);

/**
 * Le bloc de correction que la fiche porte — `resume_ordonnance`, champ
 * PROTEGE au registre (plan 04-05). La cle est ABSENTE pour qui ne detient pas
 * `ordonnance.voir`, et c'est le serveur qui la retire.
 */
function resume(surcharge: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    version: 3,
    date_prescription: "2026-02-10",
    source: "ordonnance_medicale",
    prescripteur: "Dr. Bennani",
    type_revision: "correction",
    od: { sphere: "2.00", cylindre: "-1.00", axe: 9, addition: "2.25" },
    og: { sphere: "1.75", cylindre: "-0.75", axe: 175, addition: "2.25" },
    ep_saisi: "monoculaire",
    ep_binoculaire: null,
    ep_mono_od: "31.5",
    ep_mono_og: "30.5",
    ...surcharge,
  };
}

/** Une fiche telle que `/api/clients/{id}/` la sert, SANS les cles protegees. */
function fiche(surcharge: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 1,
    nom: "Mohammed Alaoui",
    telephone: "0612345678",
    date_naissance: "1984-03-14",
    adresse: "",
    notes: "",
    actif: true,
    created_at: "2025-03-14T09:14:00Z",
    score: null,
    raison: null,
    ...surcharge,
  };
}

/** La MEME fiche, telle qu'elle arrive a qui detient `ordonnance.voir`. */
function ficheAvecResume(surcharge: Record<string, unknown> = {}): Record<string, unknown> {
  return fiche({
    derniere_ordonnance: "2026-02-10",
    resume_ordonnance: resume(),
    ...surcharge,
  });
}

/** Une version STOCKEE, dans la forme du serveur : point decimal, axe entier. */
function versionStockee(surcharge: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 31,
    client: 1,
    magasin: 1,
    version: 3,
    supersede: 22,
    type_revision: "correction",
    motif_revision: "axe OD saisi 90 au lieu de 9",
    source: "ordonnance_medicale",
    prescripteur: "Dr. Bennani",
    date_prescription: "2026-02-10",
    sphere_od: "2.00",
    sphere_og: "1.75",
    cylindre_od: "-1.00",
    cylindre_og: "-0.75",
    axe_od: 9,
    axe_og: 175,
    addition_od: "2.25",
    addition_og: "2.25",
    ep_saisi: "monoculaire",
    ep_binoculaire: null,
    ep_mono_od: "31.5",
    ep_mono_og: "30.5",
    created_at: "2026-02-12T09:14:00Z",
    created_par: "Karim Tazi",
    a_une_photo: false,
    photo_type: "",
    photo_octets: null,
    photo_attachee_le: null,
    photo_par: "",
    ...surcharge,
  };
}

/** La version 2, REMPLACEE par la 3. Une version remplacee n'est pas une erreur. */
function versionRemplacee(surcharge: Record<string, unknown> = {}): Record<string, unknown> {
  return versionStockee({
    id: 22,
    version: 2,
    supersede: null,
    type_revision: "",
    motif_revision: "",
    date_prescription: "2025-03-14",
    axe_od: 90,
    created_at: "2025-03-14T11:02:00Z",
    ...surcharge,
  });
}

function reponse(corps: unknown, statut = 200): Response {
  return new Response(JSON.stringify(corps), {
    status: statut,
    headers: { "Content-Type": "application/json" },
  });
}

function sansCorps(statut: number): Response {
  return new Response(null, { status: statut });
}

type Table = Record<string, (requete: Request) => Response | Promise<Response>>;

let appels: { methode: string; chemin: string; corps: unknown }[] = [];

function poserLesReponses(table: Table): void {
  vi.stubGlobal(
    "fetch",
    /*
      **LE DOUBLE ACCEPTE LES DEUX FORMES D'APPEL, comme le vrai `fetch`.**
      Le client genere passe un `Request` ; le televersement de la photo passe
      une URL et des options, parce que `FormData` ne transite pas par le
      client typé. Un double qui n'accepterait que la premiere forme ferait
      echouer la seconde SANS l'enregistrer — donc un test d'envoi vert par
      absence d'appel, ce qui est pire que rouge.
    */
    vi.fn(async (entree: Request | string, options?: RequestInit) => {
      // `new Request` de Node refuse une adresse RELATIVE : il faut l'absoudre
      // contre une origine, ce que le navigateur fait tout seul.
      const requete =
        typeof entree === "string"
          ? new Request(new URL(entree, "http://localhost"), options)
          : entree;
      const chemin = new URL(requete.url, "http://localhost").pathname;
      const type = requete.headers.get("Content-Type") ?? "";
      const estUnEnvoi = ["POST", "PATCH"].includes(requete.method);
      let corps: unknown = undefined;
      if (estUnEnvoi && type.includes("json")) {
        const texte = await requete.clone().text();
        corps = texte === "" ? undefined : JSON.parse(texte);
      } else if (estUnEnvoi && type.includes("multipart")) {
        // LES CLES DU FORMULAIRE, et pas les octets : c'est le NOM du champ
        // que le serveur exige, et c'est lui qu'un double de `fetch` ne
        // verifie pas tout seul.
        corps = [...(await requete.clone().formData()).keys()];
      }
      appels.push({ methode: requete.method, chemin, corps });
      const reponseDeTest = table[`${requete.method} ${chemin}`] ?? table[chemin];
      if (!reponseDeTest) {
        throw new Error(`Aucune reponse de test posee pour ${requete.method} ${chemin}`);
      }
      return reponseDeTest(requete);
    }),
  );
}

function Mouchard() {
  const emplacement = useLocation();
  return <span data-testid="chemin-courant">{emplacement.pathname}</span>;
}

function monter(table: Table, chemin: string, amorcage: unknown = AU_COMPTOIR) {
  poserLesReponses({
    "/api/auth/csrf/": () => sansCorps(204),
    "/api/auth/moi/": () => reponse(amorcage),
    "/api/clients/": () => reponse([fiche()]),
    "/api/clients/1/": () => reponse(ficheAvecResume()),
    "/api/clients/1/ordonnances/": () =>
      reponse([versionStockee(), versionRemplacee()]),
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

const cheminCourant = () => screen.getByTestId("chemin-courant").textContent ?? "";

/** Les trois mots qui ne doivent exister NULLE PART sur ces ecrans. */
const MOTS_INTERDITS = ["Supprimer", "Modifier", "Éditer"];

function occurrencesDesMotsInterdits(): string[] {
  return MOTS_INTERDITS.flatMap((mot) =>
    screen.queryAllByText(mot).map(() => mot),
  );
}

/** Les jetons qu'une liste de classes ne doit pas porter. Claim de CLASSE. */
const JETONS_ROUGES = ["destructive", "text-red", "bg-red", "border-red"];

function jetonsRougesDe(element: Element): string[] {
  const classes = element.getAttribute("class") ?? "";
  return JETONS_ROUGES.filter((jeton) => classes.includes(jeton));
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
  toast.dismiss();
});

/* =========================================================================
 * 19.1 et 21 — atteindre l'historique, ce qui precede tout le reste
 * ======================================================================= */

describe("le dossier client (CLIENT-06)", () => {
  it("client06_on_atteint_l_historique_en_CLIQUANT_depuis_la_racine", async () => {
    // LA LECON 03-14, APPLIQUEE AU PARCOURS LE PLUS LONG DE LA PHASE.
    // Le plan 04-08 a prouve les trois premiers maillons et NOMME le
    // quatrieme comme lui manquant. Celui-ci les prouve tous les quatre, et
    // c'est aussi le seul test qui dit que les onglets sont branches sur de
    // vraies routes plutot que sur un etat local.
    monter({}, "/");

    const barre = await screen.findByRole("navigation", {
      name: "Navigation principale",
    });
    fireEvent.click(within(barre).getByRole("link", { name: "Clients" }));

    fireEvent.click(await screen.findByText("Mohammed Alaoui"));
    expect(await screen.findByRole("heading", { name: "Mohammed Alaoui", level: 1 }))
      .toBeTruthy();

    const onglets = await screen.findByRole("navigation", { name: "Dossier du client" });
    fireEvent.click(within(onglets).getByRole("link", { name: "Ordonnances" }));

    // Une VRAIE carte de version, pas un titre d'attente.
    expect(await screen.findByTestId("version-3")).toBeTruthy();
    expect(cheminCourant()).toBe("/clients/1/ordonnances");
  });

  it("client06_sans_ordonnance_voir_l_onglet_est_ABSENT_et_la_fiche_ne_porte_pas_le_resume", async () => {
    // DEUX MOITIES, et une moitie positive pour que l'absence prouve quelque
    // chose. Sans `ordonnance.voir` le serveur RETIRE la cle : le client ne
    // decide de rien, il ne fait que rendre ce qui est present. C'est
    // exactement ce que `colonnesVisiblesSurLignes` fait deja pour la liste,
    // donc la moitie cliente n'ajoute AUCUNE branche (plan 04-05).
    const premier = monter({ "/api/clients/1/": () => reponse(fiche()) }, "/clients/1", SANS_ORDONNANCE_VOIR);

    const onglets = await screen.findByRole("navigation", { name: "Dossier du client" });
    // Absent, pas grise, pas d'infobulle : `03` 5.3.
    expect(within(onglets).queryByRole("link", { name: "Ordonnances" })).toBeNull();
    expect(within(onglets).getByRole("link", { name: "Fiche" })).toBeTruthy();
    expect(screen.queryByText("Dernière ordonnance")).toBeNull();
    premier.unmount();

    // MOITIE POSITIVE : avec la cle, la carte EST rendue. Sans elle, un ecran
    // qui n'afficherait jamais ce bloc passerait la premiere moitie.
    monter({}, "/clients/1");
    expect(await screen.findByText("Dernière ordonnance")).toBeTruthy();
    expect(screen.getByTestId("correction-OD").textContent).toContain("+2,00");
  });

  it("client06_aucun_controle_de_modification_ni_de_suppression_n_existe", async () => {
    // T-04-64. Le serveur rend 405 de toute facon (plan 04-05) : ceci est une
    // defense en profondeur, pas la garantie. Le mot `Supprimer` n'apparait pas
    // plus ici que dans l'interface des comptes (`03` 7.8).
    const surLaFiche = monter({}, "/clients/1");
    expect(await screen.findByText("Dernière ordonnance")).toBeTruthy();
    expect(occurrencesDesMotsInterdits()).toEqual([]);
    // CONTROLE POSITIF, dans le meme `it` : sans lui, un ecran vide passerait.
    expect(screen.getAllByText("Saisir une ordonnance").length).toBeGreaterThan(0);
    surLaFiche.unmount();

    const surLhistorique = monter({}, "/clients/1/ordonnances");
    expect(await screen.findByTestId("version-3")).toBeTruthy();
    expect(occurrencesDesMotsInterdits()).toEqual([]);
    expect(screen.getAllByText("Saisir une ordonnance").length).toBeGreaterThan(0);
    surLhistorique.unmount();

    monter({}, "/clients/1/ordonnances/3");
    const carte = await screen.findByTestId("version-3");
    expect(occurrencesDesMotsInterdits()).toEqual([]);
    expect(within(carte).queryByRole("button", { name: "Supprimer" })).toBeNull();
  });
});

/* =========================================================================
 * 21.2 — la phrase qui gouverne l'ecran
 * ======================================================================= */

describe("une version stockee, rendue telle qu'elle a ete saisie (CLIENT-06)", () => {
  it("client06_une_version_stockee_ne_se_revalide_PAS_a_l_affichage", async () => {
    // Les bornes servies REFUSERAIENT cette sphere aujourd'hui. La version
    // l'affiche quand meme, sans note, sans badge et sans annotation.
    //
    // CE QUE CE TEST ATTRAPE : la reutilisation de `verifier.ts` sur un ecran
    // de LECTURE — l'erreur naturelle, puisque le module est juste a cote.
    // Le grep du plan la refuse dans `CarteVersion.tsx` ; ce test la refuse
    // par le comportement, ce qui survit a un renommage.
    monter(
      {
        "/api/clients/1/ordonnances/": () =>
          reponse([versionStockee({ sphere_od: "12.00" })]),
      },
      "/clients/1/ordonnances",
      amorcageDe(
        ["client.voir", "ordonnance.voir", "ordonnance.saisir"],
        BORNES_ETROITES,
      ),
    );

    const carte = await screen.findByTestId("version-3");
    // La VALEUR est rendue — a l'ecran ET sur la feuille imprimee, qui passent
    // par le MEME composant. Les deux sont assertees : une divergence entre
    // l'ecran et le papier est exactement ce que la source unique interdit.
    const lignes = within(carte).getAllByTestId("correction-OD");
    expect(lignes.length).toBeGreaterThan(0);
    for (const ligne of lignes) {
      expect(ligne.textContent).toContain("+12,00");
    }
    // Et rien d'autre : ni note, ni `aria-invalid`, ni jeton destructif.
    expect(within(carte).queryByText(/À vérifier/)).toBeNull();
    expect(carte.querySelector("[aria-invalid='true']")).toBeNull();
    expect(carte.querySelector("[role='alert']")).toBeNull();
    expect(jetonsRougesDe(carte)).toEqual([]);
  });

  it("client06_rien_n_est_rouge_sur_une_version_remplacee_CLAIM_DE_CLASSE", async () => {
    // **Revendication de JETON, pas de pixel**, et le nom du test le dit :
    // jsdom ne calcule aucun CSS, donc « n'est pas rouge » ne peut etre
    // affirme ici que sur une liste de classes et un attribut de variante.
    // La revendication visuelle est la verification manuelle n° 2.
    monter({}, "/clients/1/ordonnances");

    const carte = await screen.findByTestId("version-2");
    expect(jetonsRougesDe(carte)).toEqual([]);

    // Le badge porte LE MOT (`03` 4 : la couleur n'est jamais seule porteuse).
    const badge = within(carte).getByText("Remplacée");
    expect(badge.getAttribute("data-variant")).not.toBe("destructive");
    // La carte en cours porte le sien, et les deux se distinguent par le mot.
    expect(
      within(screen.getByTestId("version-3")).getByText("Version en cours"),
    ).toBeTruthy();
  });

  it("client02_l_onglet_Achats_n_est_PAS_rendu", async () => {
    // CE N'EST PAS UN OUBLI (19.4). CLIENT-02 et le critere 1 de la feuille de
    // route ont besoin des VENTES, qui sont la phase 6 : il n'y a rien a
    // montrer et il ne peut rien y avoir. Un opticien qui clique et trouve un
    // vide permanent a appris que le produit est casse — c'est l'argument
    // `disponible: false` de `03` 5.3, un etage plus bas.
    monter({}, "/clients/1");

    const onglets = await screen.findByRole("navigation", { name: "Dossier du client" });
    expect(within(onglets).queryByRole("link", { name: "Achats" })).toBeNull();
    expect(screen.queryByText("Achats")).toBeNull();
  });
});

/* =========================================================================
 * 22 — LA PHOTO. Elle s'attache UNE FOIS, et le controle le dit.
 * ======================================================================= */

/** Un fichier dont on impose la taille : `File` de jsdom ne la fabrique pas. */
function fichierDe(nom: string, type: string, octets: number): File {
  const fichier = new File(["x"], nom, { type });
  Object.defineProperty(fichier, "size", { value: octets });
  return fichier;
}

const UN_MO = 1024 * 1024;

/**
 * Le nom qui porte celui du patient. Il ne doit JAMAIS atteindre le DOM.
 *
 * **LE PIEGE DU GREP, ENCORE.** Le compte connecte de ce fichier s'appelait
 * `Karim Benali` et son nom est rendu par le shell sur chaque ecran : la
 * recherche de « benali » dans le DOM echouait donc sur le NOM DU GERANT, pas
 * sur une fuite. Le compte a ete renomme plutot que l'assertion affaiblie —
 * restreindre la recherche au formulaire aurait rendu le test aveugle au cas
 * qui compte, un nom de fichier apparaissant dans un toast ou un titre.
 */
const NOM_QUI_PARLE = "ordonnance_benali_ahmed.jpg";

async function choisirLaPhoto(fichier: File): Promise<HTMLElement> {
  const entree = await screen.findByLabelText("Photo de l'ordonnance");
  fireEvent.change(entree, { target: { files: [fichier] } });
  return entree;
}

describe("la photo de l'ordonnance (CLIENT-09)", () => {
  it("client09_l_attache_est_une_VRAIE_entree_fichier_avec_un_label_visible", async () => {
    // Le glisser-deposer est une amelioration ; LE SELECTEUR DE FICHIER EST LE
    // CONTRAT, et il est atteignable au clavier parce que c'est une vraie
    // entree. Aucun `capture` : photographier au comptoir est le travail de
    // l'application Expo de la phase 11.
    monter({ "/api/clients/1/ordonnances/": () => reponse([]) }, "/clients/1/ordonnances/nouvelle");

    const entree = (await screen.findByLabelText("Photo de l'ordonnance")) as HTMLInputElement;
    expect(entree.tagName).toBe("INPUT");
    expect(entree.type).toBe("file");
    expect(entree.getAttribute("capture")).toBeNull();

    const acceptes = entree.getAttribute("accept") ?? "";
    expect(acceptes).toContain("image/jpeg");
    expect(acceptes).toContain("image/heic");
    // Aucun document portable en phase 4 : il demanderait une visionneuse, et
    // le chemin documentaire est la phase 9 (consigne en D-4-3).
    expect(acceptes).not.toContain("pdf");
  });

  it("client09_une_image_trop_lourde_est_refusee_en_MEGAOCTETS_et_le_message_n_echoue_PAS_le_nom", async () => {
    // **LA MOITIE CLIENTE DE T-04-66.** Un nom de fichier televerse porte
    // couramment le nom du patient, et une chaine d'erreur est la seule chaine
    // du produit qui atteint Sentry de facon fiable. Le serveur a sa moitie
    // (plan 04-06, les six cles de `SENSITIVE_KEY`) ; celle-ci est la notre, et
    // ce test la pose LITTERALEMENT en cherchant le nom du patient dans le DOM.
    monter({ "/api/clients/1/ordonnances/": () => reponse([]) }, "/clients/1/ordonnances/nouvelle");

    await choisirLaPhoto(fichierDe(NOM_QUI_PARLE, "image/jpeg", 14 * UN_MO));

    // En MEGAOCTETS, jamais en octets.
    expect(await screen.findByText("Cette image fait 14 Mo. La limite est de 10 Mo.")).toBeTruthy();
    expect(screen.queryByText(/benali/i)).toBeNull();
    expect(document.body.textContent).not.toContain("benali");
    // Et rien n'est parti au serveur : le controle est AVANT le televersement.
    expect(appels.some((appel) => appel.chemin.includes("/photo/"))).toBe(false);
  });

  it("client09_un_mauvais_type_est_refuse_SANS_type_MIME_a_l_ecran", async () => {
    monter({ "/api/clients/1/ordonnances/": () => reponse([]) }, "/clients/1/ordonnances/nouvelle");

    await choisirLaPhoto(fichierDe("scan.txt", "text/plain", 2 * UN_MO));

    expect(
      await screen.findByText(
        "Ce fichier n'est pas une image. Formats acceptés : JPG, PNG, WEBP, HEIC.",
      ),
    ).toBeTruthy();
    // Un type MIME a l'ecran ne dit rien a un opticien au comptoir.
    expect(document.body.textContent).not.toContain("text/plain");
  });

  it("client09_une_photo_posee_ne_se_remplace_PAS_et_le_controle_le_dit", async () => {
    // La ligne est immuable (CLIENT-06). Une version enregistree SANS photo
    // peut en recevoir une plus tard — le papier arrive souvent le lendemain —
    // et c'est la seule mutation permise. Jamais de remplacement, jamais de
    // suppression.
    const avecPhoto = monter(
      {
        "/api/clients/1/ordonnances/": () =>
          reponse([
            versionStockee({
              a_une_photo: true,
              photo_type: "image/jpeg",
              photo_octets: 2 * UN_MO,
              photo_attachee_le: "2026-02-12T10:02:00Z",
              photo_par: "karim@optiqueanfa.ma",
            }),
          ]),
      },
      "/clients/1/ordonnances",
    );

    const carte = await screen.findByTestId("version-3");
    expect(
      within(carte).getByText(
        "Une photo ne se remplace pas. Pour corriger, enregistrez une nouvelle version.",
      ),
    ).toBeTruthy();
    expect(within(carte).queryByLabelText("Photo de l'ordonnance")).toBeNull();
    avecPhoto.unmount();

    // CONTROLE POSITIF : sans photo, le controle EST rendu. Sans cette moitie,
    // un ecran qui n'afficherait jamais l'attache passerait la premiere.
    monter(
      { "/api/clients/1/ordonnances/": () => reponse([versionStockee()]) },
      "/clients/1/ordonnances",
    );
    const sansPhoto = await screen.findByTestId("version-3");
    expect(within(sansPhoto).getByLabelText("Photo de l'ordonnance")).toBeTruthy();
    expect(within(sansPhoto).queryByText(/ne se remplace pas/)).toBeNull();
  });

  it("client09_l_attache_envoie_le_champ_QUE_LE_SERVEUR_ATTEND", async () => {
    // **CE TEST EXISTE PARCE QUE LA SUITE NE L'AVAIT PAS ATTRAPE.** Le premier
    // jet envoyait `photo`, qui est le nom de la COLONNE ; le serialiseur du
    // plan 04-06 attend `fichier`, et la pile reelle rendait un 400 « Aucun
    // fichier n'a été soumis. » — trouve en televersant contre le serveur
    // pendant la preparation de la passe humaine, pas par ces tests.
    //
    // Un double de `fetch` ne peut pas savoir ce que le serveur exige ; ce
    // qu'il peut faire, et c'est ce que fait cette assertion, c'est figer le
    // NOM DU CHAMP pour que la prochaine reecriture ne le reperde pas.
    monter(
      {
        "/api/clients/1/ordonnances/": () => reponse([versionStockee()]),
        "POST /api/ordonnances/31/photo/": () => reponse({ a_une_photo: true }, 201),
      },
      "/clients/1/ordonnances",
    );
    await screen.findByTestId("version-3");
    await choisirLaPhoto(fichierDe("ordonnance.jpg", "image/jpeg", 2 * UN_MO));

    const envoi = await vi.waitFor(() => {
      const trouve = appels.find(
        (appel) => appel.methode === "POST" && appel.chemin === "/api/ordonnances/31/photo/",
      );
      expect(trouve).toBeDefined();
      return trouve;
    });
    expect(envoi?.corps).toEqual(["fichier"]);
  });

  it("client09_les_octets_viennent_d_une_route_API_et_l_echec_rend_le_message_GLOBAL", async () => {
    // T-04-65 : jamais un chemin de media, jamais une adresse pre-signee. La
    // vue du plan 04-06 a deja resolu `ordonnance.voir`, et `storage.url()`
    // LEVE par conception. Un echec rend le message global de
    // `src/etats/messages.ts`, REUTILISE VERBATIM — pas une icone d'image
    // cassee, qui inviterait a chercher l'adresse directe.
    monter(
      {
        "/api/clients/1/ordonnances/": () =>
          reponse([
            versionStockee({
              a_une_photo: true,
              photo_attachee_le: "2026-02-12T10:02:00Z",
            }),
          ]),
      },
      "/clients/1/ordonnances",
    );

    const carte = await screen.findByTestId("version-3");
    const vignette = within(carte).getByTestId("vignette-photo") as HTMLImageElement;
    expect(vignette.getAttribute("src")).toBe("/api/ordonnances/31/photo/");
    expect(vignette.getAttribute("src")).not.toContain("media");
    // L'image ne porte aucune information exploitable par un lecteur d'ecran.
    expect(vignette.getAttribute("alt")).toBe("");

    fireEvent.error(vignette);
    expect(
      await within(carte).findByText(
        "Impossible de charger la photo. Vérifiez votre connexion.",
      ),
    ).toBeTruthy();
  });
});

/* =========================================================================
 * 21.5 — LA FEUILLE IMPRIMEE : un bloc documentaire, aucune geometrie
 * ======================================================================= */

describe("la feuille imprimee (CLIENT-06)", () => {
  it("client06_la_feuille_porte_la_convention_et_AUCUNE_photo", async () => {
    // **CE QUE CE TEST NE PROUVE PAS, et c'est ecrit plutot que sous-entendu :**
    // jsdom n'applique aucune feuille `@media print`. Il prouve que le bloc
    // existe, qu'il porte la convention et qu'il ne contient aucune image ; il
    // ne prouve pas qu'une feuille sortie d'une imprimante est LISIBLE. C'est
    // la verification manuelle n° 4.
    const imprimer = vi.fn();
    vi.stubGlobal("print", imprimer);

    monter(
      {
        "/api/clients/1/ordonnances/": () =>
          reponse([versionStockee({ a_une_photo: true })]),
      },
      "/clients/1/ordonnances",
    );

    const carte = await screen.findByTestId("version-3");
    const feuille = within(carte).getByTestId("feuille-ordonnance");

    // L'en-tete : le client, l'affaire, le magasin, la version et sa date.
    expect(feuille.textContent).toContain("Mohammed Alaoui");
    expect(feuille.textContent).toContain("Optique Anfa");
    expect(feuille.textContent).toContain("Anfa");
    expect(feuille.textContent).toContain("Version 3");
    // La correction, par LE MEME composant qu'a l'ecran.
    expect(within(feuille).getByTestId("correction-OD").textContent).toContain("+2,00");
    // Le pied : une correction imprimee sans convention enoncee est la mauvaise
    // paire de verres en attente d'etre commandee.
    expect(feuille.textContent).toContain("Cylindre négatif.");
    // AUCUNE PHOTO sur le ticket du comptoir, meme quand la version en porte une.
    expect(feuille.querySelectorAll("img").length).toBe(0);

    fireEvent.click(within(carte).getByRole("button", { name: "Imprimer" }));
    expect(imprimer).toHaveBeenCalled();
  });

  it("client06_print_css_rend_la_feuille_visible_et_n_ajoute_AUCUNE_geometrie_de_page", () => {
    const candidats = ["src/print.css", "web/src/print.css"].map((chemin) =>
      resolve(process.cwd(), chemin),
    );
    const trouve = candidats.find((chemin) => existsSync(chemin));
    // Le controle qui empeche ce test de passer pour la mauvaise raison : un
    // fichier introuvable doit rougir, pas rendre une chaine vide.
    expect(trouve).toBeDefined();
    const FEUILLE_CSS = readFileSync(trouve as string, "utf8");
    expect(FEUILLE_CSS.length).toBeGreaterThan(0);

    // La geometrie de page a ete livree en phase 3, et c'etait tout l'interet
    // de la livrer alors. La phase 4 n'ajoute qu'un bloc documentaire.
    expect(FEUILLE_CSS).toContain("feuille-ordonnance");
    // Une seule declaration `@page` dans tout le fichier, celle de la phase 3.
    expect(FEUILLE_CSS.match(/@page/g)?.length).toBe(1);
    expect(FEUILLE_CSS).not.toContain("size: A5");
  });
});

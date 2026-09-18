import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState, type ReactElement } from "react";
import { afterEach, describe, expect, it } from "vitest";

/* ---------------------------------------------------------------------------
 * Les primitives de saisie de la phase 4, prouvees AVANT tout ecran.
 *
 * Trois choses a savoir avant de lire ce fichier.
 *
 * 1. **jsdom ne calcule pas le CSS.** `toBeVisible()` rend `true` sur un
 *    element en `opacity-0`, et une tache rapide de la phase 3 a livre un
 *    controle invisible derriere 32 tests verts pour exactement cette raison.
 *    Toute revendication de visibilite de ce fichier est donc une assertion
 *    **de classe ou d'attribut**, et son intitule le dit.
 *
 * 2. **Aucune assertion d'ici n'attend un appel reseau**, donc aucune n'a
 *    besoin d'un tour de boucle d'evenements. Piege 2 de la phase 3 : un
 *    `await` ajoute « par prudence » masque une assertion jamais atteinte.
 *
 * 3. **Les nombres cliniques ne sont pas dans le code.** Q1 et D-4b : les
 *    bornes et le pas sont SERVIS (plan 04-04) et arrivent ici en argument.
 *    Ce fichier en tient une fixture ; `src/` n'en contient aucun.
 *
 * Le chargement des modules est paresseux, par `import.meta.glob`, comme dans
 * `format.test.ts` et pour la meme raison : un module absent doit rendre un
 * echec LISIBLE au lieu de faire echouer la transformation du fichier entier.
 * C'est ce qui permet aux blocs de modules purs de virer au vert a la tache 2,
 * pendant que les blocs de rendu attendent encore la tache 3.
 * ------------------------------------------------------------------------- */

const modulesChamps = import.meta.glob("../src/champs/*.{ts,tsx}");

const chargerChamp = async <T,>(nom: string, extension: "ts" | "tsx"): Promise<T> => {
  const charger = modulesChamps[`../src/champs/${nom}.${extension}`];
  if (!charger) {
    throw new Error(
      `src/champs/${nom}.${extension} n'existe pas encore. ` +
        `Modules trouves : ${JSON.stringify(Object.keys(modulesChamps))}`,
    );
  }
  return (await charger()) as T;
};

/* ---------------------------------------------------------------------------
 * L'objet que le SERVEUR servira (plan 04-04), tenu ici en FIXTURE.
 *
 * Il vit dans `tests/` et nulle part dans `src/` : D-4b veut les bornes a UN
 * endroit nomme, et une constante TypeScript en serait un second. Le
 * proprietaire a deja change ces chiffres une fois ; le prochain changement
 * doit couter une ligne, cote serveur.
 * ------------------------------------------------------------------------- */
const BORNES_SERVIES = {
  large: { min: "-20.00", max: "20.00", pas: "0.25" },
  etroite: { min: "-5.00", max: "5.00", pas: "0.25" },
};

/** L'annee de reference des tests de siecle. Figee : jamais `new Date()`. */
const ANNEE_FIGEE = 2026;

type SigneAttendu = "requis" | "fourni-positif" | "fourni-negatif" | "aucun";
type ReglesNombre = { decimales: 0 | 1 | 2; signe?: SigneAttendu };
type BornesMinMax = { min: string; max: string };

type ModuleNombres = {
  SIGNE_MOINS: string;
  normaliserNombre: (saisi: string, regles: ReglesNombre) => string | null;
  verifierBornes: (valeur: string, bornes: BornesMinMax) => string | null;
  verifierPas: (valeur: string, pas: string) => string | null;
};

type ModuleDates = {
  masquerDate: (saisi: string) => string;
  normaliserDate: (
    saisi: string,
    anneeCourante?: number,
  ) => { valeur: string } | { faute: string };
  versISO: (jjmmaaaa: string) => string;
  depuisISO: (iso: string) => string;
};

const chargerNombres = () => chargerChamp<ModuleNombres>("nombres", "ts");
const chargerDates = () => chargerChamp<ModuleDates>("dates", "ts");

afterEach(cleanup);

/* ===========================================================================
 * Les nombres — module pur, aucun rendu.
 * ======================================================================== */
describe("nombres", () => {
  it("accepte la virgule comme le point", async () => {
    const { normaliserNombre } = await chargerNombres();

    // Le pave numerique du comptoir emet un point ; l'opticien ecrit une
    // virgule. Les deux doivent produire la meme valeur (04-UI-SPEC.md 20.4).
    const parLePoint = normaliserNombre("31.5", { decimales: 1 });
    const parLaVirgule = normaliserNombre("31,5", { decimales: 1 });

    expect(parLePoint).toBe(parLaVirgule);
    expect(parLePoint).toBe("31,5");
  });

  it("rend le signe moins typographique", async () => {
    const { normaliserNombre, SIGNE_MOINS } = await chargerNombres();

    const rendu = normaliserNombre("-1", { decimales: 2, signe: "requis" });

    // Un trait d'union a 14px a cote d'un `+` est ambigu sur une grille dense :
    // le signe affiche est U+2212, jamais U+002D.
    expect(rendu).toBe("−1,00");
    expect(SIGNE_MOINS).toBe("−");
    expect(rendu).toContain("−");
    expect(rendu).not.toContain("-");
  });

  it("refuse un pas hors grille, et n_arrondit jamais", async () => {
    const { verifierPas, normaliserNombre } = await chargerNombres();
    const pas = BORNES_SERVIES.large.pas;

    const horsGrille = verifierPas("0,17", pas);
    const surGrille = verifierPas("0,75", pas);

    // L'assertion JUMELLE est celle qui mord : verifier seulement le refus
    // laisserait passer une implementation qui refuse tout.
    expect(horsGrille).not.toBeNull();
    expect(surGrille).toBeNull();

    // Et rien n'a ete corrige en passant. Un arrondi silencieux est un nombre
    // faux SANS erreur — ce que la couche ORM refuse deja un etage plus bas
    // (menace T-04-07).
    const normalise = normaliserNombre("0,17", { decimales: 2 });
    expect(normalise).toBe("0,17");
    expect(normalise).not.toBe("0,25");
  });

  it("le pas et les bornes sont des arguments", async () => {
    const { verifierBornes } = await chargerNombres();
    const valeur = "-12,00";

    const sousLesBornesLarges = verifierBornes(valeur, BORNES_SERVIES.large);
    const sousLesBornesEtroites = verifierBornes(valeur, BORNES_SERVIES.etroite);

    // La MEME valeur change de verdict selon l'objet servi. Ce que ce test
    // attrape : une constante clinique glissee dans le module, qui rendrait les
    // deux verdicts identiques (menace T-04-10).
    expect(sousLesBornesLarges).toBeNull();
    expect(sousLesBornesEtroites).not.toBeNull();
  });
});

/* ===========================================================================
 * Les dates — module pur, aucun rendu.
 * ======================================================================== */
describe("dates", () => {
  it("insere le slash apres le deuxieme et le quatrieme chiffre, sans rien recrire d_autre", async () => {
    const { masquerDate } = await chargerDates();

    expect(masquerDate("1")).toBe("1");
    expect(masquerDate("14")).toBe("14");
    expect(masquerDate("149")).toBe("14/9");
    expect(masquerDate("14092")).toBe("14/09/2");
    expect(masquerDate("14092026")).toBe("14/09/2026");

    // Le piege de tout masque naif : l'opticien qui tape LUI-MEME les slashes.
    // Une extraction « chiffres seuls » rendrait ici `14/92/026`.
    expect(masquerDate("14/9")).toBe("14/9");
    expect(masquerDate("14/9/2026")).toBe("14/9/2026");
    // Et l'effacement ne reinsere rien : `14` ne redevient pas `14/`.
    expect(masquerDate("14/")).toBe("14/");
    expect(masquerDate("14")).toBe("14");
  });

  it("complete au blur", async () => {
    const { normaliserDate } = await chargerDates();

    expect(normaliserDate("14/9/26", ANNEE_FIGEE)).toEqual({ valeur: "14/09/2026" });
    expect(normaliserDate("14/9/99", ANNEE_FIGEE)).toEqual({ valeur: "14/09/1999" });

    // L'annee de reference est un ARGUMENT. Un module pur dont le verdict
    // depend de `new Date()` est un test qui vire rouge un 1er janvier
    // (menace T-04-11).
    expect(normaliserDate("14/9/28", ANNEE_FIGEE)).toEqual({ valeur: "14/09/1928" });
    expect(normaliserDate("14/9/28", 2030)).toEqual({ valeur: "14/09/2028" });
  });

  it("refuse l_impossible", async () => {
    const { normaliserDate } = await chargerDates();

    // Les chaines exactes de 04-UI-SPEC.md 15.4 et 23, comparees
    // litteralement — pas reformulees, pas approchees.
    expect(normaliserDate("31/02/2026", ANNEE_FIGEE)).toEqual({
      faute: "Cette date n'existe pas.",
    });
    expect(normaliserDate("14/09", ANNEE_FIGEE)).toEqual({
      faute: "Date incomplète. Écrivez jj/mm/aaaa.",
    });
  });

  it("transporte en ISO et n_affiche jamais l_ISO", async () => {
    const { versISO, depuisISO } = await chargerDates();

    expect(versISO("14/09/2026")).toBe("2026-09-14");
    expect(depuisISO("2026-09-14")).toBe("14/09/2026");
  });
});

/* ===========================================================================
 * ChampDate — le SEUL bloc de rendu de ce fichier, et il est honnete sur ce
 * qu'il prouve.
 * ======================================================================== */
type ProprietesChampDate = {
  label: string;
  valeur: string;
  surChangement: (valeur: string) => void;
  futurInterdit?: boolean;
  messageFutur?: string;
  aujourdhui?: string;
  anneeCourante?: number;
};
type ComposantChampDate = (proprietes: ProprietesChampDate) => ReactElement;

function HarnaisDate({ Champ }: { Champ: ComposantChampDate }) {
  const [valeur, setValeur] = useState("");
  return <Champ label="Date de prescription" valeur={valeur} surChangement={setValeur} />;
}

describe("ChampDate", () => {
  it("porte un vrai label visible et insere les slashes en frappant", async () => {
    const { ChampDate } = await chargerChamp<{ ChampDate: ComposantChampDate }>(
      "ChampDate",
      "tsx",
    );
    render(<HarnaisDate Champ={ChampDate} />);

    // `getByLabelText` ne regarde PAS le placeholder. C'est tout l'interet :
    // le placeholder n'est pas le label (03-UI-SPEC.md 10), et cette
    // assertion-ci est la seule du fichier qui le prouve.
    const entree = screen.getByLabelText("Date de prescription") as HTMLInputElement;
    expect(entree.getAttribute("placeholder")).toBe("jj/mm/aaaa");

    const etiquette = document.querySelector<HTMLLabelElement>(`label[for="${entree.id}"]`);
    expect(etiquette).not.toBeNull();
    expect(etiquette?.textContent).toBe("Date de prescription");
    // Revendication DE CLASSE, pas de visibilite : jsdom ne calcule aucun CSS,
    // donc tout ce qui est verifiable ici est l'absence du masquage visuel.
    expect(etiquette?.className ?? "").not.toMatch(/sr-only/);

    for (const chiffre of "14092026") {
      fireEvent.change(entree, { target: { value: entree.value + chiffre } });
    }

    expect(entree.value).toBe("14/09/2026");
  });
});

/* ===========================================================================
 * ChampNombre — deux assertions d'ATTRIBUT, aucune de style.
 * ======================================================================== */
type ProprietesChampNombre = {
  label: string;
  valeur: string;
  surChangement: (valeur: string) => void;
  bornes: { min: string; max: string; pas: string };
  regles: ReglesNombre;
  suffixe?: string;
  avertissement?: string;
  faute?: string;
};
type ComposantChampNombre = (proprietes: ProprietesChampNombre) => ReactElement;

/** Un avertissement de 04-UI-SPEC.md 16.3, ligne A2, recopie au caractere pres. */
const AVERTISSEMENT_A2 =
  "À vérifier — une sphère de −12,00 est forte. Confirmez-la sur l'ordonnance.";

function HarnaisNombre({
  Champ,
  avertissement,
}: {
  Champ: ComposantChampNombre;
  avertissement?: string;
}) {
  const [valeur, setValeur] = useState("");
  return (
    <Champ
      label="Sphère de l'œil droit"
      valeur={valeur}
      surChangement={setValeur}
      bornes={BORNES_SERVIES.large}
      regles={{ decimales: 2, signe: "requis" }}
      avertissement={avertissement}
    />
  );
}

describe("ChampNombre", () => {
  it("n_est jamais type=number", async () => {
    const { ChampNombre } = await chargerChamp<{ ChampNombre: ComposantChampNombre }>(
      "ChampNombre",
      "tsx",
    );
    render(<HarnaisNombre Champ={ChampNombre} />);

    const entree = screen.getByLabelText("Sphère de l'œil droit");

    // Assertion d'ATTRIBUT, pas de classe. Les molettes, le defilement qui
    // change la valeur sous le curseur et `valueAsNumber = NaN` sur une virgule
    // francaise sont trois defauts REELS du champ numerique natif dans ce
    // produit (menace T-04-08).
    expect(entree.getAttribute("type")).toBe("text");
    expect(entree.getAttribute("inputmode")).toBe("decimal");
  });

  it("un avertissement ne porte pas aria-invalid et n_est pas role=alert", async () => {
    const { ChampNombre } = await chargerChamp<{ ChampNombre: ComposantChampNombre }>(
      "ChampNombre",
      "tsx",
    );
    render(<HarnaisNombre Champ={ChampNombre} avertissement={AVERTISSEMENT_A2} />);

    const entree = screen.getByLabelText("Sphère de l'œil droit");
    const note = screen.getByRole("status");

    expect(note.textContent).toContain(AVERTISSEMENT_A2);
    // `aria-invalid="true"` affirme que la valeur est FAUSSE ; un avertissement
    // n'affirme que son etrangete. Le poser rendrait l'un indiscernable de
    // l'autre pour exactement l'utilisateur qui ne voit pas la difference de
    // couleur — ce qui deferait toute la conception visuelle de 16.4 en un
    // attribut (menace T-04-09).
    expect(entree.hasAttribute("aria-invalid")).toBe(false);
    // Jamais `alert` : un avertissement apparait au fil de la saisie, et une
    // interruption assertive par frappe est hostile.
    expect(screen.queryByRole("alert")).toBeNull();

    const decritPar = (entree.getAttribute("aria-describedby") ?? "").split(/\s+/);
    expect(decritPar).toContain(note.id);
  });
});

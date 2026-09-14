import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import fixture from "../../tests/fixtures/formats_mad.json";

/* ---------------------------------------------------------------------------
 * Pourquoi la fixture est a la racine du depot et non dans web/
 *
 * `tests/fixtures/formats_mad.json` est un cran AU-DESSUS de web/, et c'est tout
 * l'interet : pytest la lit pour le formateur serveur (WeasyPrint, les PDF de la
 * phase 9) et vitest la lit pour le formateur client (le DOM, dans un
 * navigateur). La deposer dans web/ ferait du client le proprietaire du format
 * et du serveur un suiveur ; la deposer dans plateforme/ ferait l'inverse.
 *
 * Deux implementations sont inevitables. Python ne rend pas du DOM et TypeScript
 * ne rend pas un PDF WeasyPrint. L'objectif atteignable n'est donc PAS « un seul
 * formateur » — cette promesse ne peut pas etre tenue et il vaut mieux le dire
 * franchement ici que de la laisser croire. L'objectif est :
 *
 *     une seule specification, deux implementations testees contre elle.
 *
 * Le jour ou l'ecran affiche 1.800,00 MAD et la facture 1 800,00 MAD, le
 * coupable est une implementation qui a cesse de lire ce fichier, et l'un des
 * deux tests le dit.
 *
 * CLAUDE.md #14 : U+00A0 comme separateur de milliers, virgule decimale. Django
 * `fr`, l'ICU `fr-FR` du navigateur et l'ICU `fr-MA` sont tous les trois en
 * desaccord ici — `fr-MA` utilise meme le point. D'ou 03-UI-SPEC.md 8.1 :
 * Intl.NumberFormat et toLocaleString sont INTERDITS pour la monnaie, et le
 * troisieme test de ce fichier fait respecter cette interdiction des maintenant.
 * ------------------------------------------------------------------------- */

/** U+00A0, espace insecable. Le separateur retenu (CLAUDE.md #14). */
const ESPACE_INSECABLE = 0x00a0;
/** U+202F, espace fine insecable. Celui de l'ICU `fr-FR`. Refuse ici. */
const ESPACE_FINE_INSECABLE = 0x202f;
/** U+0020, espace ordinaire. Ce en quoi U+00A0 degenere silencieusement. */
const ESPACE_ORDINAIRE = 0x0020;

const SEPARATEUR_ATTENDU = "\u00a0";

type CasMontant = [entree: string, attendu: string];
type CasDate = [iso: string, court: string, heure: string];

const casMontants = fixture.cas_montants as CasMontant[];
const casDates = fixture.cas_dates as CasDate[];

const pointsDeCode = (valeur: string): number[] =>
  [...valeur].map((caractere) => caractere.codePointAt(0) as number);

/**
 * Chargement differe des formateurs, qui n'existent pas encore.
 *
 * `await import("@/format/montant")` ecrit tel quel est resolu par Vite au
 * moment de la TRANSFORMATION, pas de l'execution : le fichier entier echoue a
 * se charger tant que le module est absent, et il emporte avec lui le test
 * d'audit qui, lui, doit tourner des aujourd'hui. `.skip` n'y change rien —
 * ignorer un test n'empeche pas de transformer le fichier.
 *
 * `@vite-ignore` sur un specifieur variable ne convient pas non plus : il repousse
 * bien la resolution, mais hors du resolveur de Vite, donc l'alias `@` n'est plus
 * connu et le module reste introuvable meme une fois ecrit. Verifie, pas suppose.
 *
 * `import.meta.glob` est la bonne primitive : Vite l'evalue a la transformation,
 * un motif qui ne correspond a rien rend simplement un objet vide au lieu d'une
 * erreur, et chaque valeur est un vrai import paresseux passe par le resolveur.
 * Le plan 03-11 depose `src/format/montant.ts` et `src/format/date.ts`, retire
 * les `.skip`, et n'a rien d'autre a changer ici.
 */
const modulesFormat = import.meta.glob("../src/format/*.ts");

const chargerFormat = async <T>(nom: string): Promise<T> => {
  const charger = modulesFormat[`../src/format/${nom}.ts`];
  if (!charger) {
    throw new Error(
      `src/format/${nom}.ts n'existe pas encore — il est ecrit au plan 03-11. ` +
        `Modules trouves : ${JSON.stringify(Object.keys(modulesFormat))}`,
    );
  }
  return (await charger()) as T;
};

/* ===========================================================================
 * ACTIF. La specification elle-meme, verifiee aujourd'hui.
 *
 * Ce test ne depend d'aucun formateur : il affirme que la fixture partagee dit
 * toujours ce que l'utilisateur a tranche. Il est bon marche et il est le seul
 * garde-fou entre maintenant et le plan 03-11, ou les formateurs arrivent.
 * ======================================================================== */
describe("la fixture partagee epingle l'espace insecable", () => {
  it("declare U+00A0, jamais U+202F ni l'espace ordinaire", () => {
    expect(fixture.separateur_milliers).toBe(SEPARATEUR_ATTENDU);
    expect(fixture.separateur_avant_devise).toBe(SEPARATEUR_ATTENDU);
    expect(fixture.separateur_milliers.codePointAt(0)).toBe(ESPACE_INSECABLE);
    expect(fixture.separateur_avant_devise.codePointAt(0)).toBe(ESPACE_INSECABLE);
    expect(fixture.separateur_decimal).toBe(",");
    expect(fixture.devise).toBe("MAD");
    expect(fixture.decimales).toBe(2);
  });

  it("n'emploie aucune autre espace dans les montants attendus", () => {
    for (const [, attendu] of casMontants) {
      const points = pointsDeCode(attendu);
      expect(points).not.toContain(ESPACE_FINE_INSECABLE);
      expect(points).not.toContain(ESPACE_ORDINAIRE);
    }
  });

  it("attend bien 1 800,00 MAD avec deux espaces insecables", () => {
    const cas = casMontants.find(([entree]) => entree === "1800.00");
    expect(cas).toBeDefined();
    const attendu = (cas as CasMontant)[1];
    // Une comparaison de chaines laisse passer un U+00A0 mue en espace
    // ordinaire : a l'oeil les deux sont identiques. Les points de code, non.
    expect(pointsDeCode(attendu)).toEqual([
      0x31, // 1
      ESPACE_INSECABLE,
      0x38, // 8
      0x30, // 0
      0x30, // 0
      0x2c, // ,
      0x30, // 0
      0x30, // 0
      ESPACE_INSECABLE,
      0x4d, // M
      0x41, // A
      0x44, // D
    ]);
  });
});

/* ===========================================================================
 * IGNORE JUSQU'AU PLAN 03-11.
 *
 * `formaterMontant`, `formaterDateCourte` et `formaterDateHeure` n'existent pas
 * encore : ils sont ecrits au **plan 03-11**, qui RETIRE le `.skip` ci-dessous
 * en meme temps qu'il cree `src/format/montant.ts` et `src/format/date.ts`.
 *
 * Pourquoi `describe.skip` et pas `it.todo` : un `todo` ne verifie rien et se
 * fait oublier. Ici le corps des tests est ecrit, complet, et n'attend que son
 * module. L'import est DYNAMIQUE, a l'interieur du test : un import statique
 * casserait la collecte du fichier entier, donc aussi le test d'audit ci-dessus,
 * qui lui doit tourner des aujourd'hui.
 * ======================================================================== */
describe.skip("le formatage client respecte la fixture partagee", () => {
  describe("cas_montants", () => {
    it.each(casMontants)("formaterMontant(%s) rend %s", async (entree, attendu) => {
      const { formaterMontant } = await chargerFormat<{
        formaterMontant: (entree: string) => string;
      }>("montant");
      const rendu = formaterMontant(entree);

      expect(rendu).toBe(attendu);
      // Et les points de code, parce qu'une comparaison de chaines ou un U+00A0
      // s'est mue en espace ordinaire passe a l'oeil nu et pas au test.
      expect(pointsDeCode(rendu)).toEqual(pointsDeCode(attendu));
      expect(pointsDeCode(rendu)).not.toContain(ESPACE_FINE_INSECABLE);
      expect(pointsDeCode(rendu)).not.toContain(ESPACE_ORDINAIRE);
    });
  });

  describe("cas_dates", () => {
    it.each(casDates)(
      "formaterDateCourte(%s) rend %s et formaterDateHeure rend %s",
      async (iso, court, heure) => {
        const { formaterDateCourte, formaterDateHeure } = await chargerFormat<{
          formaterDateCourte: (iso: string) => string;
          formaterDateHeure: (iso: string) => string;
        }>("date");

        expect(formaterDateCourte(iso)).toBe(court);
        // Le fuseau d'affichage est Africa/Casablanca, converti DANS le
        // formateur et jamais dans les reglages : TIME_ZONE = "UTC" cote serveur
        // porte PgBouncer et ne doit pas bouger.
        expect(formaterDateHeure(iso)).toBe(heure);
        expect(pointsDeCode(formaterDateHeure(iso))).toEqual(pointsDeCode(heure));
      },
    );
  });
});

/* ===========================================================================
 * ACTIF, et il doit le rester.
 *
 * Il passe immediatement parce qu'aucun code fautif n'existe encore. Son role
 * n'est pas de constater, c'est d'empecher : 03-UI-SPEC.md 8.1 interdit
 * Intl.NumberFormat, toLocaleString et toute etiquette de locale fr-MA dans la
 * SPA. Les trois sont des facons de laisser une base de donnees de locales
 * decider du format de la monnaie, et les trois sources plausibles sont en
 * desaccord. Chercher une locale EST le bogue.
 *
 * src/format/ est la seule exception, et seulement pour les dates :
 * Intl.DateTimeFormat("fr-FR") y est autorise et epingle. Jamais pour l'argent.
 * ======================================================================== */
describe("aucune locale ne decide du format de l'argent", () => {
  // `process.cwd()` et non `import.meta.url` : sous vitest, l'URL d'un module
  // est celle du graphe de Vite, pas un file://, et `fileURLToPath` la refuse.
  // Le repertoire de travail est la racine du projet vitest, donc web/.
  const racineSrc = resolve(process.cwd(), "src");
  const INTERDITS = ["Intl.NumberFormat", "toLocaleString", "fr-MA"];

  const fichiersSurveilles = (): string[] =>
    readdirSync(racineSrc, { recursive: true, encoding: "utf8" })
      .filter((chemin) => /\.(ts|tsx|css|js|jsx)$/.test(chemin))
      // src/format/ est exclu : c'est le seul endroit ou une locale est permise,
      // et uniquement pour les dates.
      .filter((chemin) => !chemin.startsWith("format/") && !chemin.startsWith("format\\"));

  it("trouve bien des fichiers a surveiller", () => {
    // Controle positif. Sans lui, le test ci-dessous passerait contre un dossier
    // vide ou un glob casse, ce qui est une garantie qui n'en est pas une.
    expect(fichiersSurveilles().length).toBeGreaterThan(0);
  });

  it("aucun fichier hors src/format/ n'emploie Intl.NumberFormat, toLocaleString ni fr-MA", () => {
    const fautifs: string[] = [];

    for (const chemin of fichiersSurveilles()) {
      const contenu = readFileSync(join(racineSrc, chemin), "utf8");
      for (const interdit of INTERDITS) {
        if (contenu.includes(interdit)) {
          fautifs.push(`${chemin} : ${interdit}`);
        }
      }
    }

    expect(fautifs).toEqual([]);
  });
});

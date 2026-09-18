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
      `src/format/${nom}.ts n'existe pas encore — il est ecrit par le plan qui le livre. ` +
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
 * ACTIF depuis le plan 03-11.
 *
 * `formaterMontant`, `formaterDateCourte` et `formaterDateHeure` existent
 * desormais, dans `src/format/montant.ts` et `src/format/date.ts`. Cette suite
 * etait ecrite et ignoree depuis le plan 03-03 ; 03-11 a retire l'annotation
 * d'exclusion et livre les modules, dans cet ordre — la suite a d'abord echoue
 * pour la bonne raison (« src/format/montant.ts n'existe pas encore »).
 *
 * L'import reste DYNAMIQUE : c'est ce qui permettait a l'etat rouge d'exister
 * sans casser la collecte du fichier, donc sans emporter le test d'audit plus
 * bas, qui devait tourner des le premier jour.
 * ======================================================================== */
describe("le formatage client respecte la fixture partagee", () => {
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

/* ===========================================================================
 * ACTIF. Le contrat du module lui-meme.
 *
 * Le code de production ne lit jamais `tests/` : `src/format/montant.ts` porte
 * ses propres constantes. C'est voulu — une SPA qui lirait une fixture de test
 * a l'execution serait absurde. Mais une divergence entre les deux doit rendre
 * la suite ROUGE, sinon « une seule specification » n'est qu'une intention.
 * ======================================================================== */
describe("les constantes du module s'accordent avec la fixture", () => {
  it("separateurs, decimales et devise viennent bien du meme contrat", async () => {
    const module = await chargerFormat<{
      SEPARATEUR_MILLIERS: string;
      SEPARATEUR_DECIMAL: string;
      SEPARATEUR_AVANT_DEVISE: string;
      DECIMALES: number;
      DEVISE: string;
    }>("montant");

    expect(module.SEPARATEUR_MILLIERS).toBe(fixture.separateur_milliers);
    expect(module.SEPARATEUR_DECIMAL).toBe(fixture.separateur_decimal);
    expect(module.SEPARATEUR_AVANT_DEVISE).toBe(fixture.separateur_avant_devise);
    expect(module.DECIMALES).toBe(fixture.decimales);
    expect(module.DEVISE).toBe(fixture.devise);
    // Et les points de code, pas seulement l'egalite de chaines.
    expect(module.SEPARATEUR_MILLIERS.codePointAt(0)).toBe(ESPACE_INSECABLE);
    expect(module.SEPARATEUR_AVANT_DEVISE.codePointAt(0)).toBe(ESPACE_INSECABLE);
  });

  it("le fuseau d'affichage du module est celui de la fixture", async () => {
    const { FUSEAU_AFFICHAGE } = await chargerFormat<{ FUSEAU_AFFICHAGE: string }>("date");
    expect(FUSEAU_AFFICHAGE).toBe(fixture.fuseau_affichage);
  });
});

/* ===========================================================================
 * ACTIF. Le transport est une CHAINE, et l'arrondi ne passe pas par un double.
 * ======================================================================== */
describe("le formateur prend la chaine que l'API livre", () => {
  const chargerMontant = () =>
    chargerFormat<{ formaterMontant: (entree: string | number) => string }>("montant");

  it("n'exige pas un number : la chaine brute de DRF suffit", async () => {
    const { formaterMontant } = await chargerMontant();

    // COERCE_DECIMAL_TO_STRING est vrai cote DRF : un DecimalField arrive en
    // chaine. Exiger un `number` obligerait chaque appelant a ecrire
    // `Number(...)`, c'est-a-dire a fabriquer un flottant binaire par politesse.
    expect(typeof formaterMontant("1800.00")).toBe("string");
    expect(formaterMontant("1800.00")).toBe(formaterMontant("1800"));
    expect(formaterMontant("1800.0000")).toBe("1\u00a0800,00\u00a0MAD");
  });

  it("arrondit au demi superieur sans jamais passer par un flottant", async () => {
    const { formaterMontant } = await chargerMontant();

    // 999.995 vaut 999.99499999999997 en double : un `Math.round(x * 100)`
    // rendrait 999,99 la ou le serveur, qui quantize en ROUND_HALF_UP, rend
    // 1 000,00. Ce seul cas separe une implementation sur chaine d'une
    // implementation sur double, et il est dans la fixture pour cette raison.
    expect(formaterMontant("999.995")).toBe("1\u00a0000,00\u00a0MAD");
    expect(formaterMontant("0.005")).toBe("0,01\u00a0MAD");
    expect(formaterMontant("2.675")).toBe("2,68\u00a0MAD");
    // Et un montant au-dela de 53 bits reste juste, parce qu'aucun bit n'est en
    // jeu : 9007199254740993 n'est pas representable en double.
    expect(formaterMontant("9007199254740993.00")).toBe(
      "9\u00a0007\u00a0199\u00a0254\u00a0740\u00a0993,00\u00a0MAD",
    );
  });

  it("ne rend jamais un signe negatif sans montant", async () => {
    const { formaterMontant } = await chargerMontant();

    expect(formaterMontant("-12.30")).toBe("-12,30\u00a0MAD");
    // -0,001 arrondi a deux decimales vaut zero : « -0,00 MAD » serait un signe
    // sans montant, et sur une ligne de caisse cela se lit comme un retrait.
    expect(formaterMontant("-0.001")).toBe("0,00\u00a0MAD");
  });

  it("refuse ce qui n'est pas un decimal plutot que de rendre NaN", async () => {
    const { formaterMontant } = await chargerMontant();

    // « NaN MAD » sur une facture est un chiffre faux sans message d'erreur,
    // exactement ce que la couche ORM refuse deja cote serveur.
    expect(() => formaterMontant("mille huit cents")).toThrow(TypeError);
    expect(() => formaterMontant("")).toThrow(TypeError);
  });
});

/* ===========================================================================
 * ACTIF depuis le plan 04-02. Le TROISIEME format du produit.
 *
 * `formaterTelephone` rejoint `montant.ts` et `date.ts` dans `src/format/` —
 * pas parce que le formatage d'un numero est difficile, mais parce que
 * `${client.telephone}` ecrit en ligne dans trois composants est exactement la
 * divergence que la fixture monetaire existe pour empecher (04-UI-SPEC.md
 * 18.3, 03-UI-SPEC.md 8.1).
 *
 * L'espace entre les paires est un U+00A0 pour la meme raison que celui des
 * milliers : un espace ordinaire laisse la ligne se couper au milieu d'une
 * paire, et jsdom ne le verrait jamais. L'assertion porte donc sur les POINTS
 * DE CODE, pas sur une egalite qui se lit a l'oeil.
 *
 * Aucun cas de ce bloc n'attend un appel reseau : aucun `await` de tour de
 * boucle d'evenements n'y a sa place (piege 2 de la phase 3 — un `await`
 * inutile masque une assertion jamais atteinte).
 * ======================================================================== */
describe("formaterTelephone", () => {
  const chargerTelephone = () =>
    chargerFormat<{
      formaterTelephone: (valeur: string) => string;
      SEPARATEUR_PAIRES: string;
    }>("telephone");

  it("rend un numero marocain par paires, avec des espaces insecables", async () => {
    const { formaterTelephone, SEPARATEUR_PAIRES } = await chargerTelephone();
    const rendu = formaterTelephone("0612345678");

    expect(rendu).toBe("06 12 34 56 78");
    expect(SEPARATEUR_PAIRES.codePointAt(0)).toBe(ESPACE_INSECABLE);
    const points = pointsDeCode(rendu);
    expect(points.filter((point) => point === ESPACE_INSECABLE)).toHaveLength(4);
    expect(points).not.toContain(ESPACE_ORDINAIRE);
    expect(points).not.toContain(ESPACE_FINE_INSECABLE);
  });

  it("rend la forme internationale", async () => {
    const { formaterTelephone } = await chargerTelephone();
    const rendu = formaterTelephone("212612345678");

    expect(rendu).toBe("+212 6 12 34 56 78");
    expect(pointsDeCode(rendu)).not.toContain(ESPACE_ORDINAIRE);
  });

  it("rend verbatim ce qu'il ne reconnait pas", async () => {
    const { formaterTelephone } = await chargerTelephone();

    // JAMAIS de refus a l'affichage. Une fiche importee d'un tableur porte
    // n'importe quoi, et un formateur qui leverait mettrait la LISTE ENTIERE
    // en erreur pour une seule fiche mal saisie (menace T-04-12, acceptee).
    expect(formaterTelephone("12-34")).toBe("12-34");
    expect(formaterTelephone("")).toBe("");
    expect(formaterTelephone("0612 345 678 poste 4")).toBe("0612 345 678 poste 4");
  });

  it("ne consulte aucune locale", async () => {
    const { formaterTelephone } = await chargerTelephone();

    // Controle contre la reecriture « simplifiee » par `Intl`. Le module est
    // charge AVANT le sabotage, et le resultat est compare APRES la
    // restauration : si l'assertion echouait pendant, le formateur de message
    // de vitest toucherait un Intl en piege et masquerait la vraie cause.
    const rendu = sansAucuneLocale(() => formaterTelephone("0612345678"));

    expect(rendu).toBe("06 12 34 56 78");
  });
});

/**
 * Execute `operation` avec la locale du processus forcee ailleurs qu'en
 * francais ET tout acces a `Intl` piege.
 *
 * Forcer `LC_ALL` seul ne prouverait pas grand-chose : Node lit
 * l'environnement au demarrage. Le piege sur `Intl`, lui, est categorique —
 * la moindre consultation leve.
 */
function sansAucuneLocale<T>(operation: () => T): T {
  const intlOriginal = globalThis.Intl;
  const localeOriginale = process.env.LC_ALL;

  process.env.LC_ALL = "en_US.UTF-8";
  Object.defineProperty(globalThis, "Intl", {
    configurable: true,
    writable: true,
    value: new Proxy(
      {},
      {
        get(_cible, propriete) {
          throw new Error(
            `formaterTelephone a consulte Intl.${String(propriete)} : aucune locale ne decide de ce format`,
          );
        },
      },
    ),
  });

  try {
    return operation();
  } finally {
    Object.defineProperty(globalThis, "Intl", {
      configurable: true,
      writable: true,
      value: intlOriginal,
    });
    if (localeOriginale === undefined) {
      delete process.env.LC_ALL;
    } else {
      process.env.LC_ALL = localeOriginale;
    }
  }
}

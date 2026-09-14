import type React from "react";
import { createElement } from "react";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

/* ---------------------------------------------------------------------------
 * `@testing-library/react` est importe STATIQUEMENT, et ce n'est pas un detail
 * de style. Sa purge automatique entre deux tests s'enregistre en appelant
 * `afterEach` AU MOMENT DE L'IMPORT. Importe dynamiquement a l'interieur d'un
 * test, l'appel arrive apres la phase de collecte : la purge ne s'enregistre
 * pas, le DOM du test precedent reste dans `document.body`, et une requete
 * `screen.queryByText("Prix d'achat")` retrouve l'en-tete rendu par le test
 * d'avant. Vu ici : le cas « zero ligne » echouait sur le DOM d'un autre test.
 * ------------------------------------------------------------------------- */

/* ---------------------------------------------------------------------------
 * La moitie cliente de la couche de projection (PERM-06)
 *
 * Le serveur retire un champ qu'un gerant n'a pas le droit de voir. Le client ne
 * doit pas le ressusciter en colonne vide, en tiret, en infobulle ou en zero.
 *
 * 03-UI-SPEC.md 0.6 dit pourquoi ceci est un mecanisme et pas une discipline :
 * un tableau de colonnes code en dur dans un composant React reintroduira la
 * fuite en phase 8 en rendant simplement `prix_achat: undefined` comme une
 * colonne vide avec un en-tete. « Absent, pas grise » ne se maintient pas a la
 * relecture.
 *
 * Contrat (03-UI-SPEC.md 8.3) : chaque tableau declare ses colonnes dans un
 * registre CLE PAR LE NOM DE CHAMP DE L'API, et le rendu filtre sur les champs
 * REELLEMENT PRESENTS DANS LE PAYLOAD :
 *
 *     rendu = COLONNES.filter((c) => c.champ in ligne)
 *
 * Ce test est le miroir client du test de conformite parametre du serveur
 * (`test_perm06_champ_protege_absent_de_lapi_de_lexport_et_du_document`). Il est
 * ecrit AVANT le premier tableau, volontairement : ecrit apres, il serait ecrit
 * contre l'implementation qu'il est cense contraindre (menace T-03-15).
 *
 * RAPPEL, et il vaut pour tout fichier frontend de cette phase : ce filtre est un
 * CONFORT, jamais une application de la regle. Le controle est la restriction de
 * queryset et la projection cote serveur. Un champ qui arrive dans la charge
 * utile est deja divulgue, quoi que fasse ce composant.
 * ------------------------------------------------------------------------- */

/** Registre de colonnes, tel que 03-UI-SPEC.md 8.3 le decrit. */
const COLONNES_ARTICLE = [
  { champ: "reference", libelle: "Reference", align: "left" },
  { champ: "designation", libelle: "Designation", align: "left" },
  { champ: "prix_vente", libelle: "Prix de vente", align: "right", format: "montant" },
  // Champ protege. Un gerant sans `article.voir_prix_achat` ne le recoit pas.
  { champ: "prix_achat", libelle: "Prix d'achat", align: "right", format: "montant" },
] as const;

/**
 * Une ligne telle que le serveur la sert a un gerant SANS le droit
 * `article.voir_prix_achat` : la cle `prix_achat` est absente. Pas nulle, pas
 * vide, pas a zero — ABSENTE. C'est la distinction sur laquelle tout repose.
 */
const LIGNE_SANS_PRIX_ACHAT = {
  reference: "MON-4412",
  designation: "Monture acetate",
  prix_vente: "1800.00",
};

/**
 * Chargement differe — meme mecanisme que dans tests/format.test.ts. Il n'est
 * plus necessaire depuis que le plan 03-11 a livre les modules, mais il est
 * conserve : c'est lui qui a permis a l'etat rouge du plan 03-03 d'exister sans
 * casser la collecte du fichier, et le prochain test ecrit avant son module s'en
 * resservira.
 *
 * Le chemin est `../src/tableau/` et non `../src/projection/` : le plan 03-11
 * nomme le dossier `src/tableau/` et son composant `Tableau.tsx`. L'export
 * garde le nom `TableauProjete`, qui dit ce qu'il fait — il rend une PROJECTION,
 * pas un registre complet — et fait echo a `plateforme/projection/` cote
 * serveur : un seul registre, deux moteurs de rendu.
 */
const modulesTableau = import.meta.glob("../src/tableau/*.tsx");

const chargerTableau = async <T>(nom: string): Promise<T> => {
  const charger = modulesTableau[`../src/tableau/${nom}.tsx`];
  if (!charger) {
    throw new Error(`src/tableau/${nom}.tsx n'existe pas — il est ecrit au plan 03-11.`);
  }
  return (await charger()) as T;
};

type ProprietesTableau = {
  // Volontairement re-declare ici plutot qu'importe du composant : ce test
  // decrit le CONTRAT attendu, et un test qui importe le type qu'il verifie ne
  // verifie plus rien. `align` et `format` restent facultatifs — une colonne qui
  // n'en declare pas doit rester rendable.
  colonnes: readonly {
    champ: string;
    libelle: string;
    align?: "left" | "right";
    format?: "montant" | "date" | "dateheure";
  }[];
  lignes: readonly Record<string, unknown>[];
  legende: string;
  totaux?: Readonly<Record<string, string>>;
};

const chargerTableauProjete = () =>
  chargerTableau<{ TableauProjete: React.ComponentType<ProprietesTableau> }>("Tableau").then(
    (module) => module.TableauProjete,
  );

/**
 * Requete SANS normalisation du texte.
 *
 * Le normaliseur par defaut de Testing Library remplace toute suite de `\s` par
 * une espace ORDINAIRE — et U+00A0 est un `\s`. Il efface donc exactement le
 * caractere que CLAUDE.md #14 epingle : `screen.getByText("1<U+00A0>800,00<U+00A0>MAD")`
 * ne trouve rien, parce que le texte de l'element a ete ramene a des espaces
 * ordinaires avant la comparaison, tandis que la chaine cherchee, elle, ne l'est
 * pas. Pire, avec le normaliseur par defaut un rendu FAUTIF qui produirait des
 * espaces ordinaires passerait le test.
 *
 * Neutraliser le normaliseur rend la comparaison exacte, point de code par point
 * de code — ce que la fixture partagee exige.
 */
const SANS_NORMALISATION = { normalizer: (contenu: string) => contenu };

/** Le texte d'une cellule, normalise, pour comparer a un substitut EXACT. */
const textesDeCellules = (container: HTMLElement): string[] =>
  [...container.querySelectorAll("th, td")].map((cellule) =>
    (cellule.textContent ?? "").trim(),
  );

/* ===========================================================================
 * ACTIF depuis le plan 03-11.
 * ======================================================================== */
describe("le rendu d'un tableau suit la presence dans le payload", () => {
  it("la colonne absente du payload ne produit aucun en-tete", async () => {
    const TableauProjete = await chargerTableauProjete();

    const { container } = render(
      createElement(TableauProjete, {
        colonnes: COLONNES_ARTICLE,
        lignes: [LIGNE_SANS_PRIX_ACHAT],
        legende: "Articles",
      }),
    );

    // Controle positif d'abord. Sans lui, tout ce qui suit passerait contre un
    // rendu vide — une garantie qui n'en est pas une.
    expect(screen.getByText("Prix de vente")).toBeTruthy();
    expect(screen.getByText("Monture acetate")).toBeTruthy();
    expect(screen.getByText("1\u00a0800,00\u00a0MAD", SANS_NORMALISATION)).toBeTruthy();

    // 1. Aucun en-tete.
    expect(screen.queryByText("Prix d'achat")).toBeNull();
    expect(container.querySelector('[data-champ="prix_achat"]')).toBeNull();

    // 2. Aucun substitut. Ni tiret, ni N/A, ni zero monetaire.
    //
    //    La comparaison est faite CELLULE PAR CELLULE et sur le texte EXACT, et
    //    non par `textContent.includes(...)` sur le tableau entier : « MON-4412 »
    //    contient un tiret et « 1 800,00 MAD » contient « 0,00 ». Un test qui
    //    cherche ces sous-chaines echoue sur des donnees parfaitement legitimes,
    //    et un test qui echoue au hasard finit par etre desactive.
    const substituts = ["—", "-", "–", "N/A", "n/a", "0,00\u00a0MAD", "0,00", "—", "?"];
    for (const texte of textesDeCellules(container)) {
      expect(substituts).not.toContain(texte);
    }
    expect(textesDeCellules(container)).not.toContain("");

    // 3. Aucune infobulle, aucune icone de cadenas, aucun « vous n'avez pas
    //    acces a cette colonne ». La colonne n'est pas la.
    expect(container.querySelectorAll('[role="tooltip"]').length).toBe(0);
    expect(container.querySelectorAll("[title]").length).toBe(0);
    expect(container.innerHTML.includes("prix_achat")).toBe(false);
    expect(container.innerHTML.toLowerCase().includes("acces")).toBe(false);

    // 4. Aucun total derive du champ absent. Un total affiche a zero est pire
    //    qu'une colonne absente : c'est un mauvais chiffre sans message d'erreur.
    expect(container.querySelectorAll("th, td").length).toBe(6); // 3 + 3, jamais 4 + 4
  });

  it("la colonne presente dans le payload produit bien son en-tete", async () => {
    const TableauProjete = await chargerTableauProjete();

    // Le meme registre, un payload de proprietaire : la colonne reapparait sans
    // qu'une seule ligne du registre ne change. C'est ce qui prouve que la
    // presence est pilotee par la donnee et non par une branche cote client.
    const { container } = render(
      createElement(TableauProjete, {
        colonnes: COLONNES_ARTICLE,
        lignes: [{ ...LIGNE_SANS_PRIX_ACHAT, prix_achat: "900.00" }],
        legende: "Articles",
      }),
    );

    expect(screen.getByText("Prix d'achat")).toBeTruthy();
    expect(screen.getByText("900,00\u00a0MAD", SANS_NORMALISATION)).toBeTruthy();
    expect(container.querySelectorAll("th, td").length).toBe(8);
  });

  it("un total derive d'un champ absent n'est pas affiche, meme pas a zero", async () => {
    const TableauProjete = await chargerTableauProjete();

    // Le serveur fournit les deux totaux — il les a calcules en Decimal — mais la
    // ligne servie a CE gerant n'a pas `prix_achat`. Le total correspondant ne
    // doit pas apparaitre : ni sa valeur, qui divulguerait le champ retire, ni un
    // zero, qui serait un chiffre faux sans erreur.
    const { container } = render(
      createElement(TableauProjete, {
        colonnes: COLONNES_ARTICLE,
        lignes: [LIGNE_SANS_PRIX_ACHAT],
        legende: "Articles",
        totaux: { prix_vente: "1800.00", prix_achat: "900.00" },
      }),
    );

    expect(screen.getByText("Total")).toBeTruthy();
    expect(screen.getAllByText("1\u00a0800,00\u00a0MAD", SANS_NORMALISATION).length).toBe(2); // la ligne et le total
    expect(screen.queryByText("900,00\u00a0MAD", SANS_NORMALISATION)).toBeNull();
    expect(screen.queryByText("0,00\u00a0MAD", SANS_NORMALISATION)).toBeNull();
    expect(container.innerHTML.includes("prix_achat")).toBe(false);
  });

  it("sans aucune ligne, aucun en-tete n'est devine depuis le registre", async () => {
    const TableauProjete = await chargerTableauProjete();

    // Cas limite, et c'est le plus sournois : une recherche sans resultat. Rendre
    // les en-tetes du registre revelerait a un gerant sans le droit que la
    // colonne « Prix d'achat » existe. La presence est pilotee par la donnee, et
    // il n'y a pas de donnee.
    const { container } = render(
      createElement(TableauProjete, {
        colonnes: COLONNES_ARTICLE,
        lignes: [],
        legende: "Articles",
      }),
    );

    expect(container.querySelectorAll("th").length).toBe(0);
    expect(screen.queryByText("Prix d'achat")).toBeNull();
    expect(screen.queryByText("Prix de vente")).toBeNull();
  });

  it("porte ses exigences d'accessibilite des maintenant", async () => {
    const TableauProjete = await chargerTableauProjete();

    // Ce composant est herite par neuf phases. Les exigences de 03-UI-SPEC.md
    // section 10 sont moins cheres a porter maintenant qu'a rattraper ensuite.
    const { container } = render(
      createElement(TableauProjete, {
        colonnes: COLONNES_ARTICLE,
        lignes: [LIGNE_SANS_PRIX_ACHAT],
        legende: "Articles",
      }),
    );

    const legende = container.querySelector("caption");
    expect(legende).toBeTruthy();
    expect(legende?.textContent).toBe("Articles");
    // Visuellement cache, mais lu : une legende retiree du DOM ne sert personne.
    expect(legende?.className).toContain("sr-only");

    const entetes = [...container.querySelectorAll("th")];
    expect(entetes.length).toBe(3);
    for (const entete of entetes) {
      expect(entete.getAttribute("scope")).toBe("col");
    }
  });
});

/* ===========================================================================
 * Le registre lui-meme, teste hors de tout rendu.
 * ======================================================================== */
describe("le registre filtre sur la presence du champ dans la ligne", () => {
  it("colonnesVisibles ne garde que les champs presents", async () => {
    const { colonnesVisibles } = await import("../src/tableau/registre");

    const visibles = colonnesVisibles(COLONNES_ARTICLE, LIGNE_SANS_PRIX_ACHAT);
    expect(visibles.map((colonne) => colonne.champ)).toEqual([
      "reference",
      "designation",
      "prix_vente",
    ]);

    const toutes = colonnesVisibles(COLONNES_ARTICLE, {
      ...LIGNE_SANS_PRIX_ACHAT,
      prix_achat: "900.00",
    });
    expect(toutes.map((colonne) => colonne.champ)).toEqual([
      "reference",
      "designation",
      "prix_vente",
      "prix_achat",
    ]);
  });

  it("une cle presente et nulle reste visible : null est une valeur, pas une absence", async () => {
    const { colonnesVisibles } = await import("../src/tableau/registre");

    // `in` et non `!== undefined`, et la difference est exactement le sujet : le
    // serveur RETIRE la cle quand le droit manque, et la LAISSE a null quand la
    // donnee est simplement inconnue. Tester la valeur au lieu de la presence
    // confondrait « tu n'as pas le droit » et « ce n'est pas renseigne ».
    const visibles = colonnesVisibles(COLONNES_ARTICLE, {
      ...LIGNE_SANS_PRIX_ACHAT,
      prix_achat: null,
    });
    expect(visibles.map((colonne) => colonne.champ)).toContain("prix_achat");
  });
});

/* ===========================================================================
 * `Valeur` — du contenu arabe dans une interface francaise (03-UI-SPEC.md 8.5)
 *
 * `dir="ltr"` sur `<html>` est permanent : il n'y a pas d'interface arabe, et
 * BRAND-04 concerne du CONTENU arabe dans des documents imprimes. Mais les noms,
 * les adresses et les enseignes en arabe doivent s'afficher correctement, et
 * l'algorithme bidirectionnel d'Unicode ne demande pas la permission : un nom
 * arabe voisin de ponctuation ou de chiffres fait migrer les caracteres neutres
 * qui l'entourent, et la LIGNE SE LIT FAUX sans qu'un seul caractere n'ait
 * change.
 * ======================================================================== */
describe("toute valeur fournie par l'utilisateur est isolee bidirectionnellement", () => {
  /** Un nom arabe reel, en caracteres arabes : « Mohamed Alaoui ». */
  const NOM_ARABE = "محمد العلوي";

  it("Valeur enveloppe son contenu dans un bdi", async () => {
    const { Valeur } = await chargerTableau<{
      Valeur: React.ComponentType<{ children: React.ReactNode; langue?: string }>;
    }>("Valeur");

    const { container } = render(
      createElement(Valeur, { children: NOM_ARABE, langue: "ar" }),
    );

    const isolant = container.querySelector("bdi");
    expect(isolant).toBeTruthy();
    expect(isolant?.textContent).toBe(NOM_ARABE);
    // `lang` quand la langue de la valeur est connue : la synthese vocale doit
    // lire un nom arabe en arabe, pas en francais (03-UI-SPEC.md section 10).
    expect(isolant?.getAttribute("lang")).toBe("ar");
  });

  it("un nom arabe dans une ligne ne reordonne pas ce qui l'entoure", async () => {
    const TableauProjete = await chargerTableauProjete();

    // Une ligne melangeant un nom arabe, une reference latine et un numero —
    // exactement la situation du comptoir. Sans isolation, la reference et le
    // numero neutres se rangent du cote du texte arabe et la ligne se lit a
    // l'envers.
    const { container } = render(
      createElement(TableauProjete, {
        colonnes: [
          { champ: "reference", libelle: "Reference", align: "left" },
          { champ: "nom", libelle: "Nom", align: "left" },
          { champ: "telephone", libelle: "Telephone", align: "left" },
        ],
        lignes: [{ reference: "CLI-2031", nom: NOM_ARABE, telephone: "0612-345678" }],
        legende: "Clients",
      }),
    );

    // Chaque valeur d'utilisateur est dans son propre bdi.
    const isolants = [...container.querySelectorAll("tbody bdi")];
    expect(isolants.length).toBe(3);
    expect(isolants.map((isolant) => isolant.textContent)).toEqual([
      "CLI-2031",
      NOM_ARABE,
      "0612-345678",
    ]);

    // Et l'ordre du DOM est l'ordre du registre, sans exception : c'est ce que
    // l'isolation garantit et que son absence casse.
    const cellules = [...container.querySelectorAll("tbody td")];
    expect(cellules.map((cellule) => cellule.getAttribute("data-champ"))).toEqual([
      "reference",
      "nom",
      "telephone",
    ]);
    for (const cellule of cellules) {
      expect(cellule.querySelector("bdi")).toBeTruthy();
    }
  });

  it("la colonne d'un nom reste alignee a gauche quel que soit le sens du contenu", async () => {
    const TableauProjete = await chargerTableauProjete();

    // Aligner une colonne selon le sens d'ecriture de son contenu ferait sauter
    // les valeurs d'un bord a l'autre d'une ligne a la suivante, et le tableau
    // cesserait d'etre une grille que l'oeil peut balayer. L'alignement est une
    // decision du registre, jamais une deduction du contenu.
    const colonnes = [{ champ: "nom", libelle: "Nom", align: "left" }] as const;

    const latin = render(
      createElement(TableauProjete, {
        colonnes,
        lignes: [{ nom: "Alaoui" }],
        legende: "Clients",
      }),
    );
    const celluleLatine = latin.container.querySelector("td");
    latin.unmount();

    const arabe = render(
      createElement(TableauProjete, {
        colonnes,
        lignes: [{ nom: NOM_ARABE }],
        legende: "Clients",
      }),
    );
    const celluleArabe = arabe.container.querySelector("td");

    expect(celluleArabe?.className).toBe(celluleLatine?.className);
    expect(celluleArabe?.className).toContain("text-left");
    // Et aucun `dir` pose par le tableau : c'est `<bdi>` qui isole, a l'interieur
    // de la cellule, sans deplacer la cellule.
    expect(celluleArabe?.getAttribute("dir")).toBeNull();
  });
});

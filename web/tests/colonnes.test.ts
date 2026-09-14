import type React from "react";
import { createElement } from "react";

import { describe, expect, it } from "vitest";

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
 * Chargement differe — meme raison et meme mecanisme que dans
 * tests/format.test.ts : Vite resout un `import("...")` litteral a la
 * transformation et non a l'execution, donc un module absent ferait echouer le
 * fichier entier avant meme que `.skip` n'ait son mot a dire. `import.meta.glob`
 * rend un objet vide quand rien ne correspond, au lieu d'une erreur.
 */
const modulesProjection = import.meta.glob("../src/projection/*.tsx");

const chargerProjection = async <T>(nom: string): Promise<T> => {
  const charger = modulesProjection[`../src/projection/${nom}.tsx`];
  if (!charger) {
    throw new Error(
      `src/projection/${nom}.tsx n'existe pas encore — il est ecrit au plan 03-11.`,
    );
  }
  return (await charger()) as T;
};

/* ===========================================================================
 * IGNORE JUSQU'AU PLAN 03-11.
 *
 * `TableauProjete` n'existe pas encore : il est ecrit au **plan 03-11**, qui
 * RETIRE le `.skip` ci-dessous. L'import est dynamique, a l'interieur du test,
 * pour que la collecte de ce fichier n'echoue pas d'ici la.
 *
 * Contrat attendu du module, pour que 03-11 n'ait pas a le deviner :
 *
 *     src/projection/tableau.tsx
 *     export function TableauProjete({ colonnes, lignes, legende }) { ... }
 *
 * Le nom fait echo a `plateforme/projection/` cote serveur : un seul registre,
 * deux moteurs de rendu.
 * ======================================================================== */
describe.skip("le rendu d'un tableau suit la presence dans le payload", () => {
  it("la colonne absente du payload ne produit aucun en-tete", async () => {
    const { render, screen } = await import("@testing-library/react");
    const { TableauProjete } = await chargerProjection<{
      TableauProjete: React.ComponentType<{
        colonnes: readonly { champ: string; libelle: string }[];
        lignes: readonly Record<string, unknown>[];
        legende: string;
      }>;
    }>("tableau");

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

    // 1. Aucun en-tete.
    expect(screen.queryByText("Prix d'achat")).toBeNull();
    expect(container.querySelector('[data-champ="prix_achat"]')).toBeNull();

    // 2. Aucun substitut. Ni tiret cadratin, ni N/A, ni zero monetaire.
    const texte = container.textContent ?? "";
    for (const substitut of ["—", "-", "N/A", "0,00 MAD", "0,00"]) {
      expect(texte.includes(substitut)).toBe(false);
    }

    // 3. Aucune infobulle, aucune icone de cadenas, aucun « vous n'avez pas
    //    acces a cette colonne ». La colonne n'est pas la.
    expect(container.querySelectorAll('[role="tooltip"]').length).toBe(0);
    expect(container.innerHTML.includes("prix_achat")).toBe(false);
    expect(container.innerHTML.toLowerCase().includes("acces")).toBe(false);

    // 4. Aucun total derive du champ absent. Un total affiche a zero est pire
    //    qu'une colonne absente : c'est un mauvais chiffre sans message d'erreur.
    const cellules = container.querySelectorAll("th, td");
    expect(cellules.length).toBe(6); // 3 en-tetes + 3 cellules, jamais 4 + 4
  });

  it("la colonne presente dans le payload produit bien son en-tete", async () => {
    const { render, screen } = await import("@testing-library/react");
    const { TableauProjete } = await chargerProjection<{
      TableauProjete: React.ComponentType<{
        colonnes: readonly { champ: string; libelle: string }[];
        lignes: readonly Record<string, unknown>[];
        legende: string;
      }>;
    }>("tableau");

    // Le meme registre, un payload de proprietaire : la colonne reapparait sans
    // qu'une seule ligne du registre ne change. C'est ce qui prouve que la
    // presence est pilotee par la donnee et non par une branche cote client.
    render(
      createElement(TableauProjete, {
        colonnes: COLONNES_ARTICLE,
        lignes: [{ ...LIGNE_SANS_PRIX_ACHAT, prix_achat: "900.00" }],
        legende: "Articles",
      }),
    );

    expect(screen.getByText("Prix d'achat")).toBeTruthy();
  });
});

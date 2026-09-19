import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
import { reinitialiserLeClient } from "@/api/client";
import { AVERTISSEMENT_SANS_TELEPHONE } from "@/pages/clients/messages";
import { LigneDeCorrection } from "@/pages/clients/ordonnances/LigneDeCorrection";
import { canonicaliserAxe, transposer } from "@/pages/clients/ordonnances/optique";
import { attendUnNomAccessible } from "./nomAccessible";
import {
  AVERTISSEMENTS,
  ORDONNANCE_VIDE,
  bornesDuCylindre,
  bornesDeLecartPupillaire,
  verifierOrdonnance,
  type Ordonnance,
} from "@/pages/clients/ordonnances/verifier";

/* ---------------------------------------------------------------------------
 * L'ecran de saisie d'une ordonnance — les modules purs, la grille, le
 * panneau de relecture et l'enregistrement.
 *
 * QUATRE PIEGES DEJA PAYES GOUVERNENT CE FICHIER, et les trois premiers sont
 * ceux de `tests/clients.test.tsx`.
 *
 * 1. **jsdom ne calcule AUCUN CSS.** Aucune revendication de ce fichier n'est
 *    visuelle. Ce qui se prouve ici : la presence dans le DOM, des attributs,
 *    l'ordre des noeuds, des noms accessibles, et l'ABSENCE de jetons
 *    destructifs dans une liste de classes. Ce qui NE se prouve pas ici : qu'un
 *    avertissement se lit plus discretement qu'un refus. C'est la verification
 *    manuelle n° 2 de `04-VALIDATION.md`, et elle se fait EN NIVEAUX DE GRIS.
 * 2. **`mutate()` rend la main AVANT `fetch`.** Toute assertion « rien n'est
 *    parti » attend un tour de boucle explicite.
 * 3. **Construit n'est pas atteignable.** Le premier `it` de la partie
 *    « acces » part d'une adresse de liste et CLIQUE.
 * 4. **Une table de cas partagee avec son jumeau serveur.** Les cas de
 *    transposition sont ceux de `tests/test_optique.py`, deliberement : deux
 *    implementations de la meme formule eprouvees par deux tables divergent, et
 *    personne ne le sait avant la premiere paire de verres fausse.
 * ------------------------------------------------------------------------- */

/**
 * Les bornes telles que l'amorcage les SERT (`domaine/ordonnances/bornes.py`).
 *
 * Elles vivent dans le test, jamais dans `src/pages/clients/` : c'est
 * exactement ce que `npm run audit:clinique` verifie, et ce fichier est du
 * cote ou les chiffres ont le droit d'etre ecrits.
 */
const BORNES = {
  sphere: { min: "-20.00", max: "20.00", pas: "0.25", signe_obligatoire: true },
  cylindre: { min: "-10.00", max: "0.00", pas: "0.25", convention: "negatif" },
  axe: { min: 1, max: 180, pas: 1 },
  addition: { min: "0.75", max: "4.00", pas: "0.25" },
  ep_binoculaire: { min: "45.0", max: "85.0", pas: "0.5" },
  ep_monoculaire: { min: "18.0", max: "44.5", pas: "0.5" },
};

/** Le MEME contrat, avec d'autres chiffres. Le proprietaire en a deja change une fois. */
const BORNES_ETROITES = {
  ...BORNES,
  sphere: { min: "-6.00", max: "6.00", pas: "0.25", signe_obligatoire: true },
};

const MOINS = "−";

/** Une saisie normale, complete, et parfaitement ordinaire. */
function saisieNormale(surcharge: Partial<Ordonnance> = {}): Ordonnance {
  return {
    ...ORDONNANCE_VIDE,
    sphere_od: "+2,00",
    sphere_og: "+1,75",
    cylindre_od: `${MOINS}1,00`,
    cylindre_og: `${MOINS}0,75`,
    axe_od: "90",
    axe_og: "175",
    addition_od: "+2,25",
    addition_og: "+2,25",
    ep_saisi: "monoculaire",
    ep_mono_od: "31,5",
    ep_mono_og: "30,5",
    source: "ordonnance_medicale",
    prescripteur: "Dr. Bennani",
    date_prescription: "14/03/2025",
    magasin: "1",
    ...surcharge,
  };
}

const textes = (v: Ordonnance, ctx: Parameters<typeof verifierOrdonnance>[1]) =>
  verifierOrdonnance(v, ctx).map((r) => r.texte);

const avertissements = (v: Ordonnance, ctx: Parameters<typeof verifierOrdonnance>[1]) =>
  verifierOrdonnance(v, ctx).filter((r) => r.severite === "avertissement");

const refus = (v: Ordonnance, ctx: Parameters<typeof verifierOrdonnance>[1]) =>
  verifierOrdonnance(v, ctx).filter((r) => r.severite === "refus");

/* =========================================================================
 * 20.3 — la transposition, la MEME table de cas que `tests/test_optique.py`
 * ======================================================================= */

describe("la transposition cote client (CLIENT-08)", () => {
  it("client08_l_exemple_marocain_verifie_se_transpose_a_l_identique", () => {
    // 04-RESEARCH.md 6.1 : (+1,50 ; −0,50 ; 20°) → (+1,00 ; +0,50 ; 110°).
    expect(
      transposer(
        { sphere: "+1,50", cylindre: `${MOINS}0,50`, axe: "20" },
        BORNES.axe,
      ),
    ).toEqual({ sphere: "+1,00", cylindre: "+0,50", axe: "110" });
  });

  it("client08_transposer_deux_fois_rend_la_saisie_d_origine", () => {
    for (const cas of [
      { sphere: "+2,00", cylindre: `${MOINS}1,00`, axe: "90" },
      { sphere: `${MOINS}3,25`, cylindre: `${MOINS}0,75`, axe: "175" },
      { sphere: "+0,25", cylindre: `${MOINS}2,50`, axe: "1" },
    ]) {
      expect(transposer(transposer(cas, BORNES.axe), BORNES.axe)).toEqual(cas);
    }
  });

  it("client07_un_axe_canonicalise_n_est_JAMAIS_zero", () => {
    // 0 et 180 sont le meme meridien, et un seul encodage est stocke.
    expect(canonicaliserAxe(0, BORNES.axe)).toBe(BORNES.axe.max);
    expect(canonicaliserAxe(BORNES.axe.max, BORNES.axe)).toBe(BORNES.axe.max);
    // La transposition d'un axe de 90 tombe sur le tour complet, pas sur 0.
    expect(
      transposer({ sphere: "+1,00", cylindre: `${MOINS}1,00`, axe: "90" }, BORNES.axe).axe,
    ).toBe(String(BORNES.axe.max));
  });

  it("client08_le_cylindre_vide_ne_transpose_rien", () => {
    const sansCylindre = { sphere: "+2,00", cylindre: "", axe: "" };
    expect(transposer(sansCylindre, BORNES.axe)).toEqual(sansCylindre);
  });
});

/* =========================================================================
 * 16.2 — les bornes sont SERVIES. La preuve est qu'elles changent le verdict.
 * ======================================================================= */

describe("les bornes servies (CLIENT-07, Q1)", () => {
  it("client07_deux_jeux_de_bornes_rendent_deux_verdicts_sur_la_MEME_valeur", () => {
    // La preuve qu'aucun chiffre n'est compile : seule la donnee change.
    const forte = saisieNormale({ sphere_od: "+8,00" });

    expect(refus(forte, { bornes: BORNES })).toHaveLength(0);

    const etroit = refus(forte, { bornes: BORNES_ETROITES });
    expect(etroit).toHaveLength(1);
    expect(etroit[0].champ).toBe("sphere_od");
    expect(etroit[0].texte).toBe(`La sphère va de ${MOINS}6,00 à +6,00.`);
  });

  it("client07_la_borne_de_l_ecart_pupillaire_est_l_union_des_deux_bornes_servies", () => {
    // La forme monoculaire et la forme binoculaire partagent UN champ de
    // saisie ; sa borne de refus est donc l'union des deux plages servies.
    // Le discriminant, lui, est devenu un avertissement (Q4).
    expect(bornesDeLecartPupillaire(BORNES)).toEqual({
      min: BORNES.ep_monoculaire.min,
      max: BORNES.ep_binoculaire.max,
      pas: BORNES.ep_monoculaire.pas,
    });
  });

  it("client08_la_borne_du_cylindre_positif_est_la_borne_servie_RETOURNEE", () => {
    // Aucun second chiffre : la plage positive est l'opposee de la negative.
    expect(bornesDuCylindre(BORNES, "positif")).toEqual({
      min: "0.00",
      max: "10.00",
      pas: BORNES.cylindre.pas,
    });
    expect(bornesDuCylindre(BORNES, "negatif")).toEqual(BORNES.cylindre);
  });
});

/* =========================================================================
 * 16.3 — les ONZE avertissements
 * ======================================================================= */

describe("la table d'avertissements (16.3)", () => {
  it("client07_la_table_compte_exactement_ONZE_lignes", () => {
    // 16.3 se clot par « ne pas ajouter un douzieme sans en supprimer un ».
    // Les deux discriminants d'ecart pupillaire ABSORBENT A8 et A9 au lieu de
    // s'y ajouter : onze avant l'amendement Q4, onze apres.
    expect(Object.keys(AVERTISSEMENTS)).toHaveLength(11);
  });

  it("client01_A11_est_LA_MEME_phrase_que_celle_de_l_ecran_de_creation", () => {
    // A11 ne porte pas sur une ordonnance : elle vit sur le dialogue de
    // creation d'un client (plan 04-07). La tracer ici est ce qui garde la
    // table a onze lignes sans la recopier.
    expect(AVERTISSEMENTS.A11.texte({})).toBe(AVERTISSEMENT_SANS_TELEPHONE);
  });

  it("client07_une_saisie_normale_complete_ne_rend_AUCUNE_remarque", () => {
    // Le test qui protege la valeur de la table. Si une prescription ordinaire
    // produit deux avertissements, la table est du bruit et le douzieme sera
    // ignore.
    expect(textes(saisieNormale(), { bornes: BORNES })).toEqual([]);
  });

  it("client07_A1_l_addition_differe_entre_les_deux_yeux", () => {
    const v = saisieNormale({ addition_og: "+2,00" });
    expect(textes(v, { bornes: BORNES })).toContain(
      "À vérifier — l'addition est normalement identique aux deux yeux. OD +2,25, OG +2,00.",
    );
  });

  it("client07_A2_une_sphere_forte_est_confirmee_et_non_refusee", () => {
    const v = saisieNormale({ sphere_od: `${MOINS}12,00` });
    expect(refus(v, { bornes: BORNES })).toHaveLength(0);
    expect(textes(v, { bornes: BORNES })).toContain(
      `À vérifier — une sphère de ${MOINS}12,00 est forte. Confirmez-la sur l'ordonnance.`,
    );
  });

  it("client07_A3_l_ecart_entre_les_deux_spheres", () => {
    const v = saisieNormale({ sphere_od: "+3,00", sphere_og: `${MOINS}3,00` });
    expect(textes(v, { bornes: BORNES })).toContain(
      "À vérifier — 6,00 d'écart entre les deux yeux. Vérifiez les signes.",
    );
  });

  it("client07_A7_la_somme_des_monoculaires_ne_fait_pas_le_binoculaire", () => {
    const v = saisieNormale({
      ep_saisi: "les_deux",
      ep_binoculaire: "64,0",
      ep_mono_od: "31,5",
      ep_mono_og: "30,5",
    });
    expect(textes(v, { bornes: BORNES })).toContain(
      "À vérifier — l'écart binoculaire ne correspond pas à la somme des monoculaires : " +
        "64,0 contre 31,5 + 30,5 = 62,0.",
    );
  });

  it("client07_A10_moins_de_seize_ans_et_refraction_opticien", () => {
    const v = saisieNormale({ source: "refraction_opticien", prescripteur: "" });
    expect(
      textes(v, { bornes: BORNES, dateNaissance: "01/06/2012" }),
    ).toContain(
      "À vérifier — moins de 16 ans : la correction doit venir d'une ordonnance médicale.",
    );
    // Le meme enfant, majeur au jour de la prescription : rien.
    expect(textes(v, { bornes: BORNES, dateNaissance: "01/06/2000" })).toEqual([]);
  });
});

/* =========================================================================
 * 16.3 A4/A5/A6 — ce que la version precedente ajoute, et rien d'autre
 * ======================================================================= */

describe("les avertissements de comparaison (16.3 A4, A5, A6)", () => {
  const precedente = saisieNormale({
    date_prescription: "14/03/2025",
    sphere_od: "+2,00",
    axe_od: "90",
    addition_od: "+2,25",
    addition_og: "+2,25",
  });

  it("client06_A4_A5_A6_N_EXISTENT_PAS_sans_version_precedente", () => {
    // Le premier client de l'affaire ne doit pas voir trois remarques sur une
    // saisie parfaite.
    const v = saisieNormale({ sphere_od: "+5,00", axe_od: "9", addition_od: "+1,75", addition_og: "+1,75" });
    expect(avertissements(v, { bornes: BORNES })).toEqual([]);
    expect(avertissements(v, { bornes: BORNES, precedente }).length).toBeGreaterThan(0);
  });

  it("client07_A4_attrape_le_90_tape_pour_9", () => {
    // LA panne nommee de toute la phase.
    const v = saisieNormale({ axe_od: "9" });
    expect(textes(v, { bornes: BORNES, precedente })).toContain(
      "À vérifier — l'axe OD passe de 90° à 9° depuis le 14/03/2025.",
    );
  });

  it("client07_A4_ne_hurle_PAS_sur_un_axe_qui_franchit_l_horizontale", () => {
    // SONDE. 175° et 5° sont a dix degres l'un de l'autre, pas a cent
    // soixante-dix : l'axe est periodique. Sans cette periode, A4 se
    // declencherait a chaque renouvellement d'un astigmatisme proche de
    // l'horizontale — et une table qui hurle est une table qu'on cesse de lire.
    const precedenteHorizontale = saisieNormale({ axe_od: "175", axe_og: "175" });
    const v = saisieNormale({ axe_od: "5", axe_og: "175" });
    expect(
      avertissements(v, { bornes: BORNES, precedente: precedenteHorizontale }),
    ).toEqual([]);
  });

  it("client07_A5_la_sphere_a_bouge_de_plus_de_deux_dioptries", () => {
    const v = saisieNormale({ sphere_od: "+5,00" });
    expect(textes(v, { bornes: BORNES, precedente })).toContain(
      "À vérifier — la sphère OD passe de +2,00 à +5,00 depuis le 14/03/2025.",
    );
  });

  it("client07_A6_l_addition_diminue", () => {
    const v = saisieNormale({ addition_od: "+1,75", addition_og: "+1,75" });
    expect(textes(v, { bornes: BORNES, precedente })).toContain(
      "À vérifier — l'addition diminue par rapport au 14/03/2025.",
    );
  });
});

/* =========================================================================
 * 20.5 amende — le discriminant 45 mm AVERTIT, il ne refuse plus (Q4)
 * ======================================================================= */

describe("le discriminant monoculaire/binoculaire (Q4, amendement de 20.5)", () => {
  it("client07_un_binoculaire_sous_la_borne_servie_AVERTIT_sans_refuser", () => {
    const v = saisieNormale({
      ep_saisi: "binoculaire",
      ep_binoculaire: "31,5",
      ep_mono_od: "",
      ep_mono_og: "",
    });
    const remarques = verifierOrdonnance(v, { bornes: BORNES });
    const discriminant = remarques.find((r) => r.champ === "ep_binoculaire");

    expect(discriminant?.severite).toBe("avertissement");
    expect(discriminant?.texte).toBe(
      "À vérifier — un écart binoculaire de 31,5 mm est un écart monoculaire. " +
        "Choisissez « monoculaire » ci-dessus.",
    );
    // Le renversement lui-meme : plus aucun refus sur cette valeur.
    expect(refus(v, { bornes: BORNES })).toHaveLength(0);
  });

  it("client07_un_monoculaire_au_dessus_de_la_borne_servie_AVERTIT_sans_refuser", () => {
    const v = saisieNormale({ ep_mono_od: "62,0" });
    const remarques = verifierOrdonnance(v, { bornes: BORNES });
    const discriminant = remarques.find((r) => r.champ === "ep_mono_od");

    expect(discriminant?.severite).toBe("avertissement");
    expect(discriminant?.texte).toBe(
      "À vérifier — un écart monoculaire de 62,0 mm est un écart binoculaire. " +
        "Choisissez « binoculaire » ci-dessus.",
    );
    expect(refus(v, { bornes: BORNES })).toHaveLength(0);
  });

  it("client07_hors_de_l_union_l_avertissement_ne_DOUBLE_pas_le_refus", () => {
    // SONDE. Un refus et un avertissement sur le meme champ pour la meme
    // valeur, c'est du bruit — et 16.3 refuse le bruit avant de refuser le
    // douzieme avertissement. La moitie « … est inhabituel. » de A8 et A9
    // decrivait exactement cette region : elle a ete supprimee, pas oubliee.
    const trop = saisieNormale({ ep_mono_od: "95,0" });
    expect(avertissements(trop, { bornes: BORNES }).map((r) => r.champ)).not.toContain(
      "ep_mono_od",
    );
    const sous = saisieNormale({
      ep_saisi: "binoculaire",
      ep_binoculaire: "9,0",
      ep_mono_od: "",
      ep_mono_og: "",
    });
    expect(avertissements(sous, { bornes: BORNES })).toEqual([]);
    expect(refus(sous, { bornes: BORNES })).toHaveLength(1);
  });

  it("client07_au_dela_de_l_union_des_bornes_servies_c_est_un_REFUS", () => {
    // La severite a change pour le discriminant, pas pour la borne : un
    // nombre physiquement impossible reste refuse, avec la borne SERVIE.
    const v = saisieNormale({ ep_mono_od: "95,0" });
    expect(refus(v, { bornes: BORNES }).map((r) => r.texte)).toContain(
      "L'écart pupillaire va de 18,0 à 85,0.",
    );
  });
});

/* =========================================================================
 * 20.4 et 20.8 — les refus
 * ======================================================================= */

describe("les refus de la saisie (20.4, 20.8, 20.9)", () => {
  it("client03_une_sphere_sans_signe_est_refusee", () => {
    const v = saisieNormale({ sphere_od: "2,00" });
    expect(textes(v, { bornes: BORNES })).toContain(
      `Indiquez le signe : +2,00 ou ${MOINS}2,00.`,
    );
  });

  it("client03_un_cylindre_positif_en_notation_negative_est_refuse", () => {
    const v = saisieNormale({ cylindre_od: "+1,00" });
    expect(textes(v, { bornes: BORNES })).toContain(
      "En cylindre négatif, le cylindre ne peut pas être positif. " +
        "Basculez la notation ci-dessus si l'ordonnance est en cylindre positif.",
    );
  });

  it("client03_une_valeur_hors_de_la_grille_du_pas_est_refusee_jamais_arrondie", () => {
    const v = saisieNormale({ addition_od: "+2,10", addition_og: "+2,10" });
    expect(textes(v, { bornes: BORNES })).toContain("Les valeurs vont par pas de 0,25.");
  });

  it("client07_le_cylindre_sans_axe_et_l_axe_sans_cylindre_sont_refuses_DANS_LES_DEUX_SENS", () => {
    expect(textes(saisieNormale({ axe_od: "" }), { bornes: BORNES })).toContain(
      "Le cylindre de l'œil droit demande un axe.",
    );
    expect(textes(saisieNormale({ cylindre_og: "" }), { bornes: BORNES })).toContain(
      "Un axe sans cylindre n'a pas de sens. Saisissez le cylindre, ou effacez l'axe.",
    );
  });

  it("client05_la_source_non_choisie_est_refusee", () => {
    const v = saisieNormale({ source: "", prescripteur: "" });
    expect(textes(v, { bornes: BORNES })).toContain(
      "Indiquez la source : ordonnance médicale ou réfraction opticien.",
    );
  });

  it("client04_le_prescripteur_manque_sur_une_ordonnance_medicale", () => {
    const v = saisieNormale({ prescripteur: "  " });
    expect(textes(v, { bornes: BORNES })).toContain("Qui a prescrit ? Indiquez le médecin.");
  });

  it("client04_aucun_prescripteur_n_est_exige_en_refraction_opticien", () => {
    const v = saisieNormale({ source: "refraction_opticien", prescripteur: "" });
    expect(textes(v, { bornes: BORNES })).toEqual([]);
  });

  it("client03_le_magasin_non_choisi_est_refuse", () => {
    const v = saisieNormale({ magasin: "" });
    expect(textes(v, { bornes: BORNES })).toContain(
      "Indiquez le magasin qui enregistre cette ordonnance.",
    );
  });

  it("client04_une_date_de_prescription_dans_le_futur_est_refusee", () => {
    const v = saisieNormale({ date_prescription: "14/03/2099" });
    expect(textes(v, { bornes: BORNES, aujourdhui: "2026-09-18" })).toContain(
      "Une ordonnance ne peut pas être datée dans le futur.",
    );
  });
});

/* =========================================================================
 * 19.3 — UN composant rend une correction, partout
 * ======================================================================= */

describe("LigneDeCorrection (19.3)", () => {
  it("client03_la_ligne_rend_la_correction_dans_la_NOTATION_du_papier", () => {
    render(
      <LigneDeCorrection
        oeil="OD"
        sphere="+2,00"
        cylindre={`${MOINS}1,00`}
        axe="90"
        addition="+2,25"
      />,
    );
    // Une phrase continue, et non quatre cases : c'est la FORME qui fait
    // relire, pas les chiffres.
    const ligne = screen.getByTestId("correction-OD");
    expect(ligne.textContent).toContain(`+2,00 (${MOINS}1,00 à 90°)`);
    expect(ligne.textContent).toContain("Add. +2,25");
  });

  it("client03_le_lecteur_d_ecran_entend_oeil_droit_et_non_les_lettres_OD", () => {
    render(<LigneDeCorrection oeil="OG" sphere="+1,75" cylindre="" axe="" addition="" />);
    expect(screen.getByText("œil gauche")).toBeTruthy();
  });

  it("client03_sans_cylindre_la_parenthese_n_est_pas_rendue", () => {
    render(<LigneDeCorrection oeil="OD" sphere="+2,00" cylindre="" axe="" addition="" />);
    expect(screen.getByTestId("correction-OD").textContent).not.toContain("(");
  });
});

/* =========================================================================
 * 20 — L'ECRAN. Tout ce qui suit monte l'application entiere.
 *
 * Les blocs ci-dessus eprouvent des modules PURS ; ceux qui suivent eprouvent
 * le rendu, et ils heritent des trois pieges de `tests/clients.test.tsx` :
 * jsdom ne calcule aucun CSS, `mutate()` rend la main avant `fetch`, et
 * construit n'est pas atteignable.
 * ======================================================================= */

const ANFA = { id: 1, code: "ANFA", nom: "Anfa" };
const CALIFORNIE = { id: 2, code: "CALI", nom: "Californie" };

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

/**
 * L'amorcage, **avec ses bornes cliniques**.
 *
 * C'est la moitie du contrat de 16.2 que seul un test de bout en bout peut
 * montrer : l'ecran ne porte aucun chiffre, donc il n'affiche rien tant que
 * l'amorcage ne lui en sert pas.
 */
function amorcageDe(
  permissions: string[],
  magasins: { id: number; code: string; nom: string }[] = [ANFA],
) {
  return {
    utilisateur: {
      id: 7,
      email: "karim@optiqueanfa.ma",
      nom_complet: "Karim Benali",
      est_proprietaire: false,
      doit_changer_mot_de_passe: false,
    },
    client: { code: "anfa", raison_sociale: "Optique Anfa" },
    permissions,
    magasins,
    catalogue: CATALOGUE,
    bornes_ordonnance: BORNES,
  };
}

const AU_COMPTOIR = amorcageDe([
  "client.voir",
  "ordonnance.voir",
  "ordonnance.saisir",
]);

/** Une fiche telle que `/api/clients/{id}/` la sert. */
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

/** Une version STOCKEE, dans la forme du serveur : point decimal, axe entier. */
function versionStockee(surcharge: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 11,
    client: 1,
    magasin: 1,
    version: 1,
    supersede: null,
    type_revision: "",
    motif_revision: "",
    source: "ordonnance_medicale",
    prescripteur: "Dr. Bennani",
    date_prescription: "2025-03-14",
    sphere_od: "2.00",
    sphere_og: "1.75",
    cylindre_od: "-1.00",
    cylindre_og: "-0.75",
    axe_od: 90,
    axe_og: 175,
    addition_od: "2.25",
    addition_og: "2.25",
    ep_saisi: "monoculaire",
    ep_binoculaire: null,
    ep_mono_od: "31.5",
    ep_mono_og: "30.5",
    ...surcharge,
  };
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
    vi.fn(async (requete: Request) => {
      const chemin = new URL(requete.url, "http://localhost").pathname;
      const texte = ["POST", "PATCH"].includes(requete.method)
        ? await requete.clone().text()
        : "";
      appels.push({
        methode: requete.method,
        chemin,
        corps: texte === "" ? undefined : JSON.parse(texte),
      });
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

const ROUTE_SAISIE = "/clients/1/ordonnances/nouvelle";

function monter(
  table: Table,
  chemin: string = ROUTE_SAISIE,
  amorcage: unknown = AU_COMPTOIR,
) {
  poserLesReponses({
    "/api/auth/csrf/": () => sansCorps(204),
    "/api/auth/moi/": () => reponse(amorcage),
    "/api/clients/1/": () => reponse(fiche()),
    "/api/clients/1/ordonnances/": () => reponse([]),
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

/** Le formulaire, et JAMAIS `document` : la portee est ce qui rend l'enumeration honnete. */
async function formulaire(): Promise<HTMLElement> {
  return await screen.findByTestId("formulaire-ordonnance");
}

/** Taper, puis QUITTER le champ — les deux moities sont distinctes, et 16.4 en depend. */
function taper(champ: HTMLElement, valeur: string): void {
  fireEvent.change(champ, { target: { value: valeur } });
}

function quitter(champ: HTMLElement): void {
  fireEvent.blur(champ);
}

async function champ(nom: string): Promise<HTMLElement> {
  return await screen.findByLabelText(nom);
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
 * 20.1 — la route, et ce qu'un test d'atteignabilite peut honnetement dire
 * ======================================================================= */

describe("l'acces a la saisie (CLIENT-05, 20.1)", () => {
  it("client05_la_saisie_est_montee_dans_le_ROUTEUR_de_l_application_sous_le_shell", async () => {
    // Pas un montage de composant : c'est `App` entier, sa table de routes, sa
    // garde et son shell. Un ecran qui ne rend que hors de l'application est
    // un ecran que personne n'ouvrira jamais.
    monter({});

    expect(
      await screen.findByRole("heading", { name: "Nouvelle ordonnance", level: 1 }),
    ).toBeTruthy();
    // Le shell, donc la navigation : la route vit DANS l'application.
    expect(
      screen.getByRole("navigation", { name: "Navigation principale" }),
    ).toBeTruthy();
    // Le nom du client, en sous-titre : l'ecran sait de qui il parle.
    expect(await screen.findByText("Mohammed Alaoui")).toBeTruthy();
  });

  it("client05_sans_ordonnance_saisir_la_route_rend_la_403_qui_NOMME_le_droit", async () => {
    monter({}, ROUTE_SAISIE, amorcageDe(["client.voir"]));

    expect(
      await screen.findByRole("heading", { name: "Vous n'avez pas accès à cette page." }),
    ).toBeTruthy();
    expect(
      await screen.findByText(
        "Il vous manque le droit « Saisir une ordonnance ». Demandez-le au propriétaire.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("ordonnance.saisir")).toBeNull();
  });

  it("client01_la_liste_mene_au_client_et_le_DERNIER_maillon_arrive_au_plan_04_09", async () => {
    // HONNETETE, et elle est ecrite plutot qu'impliquee. La chaine humaine
    // complete est « `/` → Clients → la ligne → `Saisir une ordonnance` ». Le
    // dernier maillon est le bouton de la carte de 19.3, qui vit sur la FICHE,
    // construite au plan 04-09 — et 18.2 interdit explicitement une colonne
    // d'actions sur la liste, donc ce plan n'a aucun endroit legitime ou le
    // poser. Ce test prouve les maillons qui existent aujourd'hui, et le
    // SUMMARY dit lequel manque.
    monter({ "/api/clients/": () => reponse([fiche()]) }, "/");

    const barre = await screen.findByRole("navigation", {
      name: "Navigation principale",
    });
    fireEvent.click(within(barre).getByRole("link", { name: "Clients" }));
    fireEvent.click(await screen.findByText("Mohammed Alaoui"));

    await waitFor(() => {
      expect(cheminCourant()).toBe("/clients/1");
    });
  });

  it("client05_aucun_numero_de_version_n_est_PREDIT_avant_l_enregistrement", async () => {
    // La meme habitude que le numero de facture emis par le client, que
    // CLAUDE.md #3 interdit. Le serveur emet la version, sous verrou.
    monter({ "/api/clients/1/ordonnances/": () => reponse([versionStockee()]) });
    const form = await formulaire();

    expect(form.textContent).not.toContain("Ce sera la version");
    expect(form.textContent).not.toContain("version 2");
  });
});

/* =========================================================================
 * 20.2 et 25.3 — la grille EST le tableau du papier
 * ======================================================================= */

describe("la grille OD/OG (CLIENT-03, 20.2, 25.3)", () => {
  const ORDRE = [
    "Sphère de l'œil droit",
    "Cylindre de l'œil droit",
    "Axe de l'œil droit",
    "Addition de l'œil droit",
    "Sphère de l'œil gauche",
    "Cylindre de l'œil gauche",
    "Axe de l'œil gauche",
    "Addition de l'œil gauche",
  ];

  it("client03_la_tabulation_parcourt_la_grille_EN_LIGNES_et_non_en_colonnes", async () => {
    // L'ordre du DOM EST l'ordre de tabulation, faute de `tabindex` positif.
    // Une grille parcourue en colonnes ferait lire le papier de travers.
    monter({});
    const grille = await screen.findByTestId("grille-od-og");
    const entrees = [...grille.querySelectorAll("input")];

    expect(entrees.map((entree) => nomDuChamp(entree))).toEqual(ORDRE);
  });

  it("client03_chaque_entree_porte_un_VRAI_label_et_non_un_aria_label", async () => {
    // 25.3 : un `<label>` agrandit aussi la cible, ce qu'un `aria-label` ne
    // fait pas. La mesure est donc double — le nom existe, ET il vient d'un
    // element `label` reel.
    monter({});
    const grille = await screen.findByTestId("grille-od-og");

    for (const entree of grille.querySelectorAll("input")) {
      attendUnNomAccessible(entree);
      expect(entree.getAttribute("aria-label")).toBeNull();
      expect(grille.querySelector(`label[for="${entree.id}"]`)).toBeTruthy();
    }
  });

  it("client03_la_grille_n_est_PAS_une_table_et_ne_porte_aucun_tabindex_positif", async () => {
    // Une table de champs fait annoncer des coordonnees au lieu du sens.
    monter({});
    const form = await formulaire();

    expect(form.querySelector("table")).toBeNull();
    for (const noeud of form.querySelectorAll("[tabindex]")) {
      expect(Number(noeud.getAttribute("tabindex"))).toBeLessThanOrEqual(0);
    }
  });

  it("client03_les_entetes_et_le_degre_sont_aria_hidden_pour_ne_pas_etre_lus_deux_fois", async () => {
    monter({});
    const grille = await screen.findByTestId("grille-od-og");

    const entete = within(grille).getByText("Sphère");
    expect(entete.closest("[aria-hidden='true']")).toBeTruthy();
    const degre = within(grille).getAllByText("°")[0];
    expect(degre.closest("[aria-hidden='true']")).toBeTruthy();
    // Le `°` est HORS de l'entree : le label masque dit deja « Axe ».
    expect(degre.querySelector("input")).toBeNull();
  });
});

/** Le nom accessible d'une entree, par son `<label>`. */
function nomDuChamp(entree: Element): string {
  const etiquette = entree.ownerDocument.querySelector(`label[for="${entree.id}"]`);
  return etiquette?.textContent?.trim() ?? "";
}

/* =========================================================================
 * 20.3 — la bascule de notation transpose SUR PLACE et l'annonce
 * ======================================================================= */

describe("la bascule de notation (CLIENT-08, 20.3)", () => {
  it("client08_basculer_transpose_les_valeurs_DEJA_TAPEES_sur_place_et_l_annonce", async () => {
    monter({});
    const sphere = await champ("Sphère de l'œil droit");
    const cylindre = await champ("Cylindre de l'œil droit");
    const axe = await champ("Axe de l'œil droit");

    taper(sphere, "+2,00");
    quitter(sphere);
    taper(cylindre, `${MOINS}1,00`);
    quitter(cylindre);
    taper(axe, "90");
    quitter(axe);

    fireEvent.click(screen.getByRole("radio", { name: "Cylindre positif" }));

    // SUR PLACE : ce sont les memes champs qui portent la valeur transposee.
    await waitFor(() => {
      expect((sphere as HTMLInputElement).value).toBe("+1,00");
    });
    expect((cylindre as HTMLInputElement).value).toBe("+1,00");
    expect((axe as HTMLInputElement).value).toBe(String(BORNES.axe.max));

    // ET L'ANNONCE, poliment.
    expect(
      screen.getByText(
        `Transposé en cylindre positif : OD +1,00 (+1,00 à ${String(BORNES.axe.max)}°).`,
      ),
    ).toBeTruthy();
  });

  it("client08_la_convention_de_stockage_est_ecrite_A_L_ECRAN", async () => {
    // `04-CONTEXT.md` le demande : une erreur de convention doit se voir a la
    // premiere saisie, pas a la premiere paire de verres fausse.
    monter({});
    const form = await formulaire();

    expect(
      within(form).getAllByText("Les valeurs sont enregistrées en cylindre négatif.")
        .length,
    ).toBeGreaterThan(0);
  });

  it("client08_le_defaut_est_le_cylindre_NEGATIF_toujours", async () => {
    monter({});
    expect(
      ((await screen.findByRole("radio", { name: "Cylindre négatif" })) as HTMLInputElement)
        .checked,
    ).toBe(true);
  });
});

/* =========================================================================
 * 20.5 — l'ecart pupillaire
 * ======================================================================= */

describe("l'ecart pupillaire (CLIENT-07, 20.5)", () => {
  it("client07_la_somme_est_un_AFFICHAGE_et_aucun_monoculaire_n_est_CALCULE", async () => {
    monter({});
    fireEvent.click(await screen.findByRole("radio", { name: "les deux" }));

    const od = await champ("Écart pupillaire de l'œil droit");
    const og = await champ("Écart pupillaire de l'œil gauche");
    const bino = await champ("Écart pupillaire binoculaire");
    taper(od, "31,5");
    quitter(od);
    taper(og, "30,5");
    quitter(og);

    expect(await screen.findByText("somme : 62,0 mm")).toBeTruthy();
    // La somme n'est PAS un champ : elle n'a ni label ni valeur soumise.
    expect(screen.queryByLabelText("somme")).toBeNull();
    // Et le binoculaire reste ce que l'opticien en a fait : vide.
    expect((bino as HTMLInputElement).value).toBe("");
  });

  it("client07_la_regle_de_l_ecart_pupillaire_est_VISIBLE_et_non_cachee_dans_un_commentaire", async () => {
    monter({});
    expect(
      await screen.findByText(
        "On enregistre ce qui a été saisi ; la somme binoculaire s'affiche comme contrôle " +
          "quand les deux monoculaires existent ; on ne calcule jamais un monoculaire.",
      ),
    ).toBeTruthy();
  });

  it("client07_la_forme_choisie_decide_des_champs_rendus", async () => {
    monter({});
    fireEvent.click(await screen.findByRole("radio", { name: "binoculaire" }));

    expect(await screen.findByLabelText("Écart pupillaire binoculaire")).toBeTruthy();
    expect(screen.queryByLabelText("Écart pupillaire de l'œil droit")).toBeNull();
  });
});

/* =========================================================================
 * 20.8 et 20.9 — source, prescripteur, magasin
 * ======================================================================= */

describe("la source, le prescripteur et le magasin (CLIENT-04, CLIENT-05, 20.8, 20.9)", () => {
  it("client05_la_source_n_a_AUCUN_defaut", async () => {
    // Une source pre-selectionnee est une affirmation clinique que personne
    // n'a faite.
    monter({});
    for (const nom of ["Ordonnance médicale", "Réfraction opticien"]) {
      expect(((await screen.findByRole("radio", { name: nom })) as HTMLInputElement).checked)
        .toBe(false);
    }
  });

  it("client04_le_prescripteur_n_est_PAS_RENDU_en_refraction_opticien", async () => {
    monter({});
    fireEvent.click(await screen.findByRole("radio", { name: "Ordonnance médicale" }));
    expect(await screen.findByLabelText("Prescripteur")).toBeTruthy();

    fireEvent.click(screen.getByRole("radio", { name: "Réfraction opticien" }));
    await waitFor(() => {
      expect(screen.queryByLabelText("Prescripteur")).toBeNull();
    });
    expect(
      screen.getByText("La réfraction a été faite au magasin. Aucun prescripteur à indiquer."),
    ).toBeTruthy();
  });

  it("client03_un_SEUL_magasin_ne_rend_aucun_controle", async () => {
    // Le precedent `03` 7.3B : pas de decision, pas de controle.
    monter({});
    const form = await formulaire();

    expect(within(form).getByText("Anfa")).toBeTruthy();
    expect(within(form).queryByRole("radio", { name: "Anfa" })).toBeNull();
    expect(within(form).queryByRole("combobox")).toBeNull();
  });

  it("client03_sous_TOUS_LES_MAGASINS_rien_n_est_preselectionne", async () => {
    // La portee par defaut d'un proprietaire a deux magasins est « Tous ».
    // 5.4 ne s'applique PAS ici : le contenu est transversal et correct, seule
    // une valeur enregistree manque — donc un champ, pas une invite pleine page.
    monter(
      {},
      ROUTE_SAISIE,
      {
        ...amorcageDe(
          ["client.voir", "ordonnance.voir", "ordonnance.saisir"],
          [ANFA, CALIFORNIE],
        ),
        utilisateur: {
          id: 7,
          email: "karim@optiqueanfa.ma",
          nom_complet: "Karim Benali",
          est_proprietaire: true,
          doit_changer_mot_de_passe: false,
        },
      },
    );
    const form = await formulaire();

    for (const nom of ["Anfa", "Californie"]) {
      expect((within(form).getByRole("radio", { name: nom }) as HTMLInputElement).checked)
        .toBe(false);
    }
    expect(
      within(form).getByText(
        "Sert à la traçabilité. L'ordonnance reste visible depuis tous les magasins.",
      ),
    ).toBeTruthy();
  });

  it("client03_au_dela_de_quatre_magasins_le_combobox_porte_un_NOM_accessible", async () => {
    // LA LECON D-1, ENUMEREE plutot que verifiee ponctuellement. La portee est
    // le FORMULAIRE : le selecteur de magasin du shell est le `combobox` sans
    // nom de `03.1/deferred-items.md`, un defaut herite que cette phase ne
    // corrige pas et sur lequel elle refuse de faire echouer son propre test.
    const cinq = [
      ANFA,
      CALIFORNIE,
      { id: 3, code: "MAAR", nom: "Maârif" },
      { id: 4, code: "GAUT", nom: "Gauthier" },
      { id: 5, code: "OASI", nom: "Oasis" },
    ];
    monter(
      {},
      ROUTE_SAISIE,
      amorcageDe(["client.voir", "ordonnance.voir", "ordonnance.saisir"], cinq),
    );
    const form = await formulaire();

    const comboboxes = within(form).getAllByRole("combobox");
    expect(comboboxes.length).toBeGreaterThan(0);
    for (const combobox of comboboxes) {
      attendUnNomAccessible(combobox, "Magasin qui enregistre");
    }
  });
});

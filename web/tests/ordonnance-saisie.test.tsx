import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AVERTISSEMENT_SANS_TELEPHONE } from "@/pages/clients/messages";
import { LigneDeCorrection } from "@/pages/clients/ordonnances/LigneDeCorrection";
import { canonicaliserAxe, transposer } from "@/pages/clients/ordonnances/optique";
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

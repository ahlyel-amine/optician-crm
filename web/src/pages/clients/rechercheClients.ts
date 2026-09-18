import { useEffect } from "react";

import { clientApi } from "@/api/client";
import type { FicheClient } from "@/api/requetes";
import { useAuth } from "@/auth/AuthProvider";
import { formaterTelephone } from "@/format";
import {
  enregistrerFournisseurDeRecherche,
  type ResultatDeRecherche,
} from "@/layout/Recherche";

import {
  GROUPE_PALETTE,
  aucuneCorrespondance,
  creerAvecCeNom,
  nomEtTelephone,
  procheDe,
} from "./messages";

/**
 * Le PREMIER fournisseur reel de la palette du shell — 04-UI-SPEC.md 18.4.
 *
 * **`web/src/layout/Recherche.tsx` ne change pas d'une ligne**, et c'etait
 * l'objet meme de sa construction en phase 3 : la palette a ete ecrite pour
 * qu'une phase ultérieure y branche une source sans la rouvrir. Si ce fichier
 * avait du la modifier, l'abstraction aurait ete fausse et il aurait fallu le
 * dire plutot que de la contourner.
 *
 * QUATRE REGLES, chacune avec sa raison.
 */

/**
 * 1. LA REQUETE BRUTE PART AU SERVEUR.
 *
 * Aucune normalisation, aucun retrait, aucun filtrage cote client (`03` 5.5 et
 * la note de `Valeur.tsx`). Une saisie arabe fait l'aller-retour inchangee, et
 * la tolerance aux graphies est une affaire d'index SQL — une seconde
 * normalisation ecrite ici ferait diverger ce qui s'affiche de ce que la base
 * sait.
 */

/**
 * 2. LE SCORE N'EST JAMAIS RENDU COMME UN NOMBRE.
 *
 * Quand le serveur marque une correspondance atteinte par la couche phonetique
 * ou par une equivalence curee plutot que par les caracteres tapes, la ligne
 * porte la raison EN MOTS. Les autres couches — la correspondance exacte, le
 * telephone, l'orthographe — ont trouve ce qui a ete tape : elles n'ont rien a
 * expliquer.
 */
const RAISONS_A_EXPLIQUER: ReadonlySet<string> = new Set(["phonetique", "equivalence"]);

/**
 * 3. `correspondance_exacte` NE SE POSE QUE SUR UN NUMERO DE TELEPHONE COMPLET
 *    ET UNIQUE. JAMAIS SUR UN NOM.
 *
 * C'est la traduction directe d'une mesure. En `word_similarity`, plan 04-03 :
 * `mhamed` vers `mohammed alaoui` vaut 0,333 — une correspondance que
 * CLIENT-10 EXIGE — tandis que `fatima` vers `fatiha bennani` vaut 0,571 et
 * `abdelkrim` vers `abdelkader bennani` 0,600 — deux paires de personnes
 * DISTINCTES. Le classement est donc inverse, et aucun seuil ne separe la
 * verite de l'erreur.
 *
 * Auto-naviguer vers un nom bien classe ouvrirait la fiche du voisin. Avec des
 * ordonnances dessus, ce n'est pas une gene d'interface : c'est une
 * divulgation de donnee de sante.
 *
 * La raison `exact` du serveur ne suffit pas non plus : elle signifie « egalite
 * de chaine normalisee », et deux personnes peuvent legitimement s'appeler
 * « Mohamed Alaoui ». Seul un numero identifie.
 */
const CHIFFRES_DUN_NUMERO_COMPLET = 9;

/**
 * Les chiffres de la requete, pour DECIDER s'il faut auto-naviguer.
 *
 * Ce n'est pas une normalisation : rien de ce qui est calcule ici n'est envoye
 * au serveur, qui recoit la chaine telle qu'elle a ete tapee. C'est une lecture
 * locale, et elle sert uniquement a refuser d'auto-naviguer sur autre chose
 * qu'un numero.
 */
const chiffresDe = (requete: string): string => requete.replace(/[^0-9]/g, "");

function libelleDuResultat(fiche: FicheClient, requete: string): string {
  if (typeof fiche.raison === "string" && RAISONS_A_EXPLIQUER.has(fiche.raison)) {
    return procheDe(fiche.nom, requete);
  }
  return nomEtTelephone(
    fiche.nom,
    fiche.telephone ? formaterTelephone(fiche.telephone) : "",
  );
}

/**
 * 4. AUCUN RESULTAT REND DEUX LIGNES, PAS UNE LISTE VIDE.
 *
 * La requete est echouee VERBATIM — c'est ce qui permet a l'opticien de voir
 * qu'il a tape « mohamed b » et non « mohamed n » — et la seconde ligne mene
 * au dialogue de creation avec le nom deja ecrit. Elles passent par la meme
 * structure de resultat que les autres, ce qui est la seule facon de les
 * rendre sans toucher a `Recherche.tsx`.
 */
function lignesDabsence(requete: string): ResultatDeRecherche[] {
  return [
    {
      id: "clients-aucune-correspondance",
      groupe: GROUPE_PALETTE,
      libelle: aucuneCorrespondance(requete),
      route: `/clients?search=${encodeURIComponent(requete)}`,
    },
    {
      id: "clients-creer",
      groupe: GROUPE_PALETTE,
      libelle: creerAvecCeNom(requete),
      route: `/clients?creer=${encodeURIComponent(requete)}`,
    },
  ];
}

export async function chercherDesClients(
  requete: string,
  signal: AbortSignal,
): Promise<ResultatDeRecherche[]> {
  const reponse = await clientApi.GET("/api/clients/", {
    params: { query: { search: requete } },
    signal,
  });
  const fiches = reponse.data ?? [];

  if (fiches.length === 0) {
    return lignesDabsence(requete);
  }

  // « Unique » est litteral : des qu'il y a deux candidats, meme si l'un est
  // manifestement meilleur, plus rien n'auto-navigue.
  const unique = fiches.length === 1;
  const assezDeChiffres = chiffresDe(requete).length >= CHIFFRES_DUN_NUMERO_COMPLET;

  return fiches.map((fiche) => ({
    id: `client-${String(fiche.id)}`,
    groupe: GROUPE_PALETTE,
    libelle: libelleDuResultat(fiche, requete),
    route: `/clients/${String(fiche.id)}`,
    correspondance_exacte: unique && assezDeChiffres && fiche.raison === "telephone",
  }));
}

/**
 * Enregistre le fournisseur pour la duree de vie du shell, et le retire en
 * partant.
 *
 * **Conditionne a `client.voir`** : sans le droit, chaque frappe dans la
 * palette produirait un 403 que le fournisseur avalerait en silence. L'absence
 * du champ de recherche est alors coherente avec l'absence de l'entree de
 * navigation — l'application d'un gerant est genuinement plus petite. Rappel
 * qui vaut ici comme ailleurs : c'est du CONFORT. Le controle est la classe de
 * permission du serveur, qui refuse quoi qu'il arrive.
 */
export function useFournisseurDeRechercheDesClients(): void {
  const { permissions } = useAuth();
  const autorise = permissions.includes("client.voir");

  useEffect(() => {
    if (!autorise) {
      return;
    }
    return enregistrerFournisseurDeRecherche({
      nom: GROUPE_PALETTE,
      chercher: chercherDesClients,
    });
  }, [autorise]);
}

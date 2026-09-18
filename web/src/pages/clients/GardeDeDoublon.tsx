import { useEffect, useState } from "react";

import { Link } from "react-router-dom";

import { $api } from "@/api/requetes";
import { formaterTelephone } from "@/format";
import { DELAI_ANTI_REBOND } from "@/layout/Recherche";
import { Valeur } from "@/tableau/Valeur";

import {
  GARDE_ACTION,
  GARDE_TITRE,
  gardeDecompte,
  nomEtTelephone,
} from "./messages";

/**
 * La garde de doublon — 04-UI-SPEC.md 18.6.
 *
 * **UNE FICHE CLIENT EN DOUBLE EST UN HISTORIQUE DE PRESCRIPTION SCINDE.**
 * C'est exactement le danger clinique qui a rendu les ordonnances transversales
 * a l'affaire plutot que propres a un magasin (decision D-4a) : deux fiches
 * pour un humain, donc deux historiques pour un seul oeil, donc une comparaison
 * avec la correction precedente qui ne voit pas la bonne precedente. Creer le
 * doublon est l'erreur la plus probable du comptoir, et le moment de
 * l'empecher est pendant que le nom se tape — pas apres, quand la fusion coute
 * une migration de donnees.
 *
 * TROIS INTERDITS, et ils sont la raison d'etre de ce composant autant que son
 * affichage :
 *
 * 1. **Jamais fusionner automatiquement.** Aucun seuil ne separe deux graphies
 *    d'un meme nom de deux personnes distinctes — la mesure du plan 04-03 le
 *    montre, le classement est meme inverse. Fusionner sur cette base melerait
 *    les ordonnances de deux personnes.
 * 2. **Jamais bloquer la creation.** Deux clients peuvent legitimement porter
 *    le meme nom. Un refus sur un homonyme reel serait un opticien qui ne peut
 *    pas enregistrer son client, ce qui est pire que le doublon.
 * 3. **Jamais pre-selectionner.** Une proposition cochee d'avance devient la
 *    reponse par defaut de quelqu'un qui est presse, et ouvre la fiche du
 *    voisin. Le controle ici est l'INFORMATION au bon moment, pas le refus.
 */

/** En deca de deux caracteres, tout nom ressemble a tous les autres. */
const CARACTERES_MINIMAUX = 2;

export type ProprietesGardeDeDoublon = {
  /** Le nom en cours de frappe, tel quel. */
  nom: string;
};

export function GardeDeDoublon({ nom }: ProprietesGardeDeDoublon) {
  const [terme, setTerme] = useState("");

  // Le meme anti-rebond de 200 ms que la palette et que le champ de la liste,
  // et pour la meme raison : une requete par frappe ferait clignoter la garde
  // et travailler l'index a chaque touche.
  useEffect(() => {
    const minuteur = setTimeout(() => setTerme(nom), DELAI_ANTI_REBOND);
    return () => clearTimeout(minuteur);
  }, [nom]);

  const actif = terme.length >= CARACTERES_MINIMAUX;

  // LA MEME ROUTE que la liste et que la palette. Un second point de
  // terminaison « de verification de doublon » serait un second classement a
  // tenir d'accord avec le premier, et il divergerait.
  const proches = $api.useQuery(
    "get",
    "/api/clients/",
    { params: { query: { search: terme } } },
    { enabled: actif },
  );

  const fiches = actif ? (proches.data ?? []) : [];
  if (fiches.length === 0) {
    return null;
  }

  return (
    <div
      data-testid="garde-de-doublon"
      className="rounded-md border border-border bg-muted/40 p-3"
    >
      <p className="text-sm font-semibold">{GARDE_TITRE}</p>
      <p className="mt-1 text-xs text-muted-foreground">{gardeDecompte(fiches.length)}</p>
      <ul className="mt-2 grid gap-1">
        {fiches.map((fiche) => (
          <li
            key={fiche.id}
            className="flex items-center justify-between gap-3 text-sm"
          >
            <Valeur>
              {nomEtTelephone(
                fiche.nom,
                fiche.telephone ? formaterTelephone(fiche.telephone) : "",
              )}
            </Valeur>
            {/*
              Un lien, jamais une case a cocher ni une option : rien n'est
              selectionne, l'opticien VA voir la fiche s'il le veut.
            */}
            <Link
              to={`/clients/${String(fiche.id)}`}
              className="shrink-0 text-sm underline underline-offset-2"
            >
              {GARDE_ACTION}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

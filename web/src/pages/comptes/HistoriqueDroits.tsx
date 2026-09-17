import { useState } from "react";

import { $api } from "@/api/requetes";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { CarteDechec } from "@/etats/CarteDechec";
import { formaterDateHeure } from "@/format";
import { Valeur } from "@/tableau/Valeur";

/**
 * `03-UI-SPEC.md` 7.3 D — l'historique des droits, la seule vue de `JournalDroit`.
 *
 * Ferme par defaut, en lecture seule, du plus recent au plus ancien. Il repond
 * a la question que le proprietaire finit toujours par poser — « qui a donne
 * les marges a Karim ? » — et il est la seule reponse possible apres une
 * revocation : celle-ci **supprime** la ligne d'octroi, donc il ne reste que
 * ce journal a interroger (menace T-03-19).
 *
 * La requete ne part **qu'a l'ouverture**. Un repli ferme qui charge quand meme
 * fait payer a chaque fiche un aller-retour que presque personne ne demande.
 */

type Entree = {
  le: string;
  action: string;
  nature: string;
  cible: string;
  libelle: string;
  par: string;
};

/**
 * La grammaire, cote client, et c'est sa place.
 *
 * « a accordé « Voir le prix d'achat » » et « a accordé l'accès au magasin
 * Maârif » ne se composent pas pareil, donc le serveur livre un libelle et une
 * nature plutot qu'une phrase — une phrase assemblee cote serveur serait
 * impossible a corriger sans redeployer.
 */
export function verbe(action: string): string {
  return action === "accorde" ? "a accordé" : "a retiré";
}

export function complement(nature: string, libelle: string): string {
  return nature === "magasin"
    ? `l'accès au magasin ${libelle}`
    : `« ${libelle} »`;
}

export function HistoriqueDroits({ compteId }: { compteId: number }) {
  const [ouvert, setOuvert] = useState(false);

  const journal = $api.useQuery(
    "get",
    "/api/comptes/{id}/journal/",
    { params: { path: { id: compteId } } },
    { enabled: ouvert },
  );

  return (
    <section aria-labelledby="titre-historique" className="mt-8">
      <h2 id="titre-historique" className="text-lg font-semibold">
        Historique des droits
      </h2>
      <Collapsible open={ouvert} onOpenChange={setOuvert} className="mt-2">
        <CollapsibleTrigger className="text-sm underline underline-offset-4">
          {ouvert ? "Masquer l'historique" : "Afficher l'historique"}
        </CollapsibleTrigger>
        <CollapsibleContent>
          {journal.isError ? (
            <CarteDechec quoi="l'historique" reessayer={() => void journal.refetch()} />
          ) : journal.isPending ? (
            <p className="mt-3 text-sm text-muted-foreground">Chargement…</p>
          ) : journal.data.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">
              Aucun changement de droits pour l'instant.
            </p>
          ) : (
            <ul className="mt-3 space-y-1">
              {(journal.data as Entree[]).map((entree, rang) => (
                <li key={`${entree.le}-${String(rang)}`} className="text-sm">
                  <span className="tabular-nums">{formaterDateHeure(entree.le)}</span>
                  {" — "}
                  <Valeur>{entree.par}</Valeur> {verbe(entree.action)}{" "}
                  {complement(entree.nature, entree.libelle)}
                </li>
              ))}
            </ul>
          )}
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}

import { useParams } from "react-router-dom";

import { $api } from "@/api/requetes";
import { CarteDechec } from "@/etats/CarteDechec";
import { Valeur } from "@/tableau/Valeur";

/**
 * `03-UI-SPEC.md` 7.3 — la fiche d'un compte.
 *
 * Quatre regions, **dans cet ordre** : Identite, Magasins, Droits, Historique.
 * L'ordre est porteur et non esthetique : un droit sans magasin n'accorde rien,
 * donc demander les magasins d'abord evite la question « je lui ai tout donne
 * et il ne voit rien ».
 */

/**
 * Le proprietaire, vu de sa propre fiche ou de celle du propriétaire par un
 * gérant-gestionnaire (7.7).
 *
 * **Aucune section de droits n'est rendue.** Pas en lecture seule, pas grisee :
 * absente. Son acces est materialise depuis le plan 03-05 — le catalogue
 * complet, pour chacun de ses magasins actifs — donc une case a cocher serait
 * un mensonge, et un mensonge qu'on peut cliquer.
 */
const PHRASE_PROPRIETAIRE =
  "Propriétaire — accès complet à tous les magasins. Ces droits ne se modifient pas.";

export function DetailCompte() {
  const { id = "" } = useParams();
  const compte = $api.useQuery("get", "/api/comptes/{id}/", {
    params: { path: { id: Number(id) } },
  });

  if (compte.isError) {
    return <CarteDechec quoi="ce compte" reessayer={() => void compte.refetch()} />;
  }
  if (compte.isPending) {
    return <p className="text-sm text-muted-foreground">Chargement…</p>;
  }

  return (
    <div className="mx-auto max-w-[880px]">
      <header>
        <h1 className="text-2xl font-semibold">
          <Valeur>{compte.data.nom_complet}</Valeur>
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">{compte.data.email}</p>
      </header>

      {compte.data.est_proprietaire ? (
        <p className="mt-8 text-sm text-muted-foreground">{PHRASE_PROPRIETAIRE}</p>
      ) : null}
    </div>
  );
}

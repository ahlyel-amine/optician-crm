import type { ReactNode } from "react";

import { Navigate, useLocation } from "react-router-dom";

import { CarteDechec } from "@/etats/CarteDechec";
import { Skeleton } from "@/components/ui/skeleton";

import { useAuth } from "./AuthProvider";

/**
 * La garde de la mise en page protegee. Tout ce qui n'est pas `/connexion` ni
 * `/mot-de-passe` passe par ici.
 *
 * Quatre issues, et l'ordre compte :
 *
 *   1. amorcage en cours  -> des squelettes, JAMAIS un spinner plein ecran
 *      (`03-UI-SPEC.md` 8.6). Un spinner plein ecran fait clignoter
 *      l'application a chaque rechargement, ce que le critere de reussite du
 *      plan interdit nommement ;
 *   2. service injoignable -> la carte d'echec en ligne, avec « Réessayer » ;
 *   3. anonyme -> `/connexion`, **en memorisant le chemin tente**, sans message
 *      d'expiration : personne n'a expire, il n'y avait pas de session ;
 *   4. changement de mot de passe force -> `/mot-de-passe`, et c'est ici que
 *      cette route devient NON REFERMABLE. La mettre ici plutot que dans le
 *      gestionnaire de connexion est ce qui la rend inevitable : taper une URL
 *      protegee a la main retombe dessus.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { etat, utilisateur, reessayerLamorcage } = useAuth();
  const emplacement = useLocation();

  if (etat === "amorcage") {
    return (
      <div className="space-y-4 p-6" aria-busy="true">
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (etat === "indisponible") {
    return (
      <div className="p-6">
        <CarteDechec quoi="l'application" reessayer={reessayerLamorcage} />
      </div>
    );
  }

  if (etat === "anonyme" || utilisateur === null) {
    return (
      <Navigate
        to="/connexion"
        replace
        state={{ de: `${emplacement.pathname}${emplacement.search}` }}
      />
    );
  }

  if (utilisateur.doit_changer_mot_de_passe) {
    return <Navigate to="/mot-de-passe" replace />;
  }

  return <>{children}</>;
}

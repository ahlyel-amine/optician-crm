import { MESSAGE_LIEN_PERDU } from "./messages";
import { useLienDisponible } from "./reseau";

/**
 * La banniere persistante de coupure, sous la barre superieure.
 *
 * `03-UI-SPEC.md` 8.6. Trois proprietes sont contractuelles :
 *
 *   1. **persistante** — elle ne s'efface pas toute seule, contrairement a un
 *      toast, parce que la condition qu'elle decrit, elle, ne s'efface pas ;
 *   2. **destructive** — elle annonce une perte, pas une information ;
 *   3. **les controles d'ecriture sont desactives tant qu'elle est la** — c'est
 *      la partie qui compte, et elle vit dans `useLienDisponible()`, que chaque
 *      formulaire des phases 4 a 12 consulte.
 *
 * `role="status"` et `aria-live="polite"` plutot qu'`alert` : la coupure n'est
 * pas declenchee par une action de l'utilisateur, donc l'interrompre au milieu
 * d'une saisie serait brutal, et l'information reste lisible a l'ecran.
 */
export function BanniereDeLien() {
  const enLigne = useLienDisponible();
  if (enLigne) {
    return null;
  }
  return (
    <div
      role="status"
      aria-live="polite"
      className="w-full bg-destructive px-6 py-2 text-sm font-semibold text-white"
    >
      {MESSAGE_LIEN_PERDU}
    </div>
  );
}

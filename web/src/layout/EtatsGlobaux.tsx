import { Skeleton } from "@/components/ui/skeleton";

/**
 * Les squelettes de chargement (03-UI-SPEC.md 8.6, ligne « Loading »).
 *
 * Trois regles, et chacune corrige une facon precise dont un chargement se rate :
 *
 *   - **ils epousent la mise en page finale.** Un rotateur plein ecran fait
 *     disparaitre l'interface puis la fait revenir ; un squelette garde la
 *     place et le regard ne se reinstalle pas a chaque requete ;
 *   - **aucun decalage de mise en page.** Le squelette de tableau rend le VRAI
 *     nombre de colonnes et cinq lignes, donc l'arrivee des donnees ne pousse
 *     rien ;
 *   - **aucun delai minimum artificiel.** Faire durer un squelette « pour que
 *     ce soit lisible » ralentit volontairement un outil de comptoir.
 *
 * Ces composants sont la moitie « chargement » des etats globaux ; les quatre
 * autres (401, 403, 404, echec de chargement, lien perdu) vivent dans
 * `src/etats/` depuis le plan 03-12 et ne sont pas redupliques ici.
 */

/** Cinq lignes : assez pour que le tableau ait sa forme, pas assez pour mentir. */
const LIGNES_PAR_DEFAUT = 5;

export function SqueletteTableau({
  colonnes,
  lignes = LIGNES_PAR_DEFAUT,
}: {
  /** Le VRAI nombre de colonnes de la table qui va s'afficher. */
  colonnes: number;
  lignes?: number;
}) {
  return (
    <div aria-busy="true" aria-live="polite" className="w-full">
      <div className="flex h-9 items-center gap-3 border-b border-border">
        {Array.from({ length: colonnes }, (_, rang) => (
          <Skeleton key={`entete-${rang}`} className="h-3 flex-1" />
        ))}
      </div>
      {Array.from({ length: lignes }, (_, ligne) => (
        <div key={`ligne-${ligne}`} className="flex h-10 items-center gap-3">
          {Array.from({ length: colonnes }, (_, colonne) => (
            <Skeleton key={`cellule-${ligne}-${colonne}`} className="h-3 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Le squelette d'un formulaire : la colonne plafonne a 640px, comme le vrai. */
export function SqueletteFormulaire({ champs = 4 }: { champs?: number }) {
  return (
    <div aria-busy="true" aria-live="polite" className="colonne-formulaire space-y-4">
      {Array.from({ length: champs }, (_, rang) => (
        <div key={rang} className="space-y-2">
          <Skeleton className="h-3 w-32" />
          <Skeleton className="h-9 w-full" />
        </div>
      ))}
    </div>
  );
}

/** Le squelette d'une page : le titre, puis ce qui vient dessous. */
export function SquelettePage({ children }: { children?: React.ReactNode }) {
  return (
    <div aria-busy="true" className="space-y-6">
      <Skeleton className="h-7 w-64" />
      {children}
    </div>
  );
}

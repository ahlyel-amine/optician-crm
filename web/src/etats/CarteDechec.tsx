import { Button } from "@/components/ui/button";

import { ACTION_REESSAYER, messageChargementImpossible } from "./messages";

export type ProprietesCarteDechec = {
  /** Ce qui n'a pas pu etre charge, au pluriel de l'ecran : « les comptes ». */
  quoi: string;
  reessayer: () => void;
};

/**
 * L'echec de chargement, en carte EN LIGNE dans la zone de contenu.
 *
 * **Jamais un toast.** Un toast d'echec de chargement s'efface au bout de
 * quelques secondes et laisse un ecran vide que plus rien n'explique ; celui-ci
 * occupe la place de ce qui aurait du s'afficher, et garde son bouton.
 */
export function CarteDechec({ quoi, reessayer }: ProprietesCarteDechec) {
  return (
    <div className="rounded-md border border-border bg-card p-6">
      <p className="text-sm">{messageChargementImpossible(quoi)}</p>
      <Button className="mt-4" variant="outline" onClick={reessayer} type="button">
        {ACTION_REESSAYER}
      </Button>
    </div>
  );
}

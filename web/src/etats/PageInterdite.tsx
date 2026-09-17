import { MESSAGE_ACCES_REFUSE, messageDroitManquant } from "./messages";

export type ProprietesPageInterdite = {
  /**
   * Le LIBELLE du droit tel que le catalogue du serveur le nomme — « Consulter
   * la caisse », jamais `caisse.voir`. Le code est du vocabulaire interne
   * (`03-UI-SPEC.md` 9.3 : `droits` a l'ecran, `permission` dans le code).
   */
  libelleDuDroit?: string;
};

/**
 * 403 — page pleine.
 *
 * Elle NOMME le droit manquant, et c'est une decision, pas une negligence : le
 * catalogue est identique pour toutes les affaires du produit, donc le nommer
 * ne revele l'existence de rien qui soit propre a un autre client. En echange,
 * l'utilisateur sait quoi demander, a qui, sans appeler le support.
 *
 * Ce n'est PAS un repere `main` : depuis le plan 03-13 cette page se rend dans
 * la zone de contenu du shell, qui est deja le `main` unique.
 */
export function PageInterdite({ libelleDuDroit }: ProprietesPageInterdite) {
  return (
    <div className="mx-auto max-w-prose py-6">
      <h1 className="text-2xl font-semibold">{MESSAGE_ACCES_REFUSE}</h1>
      {libelleDuDroit ? (
        <p className="mt-4 text-sm text-muted-foreground">
          {messageDroitManquant(libelleDuDroit)}
        </p>
      ) : null}
    </div>
  );
}

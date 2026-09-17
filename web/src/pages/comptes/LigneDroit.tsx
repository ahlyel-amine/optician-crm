import type { ReactNode } from "react";

/**
 * `03-UI-SPEC.md` 7.4 — l'anatomie d'une ligne de droit.
 *
 * Interrupteur **a gauche**, au debut du sens de lecture ; libelle cliquable
 * qui **est** le nom accessible de l'interrupteur ; explication d'une ligne en
 * dessous, en texte visible.
 *
 * **Pas une infobulle.** Une infobulle est invisible a qui balaie l'ecran, et
 * cette ligne est le levier de cout de support de tout l'ecran : a 2 400 MAD
 * par an et par boutique, elle est la difference entre une charge de support
 * viable et non viable. Elle nomme la CONSEQUENCE, pas le code.
 */

/**
 * L'interrupteur, ecrit a la main plutot que pris au bloc `switch` de shadcn.
 *
 * La raison est unique et suffisante : `03-UI-SPEC.md` 7.5 exige un **tri-etat**
 * avec `aria-checked="mixed"`, et `Switch` de Radix est un booleen — son
 * `aria-checked` ne prend que `true` ou `false`. Un troisieme etat dessine
 * par-dessus un controle qui l'ignore serait vu et non annonce, ce qui est le
 * cas exact que la section 10 existe pour interdire.
 *
 * Le reste — role, focus, activation au clavier — est ce que `<button>` donne
 * gratuitement, et un `<button>` ne peut pas oublier la barre d'espace.
 */
export type EtatInterrupteur = "actif" | "inactif" | "mixte";

const ARIA_PAR_ETAT: Record<EtatInterrupteur, "true" | "false" | "mixed"> = {
  actif: "true",
  inactif: "false",
  mixte: "mixed",
};

export type ProprietesInterrupteur = {
  nomAccessible: string;
  etat: EtatInterrupteur;
  onBascule: () => void;
  desactive?: boolean;
  identifiant?: string;
};

export function Interrupteur({
  nomAccessible,
  etat,
  onBascule,
  desactive,
  identifiant,
}: ProprietesInterrupteur) {
  const allume = etat === "actif";
  return (
    <button
      id={identifiant}
      type="button"
      role="switch"
      aria-checked={ARIA_PAR_ETAT[etat]}
      aria-label={nomAccessible}
      disabled={desactive}
      onClick={onBascule}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border border-transparent transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 ${
        allume || etat === "mixte" ? "bg-primary" : "bg-input"
      }`}
    >
      {etat === "mixte" ? (
        // Le tiret dans la piste : le tri-etat est DESSINE ici et ANNONCE par
        // `aria-checked="mixed"` juste au-dessus. Les deux, jamais l'un seul.
        <span
          aria-hidden="true"
          className="absolute left-1/2 h-0.5 w-3 -translate-x-1/2 rounded-full bg-primary-foreground"
        />
      ) : (
        <span
          aria-hidden="true"
          className={`pointer-events-none block size-4 rounded-full bg-background shadow-sm transition-transform ${
            allume ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      )}
    </button>
  );
}

export type ProprietesLigneDroit = {
  code: string;
  libelle: string;
  explication: string;
  etat: EtatInterrupteur;
  onBascule: () => void;
  /**
   * La note en ligne de la cascade de prerequis (7.6) : « « Consulter le
   * stock » a ete active automatiquement. » Elle EXPLIQUE, elle ne decide
   * pas — la fermeture est appliquee cote serveur.
   */
  note?: string;
  /**
   * L'echec d'une bascule, **sur la ligne** et jamais en toast (7.8). Un toast
   * d'echec se rate en regardant ailleurs, et ce qui reste alors a l'ecran est
   * un interrupteur qui ment sur l'etat reel.
   */
  erreur?: string;
  /** Ce que la surcharge par magasin ajoute a droite de la ligne (7.5). */
  actions?: ReactNode;
  /** La sous-liste depliee, un interrupteur par magasin accorde. */
  sousListe?: ReactNode;
};

export function LigneDroit({
  code,
  libelle,
  explication,
  etat,
  onBascule,
  note,
  erreur,
  actions,
  sousListe,
}: ProprietesLigneDroit) {
  const identifiant = `droit-${code}`;
  return (
    <li className="border-b border-border py-3 last:border-0" data-code={code}>
      <div className="flex items-start gap-3">
        <div className="pt-0.5">
          <Interrupteur
            identifiant={identifiant}
            nomAccessible={libelle}
            etat={etat}
            onBascule={onBascule}
          />
        </div>
        <div className="min-w-0 flex-1">
          {/*
            Le libelle EST le nom accessible de l'interrupteur, et il le
            declenche au clic : c'est ce qui donne une cible de 56px de haut
            plutot qu'un rectangle de 36 par 20.
          */}
          <button
            type="button"
            className="text-left text-sm"
            onClick={onBascule}
            tabIndex={-1}
            aria-hidden="true"
          >
            {libelle}
          </button>
          <p className="mt-0.5 text-xs text-muted-foreground">{explication}</p>
          {note === undefined ? null : (
            <p className="mt-1 text-xs text-muted-foreground" role="status">
              {note}
            </p>
          )}
          {erreur === undefined ? null : (
            <p className="mt-1 text-xs text-destructive" role="alert">
              {erreur}
            </p>
          )}
        </div>
        {actions}
      </div>
      {sousListe}
    </li>
  );
}

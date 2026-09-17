import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";

/**
 * `03-UI-SPEC.md` 7.4 — l'anatomie d'une ligne de droit.
 *
 * Interrupteur **a gauche**, au debut du sens de lecture ; libelle cliquable
 * qui **est** le nom accessible de l'interrupteur ; explication d'une ligne en
 * dessous, en texte visible.
 *
 * **Pas une infobulle.** Une infobulle est invisible a qui balaie l'ecran, et
 * cette ligne est le levier de cout de support de tout l'ecran : a 2 400 MAD
 * par an et par magasin, elle est la difference entre une charge de support
 * viable et non viable. Elle nomme la CONSEQUENCE, pas le code.
 *
 * **La ligne est SANS ETAT — 2026-09-17, phase 03.1, decision 1.** Elle portait
 * jusqu'ici un bouton d'ouverture par magasin, la sous-liste d'un interrupteur
 * par magasin qu'il depliait, l'etat de ce depliage et un bouton qui
 * uniformisait la ligne. Tout cela est remplace par un selecteur unique en tete
 * de section (`SelecteurDeMagasinDesDroits`), et la ligne ne decide plus rien :
 * elle recoit un etat, un badge et une aide, deja projetes par `SectionDroits`
 * selon le mode du selecteur.
 *
 * Ce n'est pas de la cosmetique. Une ligne sans etat rend le mode du selecteur
 * **observable** plutot que devinable : il n'existe plus qu'un seul endroit ou
 * la portee d'une bascule est decidee, donc plus qu'une seule chose a lire pour
 * savoir ou un clic va ecrire.
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

/**
 * Dix secondes, et une fermeture explicite.
 *
 * `03-UI-SPEC.md` 7.8 : l'annulation plutot que la confirmation. Vingt et un
 * interrupteurs a dialogues de confirmation est une fatigue de confirmation —
 * on finit par confirmer sans lire — alors que chacune de ces actions est
 * reversible en un clic. Dix secondes est le temps de lire la phrase, la
 * comprendre et se raviser ; la fermeture explicite existe pour qui a compris
 * tout de suite et veut recuperer le coin de l'ecran.
 */
export const DUREE_ANNULATION_MS = 10_000;

/** L'unique emplacement du mot, et il ne veut jamais dire « fermer » (7.10). */
const ACTION_ANNULER = "Annuler";

/**
 * Le toast d'annulation. **Un seul** par action de l'utilisateur, cascade
 * comprise.
 *
 * `cascade` est une liste separee dans la reponse du serveur alors qu'elle est
 * derivable de `lignes`, et c'est exactement pour cela : un `Annuler` par code
 * emporte produirait trois toasts pour un seul clic.
 */
export function toastDannulation(message: string, defaire: () => void): void {
  toast(message, {
    duration: DUREE_ANNULATION_MS,
    closeButton: true,
    action: { label: ACTION_ANNULER, onClick: defaire },
  });
}

/** `Personnalisé : 2 magasins sur 3`, le numerateur et son denominateur. */
export function aideDePersonnalisation(detenus: number, accordes: number): string {
  const pluriel = detenus > 1 ? "magasins" : "magasin";
  return `Personnalisé : ${String(detenus)} ${pluriel} sur ${String(accordes)}`;
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
  /**
   * Le badge `Personnalisé`, pilote par l'etat **SERVEUR** de la ligne — donc
   * vrai dans les DEUX modes du selecteur.
   *
   * « Ce droit n'est pas le meme partout » reste vrai quand on n'en regarde
   * qu'un : cacher le badge en mode nomme reviendrait a cacher l'etat, et un
   * proprietaire relisant l'ecran croirait le droit uniforme. C'est la
   * propriete que gardait l'ancien badge « une fois la ligne repliee », et
   * elle survit au repliement qui, lui, n'existe plus.
   */
  personnalise?: boolean;
  /**
   * `Personnalisé : 2 magasins sur 3`, calcule par `SectionDroits`.
   *
   * La ligne ne compte rien elle-meme : le denominateur est le nombre de
   * magasins accordes, qui n'est pas de son ressort depuis qu'elle est sans
   * etat.
   */
  aide?: string;
};

export function LigneDroit({
  code,
  libelle,
  explication,
  etat,
  onBascule,
  note,
  erreur,
  personnalise = false,
  aide,
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
          {personnalise ? (
            <Badge variant="outline" className="ml-2 align-middle">
              Personnalisé
            </Badge>
          ) : null}
          <p className="mt-0.5 text-xs text-muted-foreground">{explication}</p>
          {aide === undefined ? null : (
            <p className="mt-0.5 text-xs text-muted-foreground">{aide}</p>
          )}
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
      </div>
    </li>
  );
}

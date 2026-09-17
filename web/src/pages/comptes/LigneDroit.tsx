import { useState } from "react";

import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

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

export type ProprietesSurchargeParMagasin = {
  libelle: string;
  /** `{code: nom}` des magasins accordes, dans la portee de l'appelant. */
  magasins: readonly { code: string; nom: string }[];
  /** Les codes de magasins ou le droit est effectivement detenu. */
  detenus: readonly string[];
  surBasculeDunMagasin: (magasinCode: string, accorde: boolean) => void;
};

/**
 * La sous-liste depliee : **le seul endroit ou une grille apparait**.
 *
 * Le pire cas de `03-UI-SPEC.md` 7.1 — 21 par N controles — n'est atteignable
 * qu'au prix de 21 actions deliberees, et releve alors du choix de celui qui
 * les a faites. Dans le cas attendu, zero ligne est depliee.
 */
export function SousListeParMagasin({
  libelle,
  magasins,
  detenus,
  surBasculeDunMagasin,
}: ProprietesSurchargeParMagasin) {
  return (
    <ul className="mt-2 ml-[calc(24px+0.75rem)] space-y-2">
      {magasins.map((magasin) => {
        const detenu = detenus.includes(magasin.code);
        return (
          <li key={magasin.code} className="flex items-center gap-3">
            <Interrupteur
              // Le magasin est DANS le nom accessible : sans lui, un lecteur
              // d'ecran annonce quatre fois « Saisir en caisse, coché » et la
              // sous-liste ne veut plus rien dire (section 10).
              nomAccessible={`${libelle} — ${magasin.nom}`}
              etat={detenu ? "actif" : "inactif"}
              onBascule={() => surBasculeDunMagasin(magasin.code, !detenu)}
            />
            <span className="text-sm" aria-hidden="true">
              {magasin.nom}
            </span>
          </li>
        );
      })}
    </ul>
  );
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
   * Les magasins accordes a ce compte, dans la portee de l'appelant. C'est
   * `magasins.length >= 2` qui decide de l'existence meme de `Par magasin`.
   */
  magasinsAccordes?: readonly { code: string; nom: string }[];
  /** Les codes de magasins ou le droit est effectivement detenu, tels que servis. */
  detenus?: readonly string[];
  surBasculeDunMagasin?: (magasinCode: string, accorde: boolean) => void;
  /** Ouvre la confirmation d'uniformisation, decidee par la fiche. */
  surUniformiser?: () => void;
};

export function LigneDroit({
  code,
  libelle,
  explication,
  etat,
  onBascule,
  note,
  erreur,
  magasinsAccordes = [],
  detenus = [],
  surBasculeDunMagasin,
  surUniformiser,
}: ProprietesLigneDroit) {
  const identifiant = `droit-${code}`;
  const surchargeable = magasinsAccordes.length >= 2 && surBasculeDunMagasin !== undefined;

  /*
    **Seules les lignes que le proprietaire a personnalisees se deplient**
    d'emblee. Une ligne mixte l'est par definition — c'est l'unique etat
    personnalise de 7.5 — et une ligne uniforme ne se deplie qu'a la demande.
    Dans le cas attendu, zero ligne est depliee.
  */
  const [choix, setChoix] = useState<boolean | null>(null);
  /*
    `null` veut dire « personne n'a encore decide » : la ligne suit alors son
    etat, et une ligne personnalisee est depliee. Des que l'utilisateur plie ou
    deplie, son choix l'emporte — sans quoi une ligne qu'il vient de replier se
    redeploierait a la premiere reponse du serveur qui la redit mixte.
  */
  const deplie = choix ?? etat === "mixte";

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
          {!deplie && etat === "mixte" ? (
            /*
              Une ligne personnalisee garde son badge une fois repliee : sinon
              l'etat serait cache, et un propriétaire relisant l'ecran croirait
              le droit uniforme.
            */
            <Badge variant="outline" className="ml-2 align-middle">
              Personnalisé
            </Badge>
          ) : null}
          <p className="mt-0.5 text-xs text-muted-foreground">{explication}</p>
          {etat === "mixte" ? (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {aideDePersonnalisation(detenus.length, magasinsAccordes.length)}
            </p>
          ) : null}
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

        {surchargeable ? (
          deplie ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-xs"
              onClick={() => {
                // `Uniformiser` replie la ligne, puis demande — la fiche decide
                // s'il y a lieu de demander, puisqu'elle seule sait si les
                // sous-interrupteurs divergent.
                setChoix(false);
                surUniformiser?.();
              }}
            >
              Uniformiser
            </Button>
          ) : (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              // **Visible en permanence.** Il a d'abord ete rendu `opacity-0`
              // jusqu'au survol de sa ligne, pour ne pas encombrer un ecran
              // que la quasi-totalite des affaires n'utilisera jamais. Cela
              // rendait le controle indecouvrable — il fallait pointer
              // exactement la bonne ligne pour apprendre qu'il existait — et
              // absent purement et simplement au toucher, donc absent de la
              // tablette du comptoir. Le proprietaire en a conclu que
              // l'octroi par magasin n'existait pas.
              //
              // Ce qui limite l'encombrement n'est pas la revelation, c'est
              // `magasinsAccordes.length >= 2` juste au-dessus : une
              // entreprise mono-magasin ne voit toujours rien, et c'est elle
              // qui est le cas frequent.
              //
              // Le poids visuel reste subordonne : `ghost`, `text-xs` quand
              // le libelle du droit est en `text-sm`, et la couleur de
              // l'explication de ligne. `Uniformiser` garde sa couleur
              // pleine — il REMPLACE des reglages poses a la main, ce qui
              // pese plus que l'invitation a en poser.
              className="text-xs text-muted-foreground"
              onClick={() => setChoix(true)}
            >
              Par magasin
            </Button>
          )
        ) : null}
      </div>

      {deplie && surchargeable && surBasculeDunMagasin !== undefined ? (
        <SousListeParMagasin
          libelle={libelle}
          magasins={magasinsAccordes}
          detenus={detenus}
          surBasculeDunMagasin={surBasculeDunMagasin}
        />
      ) : null}
    </li>
  );
}

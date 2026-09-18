import { TriangleAlert } from "lucide-react";
import { useId, useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "cn";

import {
  fauteDeSigne,
  normaliserNombre,
  verifierBornes,
  verifierPas,
  type Bornes,
  type PresentationBornes,
  type ReglesNombre,
} from "./nombres";

/**
 * La saisie clinique, sans molette.
 *
 * **Le champ est textuel et son clavier est decimal.** Le type natif reserve
 * aux nombres est ecarte pour trois defauts mesures dans ce produit : les
 * molettes de la souris changent la valeur sous le curseur, le defilement de
 * la page la change aussi quand le champ a le focus, et `valueAsNumber` rend
 * `NaN` sur une virgule dans une interface francaise. Aucun des trois n'est
 * theorique, et le premier ecrit une correction que personne n'a prescrite
 * (menace T-04-08).
 *
 * **Le composant ne calcule rien** : il appelle `normaliserNombre`,
 * `verifierBornes` et `verifierPas`, qui sont pures et prouvees sans rendu.
 * Les bornes et le pas arrivent en propriete, depuis l'objet SERVI par le
 * serveur (Q1, D-4b) — ce fichier n'en connait aucun.
 *
 * **L'attribut deliberement absent, et c'est le contrat de 04-UI-SPEC.md
 * 16.4 :** quand un avertissement est fourni, le composant rend une note
 * `role="status"`, l'ajoute a `aria-describedby`, et NE POSE PAS
 * `aria-invalid`. `aria-invalid="true"` affirme que la valeur est FAUSSE ; un
 * avertissement n'affirme que son etrangete. Le poser rendrait un
 * avertissement indiscernable d'un refus exactement pour l'utilisateur qui ne
 * voit pas la difference de couleur — c'est-a-dire que cela deferait toute la
 * conception visuelle en un attribut.
 *
 * Et jamais `role="alert"` : un avertissement apparait au fil de la saisie, et
 * une interruption assertive par frappe est hostile.
 *
 * Un refus, a l'inverse, pose `aria-invalid`, prend le texte et la bordure
 * destructifs, et ne prend PAS `role="status"`.
 */
export type ProprietesChampNombre = {
  /** Un vrai `<label>`, masque visuellement dans la grille OD/OG (25.3). */
  label: string;
  valeur: string;
  surChangement: (valeur: string) => void;
  /** L'objet servi par le serveur. Aucune valeur par defaut n'existe ici. */
  bornes: Bornes;
  regles: ReglesNombre;
  /** Rendu HORS de l'entree et `aria-hidden` : le label dit deja de quoi il s'agit. */
  suffixe?: string;
  /** Une remarque qui n'est PAS un refus. Voir la docstring. */
  avertissement?: string;
  /** Un refus impose par le formulaire, par exemple a la soumission. */
  faute?: string;
  surVerdict?: (faute: string | null) => void;
  /** Le sujet et le rendu des bornes dans la phrase de refus (23). */
  presentation?: PresentationBornes;
  labelMasque?: boolean;
  /** Une des largeurs fixes de 17.1, en classe utilitaire. */
  largeur?: string;
  identifiant?: string;
};

export function ChampNombre({
  label,
  valeur,
  surChangement,
  bornes,
  regles,
  suffixe,
  avertissement,
  faute,
  surVerdict,
  presentation,
  labelMasque = false,
  largeur = "w-[88px]",
  identifiant,
}: ProprietesChampNombre) {
  const engendre = useId();
  const identifiantChamp = identifiant ?? engendre;
  const identifiantFaute = `${identifiantChamp}-faute`;
  const identifiantAvertissement = `${identifiantChamp}-avertissement`;
  const [fauteLocale, setFauteLocale] = useState<string | null>(null);
  const fauteAffichee = faute ?? fauteLocale;

  const auChangement = (evenement: React.ChangeEvent<HTMLInputElement>) => {
    // Refus et avertissements se calculent au blur et a la soumission, JAMAIS
    // au changement : taper `9` en route vers `90` ne doit rien annoncer.
    setFauteLocale(null);
    surChangement(evenement.target.value);
  };

  const auBlur = () => {
    if (valeur.trim() === "") {
      // Un champ vide est vide, jamais zero. Le serveur stocke `null`.
      setFauteLocale(null);
      surVerdict?.(null);
      return;
    }

    const normalise = normaliserNombre(valeur, regles);
    if (normalise === null) {
      const refus = fauteDeSigne(valeur, regles);
      setFauteLocale(refus);
      surVerdict?.(refus);
      return;
    }

    surChangement(normalise);

    const refus =
      verifierBornes(normalise, bornes, presentation) ?? verifierPas(normalise, bornes.pas);
    setFauteLocale(refus);
    surVerdict?.(refus);
  };

  const decritPar =
    [fauteAffichee ? identifiantFaute : null, avertissement ? identifiantAvertissement : null]
      .filter(Boolean)
      .join(" ") || undefined;

  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={identifiantChamp} className={labelMasque ? "sr-only" : undefined}>
        {label}
      </Label>

      <div className="flex items-center gap-1">
        <Input
          id={identifiantChamp}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          className={cn(largeur, "text-right tabular-nums")}
          value={valeur}
          onChange={auChangement}
          onBlur={auBlur}
          aria-invalid={fauteAffichee ? true : undefined}
          aria-describedby={decritPar}
        />
        {suffixe ? (
          <span aria-hidden="true" className="text-sm text-muted-foreground">
            {suffixe}
          </span>
        ) : null}
      </div>

      {fauteAffichee ? (
        <p id={identifiantFaute} className="max-w-prose text-xs text-destructive">
          {fauteAffichee}
        </p>
      ) : null}

      {avertissement ? (
        <p
          id={identifiantAvertissement}
          role="status"
          className="flex max-w-prose items-start gap-2 rounded-md border border-border bg-muted px-2 py-1 text-xs text-foreground"
        >
          <TriangleAlert aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
          {avertissement}
        </p>
      ) : null}
    </div>
  );
}

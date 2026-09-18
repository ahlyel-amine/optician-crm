import { useId, useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import {
  GABARIT_DATE,
  estDansLeFutur,
  masquerDate,
  normaliserDate,
  type VerdictDate,
} from "./dates";

/**
 * Le masque `jj/mm/aaaa`, SANS calendrier.
 *
 * 04-UI-SPEC.md 15.4 **renverse** la promesse de 03-UI-SPEC.md 8.2 — « un
 * masque PLUS un calendrier popover, la phase 4 le construit » — et ne livre
 * que le masque. Le renversement est partiel, assume et signale (question
 * ouverte 28-Q3, laissee ouverte) ; il est aussi ADDITIF : le jour ou le
 * calendrier arrive, le masque reste le controle primaire et rien d'autre ne
 * change.
 *
 * La raison tient en deux phrases. Une date de prescription et une date de
 * naissance se LISENT SUR DU PAPIER ET SE TAPENT : neuf frappes contre quatre
 * clics et un defilement mois par mois pour une date de trois ans en arriere.
 * Et un calendrier importe `react-day-picker`, `date-fns` et une surface de
 * locale dans un produit qui epingle ses formats a une fixture partagee
 * precisement pour tenir les donnees de locale hors du chemin de decision.
 *
 * Le champ natif de type date reste interdit pour la raison que 8.2 donne
 * deja : son rendu et son ordre de champs dependent de la locale du systeme.
 *
 * **Ce composant ne calcule rien.** Il appelle `masquerDate` en cours de
 * frappe et `normaliserDate` au blur ; les deux sont pures et prouvees sans
 * rendu, ce qui vaut mieux qu'une assertion dans jsdom, qui ne calcule aucun
 * CSS.
 *
 * **Il ne lit pas l'horloge non plus.** `aujourdhui` et `anneeCourante` sont
 * des proprietes : un composant qui appelle `new Date()` est un test qui vire
 * rouge un 1er janvier.
 */
export type ProprietesChampDate = {
  /** Un VRAI label visible au-dessus. Le placeholder n'en est pas un (03 §10). */
  label: string;
  /** La valeur affichee, `jj/mm/aaaa`. Jamais de l'ISO. */
  valeur: string;
  surChangement: (valeur: string) => void;
  /** Rend le verdict du blur au formulaire, qui decide de la suite. */
  surVerdict?: (verdict: VerdictDate) => void;
  /**
   * Le refus de date future est PARAMETRE : les deux dates du produit n'ont pas
   * la meme phrase (04-UI-SPEC.md 15.4), donc aucun defaut n'est ecrit ici.
   */
  futurInterdit?: boolean;
  messageFutur?: string;
  /** Le jour de reference, en ISO. Requis si `futurInterdit`. */
  aujourdhui?: string;
  /** L'annee de reference de la regle de siecle. */
  anneeCourante?: number;
  /** Une faute imposee par le formulaire, par exemple a la soumission. */
  faute?: string;
  identifiant?: string;
  requis?: boolean;
};

export function ChampDate({
  label,
  valeur,
  surChangement,
  surVerdict,
  futurInterdit = false,
  messageFutur,
  aujourdhui,
  anneeCourante,
  faute,
  identifiant,
  requis = false,
}: ProprietesChampDate) {
  const engendre = useId();
  const identifiantChamp = identifiant ?? engendre;
  const identifiantFaute = `${identifiantChamp}-faute`;
  const [fauteLocale, setFauteLocale] = useState<string | null>(null);
  const fauteAffichee = faute ?? fauteLocale;

  const auChangement = (evenement: React.ChangeEvent<HTMLInputElement>) => {
    // Aucun refus en cours de frappe : un refus qui apparait a la troisieme
    // touche apprend a l'opticien a ignorer les refus. Le masque n'insere que
    // les slashes et ne recrit rien d'autre.
    setFauteLocale(null);
    surChangement(masquerDate(evenement.target.value));
  };

  const auBlur = () => {
    if (valeur === "") {
      setFauteLocale(null);
      return;
    }

    const verdict = normaliserDate(valeur, anneeCourante);
    if ("faute" in verdict) {
      setFauteLocale(verdict.faute);
      surVerdict?.(verdict);
      return;
    }

    // `14/9/26` devient `14/09/2026` en QUITTANT le champ.
    surChangement(verdict.valeur);

    if (futurInterdit && aujourdhui && messageFutur) {
      if (estDansLeFutur(verdict.valeur, aujourdhui)) {
        setFauteLocale(messageFutur);
        surVerdict?.({ faute: messageFutur });
        return;
      }
    }

    setFauteLocale(null);
    surVerdict?.(verdict);
  };

  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={identifiantChamp}>{label}</Label>
      <Input
        id={identifiantChamp}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        placeholder={GABARIT_DATE}
        className="w-[136px] tabular-nums"
        value={valeur}
        onChange={auChangement}
        onBlur={auBlur}
        required={requis}
        aria-invalid={fauteAffichee ? true : undefined}
        aria-describedby={fauteAffichee ? identifiantFaute : undefined}
      />
      {fauteAffichee ? (
        <p id={identifiantFaute} className="max-w-prose text-xs text-destructive">
          {fauteAffichee}
        </p>
      ) : null}
    </div>
  );
}

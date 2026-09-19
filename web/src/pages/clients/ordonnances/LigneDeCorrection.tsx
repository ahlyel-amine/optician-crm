import { cn } from "cn";

import { OEIL_DROIT, OEIL_GAUCHE } from "./messages";

/**
 * LE composant qui rend une correction. **Un seul, partout.**
 *
 *     OD   +2,00  (−1,00 à 90°)   Add. +2,25
 *
 * Il sert le panneau de relecture (ce plan), la fiche client, l'historique des
 * versions et la feuille d'impression (plan 04-09).
 *
 * **Une correction rendue de deux facons finira par etre rendue de deux facons
 * DIFFERENTES, et le lecteur n'aura aucun moyen de savoir laquelle correspond
 * au papier.** C'est la meme regle de source unique que le formateur monetaire
 * de `src/format/montant.ts`, et pour la meme raison : deux rendus d'une meme
 * valeur derivent, et la divergence est muette.
 *
 * **La forme est celle de la PRESCRIPTION, pas celle de la grille.** Une phrase
 * continue, avec la parenthese cylindre-axe que le papier utilise — et non
 * quatre cases alignees. C'est cette difference de forme qui fait relire, et
 * qui attrape `90` tape pour `9` : restituer les memes chiffres dans la meme
 * disposition demanderait au lecteur de comparer une chose a elle-meme.
 *
 * `tabular-nums` partout, et **aucune couleur** : la phase 4 n'en introduit
 * aucune, et c'est la revendication verifiable de toute la conception de
 * l'avertissement (17.3).
 */
export type ProprietesLigneDeCorrection = {
  oeil: "OD" | "OG";
  /** Les valeurs en forme d'AFFICHAGE, deja normalisees. `""` quand le champ est vide. */
  sphere: string;
  cylindre: string;
  axe: string;
  addition: string;
  /** `Add.` — l'abreviation n'est admise que comme en-tete, jamais en prose (24). */
  prefixeAddition?: string;
  /** La taille du panneau (`Heading 18/600`) ou celle d'une ligne de liste. */
  className?: string;
};

/** Un tiret cadratin pour la valeur absente : une case vide se lit comme un oubli. */
const ABSENT = "—";

export function LigneDeCorrection({
  oeil,
  sphere,
  cylindre,
  axe,
  addition,
  prefixeAddition = "Add.",
  className,
}: ProprietesLigneDeCorrection) {
  const nomComplet = oeil === "OD" ? OEIL_DROIT : OEIL_GAUCHE;

  // La notation du papier, assemblee en UNE chaine : c'est elle que le lecteur
  // relit, et elle doit rester d'un seul tenant dans le texte accessible.
  const valeurSphere = sphere === "" ? ABSENT : sphere;
  const correction =
    cylindre === "" ? valeurSphere : `${valeurSphere} (${cylindre} à ${axe}${"°"})`;

  return (
    <p
      data-testid={`correction-${oeil}`}
      className={cn("flex items-baseline gap-2 tabular-nums", className)}
    >
      <span className="font-semibold">
        {oeil}
        {/*
          Un lecteur d'ecran qui epelle `OD` ne dit rien a personne. 25.3 : les
          deux lettres restent VISIBLES — c'est ce que le papier ecrit — et le
          sens part dans un texte masque visuellement.
        */}
        <span className="sr-only"> {nomComplet}</span>
      </span>
      <span>{correction}</span>
      {addition === "" ? null : (
        <span>
          {prefixeAddition} {addition}
        </span>
      )}
    </p>
  );
}

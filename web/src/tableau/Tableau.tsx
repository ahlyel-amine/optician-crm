import type { KeyboardEvent, ReactNode } from "react";

import { formaterDateCourte, formaterDateHeure, formaterMontant } from "@/format";

import type { Colonne } from "./registre";
import { colonnesVisiblesSurLignes } from "./registre";
import { Valeur } from "./Valeur";

/**
 * `TableauProjete` — le seul tableau de l'application.
 *
 * Il ne rend QUE `colonnesVisiblesSurLignes(colonnes, lignes)`. Les consequences
 * sont le but, et elles sont toutes des refus :
 *
 * - **aucun en-tete litteral, nulle part.** Un en-tete n'existe que si sa donnee
 *   existe. Ecrire un libelle directement dans le JSX le rendrait inconditionnel,
 *   ce qui est exactement la fuite que PERM-06 ferme (menace T-03-73) ;
 * - **aucun substitut** : ni tiret cadratin, ni sigle d'indisponibilite, ni
 *   montant nul, ni cadenas, ni infobulle « vous n'avez pas acces a cette
 *   colonne ». Chacun de ces artefacts revele l'existence et la position du
 *   champ, donc chacun est une divulgation plus discrete mais pas plus benigne
 *   (T-03-74) ;
 * - **un total derive d'un champ absent n'est pas affiche du tout**, plutot
 *   qu'affiche a zero. Un zero est un chiffre faux sans message d'erreur, ce que
 *   la couche ORM refuse deja cote serveur (T-03-75) ;
 * - **aucune arithmetique** : les totaux sont des CHAINES fournies par le
 *   serveur, calculees en `Decimal`. Ce composant ne sait pas additionner, et
 *   c'est ce qui garantit qu'il ne le fera jamais (T-03-77).
 *
 * Les vues de detail suivent la meme regle avec un registre de champs plutot que
 * de colonnes — le filtre est le meme.
 *
 * Les exigences de 03-UI-SPEC.md section 10 sont portees des maintenant, parce
 * que ce composant est herite par neuf phases et qu'une mise en accessibilite
 * retroactive sur neuf phases de tableaux ne se fait jamais : legende
 * visuellement cachee mais presente, `scope="col"` sur chaque en-tete, en-tete
 * triable rendu en `button` avec `aria-sort`, ligne activable focalisable et
 * declenchee par Entree.
 */

/** Sens de tri d'une colonne, tel qu'`aria-sort` l'exprime. */
export type SensTri = "ascending" | "descending";

export type ProprietesTableauProjete = {
  /** Le registre. Declaratif pour le libelle, l'ordre et l'alignement. */
  colonnes: readonly Colonne[];
  /** La charge utile, telle que le serveur l'a projetee. C'est elle qui decide des colonnes. */
  lignes: readonly Record<string, unknown>[];
  /** La legende du tableau, lue par les lecteurs d'ecran, invisible a l'oeil. */
  legende: string;
  /**
   * Totaux fournis par le SERVEUR, clees par nom de champ, en chaine. Un total
   * dont la colonne n'est pas rendue est ignore en silence — c'est le but.
   */
  totaux?: Readonly<Record<string, string>>;
  /** Clef primaire de la ligne, pour `key`. Par defaut, la position. */
  clefLigne?: (ligne: Record<string, unknown>, index: number) => string;
  /** Tri courant, s'il y en a un. */
  tri?: { champ: string; sens: SensTri };
  /** Appele quand un en-tete triable est active. Sans lui, les en-tetes sont du texte. */
  onTrier?: (champ: string) => void;
  /** Appele au clic ou a Entree sur une ligne. Sans lui, les lignes ne sont pas focalisables. */
  onLigneActivee?: (ligne: Record<string, unknown>) => void;
};

const LIBELLE_TOTAL = "Total";

/**
 * Le rendu d'une cellule, decide par le registre.
 *
 * `colonne.rendu` passe AVANT le format, et c'est le seul ordre correct : une
 * colonne qui declare les deux a un rendu sur mesure ET une intention de
 * formatage, et c'est le rendu sur mesure qui sait laquelle des deux
 * s'applique (une date nulle affiche « Jamais connecté », un formateur leverait).
 */
function rendreCellule(
  colonne: Colonne,
  ligne: Record<string, unknown>,
): ReactNode {
  if (colonne.rendu) {
    return colonne.rendu(ligne[colonne.champ], ligne);
  }
  return rendreValeur(ligne[colonne.champ], colonne.format);
}

/** Le rendu d'une valeur, decide par le registre — jamais par le type de la donnee. */
function rendreValeur(valeur: unknown, format: Colonne["format"]): ReactNode {
  if (format === "montant") {
    // `tabular-nums` pour que les chiffres s'alignent d'une ligne a l'autre ;
    // l'espace insecable du formateur garantit que le montant ne se coupe pas.
    return <span className="tabular-nums">{formaterMontant(valeur as string)}</span>;
  }
  if (format === "date") {
    return <span className="tabular-nums">{formaterDateCourte(valeur as string)}</span>;
  }
  if (format === "dateheure") {
    return <span className="tabular-nums">{formaterDateHeure(valeur as string)}</span>;
  }
  // Tout le reste vient de l'utilisateur : nom, adresse, reference, texte libre.
  // Donc tout le reste est isole bidirectionnellement — pas seulement les
  // colonnes qu'on croit pouvoir contenir de l'arabe. C'est un `<bdi>` par
  // cellule, et c'est ce qui evite d'avoir a deviner, colonne par colonne et
  // neuf phases durant, laquelle recevra un jour un nom en arabe.
  return <Valeur>{valeur as ReactNode}</Valeur>;
}

const classeAlignement = (colonne: Colonne): string =>
  colonne.align === "right" ? "text-right" : "text-left";

export function TableauProjete({
  colonnes,
  lignes,
  legende,
  totaux,
  clefLigne,
  tri,
  onTrier,
  onLigneActivee,
}: ProprietesTableauProjete) {
  // LA ligne qui porte PERM-06 cote client. Tout le reste de ce fichier n'est
  // que du rendu.
  const visibles = colonnesVisiblesSurLignes(colonnes, lignes);

  // Un total n'est rendu que si SA COLONNE l'est. Un total dont le champ a ete
  // retire de la charge utile disparait avec sa colonne, il ne tombe pas a zero.
  const totauxRendus = totaux
    ? visibles.filter((colonne) => colonne.champ in totaux)
    : [];

  const gererToucheLigne = (
    evenement: KeyboardEvent<HTMLTableRowElement>,
    ligne: Record<string, unknown>,
  ) => {
    if (evenement.key === "Enter" || evenement.key === " ") {
      evenement.preventDefault();
      onLigneActivee?.(ligne);
    }
  };

  return (
    <table className="w-full border-collapse text-sm">
      <caption className="sr-only">{legende}</caption>
      {visibles.length > 0 && (
        <thead>
          <tr className="border-b">
            {visibles.map((colonne) => (
              <th
                key={colonne.champ}
                scope="col"
                data-champ={colonne.champ}
                aria-sort={
                  tri?.champ === colonne.champ ? tri.sens : onTrier ? "none" : undefined
                }
                className={`px-3 py-2 font-medium ${classeAlignement(colonne)}`}
              >
                {onTrier ? (
                  <button
                    type="button"
                    onClick={() => onTrier(colonne.champ)}
                    className="inline-flex items-center gap-1"
                  >
                    {colonne.libelle}
                  </button>
                ) : (
                  colonne.libelle
                )}
              </th>
            ))}
          </tr>
        </thead>
      )}
      <tbody>
        {lignes.map((ligne, index) => (
          <tr
            key={clefLigne ? clefLigne(ligne, index) : index}
            className="border-b last:border-0"
            tabIndex={onLigneActivee ? 0 : undefined}
            onClick={onLigneActivee ? () => onLigneActivee(ligne) : undefined}
            onKeyDown={
              onLigneActivee ? (evenement) => gererToucheLigne(evenement, ligne) : undefined
            }
          >
            {visibles.map((colonne) => (
              <td
                key={colonne.champ}
                data-champ={colonne.champ}
                className={`px-3 py-2 ${classeAlignement(colonne)}`}
              >
                {rendreCellule(colonne, ligne)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
      {totauxRendus.length > 0 && (
        <tfoot>
          <tr className="border-t font-medium">
            {visibles.map((colonne, index) =>
              colonne.champ in (totaux ?? {}) ? (
                <td
                  key={colonne.champ}
                  data-champ={colonne.champ}
                  className={`px-3 py-2 ${classeAlignement(colonne)}`}
                >
                  {rendreValeur((totaux ?? {})[colonne.champ], colonne.format)}
                </td>
              ) : index === 0 ? (
                <th
                  key={colonne.champ}
                  scope="row"
                  className={`px-3 py-2 ${classeAlignement(colonne)}`}
                >
                  {LIBELLE_TOTAL}
                </th>
              ) : (
                <td key={colonne.champ} className="px-3 py-2" />
              ),
            )}
          </tr>
        </tfoot>
      )}
    </table>
  );
}

import { useState } from "react";

import type { Magasin } from "@/api/requetes";
import { Checkbox } from "@/components/ui/checkbox";
import { Valeur } from "@/tableau/Valeur";

/**
 * `03-UI-SPEC.md` 7.3 B — quels magasins ce compte peut voir (PERM-04).
 *
 * Les magasins offerts sont ceux de **l'appelant**, jamais tous ceux de
 * l'affaire : un gerant d'Anfa qui administre un collegue ne doit pas lire dans
 * une liste de cases le nom des magasins qu'il ne detient pas (7.7). C'est le
 * serveur qui les intersecte, et cette section rend ce qu'elle recoit.
 */

const AIDE_DE_SECTION =
  "Ce compte ne verra que les données des magasins cochés — clients, stock, ventes et caisse compris.";

const AIDE_MONO_MAGASIN = "Ce compte a accès au seul magasin de l'entreprise.";

/**
 * Le refus en ligne, et sa derniere proposition est un LIEN.
 *
 * Une phrase qui dit « desactivez plutot » sans donner le moyen de le faire
 * renvoie l'utilisateur chercher lui-meme le bon controle, dans un ecran qui en
 * porte une trentaine.
 */
const REFUS_DERNIER_MAGASIN = "Un compte doit avoir accès à au moins un magasin.";
const LIEN_DESACTIVER = "Désactivez plutôt le compte.";

export type ProprietesSectionMagasins = {
  /** Les magasins que l'APPELANT peut accorder, tels que le serveur les sert. */
  magasinsOffrables: readonly Magasin[];
  /** Les codes de magasins deja accordes a ce compte. */
  accordes: readonly string[];
  /**
   * Cocher **demande**, et n'ecrit rien (decision 2 de la phase 03.1).
   *
   * Symetrique de `surRetrait`, qui demandait deja une confirmation. Le
   * `Magasin` entier plutot que son code : le dialogue a besoin du nom, et
   * aller le rechercher dans le catalogue au moment de l'afficher ferait deux
   * sources pour un seul libelle.
   */
  surDemandeDajout: (magasin: Magasin) => void;
  surRetrait: (magasin: Magasin) => void;
  surDemandeDeDesactivation: () => void;
};

export function SectionMagasins({
  magasinsOffrables,
  accordes,
  surDemandeDajout,
  surRetrait,
  surDemandeDeDesactivation,
}: ProprietesSectionMagasins) {
  const [refus, setRefus] = useState(false);
  const unSeulMagasin = magasinsOffrables.length === 1;

  return (
    <section aria-labelledby="titre-magasins" className="mt-8">
      <h2 id="titre-magasins" className="text-lg font-semibold">
        Magasins
      </h2>

      {unSeulMagasin ? (
        /*
          **Zero decision la ou une seule reponse est possible.** C'est la plus
          grosse simplification disponible sur cet ecran et elle couvre tout le
          palier `Essentiel` : une case a cocher unique, qu'il faut cocher pour
          que quoi que ce soit fonctionne, est une case a cocher qu'on ne doit
          pas demander.
        */
        <div className="mt-3">
          <p className="text-sm">
            Magasin : <Valeur>{magasinsOffrables[0].nom}</Valeur>
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{AIDE_MONO_MAGASIN}</p>
        </div>
      ) : (
        <ul className="mt-3 space-y-3">
          {magasinsOffrables.map((magasin) => {
            const coche = accordes.includes(magasin.code);
            const identifiant = `magasin-${magasin.code}`;
            return (
              <li key={magasin.code} className="flex items-start gap-3">
                <Checkbox
                  id={identifiant}
                  checked={coche}
                  onCheckedChange={() => {
                    if (!coche) {
                      setRefus(false);
                      /*
                        La case reste **decochee** : elle est pilotee par
                        `accordes`, qui ne bouge qu'a la reponse du serveur.
                        Rien a faire pour cela, mais c'est ce qui rend le
                        `Retour` du dialogue sans effet visible, donc c'est
                        ecrit plutot que suppose.
                      */
                      surDemandeDajout(magasin);
                      return;
                    }
                    // Le dernier magasin : refus **en ligne**, pas un dialogue.
                    // Le serveur, lui, accepte zero magasin — un compte neuf en
                    // a legitimement zero (plan 03-09) — donc « au moins un »
                    // est un garde-fou d'interface, et il est ecrit ici.
                    if (accordes.length <= 1) {
                      setRefus(true);
                      return;
                    }
                    setRefus(false);
                    surRetrait(magasin);
                  }}
                />
                <div className="min-w-0">
                  <label htmlFor={identifiant} className="text-sm">
                    <Valeur>{magasin.nom}</Valeur>
                  </label>
                  <p className="text-xs text-muted-foreground">{magasin.code}</p>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {refus ? (
        <p className="mt-3 text-sm text-destructive" role="alert">
          {REFUS_DERNIER_MAGASIN}{" "}
          <button
            type="button"
            className="underline underline-offset-4"
            onClick={surDemandeDeDesactivation}
          >
            {LIEN_DESACTIVER}
          </button>
        </p>
      ) : null}

      <p className="mt-3 text-xs text-muted-foreground">{AIDE_DE_SECTION}</p>
    </section>
  );
}

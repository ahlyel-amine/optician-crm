import { useEffect, useState } from "react";

import { useParams } from "react-router-dom";

import {
  $api,
  type CatalogueOffrable,
  type LigneDeDroit,
  type Magasin,
  type ResultatOctroi,
} from "@/api/requetes";
import { CarteDechec } from "@/etats/CarteDechec";
import { Valeur } from "@/tableau/Valeur";

import { HistoriqueDroits } from "./HistoriqueDroits";
import { SectionDroits } from "./SectionDroits";
import { SectionMagasins } from "./SectionMagasins";

/**
 * `03-UI-SPEC.md` 7.3 — la fiche d'un compte, 880px, quatre regions.
 *
 * **Identite, Magasins, Droits, Historique — dans cet ordre.** Il est porteur
 * et non esthetique : un droit sans magasin n'accorde rien, donc poser les
 * droits d'abord produit l'appel « je lui ai tout donne et il ne voit rien »,
 * qui est le plus cher des appels evitables.
 *
 * **Sauvegarde par interrupteur, immediate, aucun bouton Enregistrer** (7.8).
 * Vingt et un interrupteurs derriere un unique Enregistrer est un formulaire
 * qu'on abandonne a moitie rempli, et `JournalDroit` enregistre un acteur et un
 * horodatage par octroi — ce qui correspond exactement a une bascule.
 */

const PHRASE_PROPRIETAIRE =
  "Propriétaire — accès complet à tous les magasins. Ces droits ne se modifient pas.";

/** Le prenom, pour la banniere et les dialogues. Le premier mot, sans plus. */
export function prenomDe(nomComplet: string): string {
  return nomComplet.trim().split(/\s+/)[0] ?? nomComplet;
}

/** L'etat des lignes, indexe par code — la forme dont l'ecran a besoin. */
function indexer(lignes: readonly LigneDeDroit[]): Record<string, LigneDeDroit> {
  return Object.fromEntries(lignes.map((ligne) => [ligne.code, ligne]));
}

type FicheCompte = {
  id: number;
  nom_complet: string;
  email: string;
  est_proprietaire: boolean;
  actif: boolean;
  magasins: Magasin[];
  droits: LigneDeDroit[];
  magasins_accordes: string[];
};

export function DetailCompte() {
  const { id = "" } = useParams();
  const identifiant = Number(id);

  const fiche = $api.useQuery("get", "/api/comptes/{id}/", {
    params: { path: { id: identifiant } },
  });
  const catalogue = $api.useQuery("get", "/api/comptes/catalogue/");

  const bascule = $api.useMutation("post", "/api/comptes/{id}/droits/");
  const basculeMagasin = $api.useMutation("post", "/api/comptes/{id}/magasins/");

  /**
   * L'etat local des lignes et des magasins.
   *
   * Il existe parce que la sauvegarde est optimiste : l'interrupteur bouge
   * d'abord, la reponse le confirme ou le retour arriere le remet. Repartir de
   * la requete a chaque fois ferait clignoter l'ecran a chaque clic, ce que 7.8
   * refuse en refusant le bouton Enregistrer.
   */
  const [lignes, setLignes] = useState<Record<string, LigneDeDroit>>({});
  const [accordes, setAccordes] = useState<readonly string[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [erreurs, setErreurs] = useState<Record<string, string>>({});

  const donnees = fiche.data as FicheCompte | undefined;
  useEffect(() => {
    if (donnees === undefined) {
      return;
    }
    setLignes(indexer(donnees.droits ?? []));
    setAccordes(donnees.magasins_accordes ?? []);
  }, [donnees]);

  if (fiche.isError || catalogue.isError) {
    return (
      <CarteDechec
        quoi="ce compte"
        reessayer={() => {
          void fiche.refetch();
          void catalogue.refetch();
        }}
      />
    );
  }
  if (fiche.isPending || catalogue.isPending) {
    return <p className="text-sm text-muted-foreground">Chargement…</p>;
  }

  const compte = fiche.data as FicheCompte;
  const offrable = catalogue.data as CatalogueOffrable;
  const prenom = prenomDe(compte.nom_complet);

  /** Absorbe la reponse d'une bascule : lignes, cascade, magasins accordes. */
  const absorber = (resultat: ResultatOctroi) => {
    setLignes((precedent) => ({ ...precedent, ...indexer(resultat.lignes) }));
    setAccordes(resultat.magasins_accordes);
    setNotes(notesDeCascade(resultat, offrable));
  };

  const basculerLeDroit = (code: string, accorde: boolean) => {
    const avant = lignes[code];
    setErreurs((precedent) => retirer(precedent, code));
    setNotes({});
    // Optimiste : l'interrupteur bouge tout de suite.
    setLignes((precedent) => ({
      ...precedent,
      [code]: {
        code,
        etat: accorde ? "actif" : "inactif",
        magasins: accorde ? [...accordes] : [],
      },
    }));
    bascule.mutate(
      {
        params: { path: { id: identifiant } },
        // **Les magasins sont nommes explicitement**, jamais omis. Omettre
        // signifie « tous les magasins accordes de la cible » (plan 03-09), ce
        // qui est juste pour un proprietaire et faux pour un
        // gerant-gestionnaire : le serveur refuserait l'octroi entier des que
        // la cible detient un magasin que l'appelant n'a pas. Envoyer la
        // portee visible est le seul chemin qui marche pour les deux.
        body: { code: code as never, accorde, magasins: [...accordes] },
      },
      {
        onSuccess: absorber,
        onError: (erreur) => {
          // Retour arriere, puis l'explication **sur la ligne** (7.8). Un
          // interrupteur laisse en place apres un echec ment sur l'etat reel.
          setLignes((precedent) => ({ ...precedent, [code]: avant ?? precedent[code] }));
          setErreurs((precedent) => ({ ...precedent, [code]: messageDechec(erreur) }));
        },
      },
    );
  };

  const basculerLeMagasin = (code: string, accorde: boolean) => {
    basculeMagasin.mutate(
      { params: { path: { id: identifiant } }, body: { magasin_code: code, accorde } },
      { onSuccess: absorber },
    );
  };

  return (
    <div className="mx-auto max-w-[880px]">
      <section aria-labelledby="titre-identite">
        <h1 className="text-2xl font-semibold">
          <Valeur>{compte.nom_complet}</Valeur>
        </h1>
        <h2 id="titre-identite" className="sr-only">
          Identité
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{compte.email}</p>
      </section>

      {compte.est_proprietaire ? (
        /*
          7.7 — aucune section de droits n'est rendue pour le proprietaire. Pas
          en lecture seule, pas grisee : absente. Son acces est materialise au
          plan 03-05, donc une case a cocher serait un mensonge cliquable.
        */
        <p className="mt-8 text-sm text-muted-foreground">{PHRASE_PROPRIETAIRE}</p>
      ) : (
        <>
          <SectionMagasins
            magasinsOffrables={offrable.magasins}
            accordes={accordes}
            surAjout={(code) => basculerLeMagasin(code, true)}
            surRetrait={(magasin) => basculerLeMagasin(magasin.code, false)}
            surDemandeDeDesactivation={() => undefined}
          />

          <SectionDroits
            catalogue={offrable}
            lignes={lignes}
            magasinsAccordes={accordes}
            prenom={prenom}
            notes={notes}
            erreurs={erreurs}
            surBascule={basculerLeDroit}
          />

          <HistoriqueDroits compteId={identifiant} />
        </>
      )}
    </div>
  );
}

/**
 * Les notes en ligne de la cascade de prerequis (7.6).
 *
 * `cascade` existe comme liste separee alors qu'elle est derivable de `lignes`,
 * et c'est delibere cote serveur : l'interface en fait deux choses que `lignes`
 * ne distingue pas — une note par ligne emportee, et **un seul** toast
 * d'annulation. La note EXPLIQUE ; la fermeture, elle, est appliquee cote
 * serveur.
 */
function notesDeCascade(
  resultat: ResultatOctroi,
  catalogue: CatalogueOffrable,
): Record<string, string> {
  const libelles = new Map(
    catalogue.sections.flatMap((section) =>
      section.droits.map((droit) => [droit.code, droit.libelle] as const),
    ),
  );
  const demande = libelles.get(resultat.code) ?? resultat.code;
  const notes: Record<string, string> = {};
  for (const code of resultat.cascade) {
    const libelle = libelles.get(code) ?? code;
    notes[code] =
      resultat.action === "accorde"
        ? `« ${libelle} » a été activé automatiquement.`
        : `« ${libelle} » a été retiré : il dépend de « ${demande} ».`;
  }
  return notes;
}

function retirer(
  table: Record<string, string>,
  clef: string,
): Record<string, string> {
  const { [clef]: _oublie, ...reste } = table;
  return reste;
}

/**
 * Le message d'un echec de bascule.
 *
 * Le serveur explique en francais — « Vous ne pouvez accorder qu'un droit que
 * vous detenez vous-meme. » — et c'est ce qu'il faut afficher. A defaut, une
 * phrase generique, jamais un code de statut ni une trace.
 */
function messageDechec(corps: unknown): string {
  if (typeof corps === "object" && corps !== null) {
    const detail = (corps as { detail?: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
    for (const valeur of Object.values(corps as Record<string, unknown>)) {
      if (Array.isArray(valeur) && typeof valeur[0] === "string") {
        return valeur[0];
      }
      if (typeof valeur === "string") {
        return valeur;
      }
    }
  }
  return "Ce changement n'a pas été enregistré. Réessayez.";
}

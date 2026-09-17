import { useState, type ReactNode } from "react";

import { useNavigate } from "react-router-dom";

import { $api } from "@/api/requetes";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CarteDechec } from "@/etats/CarteDechec";
import { formaterDateHeure } from "@/format";
import { TableauProjete } from "@/tableau/Tableau";
import type { Colonne } from "@/tableau/registre";
import { Valeur } from "@/tableau/Valeur";

import { CreerCompte } from "./CreerCompte";

/**
 * `03-UI-SPEC.md` 7.2 — la liste des comptes (PERM-02).
 *
 * Six colonnes, et **aucune action de retrait, nulle part**. Un compte est
 * reference par des ventes, par `JournalDroit` et par dix ans de conservation
 * (art. 211 CGI) : le seul chemin est la desactivation, et elle est
 * reversible. Le mot lui-meme n'apparait pas a l'ecran (7.8).
 *
 * Le tableau passe par `TableauProjete`, donc par `champ in ligne` : c'est la
 * moitie cliente de PERM-06 posee au plan 03-11, et c'est ce qui fait qu'un
 * champ retire de la charge utile ne peut pas reapparaitre en colonne vide.
 */

/** `Tous` pour le proprietaire ; sinon les noms, ou `3 magasins` au-dela de deux. */
function rendreLesMagasins(valeur: unknown, ligne: Record<string, unknown>): ReactNode {
  if (ligne.est_proprietaire === true) {
    return "Tous";
  }
  const magasins = (valeur ?? []) as { nom: string }[];
  if (magasins.length === 0) {
    return "Aucun magasin";
  }
  if (magasins.length > 2) {
    return `${magasins.length} magasins`;
  }
  return <Valeur>{magasins.map((magasin) => magasin.nom).join(", ")}</Valeur>;
}

/**
 * `12 droits`, plus le badge `Personnalisé par magasin` quand un octroi n'est
 * pas uniforme.
 *
 * `personnalise` est calcule **cote serveur** (plan 03-09). A trois magasins et
 * vingt et un codes, le recomposer ici couterait soixante-trois lectures par
 * ligne de tableau ; et un champ absent y vaut `undefined`, donc l'absence est
 * fail-closed sans branche a ecrire.
 */
function rendreLesDroits(valeur: unknown, ligne: Record<string, unknown>): ReactNode {
  const nombre = typeof valeur === "number" ? valeur : 0;
  return (
    <span className="inline-flex items-center gap-2">
      <span>{nombre <= 1 ? `${nombre} droit` : `${nombre} droits`}</span>
      {ligne.personnalise === true ? (
        <Badge variant="outline">Personnalisé par magasin</Badge>
      ) : null}
    </span>
  );
}

/**
 * `Actif` en badge neutre, `Désactivé` en badge destructif.
 *
 * **Le mot porte le sens, la couleur ne fait que le renforcer** (7.2). Un
 * pastille de couleur seule serait illisible pour une personne daltonienne et
 * muette pour un lecteur d'ecran.
 */
function rendreLeStatut(valeur: unknown): ReactNode {
  return valeur === false ? (
    <Badge variant="destructive">Désactivé</Badge>
  ) : (
    <Badge variant="secondary">Actif</Badge>
  );
}

function rendreLaDerniereConnexion(valeur: unknown): ReactNode {
  if (valeur === null || valeur === undefined) {
    return "Jamais connecté";
  }
  return <span className="tabular-nums">{formaterDateHeure(valeur as string)}</span>;
}

/**
 * Le registre. Declaratif pour le libelle, l'ordre et l'alignement ; pilote par
 * la donnee pour la PRESENCE.
 */
const COLONNES: readonly Colonne[] = [
  {
    champ: "nom_complet",
    libelle: "Nom",
    rendu: (valeur, ligne) => (
      <span className="inline-flex items-center gap-2">
        <Valeur>{valeur as ReactNode}</Valeur>
        {ligne.est_proprietaire === true ? (
          <Badge variant="outline">Propriétaire</Badge>
        ) : null}
      </span>
    ),
  },
  { champ: "email", libelle: "Adresse e-mail" },
  { champ: "magasins", libelle: "Magasins", rendu: rendreLesMagasins },
  { champ: "nombre_de_droits", libelle: "Droits", rendu: rendreLesDroits },
  { champ: "actif", libelle: "Statut", rendu: rendreLeStatut },
  {
    champ: "derniere_connexion",
    libelle: "Dernière connexion",
    rendu: rendreLaDerniereConnexion,
  },
];

const TITRE = "Comptes et droits";
const ACTION_CREER = "Créer un compte gérant";

/**
 * L'etat vide, avec sa copie exacte.
 *
 * La seconde phrase est deliberee : elle pre-empte le malentendu le plus
 * probable de CLAUDE.md #6 — « il me faut un compte par vendeur » — et elle
 * coute une ligne au lieu d'un appel telephonique. Un opticien qui cree huit
 * comptes de vendeurs paie huit fois pour rien et nous appelle ensuite pour
 * comprendre pourquoi ils ne se connectent pas.
 */
function AucunCompte({ creer }: { creer: () => void }) {
  return (
    <div className="mx-auto max-w-prose py-12 text-center">
      <h2 className="text-lg font-semibold">Aucun compte gérant</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        Créez un compte pour chaque personne qui tient un magasin. Les vendeurs n'ont pas
        besoin de compte — ils sont enregistrés sur la vente.
      </p>
      <Button className="mt-6" type="button" onClick={creer}>
        {ACTION_CREER}
      </Button>
    </div>
  );
}

export function ListeComptes() {
  const naviguer = useNavigate();
  const [dialogueOuvert, setDialogueOuvert] = useState(false);

  const comptes = $api.useQuery("get", "/api/comptes/");

  return (
    <>
      <div className="flex items-start justify-between gap-4">
        <h1 className="text-2xl font-semibold">{TITRE}</h1>
        <Button type="button" onClick={() => setDialogueOuvert(true)}>
          {ACTION_CREER}
        </Button>
      </div>

      <div className="mt-6">
        {comptes.isError ? (
          <CarteDechec quoi="les comptes" reessayer={() => void comptes.refetch()} />
        ) : comptes.isPending ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : comptes.data.length === 0 ? (
          <AucunCompte creer={() => setDialogueOuvert(true)} />
        ) : (
          <TableauProjete
            legende="Les comptes de l'entreprise, leurs magasins et leurs droits"
            colonnes={COLONNES}
            lignes={comptes.data as unknown as Record<string, unknown>[]}
            clefLigne={(ligne) => String(ligne.id)}
            onLigneActivee={(ligne) =>
              naviguer(`/parametres/comptes/${String(ligne.id)}`)
            }
          />
        )}
      </div>

      <CreerCompte
        ouvert={dialogueOuvert}
        surFermeture={() => setDialogueOuvert(false)}
        surCreation={(compte) => {
          setDialogueOuvert(false);
          void comptes.refetch();
          // Droit au detail : un compte neuf n'a ni droit ni magasin, donc le
          // detail EST la prochaine chose a faire (7.2).
          naviguer(`/parametres/comptes/${String(compte.id)}`);
        }}
      />
    </>
  );
}

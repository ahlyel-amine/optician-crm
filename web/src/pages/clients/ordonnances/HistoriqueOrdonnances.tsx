import { Link, useParams } from "react-router-dom";

import { $api } from "@/api/requetes";
import { useAuth } from "@/auth/AuthProvider";
import { RequirePermission } from "@/auth/RequirePermission";
import { Button } from "@/components/ui/button";
import { CarteDechec } from "@/etats/CarteDechec";
import { PageIntrouvable } from "@/etats/PageIntrouvable";
import { MESSAGE_CHARGEMENT } from "@/pages/clients/messages";

import { CarteVersion } from "./CarteVersion";
import {
  ACTION_SAISIR,
  QUOI_CHARGER_LES_ORDONNANCES,
  TITRE_HISTORIQUE,
  VIDE_CORPS,
  VIDE_TITRE,
} from "./messages";

/**
 * L'HISTORIQUE DES VERSIONS — 04-UI-SPEC.md 21 (CLIENT-06).
 *
 * Plus recente d'abord, une carte par version. Le serveur sert deja dans cet
 * ordre (plan 04-05) et **l'interface ne retrie rien** : un second classement
 * ecrit ici divergerait du premier le jour ou l'un des deux changerait.
 *
 * **Aucun controle de modification, aucun controle de suppression**, ni ici ni
 * sur la carte. Le seul chemin de correction est `Saisir une ordonnance`, qui
 * cree une NOUVELLE version portant son motif — et l'ancienne reste lisible
 * exactement telle qu'elle a ete saisie.
 *
 * **Le magasin est resolu depuis l'amorcage**, pas redemande : la version sert
 * une cle primaire de provenance, et les magasins de l'affaire sont deja en
 * memoire. Un magasin inconnu de l'amorcage — parce que le gerant ne l'a pas
 * accorde — rend une chaine vide plutot qu'un identifiant nu : un numero a
 * l'ecran ne dit rien a un opticien.
 */
export function HistoriqueOrdonnances() {
  const { id = "" } = useParams();
  const identifiant = Number.parseInt(id, 10);
  const { magasins } = useAuth();

  const versions = $api.useQuery("get", "/api/clients/{client_id}/ordonnances/", {
    params: { path: { client_id: identifiant } },
  });

  const nomDuMagasin = (cle: unknown): string =>
    magasins.find((magasin) => magasin.id === cle)?.nom ?? "";

  if (versions.isError) {
    return (
      <CarteDechec
        quoi={QUOI_CHARGER_LES_ORDONNANCES}
        reessayer={() => void versions.refetch()}
      />
    );
  }

  if (versions.isPending) {
    return <p className="text-sm text-muted-foreground">{MESSAGE_CHARGEMENT}</p>;
  }

  const lignes = versions.data as unknown as Record<string, unknown>[];

  return (
    <section className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <h2 className="text-xl font-semibold">{TITRE_HISTORIQUE}</h2>
        <BoutonDeSaisie identifiant={identifiant} />
      </div>

      {lignes.length === 0 ? (
        <div className="mx-auto max-w-prose py-12 text-center">
          <h3 className="text-lg font-semibold">{VIDE_TITRE}</h3>
          <p className="mt-2 text-sm text-muted-foreground">{VIDE_CORPS}</p>
          <div className="mt-6 flex justify-center">
            <BoutonDeSaisie identifiant={identifiant} />
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {lignes.map((version, rang) => (
            <CarteVersion
              key={String(version.id)}
              version={version}
              enCours={rang === 0}
              nomDuMagasin={nomDuMagasin(version.magasin)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

/**
 * Le CTA est ABSENT sans `ordonnance.saisir`, jamais desactive : un bouton
 * inerte apprend a l'utilisateur qu'un pouvoir existe et qu'il ne l'a pas.
 */
export function BoutonDeSaisie({ identifiant }: { identifiant: number }) {
  return (
    <RequirePermission code="ordonnance.saisir">
      <Button asChild type="button">
        <Link to={`/clients/${String(identifiant)}/ordonnances/nouvelle`}>
          {ACTION_SAISIR}
        </Link>
      </Button>
    </RequirePermission>
  );
}

/**
 * 21.4 — UNE VERSION SEULE, pleine largeur, pour le lien et pour l'impression.
 *
 * **La meme carte**, donc les memes regles : aucune revalidation, aucun
 * controle de modification, aucune couleur. Une seconde mise en page de la
 * meme version serait une seconde verite a tenir a jour.
 *
 * `:version` est le NUMERO DE VERSION et non la cle primaire : c'est lui que
 * l'opticien lit a l'ecran et recopie dans un message, et il est stable pour un
 * client donne.
 */
export function VersionSeule() {
  const { id = "", version = "" } = useParams();
  const identifiant = Number.parseInt(id, 10);
  const numero = Number.parseInt(version, 10);
  const { magasins } = useAuth();

  const versions = $api.useQuery("get", "/api/clients/{client_id}/ordonnances/", {
    params: { path: { client_id: identifiant } },
  });

  if (versions.isError) {
    return (
      <CarteDechec
        quoi={QUOI_CHARGER_LES_ORDONNANCES}
        reessayer={() => void versions.refetch()}
      />
    );
  }

  if (versions.isPending) {
    return <p className="text-sm text-muted-foreground">{MESSAGE_CHARGEMENT}</p>;
  }

  const lignes = versions.data as unknown as Record<string, unknown>[];
  const cherchee = lignes.find((ligne) => ligne.version === numero);

  if (cherchee === undefined) {
    // Une version qui n'existe pas est un 404, pas une carte vide.
    return <PageIntrouvable />;
  }

  return (
    <CarteVersion
      version={cherchee}
      enCours={lignes.length > 0 && lignes[0].version === numero}
      nomDuMagasin={
        magasins.find((magasin) => magasin.id === cherchee.magasin)?.nom ?? ""
      }
    />
  );
}

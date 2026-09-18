import { useEffect, useId, useState } from "react";

import { useNavigate, useSearchParams } from "react-router-dom";

import { $api } from "@/api/requetes";
import { RequirePermission } from "@/auth/RequirePermission";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CarteDechec } from "@/etats/CarteDechec";
import { DELAI_ANTI_REBOND } from "@/layout/Recherche";
import { TableauProjete } from "@/tableau/Tableau";

import { CreerClient } from "./CreerClient";
import { COLONNES_CLIENTS } from "./colonnes";
import {
  ACTION_CREER,
  LABEL_RECHERCHE,
  LEGENDE_TABLEAU,
  MESSAGE_CHARGEMENT,
  QUOI_CHARGER,
  TITRE_LISTE,
  VIDE_SANS_FICHE_CORPS,
  VIDE_SANS_FICHE_TITRE,
  VIDE_SANS_RESULTAT_CORPS,
  VIDE_SANS_RESULTAT_TITRE,
  creerAvecCeNom,
} from "./messages";

/**
 * La liste des clients — 04-UI-SPEC.md 18 (CLIENT-01, CLIENT-10).
 *
 * TROIS CHOSES QUE CET ECRAN S'INTERDIT, et qui sont son interet :
 *
 * 1. **Il ne normalise rien.** Le terme tape part au serveur TEL QUEL : pas de
 *    `trim`, pas de `toLowerCase`, pas de retrait d'accent, pas de filtrage
 *    local. La normalisation vit dans l'index SQL (plan 04-03), et une seconde,
 *    ecrite ici, ferait diverger ce que l'opticien voit de ce que la base sait.
 *    Une saisie arabe fait l'aller-retour inchangee pour la meme raison.
 * 2. **Il ne trie rien et ne filtre rien.** Le classement des candidats est
 *    celui du serveur, qui seul dispose des quatre couches de rappel.
 * 3. **Il ne decide d'aucune colonne.** La presence vient de la charge utile,
 *    par `colonnesVisiblesSurLignes`. Aucune branche cliente, nulle part sous
 *    ce dossier — une garde de CI le verifie.
 *
 * La page porte SON PROPRE champ de recherche, en plus de la palette du shell :
 * au comptoir on travaille dans la liste, pas seulement au clavier.
 */

/** L'etat d'une affaire qui n'a encore aucune fiche. */
function AucuneFiche({ creer }: { creer: () => void }) {
  return (
    <div className="mx-auto max-w-prose py-12 text-center">
      <h2 className="text-lg font-semibold">{VIDE_SANS_FICHE_TITRE}</h2>
      <p className="mt-2 text-sm text-muted-foreground">{VIDE_SANS_FICHE_CORPS}</p>
      <RequirePermission code="client.modifier">
        <Button className="mt-6" type="button" onClick={creer}>
          {ACTION_CREER}
        </Button>
      </RequirePermission>
    </div>
  );
}

/** L'etat d'une recherche qui n'a rien rendu. La requete est echouee VERBATIM. */
function AucunResultat({ terme, creer }: { terme: string; creer: () => void }) {
  return (
    <div className="mx-auto max-w-prose py-12 text-center">
      <h2 className="text-lg font-semibold">{VIDE_SANS_RESULTAT_TITRE}</h2>
      <p className="mt-2 text-sm text-muted-foreground">{VIDE_SANS_RESULTAT_CORPS}</p>
      <RequirePermission code="client.modifier">
        <Button className="mt-6" type="button" onClick={creer}>
          {creerAvecCeNom(terme)}
        </Button>
      </RequirePermission>
    </div>
  );
}

export function ListeClients() {
  const naviguer = useNavigate();
  const identifiant = useId();
  const [parametres, setParametres] = useSearchParams();

  const [saisie, setSaisie] = useState(() => parametres.get("search") ?? "");
  const [terme, setTerme] = useState(() => parametres.get("search") ?? "");
  const [nomInitial, setNomInitial] = useState("");
  const [dialogueOuvert, setDialogueOuvert] = useState(false);

  /**
   * Les deux parametres que la palette pose en arrivant ici.
   *
   * `?search=` reprend la requete, `?creer=` ouvre le dialogue avec le nom
   * deja ecrit — c'est ainsi que `Créer un client « mohamed b »` de la palette
   * atterrit sur le bon formulaire **sans qu'une ligne de `Recherche.tsx` ne
   * change**. Les parametres sont retires aussitot consommes, pour qu'un
   * rafraichissement ne rouvre pas un dialogue que l'opticien a ferme.
   */
  useEffect(() => {
    const aChercher = parametres.get("search");
    const aCreer = parametres.get("creer");
    if (aChercher === null && aCreer === null) {
      return;
    }
    if (aChercher !== null) {
      setSaisie(aChercher);
      setTerme(aChercher);
    }
    if (aCreer !== null) {
      setNomInitial(aCreer);
      setDialogueOuvert(true);
    }
    setParametres({}, { replace: true });
  }, [parametres, setParametres]);

  /**
   * L'anti-rebond de 200 ms, partage avec la palette (`03` 5.5).
   *
   * Il differe l'ENVOI, il ne touche pas au terme : ce qui part au bout des
   * 200 ms est exactement ce qui a ete tape.
   */
  useEffect(() => {
    const minuteur = setTimeout(() => setTerme(saisie), DELAI_ANTI_REBOND);
    return () => clearTimeout(minuteur);
  }, [saisie]);

  const clients = $api.useQuery(
    "get",
    "/api/clients/",
    terme === "" ? {} : { params: { query: { search: terme } } },
  );

  const ouvrirLaCreation = (nom: string) => {
    setNomInitial(nom);
    setDialogueOuvert(true);
  };

  return (
    <>
      <div className="flex items-start justify-between gap-4">
        <h1 className="text-2xl font-semibold">{TITRE_LISTE}</h1>
        {/*
          Le CTA est ABSENT sans `client.modifier`, jamais desactive : un bouton
          inerte apprend a l'utilisateur qu'un pouvoir existe et qu'il ne l'a
          pas. Le controle, lui, est la classe de permission du serveur.
        */}
        <RequirePermission code="client.modifier">
          <Button type="button" onClick={() => ouvrirLaCreation("")}>
            {ACTION_CREER}
          </Button>
        </RequirePermission>
      </div>

      {/*
        Un VRAI label visible au-dessus du champ. Un placeholder n'est pas une
        etiquette : il disparait des la premiere frappe, et il n'est pas lu par
        tous les lecteurs d'ecran (`03` 10).
      */}
      <div className="mt-6 max-w-sm">
        <Label htmlFor={`${identifiant}-recherche`}>{LABEL_RECHERCHE}</Label>
        <Input
          id={`${identifiant}-recherche`}
          className="mt-2"
          value={saisie}
          autoComplete="off"
          onChange={(evenement) => setSaisie(evenement.target.value)}
        />
      </div>

      <div className="mt-6">
        {clients.isError ? (
          <CarteDechec quoi={QUOI_CHARGER} reessayer={() => void clients.refetch()} />
        ) : clients.isPending ? (
          <p className="text-sm text-muted-foreground">{MESSAGE_CHARGEMENT}</p>
        ) : clients.data.length === 0 ? (
          /*
            ZERO LIGNE REND ZERO COLONNE, et c'est deja le comportement de
            `colonnesVisiblesSurLignes`. Rendre les en-tetes du registre sur un
            resultat vide revelerait a un gerant sans le droit que la colonne
            « Dernière ordonnance » existe : la position et l'existence d'un
            champ sont elles-memes une divulgation. L'etat vide se dit avec une
            phrase.
          */
          terme === "" ? (
            <AucuneFiche creer={() => ouvrirLaCreation("")} />
          ) : (
            <AucunResultat terme={terme} creer={() => ouvrirLaCreation(terme)} />
          )
        ) : (
          <TableauProjete
            legende={LEGENDE_TABLEAU}
            colonnes={COLONNES_CLIENTS}
            lignes={clients.data as unknown as Record<string, unknown>[]}
            clefLigne={(ligne) => String(ligne.id)}
            onLigneActivee={(ligne) => naviguer(`/clients/${String(ligne.id)}`)}
          />
        )}
      </div>

      <CreerClient
        ouvert={dialogueOuvert}
        nomInitial={nomInitial}
        surFermeture={() => setDialogueOuvert(false)}
        surCreation={() => {
          setDialogueOuvert(false);
          void clients.refetch();
        }}
      />
    </>
  );
}

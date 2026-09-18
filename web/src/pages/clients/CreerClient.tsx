import { useEffect, useId, useState } from "react";

import { $api, lireCorpsDerreur, type FicheClient } from "@/api/requetes";
import { ChampDate } from "@/champs/ChampDate";
import { versISO } from "@/champs/dates";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { MESSAGE_SERVICE_INDISPONIBLE } from "@/etats/messages";

import { GardeDeDoublon } from "./GardeDeDoublon";

import {
  ACTION_CONFIRMER,
  ACTION_RETOUR,
  AIDE_DATE_NAISSANCE,
  AIDE_NOTES,
  AVERTISSEMENT_SANS_TELEPHONE,
  LABEL_ADRESSE,
  LABEL_DATE_NAISSANCE,
  LABEL_NOM,
  LABEL_NOTES,
  LABEL_TELEPHONE,
  MESSAGE_NAISSANCE_FUTURE,
  TITRE_CREATION,
} from "./messages";

/**
 * `Créer un client` — un dialogue de 480px, sur la forme exacte de
 * `Créer un compte gérant` (`03` 7.2 et 04-UI-SPEC.md 18.6).
 *
 * Le bouton secondaire est **`Retour`**, jamais `Annuler` : dans ce produit
 * `Annuler` veut dire DEFAIRE une action deja enregistree, et il n'apparait
 * que sur un toast d'annulation (`03` 7.10). Confondre les deux ferait croire
 * a un opticien qu'il defait une creation en fermant une boite.
 *
 * ---
 *
 * **Composants controles, pas de bibliotheque de formulaire.**
 * `04-UI-SPEC.md` 15.3 RENVERSE la promesse de `03` 1, et c'est un
 * renversement assume, pas un oubli. Trois raisons, dans l'ordre de leur poids :
 *
 * 1. le modele de validation de cette phase est a trois etages — refus,
 *    avertissement non bloquant, relecture — et un avertissement n'est pas une
 *    erreur. L'exprimer par le `setError` d'une bibliotheque serait un
 *    detournement de severite dans la machine a etats d'autrui ;
 * 2. les bornes de la phase viennent du SERVEUR, donc un schema de resolveur
 *    en serait une seconde copie ecrite ;
 * 3. la phase 3 a livre `Connexion` et `CreerCompte` en composants controles ;
 *    ajouter une bibliotheque maintenant donnerait deux idiomes aux trois
 *    premiers formulaires du produit.
 *
 * **A revoir en phase 6**, dont les lignes de facture sont un tableau de champs
 * dynamique — le cas qu'une bibliotheque de formulaire gagne reellement.
 */

export type ProprietesCreerClient = {
  ouvert: boolean;
  /** Le nom deja tape ailleurs — dans la palette, ou dans le champ de la liste. */
  nomInitial?: string;
  surFermeture: () => void;
  surCreation: (client: FicheClient) => void;
};

/** Le jour de reference du refus de date future, en ISO. */
function aujourdhuiISO(): string {
  const maintenant = new Date();
  const mois = String(maintenant.getMonth() + 1).padStart(2, "0");
  const jour = String(maintenant.getDate()).padStart(2, "0");
  return `${maintenant.getFullYear()}-${mois}-${jour}`;
}

export function CreerClient({
  ouvert,
  nomInitial = "",
  surFermeture,
  surCreation,
}: ProprietesCreerClient) {
  const identifiant = useId();
  const [nom, setNom] = useState(nomInitial);
  const [telephone, setTelephone] = useState("");
  const [dateNaissance, setDateNaissance] = useState("");
  const [fauteDeDate, setFauteDeDate] = useState<string | null>(null);
  const [adresse, setAdresse] = useState("");
  const [notes, setNotes] = useState("");
  const [telephoneQuitte, setTelephoneQuitte] = useState(false);
  const [echec, setEchec] = useState<string | null>(null);

  useEffect(() => {
    if (ouvert) {
      setNom(nomInitial);
      return;
    }
    setNom("");
    setTelephone("");
    setDateNaissance("");
    setFauteDeDate(null);
    setAdresse("");
    setNotes("");
    setTelephoneQuitte(false);
    setEchec(null);
  }, [ouvert, nomInitial]);

  const creation = $api.useMutation("post", "/api/clients/");

  const envoyer = () => {
    setEchec(null);
    creation.mutate(
      {
        body: {
          nom,
          telephone,
          date_naissance: dateNaissance === "" ? null : versISO(dateNaissance),
          adresse,
          notes,
        } as FicheClient,
      },
      {
        onSuccess: (donnees) => surCreation(donnees),
        onError: (erreur) => {
          const corps = lireCorpsDerreur(erreur);
          setEchec(corps.detail ?? premierMessage(erreur) ?? MESSAGE_SERVICE_INDISPONIBLE);
        },
      },
    );
  };

  /**
   * A11 (04-UI-SPEC.md 16.3) : un client sans telephone ne recevra aucun rappel.
   *
   * C'est un AVERTISSEMENT, pas un refus. Il ne porte donc pas `aria-invalid`,
   * il est annonce par `role="status"` et non par `role="alert"`, et il
   * n'empeche rien — un client de passage qui ne laisse pas son numero doit
   * pouvoir etre enregistre.
   */
  const avertissementTelephone =
    telephoneQuitte && telephone === "" ? AVERTISSEMENT_SANS_TELEPHONE : null;

  return (
    <Dialog open={ouvert} onOpenChange={(etat) => (etat ? undefined : surFermeture())}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>{TITRE_CREATION}</DialogTitle>
        </DialogHeader>

        {/*
          LA GARDE DE DOUBLON EST RENDUE AU-DESSUS DU FORMULAIRE, jamais en
          dessous : l'information doit arriver AVANT la saisie qu'elle informe.
          Placee sous les champs, elle serait lue apres la decision qu'elle
          existe pour eclairer.
        */}
        <GardeDeDoublon nom={nom} />

        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor={`${identifiant}-nom`}>{LABEL_NOM}</Label>
            <Input
              id={`${identifiant}-nom`}
              autoFocus
              required
              value={nom}
              autoComplete="off"
              onChange={(evenement) => setNom(evenement.target.value)}
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor={`${identifiant}-telephone`}>{LABEL_TELEPHONE}</Label>
            <Input
              id={`${identifiant}-telephone`}
              inputMode="tel"
              value={telephone}
              autoComplete="off"
              aria-describedby={
                avertissementTelephone ? `${identifiant}-telephone-note` : undefined
              }
              onChange={(evenement) => setTelephone(evenement.target.value)}
              onBlur={() => setTelephoneQuitte(true)}
            />
            {avertissementTelephone === null ? null : (
              <p
                id={`${identifiant}-telephone-note`}
                role="status"
                className="text-xs text-muted-foreground"
              >
                {avertissementTelephone}
              </p>
            )}
          </div>

          <div className="grid gap-2">
            <ChampDate
              label={LABEL_DATE_NAISSANCE}
              identifiant={`${identifiant}-naissance`}
              valeur={dateNaissance}
              surChangement={setDateNaissance}
              surVerdict={(verdict) =>
                setFauteDeDate("faute" in verdict ? verdict.faute : null)
              }
              futurInterdit
              messageFutur={MESSAGE_NAISSANCE_FUTURE}
              aujourdhui={aujourdhuiISO()}
            />
            <p className="text-xs text-muted-foreground">{AIDE_DATE_NAISSANCE}</p>
          </div>

          <div className="grid gap-2">
            <Label htmlFor={`${identifiant}-adresse`}>{LABEL_ADRESSE}</Label>
            <Textarea
              id={`${identifiant}-adresse`}
              rows={2}
              value={adresse}
              onChange={(evenement) => setAdresse(evenement.target.value)}
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor={`${identifiant}-notes`}>{LABEL_NOTES}</Label>
            <Textarea
              id={`${identifiant}-notes`}
              rows={3}
              value={notes}
              aria-describedby={`${identifiant}-notes-aide`}
              onChange={(evenement) => setNotes(evenement.target.value)}
            />
            {/*
              `notes` est classe PUBLIC au registre de projection. Le dire ici
              est ce qui rend cette classification honnete vis-a-vis de celui
              qui ecrit dedans.
            */}
            <p id={`${identifiant}-notes-aide`} className="text-xs text-muted-foreground">
              {AIDE_NOTES}
            </p>
          </div>

          {echec === null ? null : (
            <p role="alert" className="text-sm text-destructive">
              {echec}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={surFermeture}>
            {ACTION_RETOUR}
          </Button>
          {/*
            Le bouton n'est desactive que pendant l'envoi et sur un REFUS en
            cours — le premier etage du modele de validation. Un avertissement,
            lui, ne desactive rien : il informe.
          */}
          <Button
            type="button"
            onClick={envoyer}
            disabled={creation.isPending || fauteDeDate !== null}
          >
            {ACTION_CONFIRMER}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Le premier message d'une erreur de validation DRF, qui est un dictionnaire de
 * listes par champ. Le nom du champ n'est pas affiche : la phrase francaise le
 * designe deja, et un prefixe technique est du vocabulaire de developpeur.
 */
function premierMessage(corps: unknown): string | undefined {
  if (typeof corps !== "object" || corps === null) {
    return undefined;
  }
  for (const valeur of Object.values(corps as Record<string, unknown>)) {
    if (typeof valeur === "string") {
      return valeur;
    }
    if (Array.isArray(valeur) && typeof valeur[0] === "string") {
      return valeur[0];
    }
  }
  return undefined;
}

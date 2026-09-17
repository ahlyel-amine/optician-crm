import { useEffect, useId, useState } from "react";

import { $api, lireCorpsDerreur, type Compte } from "@/api/requetes";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MESSAGE_SERVICE_INDISPONIBLE } from "@/etats/messages";

/**
 * `03-UI-SPEC.md` 7.2 — le dialogue de creation, 480px, trois champs.
 *
 * Le bouton secondaire est **`Retour`**, jamais `Annuler` : la regle des trois
 * mots de 7.10 reserve `Annuler` a l'annulation d'une action enregistree, et
 * c'est ce qui evite qu'un opticien croie defaire un octroi en fermant une
 * boite de dialogue.
 *
 * Les libelles sont complets — `Générer un mot de passe`, `Copier le mot de
 * passe` — plutot que les verbes seuls, comme `03-UI-CHECK.md` le recommande :
 * ils ne coutent rien et retirent toute ambiguite sur l'objet du verbe.
 */

/**
 * L'alphabet du mot de passe provisoire.
 *
 * Ni `O`/`0`, ni `l`/`I`/`1` : ce secret est lu a voix haute ou recopie sur un
 * papier, parce qu'il n'existe aucun chemin par courriel dans la pile
 * (plan 03-08). Une ambiguite typographique se paie ici d'un appel.
 */
const ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789";
const LONGUEUR = 16;

/**
 * Un secret tire de `crypto.getRandomValues`, jamais de `Math.random`.
 *
 * `Math.random` n'est pas un generateur cryptographique et son etat est
 * observable depuis la meme page ; il n'a rien a faire sur le chemin d'un mot
 * de passe, meme provisoire, meme change a la premiere connexion.
 *
 * Le rejet des valeurs au-dela du plus grand multiple de la taille de
 * l'alphabet retire le biais modulo. Il est faible sur 256 valeurs pour 55
 * caracteres, et le retirer coute trois lignes.
 */
export function engendrerUnMotDePasse(longueur = LONGUEUR): string {
  const limite = 256 - (256 % ALPHABET.length);
  let secret = "";
  while (secret.length < longueur) {
    const octets = new Uint8Array(longueur);
    crypto.getRandomValues(octets);
    for (const octet of octets) {
      if (octet < limite && secret.length < longueur) {
        secret += ALPHABET[octet % ALPHABET.length];
      }
    }
  }
  return secret;
}

export type ProprietesCreerCompte = {
  ouvert: boolean;
  surFermeture: () => void;
  surCreation: (compte: Compte) => void;
};

export function CreerCompte({
  ouvert,
  surFermeture,
  surCreation,
}: ProprietesCreerCompte) {
  const identifiant = useId();
  const [nom, setNom] = useState("");
  const [email, setEmail] = useState("");
  const [secret, setSecret] = useState("");
  const [echec, setEchec] = useState<string | null>(null);

  useEffect(() => {
    if (!ouvert) {
      setNom("");
      setEmail("");
      setSecret("");
      setEchec(null);
    }
  }, [ouvert]);

  const creation = $api.useMutation("post", "/api/comptes/");

  const envoyer = () => {
    setEchec(null);
    creation.mutate(
      {
        body: {
          nom_complet: nom,
          email,
          mot_de_passe_provisoire: secret,
        },
      },
      {
        onSuccess: (donnees) => {
          surCreation(donnees.compte);
        },
        onError: (erreur) => {
          // Le message du serveur quand il y en a un — « Cette adresse e-mail
          // n'est pas disponible. », « Ce mot de passe est trop courant. » —,
          // sinon la phrase d'indisponibilite. Jamais un code de statut, jamais
          // une trace.
          const corps = lireCorpsDerreur(erreur);
          setEchec(corps.detail ?? premierMessage(erreur) ?? MESSAGE_SERVICE_INDISPONIBLE);
        },
      },
    );
  };

  return (
    <Dialog open={ouvert} onOpenChange={(etat) => (etat ? undefined : surFermeture())}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Créer un compte gérant</DialogTitle>
          <DialogDescription>
            Ce mot de passe devra être changé à la première connexion.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor={`${identifiant}-nom`}>Nom complet</Label>
            <Input
              id={`${identifiant}-nom`}
              value={nom}
              autoComplete="off"
              onChange={(evenement) => setNom(evenement.target.value)}
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor={`${identifiant}-email`}>Adresse e-mail</Label>
            <Input
              id={`${identifiant}-email`}
              type="email"
              value={email}
              autoComplete="off"
              onChange={(evenement) => setEmail(evenement.target.value)}
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor={`${identifiant}-secret`}>Mot de passe provisoire</Label>
            <Input
              id={`${identifiant}-secret`}
              value={secret}
              autoComplete="off"
              onChange={(evenement) => setSecret(evenement.target.value)}
            />
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setSecret(engendrerUnMotDePasse())}
              >
                Générer un mot de passe
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={secret === ""}
                onClick={() => void navigator.clipboard?.writeText(secret)}
              >
                Copier le mot de passe
              </Button>
            </div>
          </div>

          {echec === null ? null : (
            <p role="alert" className="text-sm text-destructive">
              {echec}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={surFermeture}>
            Retour
          </Button>
          <Button type="button" onClick={envoyer} disabled={creation.isPending}>
            Créer le compte
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Le premier message d'une erreur de validation DRF, qui est un dictionnaire de
 * listes par champ : `{"email": ["Cette adresse e-mail n'est pas disponible."]}`.
 *
 * On n'affiche pas le nom du champ. Le dialogue en a trois, la phrase les
 * designe deja, et un « email : » prefixe devant une phrase francaise est du
 * vocabulaire de developpeur.
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

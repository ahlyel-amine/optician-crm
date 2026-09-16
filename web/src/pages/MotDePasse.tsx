import { useState, type FormEvent } from "react";

import { useNavigate } from "react-router-dom";

import { clientApi } from "@/api/client";
import { ROUTE_MOT_DE_PASSE, lireCorpsDerreur } from "@/api/requetes";
import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MESSAGE_SERVICE_INDISPONIBLE } from "@/etats/messages";

/**
 * `/mot-de-passe` — le changement force (`03-UI-SPEC.md` 6, dernier etat).
 *
 * Page pleine, **non refermable**, sans navigation de shell et sans aucun lien.
 * Ce n'est pas une modale : une modale se ferme, et un compte dont le mot de
 * passe a ete communique par un tiers ne doit pas pouvoir continuer avec.
 * L'inevitabilite est tenue par `RequireAuth`, qui y retombe tant que le
 * drapeau est vrai — taper une URL protegee a la main revient ici.
 *
 * Il n'y a pas de reinitialisation par e-mail dans ce produit : aucun
 * fournisseur d'e-mail transactionnel n'est au contrat. Le chemin sans e-mail
 * est celui-ci — le proprietaire reinitialise un gerant, l'operateur
 * reinitialise un proprietaire, et `doit_changer_mot_de_passe` force le
 * changement a la premiere connexion.
 *
 * ---
 *
 * `Mot de passe actuel` EST AU CONTRAT — ne pas le retirer.
 *
 * `03-UI-SPEC.md` 9.4 ne listait a l'origine que `Nouveau mot de passe`,
 * `Confirmer` et `Enregistrer`. L'ecart a ete porte au point de controle humain
 * du plan 03-12 le 2026-09-16, et tranche : la specification a ete amendee,
 * l'exigence serveur n'a pas ete affaiblie. Le point de terminaison livre au
 * plan 03-08 exige `mot_de_passe_actuel`, et ce n'est pas un oubli de sa part :
 * sans lui, un poste laisse deverrouille une minute — ou un CSRF reussi — ne
 * donne plus une session mais un compte, definitivement.
 *
 * Le titre, le corps et les trois autres libelles sont ceux de la
 * specification, au caractere pres.
 */
export function MotDePasse() {
  const navigate = useNavigate();
  const { adopterLamorcage } = useAuth();

  const [actuel, setActuel] = useState("");
  const [nouveau, setNouveau] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enAttente, setEnAttente] = useState(false);

  async function soumettre(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    if (enAttente) {
      return;
    }
    if (nouveau !== confirmation) {
      // Refuse avant tout appel reseau : une divergence de frappe n'a pas a
      // consommer une tentative ni a attendre un aller-retour.
      setErreur("Les deux mots de passe ne sont pas identiques.");
      return;
    }
    setEnAttente(true);
    setErreur(null);
    try {
      // `error` porte le corps deja analyse : `response` est consomme.
      const { data, error, response } = await clientApi.POST(ROUTE_MOT_DE_PASSE, {
        body: { mot_de_passe_actuel: actuel, nouveau_mot_de_passe: nouveau },
      });
      if (!response.ok || data === undefined) {
        // La politique de mot de passe est celle du serveur
        // (`AUTH_PASSWORD_VALIDATORS`) et ses messages sont deja en francais :
        // on les affiche tels quels plutot que d'en tenir une seconde copie
        // qui divergerait au premier reglage change.
        const { detail } = lireCorpsDerreur(error);
        setErreur(detail ?? messageDeValidation(error) ?? MESSAGE_SERVICE_INDISPONIBLE);
        return;
      }
      adopterLamorcage(data);
      navigate("/", { replace: true });
    } catch {
      setErreur(MESSAGE_SERVICE_INDISPONIBLE);
    } finally {
      setEnAttente(false);
    }
  }

  return (
    <main
      style={{ paddingTop: "64px" }}
      className="flex min-h-screen w-full flex-col items-center bg-[#FAFAFA] px-6"
    >
      <div className="w-full max-w-[400px] rounded-lg border border-border bg-white p-6">
        <h1 className="text-2xl font-semibold leading-tight">
          Choisissez votre mot de passe
        </h1>
        <p className="mt-4 text-sm text-muted-foreground">
          Ce mot de passe vous a été communiqué par le propriétaire. Choisissez-en un que
          vous êtes seul à connaître.
        </p>

        {erreur !== null ? (
          <div
            role="alert"
            className="mt-4 rounded-md border border-destructive px-3 py-2 text-sm text-destructive"
          >
            {erreur}
          </div>
        ) : null}

        <form className="mt-4 flex flex-col gap-4" onSubmit={soumettre} noValidate>
          <div className="flex flex-col gap-2">
            <Label className="text-xs font-semibold" htmlFor="actuel">
              Mot de passe actuel
            </Label>
            <Input
              id="actuel"
              type="password"
              autoComplete="current-password"
              value={actuel}
              onChange={(evenement) => setActuel(evenement.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label className="text-xs font-semibold" htmlFor="nouveau">
              Nouveau mot de passe
            </Label>
            <Input
              id="nouveau"
              type="password"
              autoComplete="new-password"
              value={nouveau}
              aria-invalid={erreur !== null}
              onChange={(evenement) => setNouveau(evenement.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label className="text-xs font-semibold" htmlFor="confirmation">
              Confirmer
            </Label>
            <Input
              id="confirmation"
              type="password"
              autoComplete="new-password"
              value={confirmation}
              aria-invalid={erreur !== null}
              onChange={(evenement) => setConfirmation(evenement.target.value)}
            />
          </div>
          {/* Le lexique impose « enregistrer ». L'autre verbe francais courant
              ici veut dire *backup*, et il est proscrit (`03-UI-SPEC.md` 9.3). */}
          <Button type="submit" className="w-full font-semibold" disabled={enAttente}>
            Enregistrer
          </Button>
        </form>
      </div>
    </main>
  );
}

/** Rend la premiere erreur de champ d'un corps DRF, si le corps en porte une. */
function messageDeValidation(corps: unknown): string | null {
  if (typeof corps !== "object" || corps === null) {
    return null;
  }
  for (const valeur of Object.values(corps as Record<string, unknown>)) {
    if (Array.isArray(valeur) && typeof valeur[0] === "string") {
      return valeur[0];
    }
  }
  return null;
}

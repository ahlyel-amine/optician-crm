import { useState, type FormEvent } from "react";

import { Link, useNavigate } from "react-router-dom";

import { clientApi } from "@/api/client";
import { ROUTE_MOT_DE_PASSE, lireCorpsDerreur } from "@/api/requetes";
import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MESSAGE_SERVICE_INDISPONIBLE } from "@/etats/messages";

/**
 * `/mot-de-passe` — UNE route, DEUX chemins qui ne demandent pas la meme chose.
 *
 * ---
 *
 * **Chemin force** (`doit_changer_mot_de_passe`, `03-UI-SPEC.md` 6, dernier
 * etat). Page pleine, **non refermable**, sans navigation de shell et sans
 * aucun lien. Ce n'est pas une modale : une modale se ferme, et un compte dont
 * le mot de passe a ete communique par un tiers ne doit pas pouvoir continuer
 * avec. L'inevitabilite est tenue par `RequireAuth`, qui y retombe tant que le
 * drapeau est vrai — taper une URL protegee a la main revient ici.
 *
 * **Chemin volontaire**, atteint par `Changer mon mot de passe` du menu du
 * compte (`03-UI-SPEC.md` 9.4). Rien n'est force, la personne a une issue, et
 * la copie ne peut donc pas etre celle du chemin force : « Ce mot de passe vous
 * a ete communique par le proprietaire » est faux pour quelqu'un qui a choisi
 * le sien il y a six mois.
 *
 * ---
 *
 * **DEUX champs sur le chemin force, TROIS sur le chemin volontaire.**
 *
 * Le chemin force ne demande PAS `Mot de passe actuel` : la personne vient de
 * le saisir, quelques secondes plus tot, pour ouvrir la session qui porte cette
 * requete. Et la garantie que le champ protege — qu'un poste deverrouille ou un
 * CSRF reussi donne une session et non le compte — ne protege rien dans cet
 * etat : le mot de passe d'un compte en changement force a ete POSE par le
 * proprietaire ou l'operateur, il est connu d'un tiers par construction.
 *
 * Le chemin volontaire l'exige, et le serveur aussi : la derogation est
 * conditionnee a `doit_changer_mot_de_passe` cote serveur
 * (`ChangementMotDePasseSerializer`), pas seulement ici. Un client qui omet le
 * champ hors changement force recoit un 400.
 *
 * Historique, parce que la decision a ete revisitee et qu'un lecteur doit voir
 * une decision tranchee et non une hesitation : le champ a ete ajoute au
 * chemin force au point de controle du plan 03-12 le 2026-09-16, puis retire de
 * ce seul chemin au point de controle du plan 03-13 le 2026-09-17.
 * `03-UI-SPEC.md` 9.4 decrit desormais les deux chemins.
 */
export function MotDePasse() {
  const navigate = useNavigate();
  const { utilisateur, adopterLamorcage } = useAuth();

  /** Le chemin force. Le drapeau vient du serveur, jamais de la route. */
  const force = utilisateur?.doit_changer_mot_de_passe === true;

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
        body: force
          ? { nouveau_mot_de_passe: nouveau }
          : { mot_de_passe_actuel: actuel, nouveau_mot_de_passe: nouveau },
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
          {force ? "Choisissez votre mot de passe" : "Changer mon mot de passe"}
        </h1>
        <p className="mt-4 text-sm text-muted-foreground">
          {force
            ? "Ce mot de passe vous a été communiqué par le propriétaire. Choisissez-en un que vous êtes seul à connaître."
            : "Choisissez un nouveau mot de passe. Saisissez d'abord celui que vous utilisez aujourd'hui."}
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
          {force ? null : (
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
          )}
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

        {/* L'issue, sur le chemin volontaire SEULEMENT — et c'est toute la
            difference entre les deux. Cette page est hors du shell : sans ce
            lien, quelqu'un qui a ouvert le menu par erreur n'a plus de
            navigation du tout. « Retour » et non « Annuler » : le lexique
            reserve « Annuler » a l'annulation d'une modification enregistree
            (`03-UI-SPEC.md` 7.10 et 9.3). */}
        {force ? null : (
          <p className="mt-4 text-center text-sm">
            <Link className="underline underline-offset-4" to="/">
              Retour
            </Link>
          </p>
        )}
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

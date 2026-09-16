import { useEffect, useRef, useState, type FormEvent } from "react";

import { Eye, EyeOff } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { assurerJetonCsrf, clientApi } from "@/api/client";
import { ROUTE_CONNEXION, lireCorpsDerreur } from "@/api/requetes";
import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MESSAGE_SERVICE_INDISPONIBLE } from "@/etats/messages";

/**
 * Surface A — `/connexion` (`03-UI-SPEC.md` section 6).
 *
 * **La seule page non authentifiee du produit, et elle le restera.**
 *
 * Elle ne porte AUCUNE marque de client, definitivement. Il y a une seule
 * adresse de connexion pour toute la flotte (CLAUDE.md #11), donc avant
 * authentification le serveur ignore quel opticien tape : il ne peut lui servir
 * ni son logo, ni ses couleurs, ni son enseigne. Le critere BRAND-01 de la
 * phase 9 est satisfaisable pour chaque route authentifiee et PAS pour
 * celle-ci ; la marque du client s'applique des la premiere peinture
 * authentifiee, et pas avant.
 *
 * **Ne pas ajouter une etape « qui etes-vous ? » par e-mail pour contourner
 * cela** (menace T-03-81). Elle doublerait le flux ET enumererait les comptes
 * d'une affaire a l'autre : taper une adresse et voir apparaitre le logo d'une
 * enseigne confirme que cette adresse existe chez ce client.
 */

/**
 * La phrase unique de l'echec. **Une seule, pour tous les motifs** : adresse
 * inconnue, mot de passe faux, compte desactive.
 *
 * Le motif qu'on oublie est le troisieme. Un gerant desactive ne doit pas
 * l'apprendre de l'ecran de connexion — c'est son proprietaire qui le lui dit
 * (`03-UI-SPEC.md` 6, menace T-03-80). Le serveur renvoie deja un corps unique
 * (plan 03-08) ; cet ecran n'affiche de toute facon JAMAIS le `detail` recu sur
 * un echec de connexion, donc un corps distinctif apparu plus tard ne
 * deviendrait pas un oracle d'enumeration a l'ecran.
 */
const ECHEC_IDENTIFIANTS = "Identifiant ou mot de passe incorrect.";

const TROP_DE_TENTATIVES = "Trop de tentatives. Réessayez dans une minute.";

const LIGNE_DAIDE = "Mot de passe oublié ? Contactez le propriétaire de votre magasin.";

/** Statuts lus, jamais montres. */
const ECHEC_DIDENTIFIANTS = 400;
const LIMITE_DE_DEBIT = 429;

type EtatDeLecran = "repos" | "attente";

export function Connexion() {
  const navigate = useNavigate();
  const emplacement = useLocation();
  const { adopterLamorcage } = useAuth();

  /**
   * Le chemin tente, depose soit par `RequireAuth` (visite anonyme d'une route
   * protegee), soit par le gestionnaire global de 401 (session morte en cours
   * de route). Il voyage dans l'etat de navigation, jamais dans un stockage
   * persistant.
   */
  const etatDeNavigation = (emplacement.state ?? {}) as {
    de?: string;
    message?: string;
  };

  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [motDePasseVisible, setMotDePasseVisible] = useState(false);
  const [etat, setEtat] = useState<EtatDeLecran>("repos");
  const [erreur, setErreur] = useState<string | null>(etatDeNavigation.message ?? null);
  const [secondesRestantes, setSecondesRestantes] = useState<number | null>(null);

  const champMotDePasse = useRef<HTMLInputElement>(null);

  /**
   * Le cookie CSRF, pose AVANT le premier POST.
   *
   * Un echec ici se presente comme l'etat reseau. C'est la difference entre un
   * message vrai et un message cruel : sans cookie, le POST de connexion
   * repondrait 403 et l'ecran accuserait d'identifiants faux quelqu'un qui a
   * tape les bons.
   */
  useEffect(() => {
    let vivant = true;
    assurerJetonCsrf().catch(() => {
      if (vivant) {
        setErreur(MESSAGE_SERVICE_INDISPONIBLE);
      }
    });
    return () => {
      vivant = false;
    };
  }, []);

  /** Le compte a rebours de la fenetre de limitation, dans la ligne d'aide. */
  useEffect(() => {
    if (secondesRestantes === null) {
      return;
    }
    if (secondesRestantes <= 0) {
      setSecondesRestantes(null);
      return;
    }
    const minuterie = setTimeout(() => {
      setSecondesRestantes((restant) => (restant === null ? null : restant - 1));
    }, 1000);
    return () => clearTimeout(minuterie);
  }, [secondesRestantes]);

  function echouer(message: string) {
    setErreur(message);
    setMotDePasse("");
    // Le focus revient dans le champ a corriger, et l'e-mail reste en place.
    champMotDePasse.current?.focus();
  }

  async function soumettre(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    if (etat === "attente" || secondesRestantes !== null) {
      return;
    }
    setEtat("attente");
    setErreur(null);
    try {
      await assurerJetonCsrf();
      // `error` est le corps DEJA analyse du cote non-2xx. Ne pas relire
      // `response` : openapi-fetch a consomme le flux, donc `response.json()`
      // et meme `response.clone()` levent apres coup.
      const { data, error, response } = await clientApi.POST(ROUTE_CONNEXION, {
        body: { email, mot_de_passe: motDePasse },
      });

      if (response.status === ECHEC_DIDENTIFIANTS) {
        echouer(ECHEC_IDENTIFIANTS);
        return;
      }
      if (response.status === LIMITE_DE_DEBIT) {
        const { reessayer_dans: delai } = lireCorpsDerreur(error);
        setSecondesRestantes(delai ?? 60);
        echouer(TROP_DE_TENTATIVES);
        return;
      }
      if (!response.ok || data === undefined) {
        echouer(MESSAGE_SERVICE_INDISPONIBLE);
        return;
      }

      adopterLamorcage(data);
      // Le drapeau est traite ici ET dans `RequireAuth` : ici pour eviter un
      // aller-retour visible, la-bas pour que la route reste inevitable.
      const destination = data.utilisateur.doit_changer_mot_de_passe
        ? "/mot-de-passe"
        : (etatDeNavigation.de ?? "/");
      navigate(destination, { replace: true });
    } catch {
      echouer(MESSAGE_SERVICE_INDISPONIBLE);
    } finally {
      setEtat("repos");
    }
  }

  const enAttente = etat === "attente";
  const boutonInactif =
    enAttente || secondesRestantes !== null || email === "" || motDePasse === "";

  return (
    <main
      data-testid="scene-connexion"
      // Decale du haut, JAMAIS centre verticalement : un centrage vertical fait
      // sauter la carte au moment ou le message d'erreur apparait, c'est-a-dire
      // exactement quand l'oeil est dessus (`03-UI-SPEC.md` section 6).
      style={{ paddingTop: "64px" }}
      className="flex min-h-screen w-full flex-col items-center bg-[#FAFAFA] px-6"
    >
      <div className="w-full max-w-[400px] rounded-lg border border-border bg-white p-6">
        <h1 className="text-2xl font-semibold leading-tight">Optique</h1>

        {erreur !== null ? (
          <div
            role="alert"
            className="mt-4 rounded-md border border-destructive px-3 py-2 text-sm text-destructive"
          >
            {erreur}
          </div>
        ) : null}

        <form
          data-testid="formulaire-connexion"
          className="mt-4 flex flex-col gap-4"
          onSubmit={soumettre}
          noValidate
        >
          <div className="flex flex-col gap-2">
            <Label className="text-xs font-semibold" htmlFor="email">
              Adresse e-mail
            </Label>
            <Input
              id="email"
              name="email"
              type="email"
              inputMode="email"
              autoComplete="username"
              autoFocus
              value={email}
              aria-invalid={erreur === ECHEC_IDENTIFIANTS}
              aria-describedby="ligne-daide"
              onChange={(evenement) => setEmail(evenement.target.value)}
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label className="text-xs font-semibold" htmlFor="mot-de-passe">
              Mot de passe
            </Label>
            <div className="relative">
              <Input
                id="mot-de-passe"
                name="mot-de-passe"
                ref={champMotDePasse}
                type={motDePasseVisible ? "text" : "password"}
                autoComplete="current-password"
                value={motDePasse}
                aria-invalid={erreur === ECHEC_IDENTIFIANTS}
                aria-describedby="ligne-daide"
                className="pr-11"
                onChange={(evenement) => setMotDePasse(evenement.target.value)}
              />
              <button
                type="button"
                // La cible tactile fait 44px (WCAG 2.2 AA 2.5.8) sans que la
                // boite visible grossisse : l'agrandissement passe par un
                // pseudo-element, voir `.cible-44` dans index.css.
                className="cible-44 absolute right-1 top-1/2 flex size-9 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground"
                aria-pressed={motDePasseVisible}
                aria-label={
                  motDePasseVisible ? "Masquer le mot de passe" : "Afficher le mot de passe"
                }
                onClick={() => setMotDePasseVisible((visible) => !visible)}
              >
                {motDePasseVisible ? (
                  <EyeOff aria-hidden className="size-4" />
                ) : (
                  <Eye aria-hidden className="size-4" />
                )}
              </button>
            </div>
          </div>

          <Button type="submit" className="w-full font-semibold" disabled={boutonInactif}>
            {/* Le libelle NE CHANGE PAS en attente : l'indicateur s'ajoute a
                cote. Un bouton qui devient « Connexion... » se redimensionne
                sous le curseur. */}
            <span>Se connecter</span>
            {enAttente ? (
              <span
                aria-hidden
                className="ml-2 inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
              />
            ) : null}
          </Button>
        </form>

        <p
          id="ligne-daide"
          data-testid="ligne-daide"
          className="mt-4 text-sm text-muted-foreground"
        >
          {secondesRestantes !== null
            ? `Réessayez dans ${secondesRestantes} secondes.`
            : LIGNE_DAIDE}
        </p>
      </div>
    </main>
  );
}

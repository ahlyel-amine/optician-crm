import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { useQuery } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";

import {
  ServiceInjoignable,
  clientApi,
  declarerSessionFermee,
  declarerSessionOuverte,
  estNonAuthentifie,
  surSessionExpiree,
} from "@/api/client";
import {
  ROUTE_DECONNEXION,
  ROUTE_MOI,
  type Amorcage,
  type Catalogue,
  type ClientDeLaffaire,
  type Magasin,
  type Utilisateur,
} from "@/api/requetes";
import { MESSAGE_SESSION_EXPIREE } from "@/etats/messages";

/**
 * L'amorcage de la SPA : UNE requete, et tout ce que l'application sait d'elle-meme.
 *
 * `GET /api/auth/moi/` rend le compte, l'affaire, les droits, les magasins
 * ACCORDES et le catalogue. Une requete plutot que cinq, parce que c'est la
 * toute premiere chose qui se passe apres la connexion et que chaque
 * aller-retour supplementaire est une fraction de seconde d'ecran vide au
 * comptoir (plan 03-08).
 *
 * Ce que ce contexte n'est PAS : une autorisation. `permissions` sert a decider
 * ce qu'on PROPOSE — une entree de navigation, un bouton. Ce qu'un utilisateur
 * a le droit de LIRE est decide par la restriction de queryset et la projection
 * cote serveur, et par rien d'autre (`03-UI-SPEC.md` 5.3 et 8.3).
 *
 * Ce qui n'est PAS stocke ici : aucun jeton. La session est un cookie
 * `HttpOnly`, donc illisible par le JS, donc invisible a un XSS (menace
 * T-03-83). `localStorage` ne porte qu'une preference d'affichage de magasin,
 * revalidee a chaque amorcage et refiltree par le serveur de toute facon.
 */

export type EtatAuth = "amorcage" | "anonyme" | "connecte" | "indisponible";

/** `null` signifie « Tous les magasins » (`03-UI-SPEC.md` 5.4). */
export type SelectionMagasin = string | null;

export type ValeurContexteAuth = {
  etat: EtatAuth;
  utilisateur: Utilisateur | null;
  affaire: ClientDeLaffaire | null;
  permissions: string[];
  magasins: Magasin[];
  catalogue: Catalogue | null;
  magasinSelectionne: SelectionMagasin;
  choisirMagasin: (code: SelectionMagasin) => void;
  /** Appele par `/connexion` : la reponse de connexion EST un amorcage. */
  adopterLamorcage: (amorcage: Amorcage) => void;
  seDeconnecter: () => Promise<void>;
  reessayerLamorcage: () => void;
};

const VALEUR_INITIALE: ValeurContexteAuth = {
  etat: "amorcage",
  utilisateur: null,
  affaire: null,
  permissions: [],
  magasins: [],
  catalogue: null,
  magasinSelectionne: null,
  choisirMagasin: () => {},
  adopterLamorcage: () => {},
  seDeconnecter: async () => {},
  reessayerLamorcage: () => {},
};

export const ContexteAuth = createContext<ValeurContexteAuth>(VALEUR_INITIALE);

export function useAuth(): ValeurContexteAuth {
  return useContext(ContexteAuth);
}

/** `TOUS` n'est pas un code de magasin : aucun magasin ne peut s'appeler ainsi. */
const TOUS_LES_MAGASINS = "TOUS";

function cleDuMagasin(identifiant: number): string {
  return `optique.magasin.${identifiant}`;
}

/**
 * Relit la preference de magasin ET LA REVALIDE contre les magasins accordes.
 *
 * Le cas qui compte est celui du magasin RETIRE : le proprietaire enleve
 * Californie a Karim, et le navigateur de Karim porte encore « Californie » en
 * preference. Le repli est **silencieux** — pas de message, pas d'alerte —
 * parce qu'il n'y a pas d'incident a signaler : le serveur ne lui aurait rien
 * servi de Californie de toute facon. Lui afficher une erreur reviendrait a lui
 * annoncer une decision qui appartient a son proprietaire.
 *
 * Le defaut de PREMIERE connexion, lui, suit `03-UI-SPEC.md` 5.4 : « Tous les
 * magasins » pour le proprietaire qui en detient plusieurs, le premier accorde
 * pour tout le monde d'autre.
 */
export function magasinInitial(amorcage: Amorcage): SelectionMagasin {
  const accordes = amorcage.magasins ?? [];
  if (accordes.length === 0) {
    return null;
  }
  const premier = accordes[0].code;
  let memorise: string | null = null;
  try {
    memorise = localStorage.getItem(cleDuMagasin(amorcage.utilisateur.id));
  } catch {
    memorise = null;
  }

  if (memorise === TOUS_LES_MAGASINS) {
    return accordes.length > 1 ? null : premier;
  }
  if (memorise !== null) {
    const toujoursAccorde = accordes.some((magasin) => magasin.code === memorise);
    return toujoursAccorde ? memorise : premier;
  }
  if (amorcage.utilisateur.est_proprietaire && accordes.length > 1) {
    return null;
  }
  return premier;
}

type ResultatAmorcage =
  | { etat: "anonyme" }
  | { etat: "connecte"; amorcage: Amorcage };

async function amorcer(): Promise<ResultatAmorcage> {
  const { data, response } = await clientApi.GET(ROUTE_MOI);
  if (estNonAuthentifie(response)) {
    // Le cas NORMAL d'une premiere visite. Ce n'est pas une session expiree :
    // il n'y a jamais eu de session. Voir `sessionOuverte` dans client.ts.
    return { etat: "anonyme" };
  }
  if (!response.ok || data === undefined) {
    throw new ServiceInjoignable();
  }
  declarerSessionOuverte();
  return { etat: "connecte", amorcage: data };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const emplacement = useLocation();

  const requete = useQuery({
    queryKey: ["amorcage"],
    queryFn: amorcer,
    retry: false,
    staleTime: Number.POSITIVE_INFINITY,
    refetchOnMount: false,
    refetchOnReconnect: false,
  });

  /**
   * L'amorcage courant. Il a deux sources — la requete d'amorcage au
   * chargement, et la reponse de `POST /api/auth/connexion/`, qui rend
   * exactement la meme charge utile. La seconde evite une requete de plus juste
   * apres la connexion, ce qui est precisement le clignotement que le critere
   * de reussite interdit.
   */
  const [adopte, setAdopte] = useState<Amorcage | null>(null);
  const [selection, setSelection] = useState<SelectionMagasin>(null);

  const amorcage: Amorcage | null =
    adopte ?? (requete.data?.etat === "connecte" ? requete.data.amorcage : null);

  /** L'identite du dernier amorcage applique, pour ne revalider qu'au changement. */
  const derniereEmpreinte = useRef<Amorcage | null>(null);
  useEffect(() => {
    if (amorcage === null || derniereEmpreinte.current === amorcage) {
      return;
    }
    derniereEmpreinte.current = amorcage;
    setSelection(magasinInitial(amorcage));
  }, [amorcage]);

  const choisirMagasin = useCallback(
    (code: SelectionMagasin) => {
      setSelection(code);
      if (amorcage === null) {
        return;
      }
      try {
        localStorage.setItem(cleDuMagasin(amorcage.utilisateur.id), code ?? TOUS_LES_MAGASINS);
      } catch {
        // Un navigateur en navigation privee peut refuser d'ecrire. Une
        // preference d'affichage perdue n'est pas une panne : on continue.
      }
    },
    [amorcage],
  );

  const adopterLamorcage = useCallback((nouveau: Amorcage) => {
    declarerSessionOuverte();
    setAdopte(nouveau);
  }, []);

  const oublier = useCallback(() => {
    declarerSessionFermee();
    setAdopte(null);
    derniereEmpreinte.current = null;
    setSelection(null);
    requete.refetch();
  }, [requete]);

  const seDeconnecter = useCallback(async () => {
    await clientApi.POST(ROUTE_DECONNEXION);
    declarerSessionFermee();
    setAdopte(null);
    derniereEmpreinte.current = null;
    setSelection(null);
    navigate("/connexion", { replace: true });
  }, [navigate]);

  /**
   * Le 401 global (`03-UI-SPEC.md` 8.6), ecrit UNE fois pour neuf phases.
   *
   * Vider le contexte, **memoriser le chemin tente**, router vers `/connexion`
   * avec le message d'expiration, et y revenir apres reconnexion. Le chemin
   * voyage dans l'etat de navigation plutot que dans le stockage local — qui
   * ne porte qu'une preference de magasin et rien d'autre : le chemin
   * appartient a cette tentative-ci, pas au navigateur, et un chemin oublie
   * dans un stockage persistant renverrait un jour quelqu'un sur un ecran qu'il
   * n'a pas demande.
   */
  const cheminCourant = `${emplacement.pathname}${emplacement.search}`;
  const cheminRef = useRef(cheminCourant);
  cheminRef.current = cheminCourant;

  useEffect(() => {
    return surSessionExpiree(() => {
      setAdopte(null);
      derniereEmpreinte.current = null;
      setSelection(null);
      navigate("/connexion", {
        replace: true,
        state: { de: cheminRef.current, message: MESSAGE_SESSION_EXPIREE },
      });
    });
  }, [navigate]);

  const etat: EtatAuth = useMemo(() => {
    if (amorcage !== null) {
      return "connecte";
    }
    if (requete.isPending) {
      return "amorcage";
    }
    if (requete.isError) {
      return "indisponible";
    }
    return "anonyme";
  }, [amorcage, requete.isError, requete.isPending]);

  const valeur = useMemo<ValeurContexteAuth>(
    () => ({
      etat,
      utilisateur: amorcage?.utilisateur ?? null,
      affaire: amorcage?.client ?? null,
      // Le catalogue et les droits sont exposes TELS QUE RECUS. Le serveur les
      // a deja intersectes avec ce que l'appelant detient (plan 03-09) : il n'y
      // a rien a filtrer ici, et refiltrer signifierait tenir cote client une
      // liste de codes caches — exactement ce que 7.7 refuse.
      permissions: amorcage?.permissions ?? [],
      magasins: amorcage?.magasins ?? [],
      catalogue: amorcage?.catalogue ?? null,
      magasinSelectionne: selection,
      choisirMagasin,
      adopterLamorcage,
      seDeconnecter,
      reessayerLamorcage: oublier,
    }),
    [
      adopterLamorcage,
      amorcage,
      choisirMagasin,
      etat,
      oublier,
      seDeconnecter,
      selection,
    ],
  );

  return <ContexteAuth.Provider value={valeur}>{children}</ContexteAuth.Provider>;
}

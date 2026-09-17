import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AuthProvider, useAuth } from "@/auth/AuthProvider";
import { RequireAuth } from "@/auth/RequireAuth";
import { RequireDroit } from "@/auth/RequireDroit";
import { Toaster } from "@/components/ui/sonner";
import { BanniereDeLien } from "@/etats/BanniereDeLien";
import { PageIntrouvable } from "@/etats/PageIntrouvable";
import { AppShell } from "@/layout/AppShell";
import { NAV, type EntreeNav } from "@/layout/nav";
import { Connexion } from "@/pages/Connexion";
import { MotDePasse } from "@/pages/MotDePasse";
import { DetailCompte } from "@/pages/comptes/DetailCompte";
import { ListeComptes } from "@/pages/comptes/ListeComptes";

/**
 * Les routes de la phase 3.
 *
 * Deux surfaces sont HORS du shell, et c'est structurel : `/connexion` est la
 * seule page anonyme du produit, et `/mot-de-passe` doit s'afficher sans
 * navigation pour rester non refermable.
 *
 * La banniere de coupure du lien est montee au-dessus de tout, y compris de la
 * connexion : un opticien dont la ligne est tombee doit l'apprendre avant de
 * taper son mot de passe, pas apres.
 *
 * Tout le reste vit dans l'app shell (plan 03-13), qui a remplace le
 * `ContenuProtege` provisoire du plan 03-12 sans toucher a aucune garde.
 */
export default function App() {
  return (
    <AuthProvider>
      <BanniereDeLien />
      {/*
        L'hote des toasts, monte une fois pour toute l'application.

        Il ne sert QU'A L'ANNULATION (03-UI-SPEC.md 7.8) : un echec de
        chargement est une carte en ligne, un echec d'ecriture est un message
        sur la ligne concernee. Un toast qui disparait au bout de dix secondes
        ne doit jamais etre le seul endroit ou une panne a ete annoncee.

        Deux reglages, et aucun n'est cosmetique. `containerAriaLabel` parce que
        le defaut du bloc est « Notifications », en anglais, dans un produit qui
        n'en affiche pas un mot. `hotkey={[]}` parce que le bloc pose un
        raccourci global Alt+T qui annonce sa propre existence dans le nom de la
        region — 03-UI-SPEC.md 5.7 interdit tout accord en v1, Ctrl+K etant
        l'unique exception. C'est le meme defaut que le Ctrl+B du bloc `sidebar`
        retire au plan 03-13, arrive par le meme chemin.
      */}
      <Toaster
        position="bottom-right"
        containerAriaLabel="Annulations"
        hotkey={[]}
        // Le libelle du bouton de fermeture est une option du conteneur, pas
        // de chaque toast. Son defaut est « Close toast ».
        toastOptions={{ closeButtonAriaLabel: "Fermer" }}
      />
      <Routes>
        <Route path="/connexion" element={<Connexion />} />
        <Route
          path="/mot-de-passe"
          element={
            <SessionRequise>
              <MotDePasse />
            </SessionRequise>
          }
        />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <AppShell>
                <ContenuDuShell />
              </AppShell>
            </RequireAuth>
          }
        />
      </Routes>
    </AuthProvider>
  );
}

/**
 * `/mot-de-passe` exige une session mais PAS `RequireAuth` : celui-ci y
 * redirige justement quand le drapeau est leve, et l'y appliquer produirait une
 * boucle de redirection.
 */
function SessionRequise({ children }: { children: React.ReactNode }) {
  const { etat } = useAuth();
  if (etat === "amorcage") {
    return null;
  }
  if (etat !== "connecte") {
    return <Navigate to="/connexion" replace />;
  }
  return <>{children}</>;
}

/**
 * Les routes du shell, derivees du MEME tableau que la navigation.
 *
 * Deriver les routes de `NAV` plutot que de les retaper est ce qui garantit
 * qu'une entree et sa destination ne peuvent pas diverger : il n'y a qu'une
 * liste de routes de premier niveau dans le produit.
 *
 * **La garde de droit au niveau de la route commence au plan 03-14**, et pas
 * avant. Le plan 03-13 l'avait differee en le disant : une route qui ne rend
 * qu'un titre n'a rien a divulguer, donc le retrait de l'entree de navigation
 * (contrat de 5.3) suffisait. `/parametres/comptes` est le premier ecran de la
 * phase a porter de la donnee reelle, donc le premier a meriter le 403 pleine
 * page — celui qui NOMME le droit manquant plutot que de laisser un ecran vide.
 *
 * Le controle, lui, reste ce qu'il a toujours ete : la restriction de queryset
 * et la classe de permission cote serveur. `RequireDroit` epargne un
 * aller-retour et une page blanche, rien de plus.
 */
function ContenuDuShell() {
  return (
    <Routes>
      {NAV.map((entree) => (
        <Route
          key={entree.route}
          path={entree.route === "/" ? "" : `${entree.route.slice(1)}/*`}
          element={
            SOUS_ROUTES[entree.route]?.(entree) ?? <PageEnAttente entree={entree} />
          }
        />
      ))}
      <Route path="*" element={<PageIntrouvable />} />
    </Routes>
  );
}

/**
 * Le contenu d'une entree de navigation dont le module EST construit, clee par
 * la route de `NAV`.
 *
 * Deriver de `NAV` reste la regle — il n'existe toujours qu'une liste de routes
 * de premier niveau — et cette table ne fait que dire, pour une entree donnee,
 * ce qui s'affiche a la place du titre d'attente. Une entree absente d'ici est
 * une entree dont le module n'est pas encore ecrit, ce que `disponible` dit
 * deja par ailleurs.
 */
const SOUS_ROUTES: Record<string, (entree: EntreeNav) => React.ReactNode> = {
  "/parametres": (entree) => <Parametres entree={entree} />,
};

/**
 * La navigation de second niveau des parametres (03-UI-SPEC.md 5.3).
 *
 * Dans la zone de contenu, **jamais en accordeon de barre laterale** : la
 * phase 9 (Personnalisation) et la phase 12 (Abonnement) y ajoutent leurs
 * ecrans sans que la barre laterale grossisse.
 *
 * L'index reste `PageEnAttente` : l'accueil des parametres n'a pas encore de
 * contenu propre, et le dire par le meme titre d'attente que les sept autres
 * modules vaut mieux que d'inventer une page vide qui aurait l'air finie.
 */
function Parametres({ entree }: { entree: EntreeNav }) {
  return (
    <Routes>
      <Route
        path="comptes"
        element={
          <RequireDroit code="compte.gerer" proprietaireToujours>
            <ListeComptes />
          </RequireDroit>
        }
      />
      <Route
        path="comptes/:id"
        element={
          <RequireDroit code="compte.gerer" proprietaireToujours>
            <DetailCompte />
          </RequireDroit>
        }
      />
      <Route path="*" element={<PageEnAttente entree={entree} />} />
    </Routes>
  );
}

/**
 * Le contenu d'une route dont le module n'est pas encore construit.
 *
 * Un `h1` reel, parce que c'est lui que le shell focalise et annonce a chaque
 * changement de route, et `data-testid="destination"` qui expose le chemin
 * atteint — c'est ce qui rend verifiable qu'une connexion revient bien au
 * chemin memorise.
 */
function PageEnAttente({ entree }: { entree: EntreeNav }) {
  const emplacement = useLocation();
  return (
    <>
      <h1 className="text-2xl font-semibold">{entree.libelle}</h1>
      <p data-testid="destination" className="mt-2 text-sm text-muted-foreground">
        {emplacement.pathname}
      </p>
    </>
  );
}

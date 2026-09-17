import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AuthProvider, useAuth } from "@/auth/AuthProvider";
import { RequireAuth } from "@/auth/RequireAuth";
import { BanniereDeLien } from "@/etats/BanniereDeLien";
import { PageIntrouvable } from "@/etats/PageIntrouvable";
import { AppShell } from "@/layout/AppShell";
import { NAV, type EntreeNav } from "@/layout/nav";
import { Connexion } from "@/pages/Connexion";
import { MotDePasse } from "@/pages/MotDePasse";

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
 * **Aucune garde de droit au niveau de la route en phase 3, et c'est
 * delibere.** L'entree de navigation est retiree, ce qui est le contrat de
 * 5.3 ; le 403 pleine page de `PageInterdite` appartient aux ecrans qui
 * portent reellement de la donnee, a partir du plan 03-14. Une route de phase 3
 * ne rend qu'un titre — il n'y a rien a divulguer, et le controle reste, comme
 * toujours, la restriction de queryset et la projection cote serveur.
 */
function ContenuDuShell() {
  return (
    <Routes>
      {NAV.map((entree) => (
        <Route
          key={entree.route}
          path={entree.route === "/" ? "" : `${entree.route.slice(1)}/*`}
          element={<PageEnAttente entree={entree} />}
        />
      ))}
      <Route path="*" element={<PageIntrouvable />} />
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

import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AuthProvider, useAuth } from "@/auth/AuthProvider";
import { RequireAuth } from "@/auth/RequireAuth";
import { BanniereDeLien } from "@/etats/BanniereDeLien";
import { PageIntrouvable } from "@/etats/PageIntrouvable";
import { Connexion } from "@/pages/Connexion";
import { MotDePasse } from "@/pages/MotDePasse";

/**
 * Les routes de la phase 3.
 *
 * Deux surfaces sont HORS de la mise en page protegee, et c'est structurel :
 * `/connexion` est la seule page anonyme du produit, et `/mot-de-passe` doit
 * s'afficher sans navigation de shell pour rester non refermable.
 *
 * La banniere de coupure du lien est montee au-dessus de tout, y compris de la
 * connexion : un opticien dont la ligne est tombee doit l'apprendre avant de
 * taper son mot de passe, pas apres.
 *
 * Le shell reel — barre superieure, selecteur de magasin, navigation filtree
 * par les droits, recherche — arrive au plan 03-13 et remplacera
 * `ContenuProtege` sans toucher a ces gardes.
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
              <ContenuProtege />
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
 * Le contenu protege provisoire du plan 03-12.
 *
 * `data-testid="destination"` expose le chemin atteint : c'est ce qui rend
 * verifiable, sans shell, qu'une connexion revient bien au chemin memorise.
 */
function ContenuProtege() {
  const emplacement = useLocation();
  if (emplacement.pathname === "/introuvable") {
    return <PageIntrouvable />;
  }
  return (
    <main className="p-6">
      <h1 className="text-2xl font-semibold">Optique</h1>
      <p data-testid="destination" className="mt-2 text-sm text-muted-foreground">
        {emplacement.pathname}
      </p>
    </main>
  );
}

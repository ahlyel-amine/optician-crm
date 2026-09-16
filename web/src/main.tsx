import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { clientDeRequetes } from "./api/requetes";
import "./index.css";

/**
 * L'ordre des fournisseurs est contractuel.
 *
 *   BrowserRouter > QueryClientProvider > App
 *
 * Le routeur est a l'exterieur parce que le contexte d'authentification, monte
 * a l'interieur d'`App` au plan 03-12 tache 2, navigue : sur un 401 il route
 * vers `/connexion` en memorisant le chemin tente. Un fournisseur qui appelle
 * `useNavigate()` doit etre DANS le routeur, sinon l'appel leve au premier 401 —
 * c'est-a-dire au pire moment, celui ou l'ecran devrait se rattraper.
 */
const racine = document.getElementById("root");
if (!racine) {
  throw new Error("L'element racine #root est introuvable dans index.html.");
}

createRoot(racine).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={clientDeRequetes}>
        <App />
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
);

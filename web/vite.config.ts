import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// La decision la plus lourde du shell : **meme origine des le premier jour**.
//
// Le serveur de developpement proxifie `/api` et `/static` vers Django, donc le
// navigateur ne voit **qu'une seule origine** (localhost:5173). Consequences,
// toutes voulues :
//
//   - pas de CORS, donc pas de `django-cors-headers` (liste "Do NOT add" de
//     `03-RESEARCH.md` : ne pas l'ajouter cote backend non plus) ;
//   - pas de `CORS_ALLOW_CREDENTIALS`, pas de requete de prevol ;
//   - `SameSite=Lax` suffit : pas besoin de `SameSite=None`, qui affaiblirait
//     materiellement l'argument de session de toute la phase (menace T-03-11) ;
//   - le cookie de session et le jeton CSRF se comportent en developpement
//     exactement comme en production, ou la SPA construite est servie depuis la
//     meme origine que `/api/`.
//
// Chaque panne classique du type « le cookie marche en local et pas en prod »
// est concue hors d'existence. Ne pas remplacer ce proxy par une origine
// distincte plus un en-tete CORS.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8010",
      "/static": "http://127.0.0.1:8010",
    },
  },
});

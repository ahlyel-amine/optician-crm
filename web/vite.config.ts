import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
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
//
// **Les deux proxies sont declares en forme objet, avec `changeOrigin: false`
// explicite. Ne pas revenir a la forme chaine.** La forme chaine
// (`"/api": "http://127.0.0.1:8010"`) a l'air identique et met
// `changeOrigin: true` par defaut : le proxy reecrit alors l'en-tete `Host` en
// `127.0.0.1:8010`.
//
// C'est fatal ici, parce que `CsrfViewMiddleware` reconstruit l'origine attendue
// depuis `request.get_host()`. Un `Host` reecrit fait diverger cette origine
// calculee de l'`Origin` que le navigateur a envoye, et **toute ecriture est
// refusee en 403** :
// `Origin checking failed - http://localhost:5173 does not match any trusted
// origins.` La connexion elle-meme cesse de fonctionner.
//
// Preserver le `Host` du navigateur est ce qui fait calculer a Django exactement
// l'origine que le navigateur a envoyee. C'est aussi ce que fait un vrai reverse
// proxy en production : `changeOrigin: false` aligne donc le developpement sur la
// production au lieu de l'en ecarter.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8010", changeOrigin: false },
      "/static": { target: "http://127.0.0.1:8010", changeOrigin: false },
    },
  },
});

import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

// Configuration de test separee de vite.config.ts : les tests n'ont besoin ni du
// plugin React ni du proxy meme-origine, et une configuration de test qui
// demarre un proxy est une source de lenteur et de surprise.
//
// `npm test` execute `vitest run`, JAMAIS `vitest` seul. Un `npm test` en mode
// surveillance ne sort jamais, et une tache d'execution qui ne sort jamais
// bloque la phase (menace T-03-14). Le mode surveillance reste disponible sous
// `npm run test:watch`.
export default defineConfig({
  resolve: {
    alias: {
      // Aligne sur "paths" de tsconfig.json et sur l'alias "@/*" de
      // components.json. Les trois doivent rester d'accord.
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    // jsdom : le test des colonnes rend du DOM. Voir tests/colonnes.test.ts.
    environment: "jsdom",
    globals: true,
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
  },
  server: {
    fs: {
      // tests/fixtures/formats_mad.json vit a la RACINE DU DEPOT, un cran
      // au-dessus de web/, parce que pytest et vitest la lisent tous les deux.
      // Sans cette autorisation, vite refuse de servir un fichier hors racine.
      allow: [".."],
    },
  },
});

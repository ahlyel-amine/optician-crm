/**
 * Ce que jsdom n'implemente pas, et dont le shell depend.
 *
 * `window.matchMedia` n'existe pas dans jsdom. Le bloc `sidebar` s'en sert pour
 * basculer en tiroir hors-canevas, et `AppShell` pour le rail automatique de
 * 1024 a 1279px — donc SANS ce fichier, toute suite qui monte l'application
 * leve, y compris celles du plan 03-12 qui passaient hier.
 *
 * Le double repond **faux** a toute requete : les tests se jouent sur un grand
 * ecran. Le responsive est une affaire de mise en page reelle, que jsdom ne
 * simule pas utilement et qui appartient a la verification humaine.
 *
 * Il vit ici plutot que recopie dans chaque fichier de test pour que la
 * prochaine suite de composant n'ait pas a redecouvrir le probleme.
 */

if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  window.matchMedia = (requete: string): MediaQueryList =>
    ({
      matches: false,
      media: requete,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
}

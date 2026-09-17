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

/**
 * Ce que Radix et cmdk attendent d'un navigateur, et que jsdom n'a pas.
 *
 * Le selecteur de magasin est un `popover` plus un `command`, et la palette de
 * recherche un `command` en dialogue — les deux blocs officiels de
 * `03-UI-SPEC.md` section 1. Leur positionnement passe par floating-ui, qui
 * observe le redimensionnement, et leur navigation clavier fait defiler
 * l'element actif dans la vue. Rien de tout cela n'existe dans jsdom.
 *
 * Ces doubles ne simulent RIEN : ils rendent seulement le montage possible. Ce
 * qui est verifie ensuite, ce sont les options offertes et le comportement au
 * clavier, jamais une position a l'ecran.
 */
if (typeof globalThis.ResizeObserver !== "function") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

if (typeof Element !== "undefined") {
  Element.prototype.scrollIntoView ??= () => {};
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.setPointerCapture ??= () => {};
  Element.prototype.releasePointerCapture ??= () => {};
}

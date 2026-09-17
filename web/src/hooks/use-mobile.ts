import * as React from "react"

/**
 * FICHIER VENDU, MODIFIE — point de controle du plan 03-13, 2026-09-17.
 *
 * Le bloc officiel coupe a 768. `03-UI-SPEC.md` 5.6 place la bascule ailleurs :
 *
 *   >= 1280px      barre laterale depliee, densite pleine
 *   1024 - 1279px  rail d'icones automatique (pilote par useRailAutomatique)
 *   768 - 1023px   TIROIR HORS-CANEVAS, la recherche se replie en icone
 *   < 768px        fonctionnel, non optimise
 *
 * A 768, la bande 768-1023px restait sur le rail au lieu du tiroir : une
 * navigation de 56px et un tableau dense sur une fenetre de 900px, ce que la
 * specification voulait precisement eviter. La borne est donc 1024.
 *
 * Une reinstallation du bloc (`shadcn add sidebar`) ramenerait 768. Ce qui le
 * rattrape est le test nomme « le tiroir hors-canevas s'ouvre a 1024px » de
 * web/tests/shell.test.tsx.
 */
const MOBILE_BREAKPOINT = 1024

export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined)

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    }
    mql.addEventListener("change", onChange)
    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    return () => mql.removeEventListener("change", onChange)
  }, [])

  return !!isMobile
}

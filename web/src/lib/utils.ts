// Un seul `cn` dans le projet.
//
// Les blocs vendorises sous src/components/ui importent `cn` depuis le paquet
// `cn` du registre shadcn. Ce module le reexporte sous l'alias `@/lib/utils`
// declare dans components.json, pour que le code applicatif ait un chemin
// d'import unique. Ne PAS reimplementer ici une fusion clsx + tailwind-merge :
// deux implementations de fusion de classes qui divergent est un bogue de style
// invisible a la relecture.
export { cn } from "cn";

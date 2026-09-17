import { useSyncExternalStore } from "react";

/**
 * L'etat du lien reseau, pour un produit EN LIGNE UNIQUEMENT ET DEFINITIVEMENT.
 *
 * CLAUDE.md #1 : pas de mode hors ligne, pas de stockage local des donnees, pas
 * de couche de synchronisation. La consequence d'interface est ecrite en
 * `03-UI-SPEC.md` 8.6 et elle est inhabituelle : quand le lien tombe, on ne
 * degrade pas en silence, on le DIT, fort et tout de suite, et on desactive les
 * controles d'ecriture. Les concurrents de `research/FEATURES.md` annoncent du
 * hors ligne ; le remplacement honnete n'est pas de faire semblant, c'est de ne
 * jamais laisser croire qu'un enregistrement est parti alors qu'il n'est parti
 * nulle part.
 *
 * Pourquoi un magasin d'etat maison plutot que `navigator.onLine` seul :
 * `navigator.onLine` ne sait que si une interface reseau existe. Un Wi-Fi de
 * boutique branche sur une box sans ligne le laisse a `true`. La verite
 * operationnelle est ce que fait la derniere requete — d'ou les deux signaux
 * ci-dessous, poses par l'intergiciel du client d'API.
 */

let enLigne = typeof navigator === "undefined" ? true : navigator.onLine !== false;

const abonnes = new Set<() => void>();

function diffuser(): void {
  for (const abonne of [...abonnes]) {
    abonne();
  }
}

/**
 * La derniere requete a ECHOUE au transport : le lien est tombe.
 *
 * « Echoue », pas « n'a pas abouti » — la nuance est celle qui a fait clignoter
 * la banniere a chaque navigation. Une requete ABANDONNEE n'aboutit pas non
 * plus, et elle ne doit jamais arriver ici : c'est nous qui l'avons annulee,
 * elle ne mesure rien. Le tri se fait dans `estUneRequeteAvortee()`
 * (`src/api/client.ts`), le seul appelant de cette fonction avec l'evenement
 * `offline` du navigateur.
 */
export function signalerPanneDeLien(): void {
  if (!enLigne) {
    return;
  }
  enLigne = false;
  diffuser();
}

/** Une requete vient d'aboutir : le lien est revenu. */
export function signalerLienRetabli(): void {
  if (enLigne) {
    return;
  }
  enLigne = true;
  diffuser();
}

export function lienDisponible(): boolean {
  return enLigne;
}

function sAbonner(abonne: () => void): () => void {
  abonnes.add(abonne);
  if (typeof window !== "undefined") {
    window.addEventListener("online", signalerLienRetabli);
    window.addEventListener("offline", signalerPanneDeLien);
  }
  return () => {
    abonnes.delete(abonne);
    if (typeof window !== "undefined") {
      window.removeEventListener("online", signalerLienRetabli);
      window.removeEventListener("offline", signalerPanneDeLien);
    }
  };
}

/**
 * `true` tant que le lien repond. Tout controle d'ecriture de toutes les phases
 * suivantes se desactive sur `false`.
 */
export function useLienDisponible(): boolean {
  return useSyncExternalStore(sAbonner, lienDisponible, () => true);
}

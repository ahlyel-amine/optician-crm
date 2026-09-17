import {
  Bell,
  LayoutDashboard,
  Package,
  Receipt,
  Settings,
  Truck,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";

/**
 * LE CONTRAT DE NAVIGATION. Neuf phases s'y accrochent sans redesign.
 *
 * 03-UI-SPEC.md 5.3. Huit entrees de premier niveau, un emplacement reserve,
 * **plafond dur a neuf**. Un dixieme module entre dans une section existante ou
 * en remplace une ; il n'obtient pas une dixieme ligne. Ce n'est pas une
 * preference de mise en page : au-dela, la barre laterale devient une liste
 * qu'on parcourt au lieu d'une carte qu'on connait, et chaque phase suivante
 * aurait un argument pour ajouter la sienne.
 *
 * **Rien ne rend une entree depuis l'exterieur de ce tableau.** C'est la seule
 * formulation que la discipline ne peut pas eroder : un composant qui ecrirait
 * `<NavLink to="/stock">` ailleurs echapperait au filtrage par droits, et le
 * test de comptage de `tests/shell.test.tsx` le dirait.
 *
 * **Les ordonnances n'ont pas d'entree de premier niveau.** Elles vivent dans
 * la fiche d'un client, en onglet. Les hisser serait l'erreur d'ere desktop que
 * font les concurrents : une ordonnance detachee de son client n'est pas ce
 * qu'un opticien cherche.
 *
 * RAPPEL, et il vaut pour tout ce module : masquer une entree est de
 * l'experience utilisateur. La restriction de queryset et la projection cote
 * serveur sont le controle.
 */

/**
 * La portee d'une route, declaree ici et nulle part ailleurs (03-UI-SPEC.md 5.4).
 *
 * `magasin` : l'ecran n'a pas de sens sans un magasin — la caisse, l'inventaire,
 * les mouvements de stock. Quand la portee active est « Tous les magasins », la
 * zone de contenu DEMANDE lequel. Choisir silencieusement le premier et
 * afficher son solde de caisse est le « nombre faux sans erreur » que la couche
 * ORM refuse deja ; l'interface le refuse aussi.
 *
 * `multi` : l'ecran se lit sur un magasin comme sur l'ensemble de l'affaire.
 */
export type PorteeRoute = "magasin" | "multi";

export type EntreeNav = {
  /**
   * Le code de droit qui conditionne l'entree, ou `null` quand tout utilisateur
   * authentifie y a acces.
   */
  code: string | null;
  libelle: string;
  route: string;
  icone: LucideIcon;
  /**
   * `false` tant que le module n'est pas construit. L'entree est alors absente
   * d'une construction de production et presente en developpement derriere
   * `VITE_NAV_COMPLET=1`.
   */
  disponible: boolean;
  portee: PorteeRoute;
  /**
   * La phrase d'explication de l'invite de choix, pour une route a portee
   * magasin. Elle nomme la raison, jamais le mecanisme.
   */
  explicationPortee?: string;
  /**
   * Le proprietaire garde l'entree meme si le serveur ne lui liste pas le code.
   * Vrai pour `Parametres` seul : c'est la porte par laquelle il reprend la
   * main, et se la fermer serait irrattrapable depuis l'interface.
   */
  proprietaireToujours?: true;
};

/** Le plafond dur. Neuf, emplacement reserve compris. */
export const PLAFOND_NAV = 9;

export const NAV: readonly EntreeNav[] = [
  {
    code: null,
    libelle: "Tableau de bord",
    route: "/",
    icone: LayoutDashboard,
    // Aucun droit : tout utilisateur authentifie a un tableau de bord. Le widget
    // de CA global, lui, est conditionne par `dashboard.voir_ca_global` en
    // phase 10 — le droit porte sur le CHIFFRE, pas sur la page.
    disponible: true,
    portee: "multi",
  },
  {
    code: "client.voir",
    libelle: "Clients",
    route: "/clients",
    icone: Users,
    disponible: false,
    portee: "multi",
  },
  {
    code: "stock.voir",
    libelle: "Stock",
    route: "/stock",
    icone: Package,
    disponible: false,
    portee: "multi",
  },
  {
    code: "vente.voir",
    libelle: "Ventes",
    route: "/ventes",
    icone: Receipt,
    disponible: false,
    portee: "multi",
  },
  {
    code: "caisse.voir",
    libelle: "Caisse",
    route: "/caisse",
    icone: Wallet,
    disponible: false,
    portee: "magasin",
    explicationPortee: "La caisse est propre à chaque magasin.",
  },
  {
    code: "fournisseur.voir",
    libelle: "Achats",
    route: "/achats",
    icone: Truck,
    disponible: false,
    portee: "multi",
  },
  {
    code: "rappel.voir",
    libelle: "Rappels",
    route: "/rappels",
    icone: Bell,
    disponible: false,
    portee: "multi",
  },
  {
    code: "compte.gerer",
    libelle: "Paramètres",
    route: "/parametres",
    icone: Settings,
    disponible: true,
    portee: "multi",
    proprietaireToujours: true,
  },
];

/**
 * Le drapeau de densite pleine.
 *
 * `VITE_NAV_COMPLET=1` rend les entrees non construites, **en developpement
 * seulement**. Deux conditions et non une : une variable oubliee dans un
 * environnement de construction ne doit pas livrer a un opticien sept entrees
 * qui ne menent nulle part.
 */
export function navCompletActif(): boolean {
  return import.meta.env.DEV === true && import.meta.env.VITE_NAV_COMPLET === "1";
}

export type ContexteNav = {
  /** Les droits tels que le serveur les a rendus, jamais refiltres ici. */
  permissions: readonly string[];
  proprietaire: boolean;
  complet?: boolean;
};

/**
 * Les entrees a rendre. **La seule source d'une entree de navigation.**
 *
 * Une entree dont le code n'est pas detenu est RETIREE, pas desactivee. Pas
 * d'infobulle, pas de cadenas, pas de gris. L'application d'un gerant est
 * genuinement plus petite, et c'est un avantage produit : le marche est
 * encombre d'outils d'ere desktop, et le differenciateur n'est pas plus
 * d'ecrans (`research/FEATURES.md`).
 */
export function entreesVisibles(contexte: ContexteNav): EntreeNav[] {
  const complet = contexte.complet ?? navCompletActif();
  return NAV.filter((entree) => {
    if (!entree.disponible && !complet) {
      return false;
    }
    if (entree.code === null) {
      return true;
    }
    if (contexte.proprietaire && entree.proprietaireToujours) {
      return true;
    }
    return contexte.permissions.includes(entree.code);
  });
}

/**
 * L'entree qui porte le chemin courant, ou `undefined`.
 *
 * Le prefixe suffit : `/parametres/comptes` appartient a `Parametres`, et c'est
 * ce qui fait que la navigation de second niveau reste dans la zone de contenu
 * plutot qu'en accordeon de barre laterale (03-UI-SPEC.md 5.3).
 */
export function entreePourChemin(chemin: string): EntreeNav | undefined {
  if (chemin === "/") {
    return NAV[0];
  }
  return NAV.find(
    (entree) =>
      entree.route !== "/" && (chemin === entree.route || chemin.startsWith(`${entree.route}/`)),
  );
}

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { Search } from "lucide-react";
import { useNavigate } from "react-router-dom";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

/**
 * La recherche — le mode d'acces principal (03-UI-SPEC.md 5.5).
 *
 * La lecture de code-barres a ete deliberement exclue du produit, ce qui fait
 * de la recherche la facon dont le comptoir trouve les choses. Deux contrats
 * sont poses ICI pour que les phases 4 et 5 ne touchent plus au shell :
 *
 *   1. **La normalisation est cote serveur.** La SPA envoie la requete BRUTE.
 *      Pas de mise en minuscules, pas de retrait d'accent, pas de filtrage
 *      local, pas de longueur minimale au-dela de deux. Une saisie arabe ou une
 *      reference de douchette alteree en chemin ne revient pas (T-03-92), et
 *      l'insensibilite aux accents comme aux variantes de translitteration est
 *      une affaire d'index SQL, pas de JavaScript (CLIENT-10).
 *   2. **Le raccourci de reference exacte.** Quand le serveur marque un
 *      resultat `correspondance_exacte`, `Entree` y navigue directement et la
 *      liste n'est jamais rendue. Une douchette clavier tape une reference puis
 *      envoie `Entree` ; cela doit atterrir sur l'article (STOCK-07, phase 5).
 *
 * **La phase 3 n'a rien a chercher.** Le champ ne se rend que lorsqu'un
 * fournisseur est enregistre — mais l'emplacement garde ses 480px, pour que la
 * barre superieure ne se reflue pas le jour ou la phase 4 arrive.
 */

/** Ce qu'un fournisseur rend. `correspondance_exacte` vient du SERVEUR. */
export type ResultatDeRecherche = {
  id: string;
  groupe: string;
  libelle: string;
  route: string;
  correspondance_exacte?: boolean;
};

export type FournisseurDeRecherche = {
  nom: string;
  chercher: (requete: string, signal: AbortSignal) => Promise<ResultatDeRecherche[]>;
};

/**
 * Les touches par lesquelles un utilisateur CHOISIT une ligne.
 *
 * Elles sont laissees passer jusqu'a `cmdk`, qui deplace le surlignage ; ce
 * fichier ne fait que retenir que le choix a eu lieu.
 */
const TOUCHES_DE_SELECTION: ReadonlySet<string> = new Set([
  "ArrowDown",
  "ArrowUp",
  "Home",
  "End",
]);

export const LARGEUR_EMPLACEMENT = "w-[480px]";
export const DELAI_ANTI_REBOND = 200;
export const MAX_PAR_GROUPE = 5;

const fournisseurs = new Set<FournisseurDeRecherche>();
const abonnes = new Set<() => void>();

function prevenir(): void {
  for (const abonne of abonnes) {
    abonne();
  }
}

/**
 * Enregistre un fournisseur. Rend la fonction qui le retire.
 *
 * La phase 4 enregistrera `Clients`, la phase 5 `Articles`, la phase 6
 * `Factures` — et aucune ne touchera a ce fichier.
 */
export function enregistrerFournisseurDeRecherche(
  fournisseur: FournisseurDeRecherche,
): () => void {
  fournisseurs.add(fournisseur);
  prevenir();
  return () => {
    fournisseurs.delete(fournisseur);
    prevenir();
  };
}

function sabonner(rappel: () => void): () => void {
  abonnes.add(rappel);
  return () => {
    abonnes.delete(rappel);
  };
}

function lireLeNombre(): number {
  return fournisseurs.size;
}

export type GroupeDeResultats = { nom: string; resultats: ResultatDeRecherche[] };

/** Groupe par type, dans l'ordre d'apparition, cinq par groupe au plus. */
export function grouperResultats(resultats: readonly ResultatDeRecherche[]): GroupeDeResultats[] {
  const groupes: GroupeDeResultats[] = [];
  for (const resultat of resultats) {
    let groupe = groupes.find((candidat) => candidat.nom === resultat.groupe);
    if (groupe === undefined) {
      groupe = { nom: resultat.groupe, resultats: [] };
      groupes.push(groupe);
    }
    if (groupe.resultats.length < MAX_PAR_GROUPE) {
      groupe.resultats.push(resultat);
    }
  }
  return groupes;
}

/** Le resultat que le SERVEUR a marque exact, s'il y en a un. */
export function resultatExact(
  resultats: readonly ResultatDeRecherche[],
): ResultatDeRecherche | undefined {
  return resultats.find((resultat) => resultat.correspondance_exacte === true);
}

/** Vrai quand le focus est dans un champ : `/` doit alors s'y ecrire. */
function saisieEnCours(cible: EventTarget | null): boolean {
  if (!(cible instanceof HTMLElement)) {
    return false;
  }
  return (
    cible.isContentEditable ||
    cible instanceof HTMLInputElement ||
    cible instanceof HTMLTextAreaElement ||
    cible instanceof HTMLSelectElement
  );
}

export function Recherche() {
  const nombreDeFournisseurs = useSyncExternalStore(sabonner, lireLeNombre, lireLeNombre);
  const naviguer = useNavigate();

  const [ouverte, setOuverte] = useState(false);
  const [requete, setRequete] = useState("");
  const [resultats, setResultats] = useState<ResultatDeRecherche[]>([]);
  /**
   * LA SELECTION A-T-ELLE ETE VOULUE ? Trouvaille du plan 04-07.
   *
   * Le contrat « rien n'auto-navigue sur un nom » (04-UI-SPEC.md 18.4) etait
   * cense tenir par `correspondance_exacte`, que le serveur ne pose que sur un
   * numero complet. **Il ne tenait pas.** `cmdk` surligne le PREMIER element
   * des qu'une liste arrive et lie `Entree` a l'element surligne : taper un
   * nom puis envoyer `Entree` ouvrait le premier candidat, quelle que soit la
   * prudence du fournisseur. Aucun fournisseur ne pouvait l'empecher, donc
   * l'abstraction de la phase 3 etait incomplete et le correctif est ici.
   *
   * Pourquoi cela compte : aucun seuil ne separe la verite de l'erreur dans ce
   * classement — `mhamed` vers `mohammed alaoui` vaut 0,333 quand `fatima`
   * vers `fatiha bennani` vaut 0,571, mesures du plan 04-03, donc le classement
   * est INVERSE. Le premier candidat est un reflexe, pas une reponse, et avec
   * des ordonnances sur la fiche l'ouvrir est une divulgation de donnee de
   * sante.
   *
   * La regle posee ici : `Entree` active ce que l'utilisateur a DELIBEREMENT
   * choisi — a la fleche, ou au clic — ou ce que le SERVEUR a marque exact.
   * Jamais un surlignage que personne n'a demande. La navigation au clavier
   * reste entiere : c'est une fleche de plus, pas un chemin ferme.
   */
  const [selectionDeliberee, setSelectionDeliberee] = useState(false);
  const declencheur = useRef<HTMLElement | null>(null);

  const disponible = nombreDeFournisseurs > 0;

  const ouvrir = useCallback(() => {
    // D'ou venait le focus, pour le lui rendre a la fermeture.
    declencheur.current = document.activeElement as HTMLElement | null;
    setOuverte(true);
  }, []);

  const fermer = useCallback((ouvert: boolean) => {
    setOuverte(ouvert);
    if (!ouvert) {
      setRequete("");
      setResultats([]);
      declencheur.current?.focus();
    }
  }, []);

  /** `/` ou `Ctrl+K`, partout sauf pendant une saisie (03-UI-SPEC.md 5.7). */
  useEffect(() => {
    if (!disponible) {
      return;
    }
    const surTouche = (evenement: KeyboardEvent) => {
      const combinaison = evenement.key === "k" && (evenement.ctrlKey || evenement.metaKey);
      const barre = evenement.key === "/" && !saisieEnCours(evenement.target);
      if (combinaison || barre) {
        evenement.preventDefault();
        ouvrir();
      }
    };
    window.addEventListener("keydown", surTouche);
    return () => window.removeEventListener("keydown", surTouche);
  }, [disponible, ouvrir]);

  /**
   * L'anti-rebond de 200ms, et l'interrogation des fournisseurs.
   *
   * La requete part TELLE QUELLE. Le seul filtre applique cote client est une
   * longueur minimale de deux caracteres, que la specification autorise
   * explicitement — et rien d'autre.
   */
  useEffect(() => {
    if (!ouverte || requete.length < 2) {
      setResultats([]);
      return;
    }
    const controleur = new AbortController();
    const minuteur = setTimeout(() => {
      const actifs = Array.from(fournisseurs);
      void Promise.all(
        actifs.map(async (fournisseur) => {
          try {
            return await fournisseur.chercher(requete, controleur.signal);
          } catch {
            // Un fournisseur qui echoue ne doit pas vider la palette des
            // autres : une recherche partielle vaut mieux qu'un ecran vide.
            return [];
          }
        }),
      ).then((paquets) => {
        if (!controleur.signal.aborted) {
          setResultats(paquets.flat());
        }
      });
    }, DELAI_ANTI_REBOND);

    return () => {
      controleur.abort();
      clearTimeout(minuteur);
    };
  }, [ouverte, requete]);

  // Une nouvelle frappe annule le choix : sans cela, une fleche pressee sur une
  // requete rendrait `Entree` active sur la SUIVANTE, dont les resultats sont
  // d'autres personnes.
  useEffect(() => {
    setSelectionDeliberee(false);
  }, [requete, ouverte]);

  const exact = resultatExact(resultats);
  const groupes = grouperResultats(resultats);

  const aller = useCallback(
    (route: string) => {
      fermer(false);
      naviguer(route);
    },
    [fermer, naviguer],
  );

  return (
    <div
      data-testid="emplacement-recherche"
      className={`${LARGEUR_EMPLACEMENT} hidden shrink-0 lg:block`}
    >
      {disponible ? (
        <>
          <button
            type="button"
            onClick={ouvrir}
            // Nom accessible exact : le rappel « Ctrl+K » est une aide
            // visuelle, pas une partie du nom du controle.
            aria-label="Recherche"
            className="flex h-8 w-full items-center gap-2 rounded-md border border-border px-3 text-left text-sm text-[#52525B]"
          >
            <Search aria-hidden="true" className="size-4" />
            <span>Recherche</span>
            <kbd className="ml-auto text-xs">Ctrl+K</kbd>
          </button>

          {/*
            `Dialog` plus `Command`, et non le bloc `CommandDialog` : celui-ci
            ne transmet pas `shouldFilter` a `Command`, donc cmdk filtrerait la
            liste lui-meme — en minuscules et sans accents. Ce serait exactement
            la normalisation cliente interdite ici (T-03-92) : le serveur a deja
            decide ce qui correspond, et une saisie arabe ne survit pas a un
            second filtrage.
          */}
          <Dialog open={ouverte} onOpenChange={fermer}>
            <DialogContent className="overflow-hidden p-0">
              <DialogHeader className="sr-only">
                <DialogTitle>Recherche</DialogTitle>
                <DialogDescription>
                  Chercher un client, un article, un document
                </DialogDescription>
              </DialogHeader>
              <Command
                shouldFilter={false}
                /*
                  `cmdk` surligne le premier element tout seul. Tant que
                  personne n'a choisi, ce surlignage est retire VISUELLEMENT
                  aussi, pas seulement desarme : une ligne qui a l'air
                  selectionnee et qu'`Entree` ignore serait une interface qui
                  ment. Revendication de CLASSE — jsdom ne calcule aucun CSS,
                  donc le test assert la classe, et l'oeil humain la couleur
                  (04-VALIDATION.md).
                */
                className={
                  selectionDeliberee ? undefined : "[&_[data-selected=true]]:bg-transparent"
                }
              >
                <div className="border-b border-border p-2">
                  <Input
                    autoFocus
                    placeholder="Recherche"
                    value={requete}
                    onChange={(evenement) => setRequete(evenement.target.value)}
                    onKeyDown={(evenement) => {
                      if (TOUCHES_DE_SELECTION.has(evenement.key)) {
                        // La fleche EST le choix. A partir d'ici `Entree`
                        // active ce que l'utilisateur regarde.
                        setSelectionDeliberee(true);
                        return;
                      }
                      if (evenement.key !== "Enter") {
                        return;
                      }
                      if (exact !== undefined) {
                        // Le raccourci de reference exacte, decide par le
                        // SERVEUR et jamais pose sur un nom : une douchette
                        // clavier tape une reference et envoie `Entree`.
                        evenement.preventDefault();
                        evenement.stopPropagation();
                        aller(exact.route);
                        return;
                      }
                      if (!selectionDeliberee) {
                        // L'evenement est ARRETE, pas seulement annule :
                        // `cmdk` ecoute sur la racine et ne consulte pas
                        // `defaultPrevented`.
                        evenement.preventDefault();
                        evenement.stopPropagation();
                      }
                    }}
                  />
                </div>
                {/*
                  Le raccourci de reference exacte : quand le serveur a marque un
                  resultat, la liste n'est PAS rendue. C'est ce dont une douchette
                  clavier a besoin.
                */}
                {exact === undefined ? (
                  <CommandList>
                    {requete.length >= 2 && groupes.length === 0 ? (
                      <CommandEmpty>{`Aucun résultat pour « ${requete} »`}</CommandEmpty>
                    ) : null}
                    {groupes.map((groupe) => (
                      <CommandGroup key={groupe.nom} heading={groupe.nom}>
                        {groupe.resultats.map((resultat) => (
                          <CommandItem
                            key={resultat.id}
                            value={resultat.id}
                            onSelect={() => aller(resultat.route)}
                          >
                            {resultat.libelle}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    ))}
                  </CommandList>
                ) : null}
              </Command>
            </DialogContent>
          </Dialog>
        </>
      ) : null}
    </div>
  );
}

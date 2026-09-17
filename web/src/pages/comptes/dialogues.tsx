import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * `03-UI-SPEC.md` 7.9 et 7.10 — les confirmations, et la regle des trois mots.
 *
 * **Le bouton secondaire d'un dialogue est `Retour`**, et le mot que le
 * francais emploie aussi pour *defaire une action enregistree* est banni de ce
 * fichier — il est reserve a l'action d'un toast d'annulation, et il ne se lit
 * donc que dans `LigneDroit.tsx`. Le francais confond les deux sens, et neuf
 * phases de dialogues valent bien une regle ecrite une fois. Un utilisateur qui
 * croit fermer un dialogue et defait un octroi — ou l'inverse — est la menace
 * T-03-102, et elle se ferme par le vocabulaire. Un `grep` de ce mot dans ce
 * fichier doit rester vide, ce qui est la formulation que la discipline ne peut
 * pas eroder.
 *
 * **Aucune confirmation tapee** dans aucune des trois confirmations : chacune
 * de ces actions se rattrape — on reactive un compte, on rend un magasin, on
 * communique le nouveau mot de passe — et faire recopier un nom pour une
 * action rattrapable entraine a recopier sans lire.
 *
 * **La seconde phrase enonce ce qui survit.** Un dialogue qui ne nomme que ce
 * qu'il detruit laisse l'utilisateur deviner ce qu'il advient de son historique
 * de ventes, et deviner est un appel telephonique.
 */

const RETOUR = "Retour";

export type ProprietesDialogueDesactivation = {
  ouvert: boolean;
  nomComplet: string;
  surRetour: () => void;
  surConfirmation: () => void;
};

export function DialogueDesactivation({
  ouvert,
  nomComplet,
  surRetour,
  surConfirmation,
}: ProprietesDialogueDesactivation) {
  return (
    <AlertDialog open={ouvert} onOpenChange={(etat) => (etat ? undefined : surRetour())}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            Désactiver le compte de {nomComplet} ?
          </AlertDialogTitle>
          <AlertDialogDescription>
            Il sera déconnecté dès sa prochaine action. Ses ventes et ses saisies restent
            enregistrées à son nom. Vous pourrez réactiver ce compte plus tard.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={surRetour}>{RETOUR}</AlertDialogCancel>
          <AlertDialogAction
            onClick={surConfirmation}
            className="bg-destructive text-white hover:bg-destructive/90"
          >
            Désactiver le compte
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/**
 * Le nombre de reglages par magasin emportes par un retrait.
 *
 * Ce sont les lignes **personnalisees** qui visent ce magasin : une ligne
 * uniforme perd sa portee sur ce magasin comme les autres, mais elle n'avait
 * pas de reglage propre a annoncer.
 */
export function phraseDesReglages(nombre: number): string {
  if (nombre === 0) {
    return "";
  }
  return nombre === 1
    ? " Le réglage par magasin d'un droit pour ce magasin sera retiré."
    : ` Les réglages par magasin de ${String(nombre)} droits pour ce magasin seront supprimés.`;
}

export type ProprietesDialogueRetraitMagasin = {
  ouvert: boolean;
  prenom: string;
  nomDuMagasin: string;
  reglagesPersonnalises: number;
  surRetour: () => void;
  surConfirmation: () => void;
};

export function DialogueRetraitMagasin({
  ouvert,
  prenom,
  nomDuMagasin,
  reglagesPersonnalises,
  surRetour,
  surConfirmation,
}: ProprietesDialogueRetraitMagasin) {
  return (
    <AlertDialog open={ouvert} onOpenChange={(etat) => (etat ? undefined : surRetour())}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            Retirer l'accès au magasin {nomDuMagasin} ?
          </AlertDialogTitle>
          <AlertDialogDescription>
            {`${prenom} ne verra plus les clients, le stock, les ventes ni la caisse de ${nomDuMagasin}.${phraseDesReglages(reglagesPersonnalises)}`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={surRetour}>{RETOUR}</AlertDialogCancel>
          <AlertDialogAction
            onClick={surConfirmation}
            className="bg-destructive text-white hover:bg-destructive/90"
          >
            Retirer l'accès
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export type ProprietesDialogueReinitialisation = {
  ouvert: boolean;
  prenom: string;
  surRetour: () => void;
  surConfirmation: () => void;
};

/**
 * La confirmation que 7.9 ne nomme pas, et qui manquait.
 *
 * 7.9 enumere deux dialogues destructifs ; celui-ci est le troisieme, ajoute
 * apres coup. `DialogueMotDePasse`, plus bas, **n'est pas** une confirmation :
 * il AFFICHE un mot de passe deja genere, c'est-a-dire un degat deja fait.
 * Jusqu'ici la reinitialisation partait du `onClick` du bouton de la fiche.
 *
 * C'etait la seule action de l'ecran a la fois **immediate et sans retour** :
 * les vingt et une bascules ont leur toast defaisable (7.8), la desactivation
 * et le retrait de magasin ont leur confirmation. Un clic par megarde coupait
 * l'acces d'un gerant en plein service, et l'ancien mot de passe n'existait
 * plus.
 *
 * (Le mot de l'action d'un toast reste banni de ce fichier — voir le bloc de
 * tete. Cette confirmation est la troisieme, et la regle ne s'assouplit pas
 * parce qu'un commentaire aurait ete plus court avec.)
 *
 * **Pas de `bg-destructive` sur l'action**, contrairement aux deux dialogues
 * de 7.9 : l'action REMPLACE une identification, elle ne detruit aucune
 * donnee et ne ferme aucune porte — le nouveau mot de passe est delivre dans
 * le meme geste. Peindre en rouge une operation de routine du support use le
 * rouge des deux qui en ont besoin.
 */
export function DialogueReinitialisation({
  ouvert,
  prenom,
  surRetour,
  surConfirmation,
}: ProprietesDialogueReinitialisation) {
  return (
    <AlertDialog open={ouvert} onOpenChange={(etat) => (etat ? undefined : surRetour())}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            Réinitialiser le mot de passe de {prenom} ?
          </AlertDialogTitle>
          <AlertDialogDescription>
            Son mot de passe actuel cessera immédiatement de fonctionner. Vous devrez lui
            communiquer le nouveau.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={surRetour}>{RETOUR}</AlertDialogCancel>
          <AlertDialogAction onClick={surConfirmation}>Réinitialiser</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export type ProprietesDialogueMotDePasse = {
  ouvert: boolean;
  secret: string | null;
  surFermeture: () => void;
};

/**
 * `03-UI-SPEC.md` 7.3 A — le mot de passe reinitialise, montre **une seule fois**.
 *
 * Il n'existe aucun chemin par courriel dans la pile (plan 03-08), donc le
 * proprietaire le transmet de vive voix, et l'ecran doit le dire plutot que de
 * le laisser decouvrir. L'echappatoire d'un panneau est `Fermer` (7.10), pas
 * `Retour` — il n'y a rien a annuler, l'action est deja faite.
 */
export function DialogueMotDePasse({
  ouvert,
  secret,
  surFermeture,
}: ProprietesDialogueMotDePasse) {
  return (
    <Dialog open={ouvert} onOpenChange={(etat) => (etat ? undefined : surFermeture())}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Nouveau mot de passe provisoire</DialogTitle>
          <DialogDescription>
            Notez-le maintenant : il ne sera plus affiché.
          </DialogDescription>
        </DialogHeader>
        <p className="rounded-md border border-border bg-muted/40 p-3 font-mono text-sm">
          {secret}
        </p>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => void navigator.clipboard?.writeText(secret ?? "")}
          >
            Copier le mot de passe
          </Button>
          <Button type="button" onClick={surFermeture}>
            Fermer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

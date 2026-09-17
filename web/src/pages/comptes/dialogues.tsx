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
 * **Aucune confirmation tapee** dans aucun des deux : les deux actions sont
 * reversibles, et faire recopier un nom pour une action reversible entraine a
 * recopier sans lire.
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

export type ProprietesDialogueUniformisation = {
  ouvert: boolean;
  libelleDuDroit: string;
  prenom: string;
  nombreDeMagasins: number;
  surRetour: () => void;
  surConfirmation: () => void;
};

/**
 * `Uniformiser` remplace des reglages que le proprietaire a poses a la main.
 *
 * Il demande donc d'abord — et seulement quand les sous-interrupteurs divergent,
 * puisqu'une ligne deja uniforme n'a rien a remplacer.
 */
export function DialogueUniformisation({
  ouvert,
  libelleDuDroit,
  prenom,
  nombreDeMagasins,
  surRetour,
  surConfirmation,
}: ProprietesDialogueUniformisation) {
  return (
    <AlertDialog open={ouvert} onOpenChange={(etat) => (etat ? undefined : surRetour())}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            Appliquer le même droit à tous les magasins ?
          </AlertDialogTitle>
          <AlertDialogDescription>
            {`Les réglages par magasin de « ${libelleDuDroit} » seront remplacés. ${prenom} aura ce droit dans les ${String(nombreDeMagasins)} magasins.`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={surRetour}>{RETOUR}</AlertDialogCancel>
          <AlertDialogAction onClick={surConfirmation}>Uniformiser</AlertDialogAction>
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

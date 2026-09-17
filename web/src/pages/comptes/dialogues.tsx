import { useEffect, useId, useState } from "react";

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
 * **Aucune confirmation tapee** dans aucune des quatre confirmations : chacune
 * de ces actions se rattrape — on reactive un compte, on rend un magasin, on
 * communique le nouveau mot de passe, on decoche un magasin accorde par
 * erreur — et faire recopier un nom pour une action rattrapable entraine a
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

/**
 * Ce qui S'ETEND au magasin ajoute — les lignes accordees uniformement.
 *
 * Exportee et testable comme `phraseDesReglages`, et pour la meme raison : une
 * phrase chiffree fausse dans un dialogue qui distribue des permissions est un
 * octroi mal compris.
 *
 * Le cas `0` n'est pas une curiosite : un compte neuf demarre **sans aucun
 * droit** (CLAUDE.md #6, et le hors-perimetre du CONTEXT de la phase 03.1),
 * donc lui ajouter un second magasin est le cas frequent. « Les 0 droits
 * accordes dans tous ses magasins le seront aussi » serait a la fois faux de
 * grammaire et faux de sens.
 */
export function phraseDesDroitsEtendus(nombre: number, nomDuMagasin: string): string {
  if (nombre === 0) {
    return `Aucun droit n'est aujourd'hui accordé dans tous ses magasins : il n'y a rien à réappliquer à ${nomDuMagasin}.`;
  }
  return nombre === 1
    ? `Le droit accordé dans tous ses magasins le sera aussi à ${nomDuMagasin}.`
    : `Les ${String(nombre)} droits accordés dans tous ses magasins le seront aussi à ${nomDuMagasin}.`;
}

/**
 * Ce qui NE s'etend PAS — les lignes reglees magasin par magasin.
 *
 * **C'est la phrase que la menace T-03-62 rend obligatoire.** Sans elle,
 * « reappliquer les droits existants » se lit comme « tous les droits », et le
 * proprietaire attendrait du produit une elevation que le serveur refuse. La
 * garde effective est serveur (plan `03.1-02`, `etat != actif` → on passe) ;
 * celle-ci ferme l'ecart d'attente, qui est le seul que du code ne ferme pas.
 *
 * Vide quand il n'y a rien a excepter : une phrase qui chiffre zero exception
 * invente un doute qui n'existe pas.
 */
export function phraseDesDroitsNonEtendus(
  nombre: number,
  nomDuMagasin: string,
): string {
  if (nombre === 0) {
    return "";
  }
  return nombre === 1
    ? `Le droit réglé magasin par magasin ne le sera pas : ${nomDuMagasin} démarre sans lui.`
    : `Les ${String(nombre)} droits réglés magasin par magasin ne le seront pas : ${nomDuMagasin} démarre sans eux.`;
}

const AJOUT_REAPPLIQUER = "Réappliquer les droits existants";
const AJOUT_VIERGE = "Démarrer sans aucun droit";
const AJOUT_CONFIRMER = "Ajouter le magasin";

export type ProprietesDialogueAjoutMagasin = {
  ouvert: boolean;
  nomDuMagasin: string;
  prenom: string;
  /** Les lignes accordees uniformement — celles qui s'etendraient. */
  uniformes: number;
  /** Les lignes reglees magasin par magasin — celles qui ne s'etendront jamais. */
  personnalisees: number;
  surRetour: () => void;
  surConfirmation: (reappliquer: boolean) => void;
};

/**
 * `03-UI-SPEC.md` 7.3 B et 7.5 — **ajouter un magasin demande, au lieu
 * d'appliquer une regle jamais enoncee** (decision 2 de la phase 03.1).
 *
 * Jusqu'ici cocher une case etendait les lignes uniformes, laissait les lignes
 * personnalisees a l'arret, et racontait la regle **apres coup** par une note
 * de section. Le proprietaire veut etre interroge plutot que subir. La regle
 * d'hier n'est pas jetee pour autant : elle devient **l'option proposee par
 * defaut**, parce qu'etre interroge est plus sur que subir, ce qui n'est pas
 * une raison de changer la reponse.
 *
 * **Un groupe de boutons radio natifs, pas trois boutons dans le pied.** Trois
 * raisons : trois boutons de pied se lisent comme trois actions de poids egal
 * alors que l'une est le defaut ; une radio pre-selectionnee **est** la facon
 * d'offrir un defaut ; et l'etat choisi reste lisible avant la confirmation.
 * Radio natif plutot que composant : `radio-group` n'est pas installe, et
 * l'ecran a deja le precedent du `<select>` natif de `Statut` (7.3 A).
 *
 * **Pas de `bg-destructive`** : ajouter un magasin ne detruit rien. Peindre en
 * rouge une action d'ouverture use le rouge des deux qui en ont besoin.
 */
export function DialogueAjoutMagasin({
  ouvert,
  nomDuMagasin,
  prenom,
  uniformes,
  personnalisees,
  surRetour,
  surConfirmation,
}: ProprietesDialogueAjoutMagasin) {
  const groupe = useId();
  const decritReappliquer = useId();
  const decritVierge = useId();
  const [reappliquer, setReappliquer] = useState(true);

  /*
    Reinitialiser a l'ouverture, et pas seulement au montage.

    Le dialogue reste monte entre deux usages : sans cela, un `Retour` apres
    avoir choisi « vierge » puis une reouverture proposeraient le choix
    precedent au lieu du defaut — et le defaut est precisement ce que la
    decision 2 fait tenir.
  */
  useEffect(() => {
    if (ouvert) {
      setReappliquer(true);
    }
  }, [ouvert]);

  const nonEtendus = phraseDesDroitsNonEtendus(personnalisees, nomDuMagasin);

  return (
    <AlertDialog open={ouvert} onOpenChange={(etat) => (etat ? undefined : surRetour())}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            Ajouter le magasin {nomDuMagasin} au compte de {prenom} ?
          </AlertDialogTitle>
        </AlertDialogHeader>

        <fieldset className="space-y-3">
          <AlertDialogDescription asChild>
            <legend className="text-sm text-muted-foreground">
              Les droits de {prenom} dans {nomDuMagasin}
            </legend>
          </AlertDialogDescription>

          <label className="flex gap-3 text-sm">
            <input
              type="radio"
              name={groupe}
              className="mt-1 shrink-0"
              checked={reappliquer}
              aria-describedby={decritReappliquer}
              onChange={() => setReappliquer(true)}
            />
            <span>
              <span className="font-medium">{AJOUT_REAPPLIQUER}</span>
              <span id={decritReappliquer} className="mt-1 block text-muted-foreground">
                <span className="block">
                  {phraseDesDroitsEtendus(uniformes, nomDuMagasin)}
                </span>
                {nonEtendus === "" ? null : <span className="block">{nonEtendus}</span>}
              </span>
            </span>
          </label>

          <label className="flex gap-3 text-sm">
            <input
              type="radio"
              name={groupe}
              className="mt-1 shrink-0"
              checked={!reappliquer}
              aria-describedby={decritVierge}
              onChange={() => setReappliquer(false)}
            />
            <span>
              <span className="font-medium">{AJOUT_VIERGE}</span>
              <span id={decritVierge} className="mt-1 block text-muted-foreground">
                {`${prenom} verra ${nomDuMagasin}, mais n'y aura aucun droit. Vous les accorderez ensuite.`}
              </span>
            </span>
          </label>
        </fieldset>

        <AlertDialogFooter>
          <AlertDialogCancel onClick={surRetour}>{RETOUR}</AlertDialogCancel>
          <AlertDialogAction onClick={() => surConfirmation(reappliquer)}>
            {AJOUT_CONFIRMER}
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

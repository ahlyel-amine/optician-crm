import { useEffect, useId, useState } from "react";

import { useParams } from "react-router-dom";

import {
  $api,
  type CatalogueOffrable,
  type LigneDeDroit,
  type Magasin,
  type ResultatOctroi,
} from "@/api/requetes";
import { Button } from "@/components/ui/button";
import { CarteDechec } from "@/etats/CarteDechec";
import { Valeur } from "@/tableau/Valeur";

import { HistoriqueDroits } from "./HistoriqueDroits";
import { toastDannulation } from "./LigneDroit";
import { SectionDroits } from "./SectionDroits";
import { SectionMagasins } from "./SectionMagasins";
import { MODE_PAR_DEFAUT } from "./SelecteurDeMagasinDesDroits";
import {
  DialogueAjoutMagasin,
  DialogueDesactivation,
  DialogueMotDePasse,
  DialogueReinitialisation,
  DialogueRetraitMagasin,
} from "./dialogues";

/**
 * `03-UI-SPEC.md` 7.3 — la fiche d'un compte, 880px, quatre regions.
 *
 * **Identite, Magasins, Droits, Historique — dans cet ordre.** Il est porteur
 * et non esthetique : un droit sans magasin n'accorde rien, donc poser les
 * droits d'abord produit l'appel « je lui ai tout donne et il ne voit rien »,
 * qui est le plus cher des appels evitables.
 *
 * **Sauvegarde par interrupteur, immediate, aucun bouton Enregistrer** (7.8).
 * Vingt et un interrupteurs derriere un unique Enregistrer est un formulaire
 * qu'on abandonne a moitie rempli, et `JournalDroit` enregistre un acteur et un
 * horodatage par octroi — ce qui correspond exactement a une bascule.
 *
 * Les deux actions a large rayon — retirer un magasin, desactiver un compte —
 * gardent une confirmation (7.8) : la premiere change tous les droits d'un
 * coup, la seconde ferme la porte. Les vingt et un interrupteurs, eux, ont une
 * annulation : vingt et une confirmations est une fatigue de confirmation.
 */

const PHRASE_PROPRIETAIRE =
  "Propriétaire — accès complet à tous les magasins. Ces droits ne se modifient pas.";

/** Le prenom, pour la banniere et les dialogues. Le premier mot, sans plus. */
export function prenomDe(nomComplet: string): string {
  return nomComplet.trim().split(/\s+/)[0] ?? nomComplet;
}

/** L'etat des lignes, indexe par code — la forme dont l'ecran a besoin. */
function indexer(lignes: readonly LigneDeDroit[]): Record<string, LigneDeDroit> {
  return Object.fromEntries(lignes.map((ligne) => [ligne.code, ligne]));
}

/** Le nombre de lignes personnalisees — celles que 7.5 appelle « mixte ». */
function compterLesPersonnalisees(
  lignes: Record<string, LigneDeDroit>,
  magasinCode?: string,
): number {
  return Object.values(lignes).filter(
    (ligne) =>
      ligne.etat === "mixte" &&
      (magasinCode === undefined || ligne.magasins.includes(magasinCode)),
  ).length;
}

type FicheCompte = {
  id: number;
  nom_complet: string;
  email: string;
  est_proprietaire: boolean;
  actif: boolean;
  magasins: Magasin[];
  droits: LigneDeDroit[];
  magasins_accordes: string[];
};

/**
 * Les quatre confirmations de l'ecran, **une union et non quatre booleens**.
 *
 * Le motif a ete pose par la confirmation de reinitialisation : un booleen
 * d'etat par dialogue rend representable l'etat « deux dialogues ouverts »,
 * qui n'existe pas. L'union le rend impossible a ecrire.
 */
type Confirmation =
  | { quoi: "desactivation" }
  | { quoi: "ajout-magasin"; magasin: Magasin }
  | { quoi: "retrait-magasin"; magasin: Magasin }
  | { quoi: "reinitialisation" };

export function DetailCompte() {
  const { id = "" } = useParams();
  const identifiant = Number(id);
  const champStatut = useId();

  const fiche = $api.useQuery("get", "/api/comptes/{id}/", {
    params: { path: { id: identifiant } },
  });
  const catalogue = $api.useQuery("get", "/api/comptes/catalogue/");

  const bascule = $api.useMutation("post", "/api/comptes/{id}/droits/");
  const basculeMagasin = $api.useMutation("post", "/api/comptes/{id}/magasins/");
  const changementDeStatut = $api.useMutation("post", "/api/comptes/{id}/statut/");
  const reinitialisation = $api.useMutation("post", "/api/comptes/{id}/mot-de-passe/");

  /**
   * L'etat local des lignes et des magasins.
   *
   * Il existe parce que la sauvegarde est optimiste : l'interrupteur bouge
   * d'abord, la reponse le confirme ou le retour arriere le remet. Repartir de
   * la requete a chaque fois ferait clignoter l'ecran a chaque clic, ce que 7.8
   * refuse en refusant le bouton Enregistrer.
   */
  const [lignes, setLignes] = useState<Record<string, LigneDeDroit>>({});
  const [accordes, setAccordes] = useState<readonly string[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  const [noteDeSection, setNoteDeSection] = useState<string | undefined>(undefined);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [secret, setSecret] = useState<string | null>(null);
  /**
   * Le mode du selecteur de la section des droits. `null` === `Tous`.
   *
   * Il vit ICI, avec la fonction qui construit le corps de la requete : le mode
   * affiche et la portee envoyee sur le fil doivent etre lus au meme endroit,
   * sans quoi l'ecran peut montrer un magasin et en ecrire un autre.
   */
  const [magasinChoisi, setMagasinChoisi] = useState<string | null>(MODE_PAR_DEFAUT);

  const donnees = fiche.data as FicheCompte | undefined;
  useEffect(() => {
    if (donnees === undefined) {
      return;
    }
    setLignes(indexer(donnees.droits ?? []));
    setAccordes(donnees.magasins_accordes ?? []);
  }, [donnees]);

  if (fiche.isError || catalogue.isError) {
    return (
      <CarteDechec
        quoi="ce compte"
        reessayer={() => {
          void fiche.refetch();
          void catalogue.refetch();
        }}
      />
    );
  }
  if (fiche.isPending || catalogue.isPending) {
    return <p className="text-sm text-muted-foreground">Chargement…</p>;
  }

  const compte = fiche.data as FicheCompte;
  const offrable = catalogue.data as CatalogueOffrable;
  const prenom = prenomDe(compte.nom_complet);
  const libelles = new Map(
    offrable.sections.flatMap((section) =>
      section.droits.map((droit) => [droit.code, droit.libelle] as const),
    ),
  );

  /** Absorbe la reponse d'une bascule : lignes, cascade, magasins accordes. */
  const absorber = (resultat: ResultatOctroi): Record<string, LigneDeDroit> => {
    const fusion = { ...lignes, ...indexer(resultat.lignes) };
    setLignes(fusion);
    setAccordes(resultat.magasins_accordes);
    setNotes(notesDeCascade(resultat, libelles));
    return fusion;
  };

  /**
   * Rejoue un etat anterieur — **l'annulation**, cascade comprise.
   *
   * Une annulation qui ne restaurerait que le code demande laisserait les codes
   * emportes par la cascade a l'arret : le `Annuler` unique de 7.6 ne tiendrait
   * pas sa promesse, et l'utilisateur croirait avoir tout remis.
   */
  const rejouer = async (avant: readonly LigneDeDroit[]) => {
    for (const ligne of avant) {
      await bascule.mutateAsync({
        params: { path: { id: identifiant } },
        body: {
          code: ligne.code as never,
          accorde: ligne.magasins.length > 0,
          magasins: ligne.magasins.length > 0 ? [...ligne.magasins] : [...accordes],
        },
      });
    }
    void fiche.refetch();
  };

  /**
   * **Le seul chemin d'ecriture d'un droit**, parametre par le mode du
   * selecteur.
   *
   * Il y en avait deux — `basculerLeDroit` et `basculerUnMagasin` — qui ne
   * differaient que par le corps envoye. En garder deux ferait vivre deux
   * chemins pour un seul mecanisme, ce que la decision 1 de la phase 03.1
   * supprime precisement.
   */
  const basculerLeDroit = (code: string, accorde: boolean) => {
    const avant = lignes[code] ?? { code, etat: "inactif", magasins: [] };
    const etaitMixte = avant.etat === "mixte";
    setErreurs((precedent) => retirer(precedent, code));
    setNotes({});
    setNoteDeSection(undefined);

    /*
      **Les magasins sont nommes explicitement**, jamais omis. Omettre signifie
      « tous les magasins accordes de la cible » (plan 03-09), ce qui est juste
      pour un proprietaire et faux pour un gerant-gestionnaire : le serveur
      refuserait l'octroi entier des que la cible detient un magasin que
      l'appelant n'a pas. Envoyer la portee visible est le seul chemin qui
      marche pour les deux — et cela vaut pour les deux modes du selecteur, le
      mode nomme n'etant qu'une portee visible plus courte.
    */
    const magasinsVises = magasinChoisi === null ? [...accordes] : [magasinChoisi];

    /*
      L'optimisme suit le mode, lui aussi.

      La version precedente ecrivait `magasins: accorde ? [...accordes] : []`,
      ce qui n'a de sens qu'en mode `Tous` : en mode nomme, elle marquait
      brievement la ligne comme detenue PARTOUT avant que `absorber` ne la
      corrige. Le defaut se soignait tout seul en un aller-retour, mais il
      montrait pendant ce temps l'exact contraire de ce que le clic allait
      ecrire — et c'est ce que 7.8 achete en refusant le bouton Enregistrer.
    */
    const magasinsApres =
      magasinChoisi === null
        ? accorde
          ? [...accordes]
          : []
        : accorde
          ? [...new Set([...avant.magasins, magasinChoisi])]
          : avant.magasins.filter((magasin) => magasin !== magasinChoisi);
    const etatApres: LigneDeDroit["etat"] =
      magasinsApres.length === 0
        ? "inactif"
        : magasinsApres.length >= accordes.length
          ? "actif"
          : "mixte";
    setLignes((precedent) => ({
      ...precedent,
      [code]: { code, etat: etatApres, magasins: magasinsApres },
    }));

    bascule.mutate(
      {
        params: { path: { id: identifiant } },
        body: { code: code as never, accorde, magasins: magasinsVises },
      },
      {
        onSuccess: (resultat) => {
          absorber(resultat);
          const etatAvant = [
            avant,
            ...resultat.cascade.map(
              (emporte) =>
                lignes[emporte] ?? { code: emporte, etat: "inactif", magasins: [] },
            ),
          ];
          const libelle = libelles.get(code) ?? code;
          const nomDuMagasin =
            magasinChoisi === null
              ? null
              : (offrable.magasins.find((magasin) => magasin.code === magasinChoisi)
                  ?.nom ?? magasinChoisi);
          if (!accorde) {
            /*
              Le toast d'annulation de 7.8 couvre desormais les DEUX modes.
              L'ancienne sous-liste n'en offrait aucun — une incoherence avec
              7.8, qui se corrige ici parce que ce chemin devient le chemin
              principal et non plus un recoin.
            */
            toastDannulation(
              nomDuMagasin === null
                ? `Droit retiré : « ${libelle} ».`
                : `Droit retiré dans ${nomDuMagasin} : « ${libelle} ».`,
              () => void rejouer(etatAvant),
            );
          } else if (magasinChoisi === null && etaitMixte) {
            // Cliquer un parent mixte allume TOUS les magasins, et le toast le
            // dit : sans cette phrase, l'action a l'air d'un simple « cocher »
            // alors qu'elle distribue le droit la ou il etait deliberement
            // absent. En mode nomme la phrase serait fausse — un seul magasin
            // est touche — et la ligne n'y est de toute facon jamais mixte.
            toastDannulation(
              `Droit accordé dans tous les magasins : « ${libelle} ».`,
              () => void rejouer(etatAvant),
            );
          }
        },
        onError: (erreur) => {
          // Retour arriere, puis l'explication **sur la ligne** (7.8). Un
          // interrupteur laisse en place apres un echec ment sur l'etat reel.
          setLignes((precedent) => ({ ...precedent, [code]: avant }));
          setErreurs((precedent) => ({ ...precedent, [code]: messageDechec(erreur) }));
        },
      },
    );
  };

  /**
   * L'ajout d'un magasin, **derriere sa confirmation et porteur du choix**.
   *
   * `reappliquer` part TOUJOURS sur le fil, y compris quand il vaut `true` et
   * qu'il coincide avec le defaut serveur. S'appuyer sur ce defaut rendrait le
   * choix du proprietaire invisible sur le fil, donc indebogable dans un
   * journal d'acces — alors que le rendre explicite est exactement ce que la
   * decision 2 de la phase 03.1 existe pour faire.
   *
   * **Un seul appel, jamais deux.** Le choix voyage en parametre de
   * `accorder_magasin`, qui est atomique : deux appels enchaines — accorder,
   * puis retirer ce qui vient de s'etendre — ouvriraient une fenetre pendant
   * laquelle des droits refuses existent en base, et un gerant qui agit dans
   * cette fenetre agit avec eux.
   */
  const ajouterUnMagasin = (magasin: Magasin, reappliquer: boolean) => {
    setConfirmation(null);
    setNotes({});
    basculeMagasin.mutate(
      {
        params: { path: { id: identifiant } },
        body: { magasin_code: magasin.code, accorde: true, reappliquer },
      },
      {
        onSuccess: (resultat) => {
          const fusion = absorber(resultat);
          if (!reappliquer) {
            /*
              **Aucune note quand le magasin demarre vierge**, et rien a la
              place. « Verifiez les N droits personnalises » designerait une
              PARTIE du travail alors que tout est a regler, ce qui est
              trompeur ; et repeter que le magasin demarre sans droit serait
              redire une phrase lue il y a deux secondes dans le dialogue.
            */
            setNoteDeSection(undefined);
            return;
          }
          // Les lignes uniformes se sont etendues, les personnalisees non.
          // La note existe pour que cette asymetrie — voulue, et qui evite une
          // elevation silencieuse — ne passe pas inapercue.
          const personnalisees = compterLesPersonnalisees(fusion);
          setNoteDeSection(
            personnalisees === 0
              ? undefined
              : noteDeMagasinAjoute(magasin.nom, personnalisees),
          );
        },
      },
    );
  };

  const retirerUnMagasin = (magasin: Magasin) => {
    setConfirmation(null);
    setNoteDeSection(undefined);
    basculeMagasin.mutate(
      {
        params: { path: { id: identifiant } },
        body: { magasin_code: magasin.code, accorde: false },
      },
      { onSuccess: absorber },
    );
  };

  /**
   * La reinitialisation, **derriere sa confirmation**.
   *
   * Le corps est celui qui vivait dans le `onClick` du bouton : il n'a pas
   * change, il a recule d'un cran. Un clic par megarde coupait l'acces d'un
   * gerant en plein service sans rien demander et sans rien laisser defaire —
   * la seule action de l'ecran qui fut a la fois immediate et sans retour.
   * `DialogueMotDePasse`, en fin de fichier, n'y pouvait rien : il affiche un
   * mot de passe deja genere.
   */
  const reinitialiserLeMotDePasse = () => {
    setConfirmation(null);
    reinitialisation.mutate(
      { params: { path: { id: identifiant } }, body: {} as never },
      {
        onSuccess: (reponse) => {
          setSecret(
            (reponse as { mot_de_passe_provisoire: string }).mot_de_passe_provisoire,
          );
        },
      },
    );
  };

  const changerLeStatut = (actif: boolean) => {
    setConfirmation(null);
    changementDeStatut.mutate(
      { params: { path: { id: identifiant } }, body: { actif } },
      { onSuccess: () => void fiche.refetch() },
    );
  };

  return (
    <div className="mx-auto max-w-[880px]">
      <section aria-labelledby="titre-identite">
        <h1 className="text-2xl font-semibold">
          <Valeur>{compte.nom_complet}</Valeur>
        </h1>
        <h2 id="titre-identite" className="sr-only">
          Identité
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{compte.email}</p>

        {compte.est_proprietaire ? null : (
          <div className="mt-4 flex items-center gap-4">
            {/*
              `Statut` est une LISTE DEROULANTE et non un interrupteur (7.3 A) :
              un interrupteur suggere une bascule instantanee, alors que la
              desactivation merite une confirmation. Et la reactivation, elle,
              n'en merite pas — on ne confirme pas de rouvrir une porte.
            */}
            <label htmlFor={champStatut} className="text-sm">
              Statut
            </label>
            <select
              id={champStatut}
              className="h-9 rounded-md border border-border bg-background px-2 text-sm"
              value={compte.actif ? "actif" : "inactif"}
              onChange={(evenement) => {
                if (evenement.target.value === "inactif") {
                  setConfirmation({ quoi: "desactivation" });
                  return;
                }
                changerLeStatut(true);
              }}
            >
              <option value="actif">Actif</option>
              <option value="inactif">Désactivé</option>
            </select>

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setConfirmation({ quoi: "reinitialisation" })}
            >
              Réinitialiser le mot de passe
            </Button>
          </div>
        )}
      </section>

      {compte.est_proprietaire ? (
        /*
          7.7 — aucune section de droits n'est rendue pour le proprietaire. Pas
          en lecture seule, pas grisee : absente. Son acces est materialise au
          plan 03-05, donc une case a cocher serait un mensonge cliquable.
        */
        <p className="mt-8 text-sm text-muted-foreground">{PHRASE_PROPRIETAIRE}</p>
      ) : (
        <>
          <SectionMagasins
            magasinsOffrables={offrable.magasins}
            accordes={accordes}
            surDemandeDajout={(magasin) =>
              setConfirmation({ quoi: "ajout-magasin", magasin })
            }
            surRetrait={(magasin) =>
              setConfirmation({ quoi: "retrait-magasin", magasin })
            }
            surDemandeDeDesactivation={() => setConfirmation({ quoi: "desactivation" })}
          />

          <SectionDroits
            catalogue={offrable}
            lignes={lignes}
            magasinsAccordes={accordes}
            prenom={prenom}
            notes={notes}
            erreurs={erreurs}
            noteDeSection={noteDeSection}
            surBascule={basculerLeDroit}
            magasinChoisi={magasinChoisi}
            surChoixDeMagasin={setMagasinChoisi}
          />

          <HistoriqueDroits compteId={identifiant} />
        </>
      )}

      <DialogueDesactivation
        ouvert={confirmation?.quoi === "desactivation"}
        nomComplet={compte.nom_complet}
        surRetour={() => setConfirmation(null)}
        surConfirmation={() => changerLeStatut(false)}
      />

      {/*
        Les deux chiffres sont derives de `lignes`, **deja intersecte** aux
        droits et magasins de l'appelant par le serveur (plan 03-09) : un
        gerant-gestionnaire compte donc ce qu'il detient, et rien de plus.
        Aucune source nouvelle, et surtout aucun point de terminaison de
        simulation — l'apercu et l'effet seraient alors deux calculs libres de
        diverger.
      */}
      <DialogueAjoutMagasin
        ouvert={confirmation?.quoi === "ajout-magasin"}
        nomDuMagasin={
          confirmation?.quoi === "ajout-magasin" ? confirmation.magasin.nom : ""
        }
        prenom={prenom}
        uniformes={Object.values(lignes).filter((ligne) => ligne.etat === "actif").length}
        personnalisees={compterLesPersonnalisees(lignes)}
        surRetour={() => setConfirmation(null)}
        surConfirmation={(reappliquer) => {
          if (confirmation?.quoi === "ajout-magasin") {
            ajouterUnMagasin(confirmation.magasin, reappliquer);
          }
        }}
      />

      <DialogueRetraitMagasin
        ouvert={confirmation?.quoi === "retrait-magasin"}
        prenom={prenom}
        nomDuMagasin={
          confirmation?.quoi === "retrait-magasin" ? confirmation.magasin.nom : ""
        }
        reglagesPersonnalises={
          confirmation?.quoi === "retrait-magasin"
            ? compterLesPersonnalisees(lignes, confirmation.magasin.code)
            : 0
        }
        surRetour={() => setConfirmation(null)}
        surConfirmation={() => {
          if (confirmation?.quoi === "retrait-magasin") {
            retirerUnMagasin(confirmation.magasin);
          }
        }}
      />

      <DialogueReinitialisation
        ouvert={confirmation?.quoi === "reinitialisation"}
        prenom={prenom}
        surRetour={() => setConfirmation(null)}
        surConfirmation={reinitialiserLeMotDePasse}
      />

      <DialogueMotDePasse
        ouvert={secret !== null}
        secret={secret}
        surFermeture={() => setSecret(null)}
      />
    </div>
  );
}

/** `Californie a été ajouté. Vérifiez les 2 droits personnalisés par magasin.` */
export function noteDeMagasinAjoute(nom: string, personnalises: number): string {
  return personnalises === 1
    ? `${nom} a été ajouté. Vérifiez le droit personnalisé par magasin.`
    : `${nom} a été ajouté. Vérifiez les ${String(personnalises)} droits personnalisés par magasin.`;
}

/**
 * Les notes en ligne de la cascade de prerequis (7.6).
 *
 * `cascade` existe comme liste separee alors qu'elle est derivable de `lignes`,
 * et c'est delibere cote serveur : l'interface en fait deux choses que `lignes`
 * ne distingue pas — une note par ligne emportee, et **un seul** toast
 * d'annulation. La note EXPLIQUE ; la fermeture, elle, est appliquee cote
 * serveur.
 */
function notesDeCascade(
  resultat: ResultatOctroi,
  libelles: ReadonlyMap<string, string>,
): Record<string, string> {
  const demande = libelles.get(resultat.code) ?? resultat.code;
  const notes: Record<string, string> = {};
  for (const code of resultat.cascade) {
    const libelle = libelles.get(code) ?? code;
    notes[code] =
      resultat.action === "accorde"
        ? `« ${libelle} » a été activé automatiquement.`
        : `« ${libelle} » a été retiré : il dépend de « ${demande} ».`;
  }
  return notes;
}

function retirer(
  table: Record<string, string>,
  clef: string,
): Record<string, string> {
  const { [clef]: _oublie, ...reste } = table;
  return reste;
}

/**
 * Le message d'un echec de bascule.
 *
 * Le serveur explique en francais — « Vous ne pouvez accorder qu'un droit que
 * vous detenez vous-meme. » — et c'est ce qu'il faut afficher. A defaut, une
 * phrase generique, jamais un code de statut ni une trace.
 */
function messageDechec(corps: unknown): string {
  if (typeof corps === "object" && corps !== null) {
    const detail = (corps as { detail?: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
    for (const valeur of Object.values(corps as Record<string, unknown>)) {
      if (Array.isArray(valeur) && typeof valeur[0] === "string") {
        return valeur[0];
      }
      if (typeof valeur === "string") {
        return valeur;
      }
    }
  }
  return "Ce changement n'a pas été enregistré. Réessayez.";
}

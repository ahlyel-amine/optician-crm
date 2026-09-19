import { useEffect, useReducer, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { $api, type OrdonnanceASaisir } from "@/api/requetes";
import { useAuth } from "@/auth/AuthProvider";
import { ChampDate } from "@/champs/ChampDate";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { depuisISO, versISO } from "@/champs/dates";
import { MESSAGE_SERVICE_INDISPONIBLE } from "@/etats/messages";
import { useLienDisponible } from "@/etats/reseau";

import { BlocEcartPupillaire } from "./BlocEcartPupillaire";
import { ChoixDePhoto, televerserLaPhoto } from "./PhotoOrdonnance";
import { GrilleOdOg, type RemarquesDuChamp } from "./GrilleOdOg";
import { PanneauRelecture } from "./PanneauRelecture";
import { canonicaliserAxe, rendreMilliemes, enMilliemes, transposer } from "./optique";
import {
  ACTION_ENREGISTRER,
  ACTION_FERMER,
  ACTION_QUITTER,
  ACTION_REPRENDRE,
  ACTION_RETOUR,
  AIDE_LIEN_COUPE,
  AIDE_MAGASIN,
  AIDE_MOTIF,
  AIDE_OPTICIEN,
  CORPS_CONFIRMATION_AVERTISSEMENTS,
  CORPS_QUITTER,
  LABEL_DATE_PRESCRIPTION,
  LABEL_MAGASIN,
  LABEL_MOTIF,
  LABEL_PRESCRIPTEUR,
  LEGENDE_SOURCE,
  LEGENDE_TYPE_SAISIE,
  MESSAGE_PRESCRIPTION_FUTURE,
  NOTATION_NEGATIVE,
  NOTATION_POSITIVE,
  OEIL_DROIT,
  OEIL_GAUCHE,
  REFUS_AXE_SANS_CYLINDRE,
  REFUS_CYLINDRE_SANS_AXE,
  SOURCE_MEDICALE,
  SOURCE_OPTICIEN,
  TITRE_QUITTER,
  TITRE_SAISIE,
  TYPE_CORRECTION,
  TYPE_RENOUVELLEMENT,
  annonceAxeCanonicalise,
  annonceReprise,
  annonceTransposition,
  titreConfirmationAvertissements,
  toastEnregistree,
} from "./messages";
import {
  ORDONNANCE_VIDE,
  decimalesDuPas,
  bornesDeLecartPupillaire,
  verifierOrdonnance,
  type BornesServies,
  type EpSaisi,
  type Notation,
  type Ordonnance,
  type Remarque,
  type Source,
  type TypeRevision,
} from "./verifier";
import type { BorneAxe } from "./optique";

/**
 * L'ecran de saisie d'une ordonnance — le plus dense du produit apres
 * `Comptes et droits`.
 *
 * **La position de la phase, et tout cet ecran en decoule.** La validation
 * attrape l'impossible ; seul l'ecran attrape l'invraisemblable, et il
 * l'attrape de trois facons exactement : en rendant la valeur relisible dans la
 * notation du papier (le panneau de relecture), en la montrant a cote de la
 * precedente (la colonne de reference), et en disant a voix haute, **sans
 * refuser**, que quelque chose parait bizarre.
 *
 * **Cet ecran n'evalue rien.** Il appelle `verifierOrdonnance`, qui est pure et
 * prouvee sans rendu, et il rend ce qu'elle dit. Un module de verification
 * melange a du rendu se teste par le DOM, donc mal, donc peu.
 *
 * **Une route, pas un dialogue** (20.1). Un dialogue piegerait le focus,
 * plafonnerait la largeur et rendrait le panneau de relecture impossible a
 * placer. L'echappatoire s'appelle `Fermer` — pas `Annuler`, qui dans ce
 * produit veut dire *defaire*.
 *
 * **Aucun numero de version n'est predit avant l'enregistrement.** Ecrire
 * `Ce sera la version 3.` sur le formulaire est l'habitude exacte qui produit
 * un numero de facture emis par le client, ce que CLAUDE.md #3 interdit pour
 * une raison qui se transfere telle quelle.
 *
 * **Aucun brouillon, aucune sauvegarde automatique, aucun stockage navigateur.**
 * CLAUDE.md #1 : aucune donnee metier ne persiste dans le navigateur, et une
 * ordonnance est une donnee de sante.
 *
 * **`react-hook-form` n'est pas installe** (15.3). L'etat est un `useReducer`
 * type sur un objet plat, et la raison qui compte est qu'un **avertissement
 * n'est pas une erreur** : l'exprimer par le `setError` d'une bibliotheque
 * tierce serait un detournement de severite dans la machine a etats de
 * quelqu'un d'autre.
 */

/* ---------------------------------------------------------------------------
 * L'etat, et la seule regle de temporalite qui compte
 * ------------------------------------------------------------------------- */

/**
 * `evalue` est l'INSTANTANE verifie, et il n'est pris qu'au blur et a la
 * soumission — **jamais a la frappe** (16.4).
 *
 * C'est ce champ, et lui seul, qui tient la promesse « taper `9` en route vers
 * `90` n'annonce rien » : les remarques se derivent de `evalue`, pas de
 * `valeur`. Les rendre depuis `valeur` les ferait apparaitre a la troisieme
 * touche, ce qui apprend a l'opticien a les ignorer.
 */
export type EtatDeSaisie = {
  valeur: Ordonnance;
  evalue: Ordonnance | null;
  /** La region polie : transposition, canonicalisation d'axe, reprise. */
  annonce: string;
  /**
   * Une tentative de soumission a eu lieu.
   *
   * Elle commande l'apparition des refus qui ne portent sur AUCUNE valeur
   * saisie — source non choisie, magasin non choisi, prescripteur manquant, et
   * les deux refus croises axe-cylindre. 20.4 et 20.8 les verifient « on
   * submit », et les montrer au premier blur reprocherait a l'opticien de ne
   * pas avoir encore rempli un champ qu'il s'apprete a remplir. Les refus qui
   * portent sur une valeur TAPEE, eux, apparaissent au blur : ils parlent de ce
   * qui vient d'etre quitte.
   */
  soumisUneFois: boolean;
};

export type ActionDeSaisie =
  | { type: "champ"; champ: keyof Ordonnance; valeur: string }
  | { type: "forme"; forme: EpSaisi }
  | { type: "source"; source: Source }
  | { type: "notation"; notation: Notation; borneAxe: BorneAxe }
  | { type: "evaluer"; borneAxe: BorneAxe }
  | { type: "soumettre"; borneAxe: BorneAxe }
  | { type: "reprendre"; precedente: Ordonnance; annonce: string };

const ETAT_INITIAL: EtatDeSaisie = {
  valeur: ORDONNANCE_VIDE,
  evalue: null,
  annonce: "",
  soumisUneFois: false,
};

/** `OD +2,00 (−1,00 à 90°)` — la forme du papier, pour une annonce. */
function ligneDite(oeil: "OD" | "OG", v: Ordonnance): string {
  const suffixe = oeil === "OD" ? "od" : "og";
  const sphere = v[`sphere_${suffixe}` as keyof Ordonnance] as string;
  const cylindre = v[`cylindre_${suffixe}` as keyof Ordonnance] as string;
  const axe = v[`axe_${suffixe}` as keyof Ordonnance] as string;
  if (cylindre === "") {
    return `${oeil} ${sphere}`;
  }
  return `${oeil} ${sphere} (${cylindre} à ${axe}°)`;
}

export function reduire(etat: EtatDeSaisie, action: ActionDeSaisie): EtatDeSaisie {
  switch (action.type) {
    case "champ":
      return {
        ...etat,
        valeur: { ...etat.valeur, [action.champ]: action.valeur },
      };

    case "forme":
      return { ...etat, valeur: { ...etat.valeur, ep_saisi: action.forme } };

    case "source":
      // Passer en refraction opticien efface le prescripteur : le champ n'est
      // plus rendu, et un prescripteur invisible qui part au serveur serait
      // une donnee que personne n'a confirmee.
      return {
        ...etat,
        valeur: {
          ...etat.valeur,
          source: action.source,
          prescripteur:
            action.source === "ordonnance_medicale" ? etat.valeur.prescripteur : "",
        },
      };

    case "notation": {
      // LA TRANSPOSITION SUR PLACE. Les memes champs portent la valeur
      // transposee : c'est la seule facon de voir ce que la bascule fait, et
      // une transposition mentale passe toutes les bornes (20.3).
      const od = transposer(
        {
          sphere: etat.valeur.sphere_od,
          cylindre: etat.valeur.cylindre_od,
          axe: etat.valeur.axe_od,
        },
        action.borneAxe,
      );
      const og = transposer(
        {
          sphere: etat.valeur.sphere_og,
          cylindre: etat.valeur.cylindre_og,
          axe: etat.valeur.axe_og,
        },
        action.borneAxe,
      );
      const valeur: Ordonnance = {
        ...etat.valeur,
        notation: action.notation,
        sphere_od: od.sphere,
        cylindre_od: od.cylindre,
        axe_od: od.axe,
        sphere_og: og.sphere,
        cylindre_og: og.cylindre,
        axe_og: og.axe,
      };
      const libelle =
        action.notation === "negatif" ? NOTATION_NEGATIVE : NOTATION_POSITIVE;
      const ligne =
        valeur.cylindre_od === "" ? ligneDite("OG", valeur) : ligneDite("OD", valeur);
      return {
        ...etat,
        valeur,
        // L'instantane suit la transposition : les remarques deja affichees
        // portaient sur des valeurs qui n'existent plus.
        evalue: etat.evalue === null ? null : valeur,
        annonce: annonceTransposition(libelle, ligne),
      };
    }

    case "soumettre":
      return { ...reduire(etat, { type: "evaluer", borneAxe: action.borneAxe }), soumisUneFois: true };

    case "evaluer": {
      // Le zero d'axe est accepte a la saisie et canonicalise ICI, au blur,
      // visiblement et en le disant (20.4).
      let valeur = etat.valeur;
      let annonce = etat.annonce;
      for (const suffixe of ["od", "og"] as const) {
        const cle = `axe_${suffixe}` as keyof Ordonnance;
        const brut = (valeur[cle] as string).trim();
        if (brut !== "" && Number.parseInt(brut, 10) === 0) {
          valeur = {
            ...valeur,
            [cle]: String(canonicaliserAxe(0, action.borneAxe)),
          };
          annonce = annonceAxeCanonicalise(action.borneAxe.max);
        }
      }
      return { ...etat, valeur, evalue: valeur, annonce };
    }

    case "reprendre":
      return {
        ...etat,
        valeur: { ...action.precedente, magasin: etat.valeur.magasin },
        annonce: action.annonce,
      };
  }
}

/* ---------------------------------------------------------------------------
 * Une version STOCKEE vers la forme d'affichage
 * ------------------------------------------------------------------------- */

/** `"-1.00"` vers `−1,00`. Vide quand la colonne est nulle : vide n'est pas zero. */
function afficher(
  brut: string | null | undefined,
  decimales: 0 | 1 | 2,
  avecSigne: boolean,
): string {
  if (brut === null || brut === undefined || brut === "") {
    return "";
  }
  const milliemes = enMilliemes(brut);
  return milliemes === null ? "" : rendreMilliemes(milliemes, decimales, avecSigne);
}

/**
 * La derniere version, dans la forme que la grille et le panneau lisent.
 *
 * **Elle n'est jamais revalidee** (CLIENT-06) : elle sert de reference a l'oeil
 * et de base aux avertissements A4, A5 et A6, et rien d'autre.
 */
export function depuisLaVersionStockee(brut: Record<string, unknown>): Ordonnance {
  const texte = (cle: string): string => {
    const valeur = brut[cle];
    return typeof valeur === "string" ? valeur : "";
  };
  const entier = (cle: string): string => {
    const valeur = brut[cle];
    return typeof valeur === "number" ? String(valeur) : "";
  };
  return {
    ...ORDONNANCE_VIDE,
    sphere_od: afficher(texte("sphere_od"), 2, true),
    sphere_og: afficher(texte("sphere_og"), 2, true),
    cylindre_od: afficher(texte("cylindre_od"), 2, true),
    cylindre_og: afficher(texte("cylindre_og"), 2, true),
    axe_od: entier("axe_od"),
    axe_og: entier("axe_og"),
    addition_od: afficher(texte("addition_od"), 2, true),
    addition_og: afficher(texte("addition_og"), 2, true),
    ep_saisi: (texte("ep_saisi") || "binoculaire") as EpSaisi,
    ep_binoculaire: afficher(texte("ep_binoculaire"), 1, false),
    ep_mono_od: afficher(texte("ep_mono_od"), 1, false),
    ep_mono_og: afficher(texte("ep_mono_og"), 1, false),
    source: (texte("source") || "") as Source,
    prescripteur: texte("prescripteur"),
    date_prescription: depuisISO(texte("date_prescription")),
  };
}

/* ---------------------------------------------------------------------------
 * L'ecran
 * ------------------------------------------------------------------------- */

/** Le jour de reference. Il est LU ICI et passe en propriete : un composant qui appelle l'horloge est un test rouge un 1er janvier. */
function aujourdhuiISO(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Au-dela de ce nombre de magasins, la liste devient un combobox nomme (20.9). */
const MAGASINS_AVANT_COMBOBOX = 4;

export function SaisieOrdonnance() {
  const { id = "" } = useParams();
  const identifiant = Number.parseInt(id, 10);
  const { bornes, magasins, magasinSelectionne } = useAuth();

  const client = $api.useQuery("get", "/api/clients/{id}/", {
    params: { path: { id: identifiant } },
  });
  const historique = $api.useQuery("get", "/api/clients/{client_id}/ordonnances/", {
    params: { path: { client_id: identifiant } },
  });

  // Le magasin pre-selectionne : la portee active quand elle nomme un magasin,
  // l'unique magasin quand il n'y en a qu'un, et RIEN sous « Tous les magasins ».
  const magasinParDefaut =
    magasins.length === 1
      ? String(magasins[0].id)
      : (magasins.find((magasin) => magasin.code === magasinSelectionne)?.id ?? "");

  const [etat, envoyer] = useReducer(reduire, {
    ...ETAT_INITIAL,
    valeur: { ...ORDONNANCE_VIDE, magasin: String(magasinParDefaut) },
  });

  if (bornes === null) {
    // L'amorcage n'a pas encore servi les bornes. Rien ne se rend, parce que
    // rien ne PEUT se rendre : aucun chiffre clinique n'est compile ici.
    return null;
  }

  return (
    <CorpsDeLaSaisie
      identifiantDuClient={identifiant}
      etat={etat}
      envoyer={envoyer}
      bornes={bornes}
      nomDuClient={lireNom(client.data)}
      dateDeNaissance={lireNaissance(client.data)}
      versions={(historique.data ?? []) as unknown as Record<string, unknown>[]}
      magasins={magasins}
    />
  );
}

function lireNom(fiche: unknown): string {
  const nom = (fiche as { nom?: unknown } | undefined)?.nom;
  return typeof nom === "string" ? nom : "";
}

function lireNaissance(fiche: unknown): string {
  const brut = (fiche as { date_naissance?: unknown } | undefined)?.date_naissance;
  return typeof brut === "string" ? depuisISO(brut) : "";
}

type ProprietesCorps = {
  identifiantDuClient: number;
  etat: EtatDeSaisie;
  envoyer: (action: ActionDeSaisie) => void;
  bornes: BornesServies;
  nomDuClient: string;
  dateDeNaissance: string;
  versions: Record<string, unknown>[];
  magasins: { id: number; code: string; nom: string }[];
};

/** Les champs dont le refus attend la SOUMISSION : aucun ne porte de valeur tapee. */
const CHAMPS_DE_SOUMISSION = new Set(["source", "prescripteur", "magasin"]);

/**
 * Un refus qui ne parle pas de ce que l'opticien vient de quitter.
 *
 * Les deux refus croises axe-cylindre en font partie : ils portent sur une
 * PAIRE de champs, et le premier des deux est fatalement vide au moment ou on
 * quitte le second. Les afficher au blur reviendrait a reprocher une saisie en
 * cours.
 */
function estUnRefusDeSoumission(remarque: Remarque): boolean {
  if (remarque.severite !== "refus") {
    return false;
  }
  return (
    CHAMPS_DE_SOUMISSION.has(remarque.champ) ||
    remarque.texte === REFUS_AXE_SANS_CYLINDRE ||
    remarque.texte === REFUS_CYLINDRE_SANS_AXE(OEIL_DROIT) ||
    remarque.texte === REFUS_CYLINDRE_SANS_AXE(OEIL_GAUCHE)
  );
}

function CorpsDeLaSaisie({
  identifiantDuClient,
  etat,
  envoyer,
  bornes,
  nomDuClient,
  dateDeNaissance,
  versions,
  magasins,
}: ProprietesCorps) {
  const naviguer = useNavigate();
  const lienDisponible = useLienDisponible();
  const borneAxe = bornes.axe;

  const [confirmation, setConfirmation] = useState(false);
  const [sortie, setSortie] = useState(false);
  /**
   * La photo choisie AVANT l'enregistrement, envoyee APRES.
   *
   * L'ordre est impose par le serveur et il est le bon : la route de la photo
   * porte l'identifiant de l'ordonnance, qui n'existe qu'une fois la version
   * emise. Le fichier attend donc en memoire, et rien n'est televerse si
   * l'enregistrement echoue — il n'y a pas d'octets orphelins a nettoyer.
   */
  const [photo, setPhoto] = useState<File | null>(null);
  const [echec, setEchec] = useState<string | null>(null);
  const refDeLechec = useRef<HTMLParagraphElement | null>(null);

  const creation = $api.useMutation("post", "/api/clients/{client_id}/ordonnances/");

  const precedente = versions.length === 0 ? null : depuisLaVersionStockee(versions[0]);
  const idDeLaPrecedente =
    versions.length === 0 ? null : lireEntier(versions[0], "id");

  const contexte = {
    bornes,
    precedente: precedente ?? undefined,
    dateNaissance: dateDeNaissance === "" ? undefined : dateDeNaissance,
    aujourdhui: aujourdhuiISO(),
  };

  const remarques = etat.evalue === null ? [] : verifierOrdonnance(etat.evalue, contexte);
  const affichees = remarques.filter(
    (remarque) => etat.soumisUneFois || !estUnRefusDeSoumission(remarque),
  );
  const avertissements = remarques.filter(
    (remarque) => remarque.severite === "avertissement",
  );

  const remarquesDe = (champ: string): RemarquesDuChamp => ({
    faute: affichees.find((r) => r.champ === champ && r.severite === "refus")?.texte,
    avertissement: affichees.find(
      (r) => r.champ === champ && r.severite === "avertissement",
    )?.texte,
  });

  const evaluer = () => envoyer({ type: "evaluer", borneAxe });
  const poser = (champ: keyof Ordonnance, valeur: string) =>
    envoyer({ type: "champ", champ, valeur });

  // L'ECHEC PREND LE FOCUS (25.4). Un message au-dessus d'un bouton qu'on vient
  // de cliquer n'est pas lu par qui n'y regarde pas.
  useEffect(() => {
    if (echec !== null) {
      refDeLechec.current?.focus();
    }
  }, [echec]);

  const envoyerAuServeur = () => {
    setEchec(null);
    creation.mutate(
      {
        params: { path: { client_id: identifiantDuClient } },
        body: construireLaCharge(etat.valeur, bornes, idDeLaPrecedente),
      },
      {
        onSuccess: (creee) => {
          // AUCUN ETAT OPTIMISTE : le succes vient du serveur ou n'est pas
          // affiche, et la version affichee est CELLE QU'IL A EMISE.
          // `creee` est typee non nulle par le contrat, et une reponse 2xx sans
          // corps la rendrait pourtant indefinie. On ne lui fait pas confiance
          // sur parole : la version vient du serveur ou le toast ne l'affirme pas.
          const rendue = (creee ?? {}) as Record<string, unknown>;
          const version = lireEntier(rendue, "version") ?? 0;
          const idCreee = lireEntier(rendue, "id");
          // LA PHOTO SUIT L'ORDONNANCE, jamais l'inverse. Son echec ne remet
          // pas en cause l'enregistrement : la version EST enregistree, et la
          // photo peut etre attachee plus tard depuis l'historique — c'est
          // exactement la transition que 22.3 autorise.
          if (photo !== null && idCreee !== null) {
            void televerserLaPhoto(idCreee, photo).catch(() => {});
          }
          naviguer(`/clients/${String(identifiantDuClient)}/ordonnances`);
          // Le toast n'offre AUCUNE action : `Annuler` est reserve a
          // l'annulation, et il n'y a rien a annuler — la ligne est immuable.
          toast(toastEnregistree(version));
        },
        onError: () => setEchec(MESSAGE_SERVICE_INDISPONIBLE),
      },
    );
  };

  const tenterDeSoumettre = () => {
    envoyer({ type: "soumettre", borneAxe });
    const verdict = verifierOrdonnance(etat.valeur, contexte);
    if (verdict.some((remarque) => remarque.severite === "refus")) {
      return;
    }
    if (verdict.some((remarque) => remarque.severite === "avertissement")) {
      setConfirmation(true);
      return;
    }
    envoyerAuServeur();
  };

  const saisieCommencee = aUneValeur(etat.valeur);
  const nomDuMagasin =
    magasins.find((magasin) => String(magasin.id) === etat.valeur.magasin)?.nom ?? "";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{TITRE_SAISIE}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          <bdi>{nomDuClient}</bdi>
        </p>
      </div>

      {/*
        La region polie de l'ecran : transposition, canonicalisation d'axe,
        reprise des valeurs. `role="status"` et jamais `role="alert"` — aucune
        de ces trois nouvelles n'est une panne.
      */}
      <p role="status" className="text-sm text-muted-foreground">
        {etat.annonce}
      </p>

      <div className="flex flex-col gap-8 xl:flex-row xl:items-start">
        <form
          data-testid="formulaire-ordonnance"
          className="flex flex-1 flex-col gap-8"
          onSubmit={(evenement) => {
            // `Enter` soumet, `03` 5.7 : le formulaire n'a qu'une action
            // primaire, et c'est pour cela que la confirmation de 16.5 existe.
            evenement.preventDefault();
            tenterDeSoumettre();
          }}
        >
          <GrilleOdOg
            valeur={etat.valeur}
            bornes={bornes}
            surChamp={poser}
            surSortieDeChamp={evaluer}
            surNotation={(notation) => envoyer({ type: "notation", notation, borneAxe })}
            remarquesDe={remarquesDe}
            precedente={precedente}
            dateDeLaPrecedente={precedente?.date_prescription ?? ""}
          />

          <BlocEcartPupillaire
            valeur={etat.valeur}
            bornes={bornes}
            surChamp={poser}
            surSortieDeChamp={evaluer}
            surForme={(forme) => envoyer({ type: "forme", forme })}
            remarquesDe={remarquesDe}
          />

          <BlocSource
            valeur={etat.valeur}
            envoyer={envoyer}
            evaluer={evaluer}
            poser={poser}
            remarquesDe={remarquesDe}
          />

          <BlocMagasin
            valeur={etat.valeur}
            magasins={magasins}
            poser={poser}
            evaluer={evaluer}
            remarquesDe={remarquesDe}
          />

          {precedente === null ? null : (
            <BlocTypeDeSaisie
              valeur={etat.valeur}
              poser={poser}
              surReprise={() => {
                envoyer({
                  type: "reprendre",
                  precedente,
                  annonce: annonceReprise(precedente.date_prescription),
                });
                // LE FOCUS REVIENT A LA PREMIERE SPHERE (25.4) : les valeurs
                // viennent d'etre remplies, elles doivent etre RELUES sur le
                // papier, et le clavier repart la ou la relecture commence.
                document.getElementById("ord-sphere-od")?.focus();
              }}
            />
          )}

          {/*
            LE DERNIER BLOC AVANT LES BOUTONS (22.1). Une vraie entree fichier,
            un label visible, et le fichier retenu en memoire jusqu'a ce que le
            serveur ait emis la version.
          */}
          <ChoixDePhoto fichier={photo} surChoix={setPhoto} />

          {echec === null ? null : (
            <p
              ref={refDeLechec}
              role="alert"
              tabIndex={-1}
              className="max-w-prose text-sm text-destructive"
            >
              {echec}
            </p>
          )}

          <div className="flex items-center gap-4">
            <Button
              type="submit"
              disabled={creation.isPending || !lienDisponible}
              className="h-9"
            >
              {creation.isPending ? (
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              ) : null}
              {/* LE LIBELLE NE CHANGE PAS pendant l'envoi : le bouton ne se
                  redimensionne pas sous le curseur. */}
              {ACTION_ENREGISTRER}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                if (saisieCommencee) {
                  setSortie(true);
                  return;
                }
                naviguer(`/clients/${String(identifiantDuClient)}`);
              }}
            >
              {ACTION_FERMER}
            </Button>
            {lienDisponible ? null : (
              <p className="max-w-prose text-xs text-muted-foreground">
                {AIDE_LIEN_COUPE}
              </p>
            )}
          </div>
        </form>

        <PanneauRelecture
          valeur={etat.valeur}
          bornes={bornes}
          avertissements={avertissements.length}
          nomDuMagasin={nomDuMagasin}
        />
      </div>

      {/*
        L'UNIQUE clic que coute un avertissement (16.5). Elle n'apparait que
        lorsque quelque chose est reellement bizarre, donc elle est rare par
        construction — c'est ce qui la separe de la fatigue a vingt-et-un
        interrupteurs que `03` 7.8 refuse. NON DESTRUCTIVE : rien n'est detruit,
        et la seconde phrase enonce ce qui SURVIT.
      */}
      <AlertDialog open={confirmation} onOpenChange={setConfirmation}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {titreConfirmationAvertissements(avertissements.length)}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {CORPS_CONFIRMATION_AVERTISSEMENTS}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {avertissements.map((remarque) => (
              <li key={`${remarque.champ}-${remarque.texte}`}>{remarque.texte}</li>
            ))}
          </ul>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setConfirmation(false)}>
              {ACTION_RETOUR}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setConfirmation(false);
                envoyerAuServeur();
              }}
            >
              {ACTION_ENREGISTRER}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={sortie} onOpenChange={setSortie}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{TITRE_QUITTER}</AlertDialogTitle>
            <AlertDialogDescription>{CORPS_QUITTER}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setSortie(false)}>
              {ACTION_RETOUR}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => naviguer(`/clients/${String(identifiantDuClient)}`)}
            >
              {ACTION_QUITTER}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

/** Une saisie a commence des qu'un champ porte autre chose que son defaut. */
function aUneValeur(valeur: Ordonnance): boolean {
  const defaut = ORDONNANCE_VIDE;
  return (Object.keys(defaut) as (keyof Ordonnance)[]).some(
    (cle) => cle !== "magasin" && cle !== "notation" && valeur[cle] !== defaut[cle],
  );
}

function lireEntier(brut: Record<string, unknown>, cle: string): number | null {
  const valeur = brut[cle];
  return typeof valeur === "number" ? valeur : null;
}

/* ---------------------------------------------------------------------------
 * La charge utile — et la seule convention qui en sorte
 * ------------------------------------------------------------------------- */

/** `−1,00` vers `"-1.00"`. Vide vers `null` : un champ vide est vide, jamais zero. */
function versDecimal(valeur: string, decimales: 0 | 1 | 2): string | null {
  const milliemes = enMilliemes(valeur);
  if (milliemes === null) {
    return null;
  }
  const rendu = rendreMilliemes(milliemes, decimales, false);
  return rendu.replace("\u2212", "-").replace(",", ".");
}

function versEntier(valeur: string, borne: BorneAxe): number | null {
  const brut = Number.parseInt(valeur.trim(), 10);
  if (Number.isNaN(brut)) {
    return null;
  }
  return brut === 0 ? canonicaliserAxe(brut, borne) : brut;
}

/**
 * Ce qui part au serveur.
 *
 * **Toujours du cylindre negatif**, quelle que soit la bascule : la
 * transposition est faite ICI, une derniere fois, et il n'existe aucune seconde
 * representation rangee. Une seconde colonne serait une seconde source de
 * verite, et les deux divergeraient le jour ou une correction n'en met a jour
 * qu'une.
 *
 * **`version` n'est pas dans cette charge**, et c'est la meme garantie que le
 * numero de facture de CLAUDE.md #3 : le serveur l'emet sous verrou, dans la
 * transaction d'insertion.
 */
export function construireLaCharge(
  saisie: Ordonnance,
  bornes: BornesServies,
  idDeLaPrecedente: number | null,
): OrdonnanceASaisir {
  const valeur =
    saisie.notation === "positif" ? transposerPourLenvoi(saisie, bornes.axe) : saisie;
  const decimalesEp = decimalesDuPas(bornesDeLecartPupillaire(bornes).pas);

  return {
    magasin: Number.parseInt(valeur.magasin, 10),
    source: valeur.source as OrdonnanceASaisir["source"],
    prescripteur: valeur.prescripteur,
    date_prescription: versISO(valeur.date_prescription),
    supersede: valeur.type_revision === "correction" ? idDeLaPrecedente : null,
    type_revision: valeur.type_revision as OrdonnanceASaisir["type_revision"],
    motif_revision: valeur.motif_revision,
    sphere_od: versDecimal(valeur.sphere_od, 2),
    sphere_og: versDecimal(valeur.sphere_og, 2),
    cylindre_od: versDecimal(valeur.cylindre_od, 2),
    cylindre_og: versDecimal(valeur.cylindre_og, 2),
    axe_od: versEntier(valeur.axe_od, bornes.axe),
    axe_og: versEntier(valeur.axe_og, bornes.axe),
    addition_od: versDecimal(valeur.addition_od, 2),
    addition_og: versDecimal(valeur.addition_og, 2),
    ep_binoculaire: versDecimal(valeur.ep_binoculaire, decimalesEp),
    ep_mono_od: versDecimal(valeur.ep_mono_od, decimalesEp),
    ep_mono_og: versDecimal(valeur.ep_mono_og, decimalesEp),
    ep_saisi: valeur.ep_saisi,
  };
}

function transposerPourLenvoi(valeur: Ordonnance, borne: BorneAxe): Ordonnance {
  const od = transposer(
    { sphere: valeur.sphere_od, cylindre: valeur.cylindre_od, axe: valeur.axe_od },
    borne,
  );
  const og = transposer(
    { sphere: valeur.sphere_og, cylindre: valeur.cylindre_og, axe: valeur.axe_og },
    borne,
  );
  return {
    ...valeur,
    sphere_od: od.sphere,
    cylindre_od: od.cylindre,
    axe_od: od.axe,
    sphere_og: og.sphere,
    cylindre_og: og.cylindre,
    axe_og: og.axe,
  };
}

/**
 * `Type de saisie` et `Reprendre la precedente`.
 *
 * **Aucun pre-remplissage automatique** : une prescription qui apparait dans
 * les champs sans avoir ete tapee est une prescription que personne n'a lue.
 * Le bouton remplit VISIBLEMENT, l'annonce, et rend le focus a la premiere
 * sphere — c'est-a-dire la ou la relecture sur le papier commence.
 */
function BlocTypeDeSaisie({
  valeur,
  poser,
  surReprise,
}: {
  valeur: Ordonnance;
  poser: (champ: keyof Ordonnance, valeur: string) => void;
  surReprise: () => void;
}) {
  const TYPES: { code: TypeRevision; libelle: string }[] = [
    { code: "renouvellement", libelle: TYPE_RENOUVELLEMENT },
    { code: "correction", libelle: TYPE_CORRECTION },
  ];

  return (
    <fieldset role="radiogroup" aria-labelledby="ord-type-legende">
      <legend id="ord-type-legende" className="text-sm font-medium">
        {LEGENDE_TYPE_SAISIE}
      </legend>
      <div className="mt-2 flex flex-wrap items-center gap-6">
        {TYPES.map((type) => (
          <label key={type.code} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="ord-type-saisie"
              value={type.code}
              checked={valeur.type_revision === type.code}
              onChange={() => poser("type_revision", type.code)}
            />
            {type.libelle}
          </label>
        ))}
      </div>

      {valeur.type_revision === "renouvellement" ? (
        <Button type="button" variant="ghost" className="mt-2" onClick={surReprise}>
          {ACTION_REPRENDRE}
        </Button>
      ) : null}

      {valeur.type_revision === "correction" ? (
        <div className="mt-3 flex flex-col gap-1">
          <Label htmlFor="ord-motif">{LABEL_MOTIF}</Label>
          <Textarea
            id="ord-motif"
            className="max-w-prose"
            value={valeur.motif_revision}
            onChange={(evenement) => poser("motif_revision", evenement.target.value)}
          />
          <p className="max-w-prose text-xs text-muted-foreground">{AIDE_MOTIF}</p>
        </div>
      ) : null}
    </fieldset>
  );
}

/**
 * Source, prescripteur et date.
 *
 * `Source` n'a **aucun defaut** : une source pre-selectionnee est une
 * affirmation clinique que personne n'a faite. Et en refraction opticien, le
 * champ `Prescripteur` n'est **pas rendu** — il n'y a pas de prescripteur a
 * nommer — avec une aide qui le dit plutot qu'un champ desactive qui laisserait
 * croire a un droit manquant.
 */
function BlocSource({
  valeur,
  envoyer,
  evaluer,
  poser,
  remarquesDe,
}: {
  valeur: Ordonnance;
  envoyer: (action: ActionDeSaisie) => void;
  evaluer: () => void;
  poser: (champ: keyof Ordonnance, valeur: string) => void;
  remarquesDe: (champ: string) => RemarquesDuChamp;
}) {
  const surSource = remarquesDe("source");
  const surPrescripteur = remarquesDe("prescripteur");

  return (
    <div className="flex flex-col gap-4">
      <fieldset role="radiogroup" aria-labelledby="ord-source-legende">
        <legend id="ord-source-legende" className="text-sm font-medium">
          {LEGENDE_SOURCE}
        </legend>
        <div className="mt-2 flex flex-wrap items-center gap-6">
          {[
            { code: "ordonnance_medicale" as const, libelle: SOURCE_MEDICALE },
            { code: "refraction_opticien" as const, libelle: SOURCE_OPTICIEN },
          ].map((option) => (
            <label key={option.code} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="ord-source"
                value={option.code}
                checked={valeur.source === option.code}
                onChange={() => {
                  envoyer({ type: "source", source: option.code });
                }}
              />
              {option.libelle}
            </label>
          ))}
        </div>
        {surSource.faute === undefined ? null : (
          <p id="ord-source-faute" className="mt-2 text-xs text-destructive">
            {surSource.faute}
          </p>
        )}
        {surSource.avertissement === undefined ? null : (
          <p
            id="ord-source-avertissement"
            role="status"
            className="mt-2 max-w-prose rounded-md border border-border bg-muted px-2 py-1 text-xs text-foreground"
          >
            {surSource.avertissement}
          </p>
        )}
      </fieldset>

      {valeur.source === "refraction_opticien" ? (
        <p className="max-w-prose text-xs text-muted-foreground">{AIDE_OPTICIEN}</p>
      ) : (
        <div className="flex flex-col gap-1">
          <Label htmlFor="ord-prescripteur">{LABEL_PRESCRIPTEUR}</Label>
          <Input
            id="ord-prescripteur"
            className="w-[320px]"
            autoComplete="off"
            value={valeur.prescripteur}
            onChange={(evenement) => poser("prescripteur", evenement.target.value)}
            onBlur={evaluer}
            aria-invalid={surPrescripteur.faute === undefined ? undefined : true}
            aria-describedby={
              surPrescripteur.faute === undefined ? undefined : "ord-prescripteur-faute"
            }
          />
          {surPrescripteur.faute === undefined ? null : (
            <p id="ord-prescripteur-faute" className="text-xs text-destructive">
              {surPrescripteur.faute}
            </p>
          )}
        </div>
      )}

      <ChampDate
        identifiant="ord-date-prescription"
        label={LABEL_DATE_PRESCRIPTION}
        valeur={valeur.date_prescription}
        surChangement={(saisie) => poser("date_prescription", saisie)}
        surVerdict={() => evaluer()}
        futurInterdit
        messageFutur={MESSAGE_PRESCRIPTION_FUTURE}
        aujourdhui={aujourdhuiISO()}
        requis
      />
    </div>
  );
}

/**
 * `Magasin qui enregistre` — un CHAMP, et non l'invite pleine page de `03` 5.4.
 *
 * **C'est une extension deliberee de cette regle, pas un oubli.** 5.4 existe
 * parce que le *contenu* d'un ecran scope serait silencieusement faux — un
 * solde de caisse pour un magasin que personne n'a choisi. Ici le contenu est
 * transversal a l'affaire et correct, et c'est exactement **une valeur
 * enregistree** qui manque. Une invite pleine page pretendrait l'ecran
 * inutilisable alors qu'il ne l'est pas, et couterait un clic a chaque saisie.
 * Deviner, en revanche, reste refuse : sous « Tous les magasins », rien n'est
 * pre-selectionne et la soumission est refusee.
 *
 * Trois formes (20.9) : un seul magasin, aucun controle — le precedent `03`
 * 7.3B, pas de decision, pas de controle ; jusqu'a quatre, un `radiogroup` ;
 * au-dela, un combobox qui porte `aria-labelledby` vers son `<label>` visible,
 * ce qui est la lecon D-1 ecrite en un attribut.
 */
function BlocMagasin({
  valeur,
  magasins,
  poser,
  evaluer,
  remarquesDe,
}: {
  valeur: Ordonnance;
  magasins: { id: number; code: string; nom: string }[];
  poser: (champ: keyof Ordonnance, valeur: string) => void;
  evaluer: () => void;
  remarquesDe: (champ: string) => RemarquesDuChamp;
}) {
  const remarque = remarquesDe("magasin");
  const choisir = (identifiant: string) => {
    poser("magasin", identifiant);
    evaluer();
  };

  if (magasins.length === 1) {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium">{LABEL_MAGASIN}</span>
        <p className="text-sm">{magasins[0].nom}</p>
        <p className="max-w-prose text-xs text-muted-foreground">{AIDE_MAGASIN}</p>
      </div>
    );
  }

  if (magasins.length > MAGASINS_AVANT_COMBOBOX) {
    return (
      <div className="flex flex-col gap-1">
        <Label id="ord-magasin-label" htmlFor="ord-magasin">
          {LABEL_MAGASIN}
        </Label>
        <select
          id="ord-magasin"
          aria-labelledby="ord-magasin-label"
          className="h-9 w-[240px] rounded-md border border-input bg-transparent px-3 text-sm"
          value={valeur.magasin}
          onChange={(evenement) => choisir(evenement.target.value)}
          aria-invalid={remarque.faute === undefined ? undefined : true}
        >
          <option value="" />
          {magasins.map((magasin) => (
            <option key={magasin.id} value={String(magasin.id)}>
              {magasin.nom}
            </option>
          ))}
        </select>
        <p className="max-w-prose text-xs text-muted-foreground">{AIDE_MAGASIN}</p>
        {remarque.faute === undefined ? null : (
          <p className="text-xs text-destructive">{remarque.faute}</p>
        )}
      </div>
    );
  }

  return (
    <fieldset role="radiogroup" aria-labelledby="ord-magasin-legende">
      <legend id="ord-magasin-legende" className="text-sm font-medium">
        {LABEL_MAGASIN}
      </legend>
      <div className="mt-2 flex flex-wrap items-center gap-6">
        {magasins.map((magasin) => (
          <label key={magasin.id} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="ord-magasin"
              value={String(magasin.id)}
              checked={valeur.magasin === String(magasin.id)}
              onChange={() => choisir(String(magasin.id))}
            />
            {magasin.nom}
          </label>
        ))}
      </div>
      <p className="mt-2 max-w-prose text-xs text-muted-foreground">{AIDE_MAGASIN}</p>
      {remarque.faute === undefined ? null : (
        <p className="mt-2 text-xs text-destructive">{remarque.faute}</p>
      )}
    </fieldset>
  );
}

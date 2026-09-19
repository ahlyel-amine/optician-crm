import { useId, useState } from "react";

import { EN_TETE_CSRF, lireCookie } from "@/api/client";
import { RequirePermission } from "@/auth/RequirePermission";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { messageChargementImpossible } from "@/etats/messages";
import { formaterDateHeure } from "@/format";

import {
  ACTION_AJOUTER_PHOTO,
  ACTION_VOIR_PHOTO,
  AIDE_PHOTO,
  ECHEC_TELEVERSEMENT,
  LABEL_PHOTO,
  MAUVAIS_TYPE,
  PHOTO_NE_SE_REMPLACE_PAS,
  QUOI_CHARGER_LA_PHOTO,
  imageTropLourde,
  photoAttacheeLe,
  titreDeLaPhoto,
} from "./messages";

/**
 * LA PHOTO DE L'ORDONNANCE — 04-UI-SPEC.md 22 (CLIENT-09).
 *
 * ---
 *
 * **Les octets viennent d'une route DRF authentifiee qui a deja resolu
 * `ordonnance.voir`** (plan 04-06). Jamais une adresse de media, jamais une
 * adresse pre-signee : le stockage n'en fabrique aucune, et sa methode d'URL
 * LEVE par conception. Donc `<img src>` est un chemin d'API, et un echec rend
 * le message global de `src/etats/messages.ts` — REUTILISE VERBATIM — plutot
 * qu'une icone d'image cassee, qui inviterait a chercher l'adresse directe
 * (T-04-65).
 *
 * ---
 *
 * **Le nom du fichier n'est affiche nulle part, et 22.2 a ete amendee pour le
 * dire.** Il n'est conserve ni sur le disque — le stockage fabrique un
 * identifiant aleatoire — ni en colonne, ni dans une erreur, parce qu'il porte
 * couramment le nom du patient (D-4-4). Ce qui reste comme controle de mauvaise
 * piece jointe est la vignette, plus la date d'attache : la vignette est de
 * toute facon le meilleur des deux, puisqu'elle montre le papier.
 *
 * ---
 *
 * **L'attache est a sens unique** (22.3). Une version enregistree sans photo
 * peut en recevoir une plus tard ; une version qui en porte une n'offre plus
 * aucun controle, et la phrase prend sa place (T-04-67).
 */

/** 10 Mo, verifies AVANT le televersement. Le serveur a la meme limite. */
const LIMITE_MO = 10;
const OCTETS_PAR_MO = 1024 * 1024;

/**
 * Les types acceptes. **Aucun document portable en phase 4** : il demanderait
 * une visionneuse, et le chemin documentaire appartient a la phase 9. Consigne
 * en D-4-3 de `deferred-items.md`, donc differe et non oublie.
 */
const TYPES_ACCEPTES = ["image/jpeg", "image/png", "image/webp", "image/heic"];
const EXTENSIONS_ACCEPTEES = [".jpg", ".jpeg", ".png", ".webp", ".heic"];

export const ACCEPT_PHOTO = TYPES_ACCEPTES.join(",");

/** Le chemin de l'API. Il n'existe pas d'autre facon d'atteindre les octets. */
export function cheminDeLaPhoto(idOrdonnance: number): string {
  return `/api/ordonnances/${String(idOrdonnance)}/photo/`;
}

/**
 * Le verdict d'un fichier choisi, rendu AVANT tout televersement.
 *
 * **Il ne cite jamais le nom du fichier** — c'est la moitie cliente de
 * T-04-66 — et il parle en megaoctets, jamais en octets et jamais en type MIME.
 */
export function verifierLeFichier(fichier: File): string | null {
  const parExtension = EXTENSIONS_ACCEPTEES.some((suffixe) =>
    fichier.name.toLowerCase().endsWith(suffixe),
  );
  // Un navigateur ne reconnait pas toujours le type de certaines images de
  // telephone et rend une chaine vide : l'extension sert alors de repli, et le
  // serveur reste seul juge des octets magiques (plan 04-06).
  const typeAcceptable =
    fichier.type === "" ? parExtension : TYPES_ACCEPTES.includes(fichier.type);
  if (!typeAcceptable) {
    return MAUVAIS_TYPE;
  }
  if (fichier.size > LIMITE_MO * OCTETS_PAR_MO) {
    // Arrondi AU-DESSUS : annoncer « 10 Mo » pour un fichier refuse a 10,4
    // ferait passer la limite pour un caprice.
    return imageTropLourde(Math.ceil(fichier.size / OCTETS_PAR_MO), LIMITE_MO);
  }
  return null;
}

/** Le televersement : `multipart`, avec le jeton anti-CSRF de la session. */
export async function televerserLaPhoto(
  idOrdonnance: number,
  fichier: File,
): Promise<void> {
  const corps = new FormData();
  // **`fichier`, le nom du champ du serialiseur du plan 04-06** — et non
  // `photo`, qui est le nom de la COLONNE. Les deux different, et le serveur
  // rend un 400 « Aucun fichier n'a été soumis. » sur le mauvais. Trouve en
  // televersant reellement contre la pile, pas par la suite : un `fetch`
  // double ne verifie pas ce que le serveur attend.
  corps.append("fichier", fichier);
  const jeton = lireCookie("csrftoken");
  const reponse = await fetch(cheminDeLaPhoto(idOrdonnance), {
    method: "POST",
    body: corps,
    credentials: "include",
    headers: jeton === null ? {} : { [EN_TETE_CSRF]: jeton },
  });
  if (!reponse.ok) {
    // **L'erreur ne porte PAS le nom du fichier**, ni ici ni plus haut : une
    // exception remontee telle quelle atteindrait la telemetrie.
    throw new Error(ECHEC_TELEVERSEMENT);
  }
}

export type ProprietesChoixDePhoto = {
  /** Le fichier retenu, ou `null`. L'appelant l'envoie APRES l'enregistrement. */
  fichier: File | null;
  surChoix: (fichier: File | null) => void;
  /** Un echec impose par l'appelant, par exemple un televersement refuse. */
  echec?: string | null;
};

/**
 * LE CONTROLE D'ATTACHE : une vraie `input[type=file]`, un `<label>` VISIBLE.
 *
 * Le glisser-deposer serait une amelioration ; le selecteur de fichier est le
 * contrat, et il est atteignable au clavier precisement parce que c'est une
 * vraie entree et non un bouton qui en simule une. Aucun attribut de capture :
 * photographier au comptoir est le travail de l'application Expo de la
 * phase 11.
 */
export function ChoixDePhoto({ fichier, surChoix, echec = null }: ProprietesChoixDePhoto) {
  const identifiant = useId();
  const [refus, setRefus] = useState<string | null>(null);
  const identifiantFaute = `${identifiant}-faute`;
  const affiche = echec ?? refus;

  const auChoix = (evenement: React.ChangeEvent<HTMLInputElement>) => {
    const choisi = evenement.target.files?.[0] ?? null;
    if (choisi === null) {
      setRefus(null);
      surChoix(null);
      return;
    }
    const verdict = verifierLeFichier(choisi);
    setRefus(verdict);
    surChoix(verdict === null ? choisi : null);
  };

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={identifiant}>{LABEL_PHOTO}</Label>
      <input
        id={identifiant}
        type="file"
        accept={ACCEPT_PHOTO}
        className="text-sm file:mr-4 file:rounded-md file:border file:border-border file:bg-secondary file:px-3 file:py-1.5 file:text-sm file:font-medium"
        aria-invalid={affiche !== null}
        aria-describedby={affiche === null ? undefined : identifiantFaute}
        onChange={auChoix}
      />
      <p className="max-w-prose text-xs text-muted-foreground">{AIDE_PHOTO}</p>
      {affiche === null ? null : (
        <p id={identifiantFaute} role="alert" className="text-sm text-destructive">
          {affiche}
        </p>
      )}
      {fichier === null ? null : (
        /* Le fichier retenu est confirme SANS son nom : la confirmation qui
           compte est la vignette, apres l'enregistrement. */
        <p className="text-xs text-muted-foreground">{ACTION_AJOUTER_PHOTO} ✓</p>
      )}
    </div>
  );
}

export type ProprietesPhotoDeLaVersion = {
  idOrdonnance: number;
  version: number;
  aUnePhoto: boolean;
  /** `photo_attachee_le`, tel que le serveur le sert. Il remplace le nom. */
  attacheeLe: string | null;
  /** Rejoue la liste apres une attache : la version porte alors son booleen. */
  surAttache: () => void;
};

/**
 * Ce qu'une carte de version montre de sa photo — ou de son absence.
 *
 * Deux etats, et aucun troisieme : **avec** une photo, la vignette, le
 * dialogue et la phrase qui dit que c'est definitif ; **sans**, le controle
 * d'attache, derriere `ordonnance.saisir`.
 */
export function PhotoDeLaVersion({
  idOrdonnance,
  version,
  aUnePhoto,
  attacheeLe,
  surAttache,
}: ProprietesPhotoDeLaVersion) {
  const [fichier, setFichier] = useState<File | null>(null);
  const [echec, setEchec] = useState<string | null>(null);
  const [illisible, setIllisible] = useState(false);

  if (!aUnePhoto) {
    return (
      <RequirePermission code="ordonnance.saisir">
        <div className="mt-4 flex flex-col gap-2 border-t border-border pt-4">
          <ChoixDePhoto
            fichier={fichier}
            echec={echec}
            surChoix={(choisi) => {
              setFichier(choisi);
              setEchec(null);
              if (choisi === null) {
                return;
              }
              void televerserLaPhoto(idOrdonnance, choisi)
                .then(() => {
                  setFichier(null);
                  surAttache();
                })
                .catch(() => setEchec(ECHEC_TELEVERSEMENT));
            }}
          />
        </div>
      </RequirePermission>
    );
  }

  const source = cheminDeLaPhoto(idOrdonnance);

  return (
    <div
      // L'IMPRESSION NE PREND PAS LA PHOTO : une photo de telephone en niveaux
      // de gris coute de l'encre et ne prouve rien. La photo est une preuve
      // tenue dans le dossier, pas sur le ticket du comptoir (21.5).
      data-photo-ordonnance=""
      className="mt-4 flex items-start gap-4 border-t border-border pt-4"
    >
      {illisible ? (
        <p className="text-sm text-muted-foreground">
          {messageChargementImpossible(QUOI_CHARGER_LA_PHOTO)}
        </p>
      ) : (
        <img
          data-testid="vignette-photo"
          src={source}
          alt=""
          className="size-24 rounded-md border border-border object-cover"
          onError={() => setIllisible(true)}
        />
      )}
      <div className="flex flex-col gap-2">
        {attacheeLe === null ? null : (
          <p className="text-xs text-muted-foreground">
            {photoAttacheeLe(formaterDateHeure(attacheeLe))}
          </p>
        )}
        <Dialog>
          <DialogTrigger asChild>
            <Button type="button" variant="outline" size="sm">
              {ACTION_VOIR_PHOTO}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              {/* L'image porte `alt=""` : elle ne dit rien d'exploitable a un
                  lecteur d'ecran. LE TITRE, lui, le dit. */}
              <DialogTitle>{titreDeLaPhoto(version)}</DialogTitle>
            </DialogHeader>
            <img src={source} alt="" className="max-h-[90vh] w-full object-contain" />
          </DialogContent>
        </Dialog>
        <p className="max-w-prose text-xs text-muted-foreground">
          {PHOTO_NE_SE_REMPLACE_PAS}
        </p>
      </div>
    </div>
  );
}

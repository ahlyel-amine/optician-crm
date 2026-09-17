import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clientApi, reinitialiserLeClient } from "@/api/client";
import { BanniereDeLien } from "@/etats/BanniereDeLien";
import { MESSAGE_LIEN_PERDU } from "@/etats/messages";
import {
  lienDisponible,
  signalerLienRetabli,
  signalerPanneDeLien,
} from "@/etats/reseau";

/* ---------------------------------------------------------------------------
 * La banniere de coupure, et la seule question qui la rend utile : QUAND.
 *
 * `03-UI-SPEC.md` 8.6 en fait un contrat, pas une decoration — tant qu'elle est
 * levee, tout controle d'ecriture est desactive, et les phases 4 a 12
 * consultent `useLienDisponible()`. Donc une banniere qui se leve a tort n'est
 * pas un defaut cosmetique : c'est le produit entier qui se croit hors ligne.
 *
 * Le defaut corrige ici a ete trouve par une personne dans un navigateur, pas
 * par cette suite : la banniere clignotait a chaque rechargement et a chaque
 * changement de route. react-query annule ses requetes au demontage du dernier
 * observateur — donc a chaque navigation — et l'ancien `onError` comptait cet
 * abandon comme une coupure.
 *
 * Ces tests tiennent en tenaille. Le premier interdit de crier au loup ; le
 * second interdit la correction paresseuse qui ferait passer le premier en ne
 * signalant plus jamais rien. Aucun des deux n'est suffisant seul.
 * ------------------------------------------------------------------------- */

/**
 * `enLigne` est un etat de MODULE : il survit d'un test au suivant.
 *
 * Sans cette remise a zero, le test 2 laisse le lien tombe et le test 3 part
 * d'un etat qu'il n'a pas choisi — le mode de defaillance ou une suite passe
 * dans un ordre et echoue dans un autre.
 */
beforeEach(() => {
  signalerLienRetabli();
  reinitialiserLeClient();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  signalerLienRetabli();
});

/** Un `fetch` qui avorte la requete en cours, puis rejette comme le ferait le navigateur. */
function poserUnAbandon(controleur: AbortController, erreur: unknown): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      controleur.abort();
      throw erreur;
    }),
  );
}

/** Un `fetch` qui echoue au transport : DNS, socket, TLS. Rien n'est avorte. */
function poserUnEchecDeTransport(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }),
  );
}

/**
 * Joue un appel reel a travers `clientApi` — intergiciels compris.
 *
 * Passer par le vrai client est le point : c'est `intergicielDeSession.onError`
 * qui est sous test, et un double du client ne le traverserait pas. Le rejet
 * est avale ici parce que le sujet n'est pas ce que voit l'appelant, c'est ce
 * que devient l'etat du lien.
 */
async function appeler(signal?: AbortSignal): Promise<void> {
  await act(async () => {
    await clientApi.GET("/api/auth/moi/", signal ? { signal } : {}).catch(() => undefined);
  });
}

describe("l'etat du lien face a une requete avortee", () => {
  it("test_app01_une_requete_avortee_ne_leve_pas_la_banniere_de_lien_perdu", async () => {
    render(<BanniereDeLien />);
    const controleur = new AbortController();
    poserUnAbandon(
      controleur,
      new DOMException("The operation was aborted.", "AbortError"),
    );

    await appeler(controleur.signal);

    expect(lienDisponible()).toBe(true);
    expect(screen.queryByText(MESSAGE_LIEN_PERDU)).toBeNull();
  });

  it("test_app01_un_abandon_sans_DOMException_est_reconnu_aussi", async () => {
    // Tous les environnements ne rejettent pas avec une `DOMException` : certains
    // rendent un `Error` simple dont seul le `name` porte l'information.
    render(<BanniereDeLien />);
    const controleur = new AbortController();
    const erreur = new Error("aborted");
    erreur.name = "AbortError";
    poserUnAbandon(controleur, erreur);

    await appeler(controleur.signal);

    expect(lienDisponible()).toBe(true);
    expect(screen.queryByText(MESSAGE_LIEN_PERDU)).toBeNull();
  });

  it("test_app01_un_abandon_ne_retablit_pas_un_lien_deja_tombe", async () => {
    // L'abandon ne touche l'etat dans AUCUN des deux sens : il n'est pas une
    // observation du lien, c'est une observation qui n'a pas eu lieu.
    signalerPanneDeLien();
    render(<BanniereDeLien />);
    expect(screen.getByText(MESSAGE_LIEN_PERDU)).toBeTruthy();

    const controleur = new AbortController();
    poserUnAbandon(
      controleur,
      new DOMException("The operation was aborted.", "AbortError"),
    );
    await appeler(controleur.signal);

    expect(lienDisponible()).toBe(false);
    expect(screen.getByText(MESSAGE_LIEN_PERDU)).toBeTruthy();
  });
});

describe("l'etat du lien face a une vraie coupure", () => {
  it("test_app01_un_echec_de_transport_leve_bien_la_banniere", async () => {
    // Le garde-fou. Sans lui, « ne plus jamais signaler de coupure » ferait
    // passer les trois tests ci-dessus, et le produit mentirait dans l'autre
    // sens — controles d'ecriture actifs sur un lien mort.
    render(<BanniereDeLien />);
    poserUnEchecDeTransport();

    await appeler();

    expect(lienDisponible()).toBe(false);
    expect(screen.getByText(MESSAGE_LIEN_PERDU)).toBeTruthy();
  });
});

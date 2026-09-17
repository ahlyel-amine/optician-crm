import type { CatalogueOffrable, LigneDeDroit } from "@/api/requetes";

import {
  LigneDroit,
  aideDePersonnalisation,
  type EtatInterrupteur,
} from "./LigneDroit";
import { SelecteurDeMagasinDesDroits } from "./SelecteurDeMagasinDesDroits";

/**
 * `03-UI-SPEC.md` 7.4 — la liste des droits, le coeur de l'ecran.
 *
 * **Tout vient du catalogue serveur** : les sections, leur ordre, les libelles,
 * les explications et la carte des prerequis. La SPA ne code aucun libelle de
 * permission en dur, et il n'y a **aucune branche de filtrage** ici — le
 * catalogue arrive deja intersecte avec ce que l'appelant peut accorder
 * (plan 03-09), donc rendre tout ce qu'on recoit EST la garantie de 7.7. Un
 * filtrage cote client laisserait les codes caches dans la reponse, ce qui est
 * precisement ce que « absent, pas grise » refuse.
 *
 * Consequence directe : un code ajoute en phase 8 apparait ici sans qu'une
 * ligne de ce fichier change, et un libelle ne peut jamais deriver de son code.
 */

/** La banniere d'un compte neuf. Fail-closed, en miroir de `Acces.ANONYME`. */
function banniereAucunDroit(prenom: string): string {
  return `Ce compte n'a encore aucun droit. ${prenom} pourra se connecter, mais ne verra rien.`;
}

/**
 * La phrase de temporalite, **permanente** au pied de la section.
 *
 * Elle repond a la question de support la plus previsible de l'ecran, et elle
 * est vraie : les droits sont relus depuis le plan de controle a chaque requete
 * (plan 03-05), et un test nomme du serveur le verifie de bout en bout.
 */
const LIGNE_DE_TEMPORALITE =
  "Les changements prennent effet immédiatement, dès l'action suivante de l'utilisateur. Il n'a pas besoin de se reconnecter.";

/** Au-dela de quatre magasins, la phrase de portee compte au lieu de nommer. */
const MAGASINS_NOMMES_AU_PLUS = 4;

export function phraseDePortee(noms: readonly string[]): string | null {
  if (noms.length === 0) {
    return null;
  }
  if (noms.length === 1) {
    return `Ces droits s'appliquent au magasin ${noms[0]}.`;
  }
  if (noms.length <= MAGASINS_NOMMES_AU_PLUS) {
    return `Ces droits s'appliquent à tous les magasins de ce compte (${noms.join(", ")}).`;
  }
  return `Ces droits s'appliquent à ses ${String(noms.length)} magasins.`;
}

export type ProprietesSectionDroits = {
  catalogue: CatalogueOffrable;
  /** L'etat de chaque code, tel que le serveur l'a resolu. */
  lignes: Readonly<Record<string, LigneDeDroit>>;
  /** Les codes de magasins accordes a ce compte, dans la portee de l'appelant. */
  magasinsAccordes: readonly string[];
  prenom: string;
  /** Les notes en ligne de la cascade, clees par code (7.6). */
  notes?: Readonly<Record<string, string>>;
  /** Les echecs de bascule, clees par code — **sur la ligne**, jamais en toast. */
  erreurs?: Readonly<Record<string, string>>;
  surBascule: (code: string, accorde: boolean) => void;
  /**
   * Le magasin sur lequel les bascules portent. `null` === `Tous`.
   *
   * Il vit dans la fiche et non ici, parce que c'est la fiche qui construit le
   * corps de la requete : le mode et la portee envoyee sur le fil doivent etre
   * lus au meme endroit, sans quoi ils peuvent diverger (T-03.1-03).
   */
  magasinChoisi: string | null;
  surChoixDeMagasin: (code: string | null) => void;
  /** La note d'un magasin ajoute plus tard (7.5). */
  noteDeSection?: string;
};

export function SectionDroits({
  catalogue,
  lignes,
  magasinsAccordes,
  prenom,
  notes,
  erreurs,
  surBascule,
  magasinChoisi,
  surChoixDeMagasin,
  noteDeSection,
}: ProprietesSectionDroits) {
  const nomsParCode = new Map(
    catalogue.magasins.map((magasin) => [magasin.code, magasin.nom]),
  );
  const noms = magasinsAccordes.map((code) => nomsParCode.get(code) ?? code);
  const magasinsDuCompte = magasinsAccordes.map((code) => ({
    code,
    nom: nomsParCode.get(code) ?? code,
  }));
  const nomDuMagasinChoisi =
    magasinChoisi === null ? null : (nomsParCode.get(magasinChoisi) ?? magasinChoisi);
  /*
    La phrase de portee SUIT le mode, par reemploi de `phraseDePortee` et sans
    copie nouvelle : appelee avec un seul nom, elle rend deja
    `Ces droits s'appliquent au magasin Anfa.` Une seconde phrase pour dire la
    meme chose serait une seconde chose a garder juste.
  */
  const portee = phraseDePortee(
    nomDuMagasinChoisi === null ? noms : [nomDuMagasinChoisi],
  );
  const aucunDroit = Object.values(lignes).every((ligne) => ligne.etat === "inactif");

  return (
    <section aria-labelledby="titre-droits" className="mt-8">
      <h2 id="titre-droits" className="text-lg font-semibold">
        Droits
      </h2>
      {portee === null ? null : (
        <p className="mt-1 text-sm text-muted-foreground">{portee}</p>
      )}

      {/*
        Le selecteur est monte MEME a moins de deux magasins : il rend `null`
        dans ce cas, mais son effet de revalidation doit continuer de tourner
        pour faire retomber une selection perimee sur `Tous` (T-03.1-04).
      */}
      <SelecteurDeMagasinDesDroits
        magasins={magasinsDuCompte}
        choisi={magasinChoisi}
        surChoix={surChoixDeMagasin}
      />

      {aucunDroit ? (
        <p className="mt-3 rounded-md border border-border bg-muted/40 p-3 text-sm">
          {banniereAucunDroit(prenom)}
        </p>
      ) : null}

      {noteDeSection === undefined ? null : (
        <p className="mt-3 rounded-md border border-border p-3 text-sm" role="status">
          {noteDeSection}
        </p>
      )}

      {catalogue.sections.map((section) => (
        <div key={section.titre} className="mt-6">
          <h3 className="text-sm font-semibold">{section.titre}</h3>
          <ul className="mt-2">
            {section.droits.map((droit) => {
              const ligne = lignes[droit.code];
              /*
                Le badge suit l'etat SERVEUR, dans les deux modes : il dit
                « ce droit n'est pas le meme partout », et cette phrase reste
                vraie quand on n'en regarde qu'un.
              */
              const personnalise = ligne?.etat === "mixte";
              /*
                **En mode nomme, l'etat est une APPARTENANCE, pas un etat.**
                `lignes[].magasins` porte deja l'ensemble des magasins ou le
                droit est detenu ; consulter cet ensemble n'est pas calculer un
                etat, donc cela n'ecrit PAS une quatrieme variante de
                `services.etat_de` — la regle d'etat de 7.5 reste ecrite une
                seule fois, cote serveur. Corollaire : un magasin unique ne peut
                pas etre `mixte`.
              */
              const etat: EtatInterrupteur =
                magasinChoisi === null
                  ? ((ligne?.etat ?? "inactif") as EtatInterrupteur)
                  : ligne?.magasins.includes(magasinChoisi)
                    ? "actif"
                    : "inactif";
              /*
                `Personnalisé : 2 magasins sur 3` ne se lit qu'en mode `Tous` :
                en mode nomme, le denominateur affiche serait celui d'une
                portee qu'on ne regarde pas.
              */
              const aide =
                magasinChoisi === null && personnalise && ligne !== undefined
                  ? aideDePersonnalisation(
                      ligne.magasins.length,
                      magasinsAccordes.length,
                    )
                  : undefined;
              return (
                <LigneDroit
                  key={droit.code}
                  code={droit.code}
                  libelle={droit.libelle}
                  explication={droit.explication}
                  etat={etat}
                  note={notes?.[droit.code]}
                  erreur={erreurs?.[droit.code]}
                  personnalise={personnalise}
                  aide={aide}
                  // En mode `Tous`, un parent MIXTE s'allume : cliquer dessus
                  // met tous les magasins a l'allumage, et le toast
                  // d'annulation le dit (7.5). L'autre lecture — « eteindre
                  // tout » — ferait d'un clic sur un etat intermediaire une
                  // revocation partielle silencieuse. En mode nomme, la meme
                  // expression est une bascule binaire ordinaire.
                  onBascule={() => surBascule(droit.code, etat !== "actif")}
                />
              );
            })}
          </ul>
        </div>
      ))}

      <p className="mt-6 text-xs text-muted-foreground">{LIGNE_DE_TEMPORALITE}</p>
    </section>
  );
}

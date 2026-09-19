import { useEffect, useId, useState } from "react";

import { Link, useParams } from "react-router-dom";

import { $api } from "@/api/requetes";
import { useAuth } from "@/auth/AuthProvider";
import { ChampDate } from "@/champs/ChampDate";
import { depuisISO, versISO, type VerdictDate } from "@/champs/dates";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { CarteDechec } from "@/etats/CarteDechec";
import { formaterDateCourte, formaterTelephone } from "@/format";

import {
  BlocCorrection,
  type EcartServi,
  type OeilServi,
} from "./ordonnances/CarteVersion";
import {
  ACTION_VOIR_HISTORIQUE,
  TITRE_DERNIERE,
} from "./ordonnances/messages";
import { BoutonDeSaisie } from "./ordonnances/HistoriqueOrdonnances";
import {
  ECHEC_ENREGISTREMENT_DU_CHAMP,
  LABEL_ADRESSE,
  LABEL_CLIENT_DEPUIS,
  LABEL_DATE_NAISSANCE,
  LABEL_NOM,
  LABEL_NOTES,
  LABEL_TELEPHONE,
  MESSAGE_CHARGEMENT,
  QUOI_CHARGER_LA_FICHE,
  TITRE_COORDONNEES,
} from "./messages";

/**
 * LA FICHE CLIENT — 04-UI-SPEC.md 19 (CLIENT-01, CLIENT-06).
 *
 * Deux regions, et une troisieme dont l'ABSENCE est la decision.
 *
 * **Region A — Coordonnees**, en edition sur place comme `03` 7.3A :
 * enregistrement par champ au blur, l'echec rendu SUR CE CHAMP et jamais en
 * toast. Un toast d'echec d'ecriture disparait et laisse une valeur que
 * l'opticien croit enregistree. Sans `client.modifier`, les champs se rendent
 * en valeurs statiques — **pas en entrees desactivees**, qui apprendraient
 * qu'un pouvoir existe et qu'il manque.
 *
 * **Region B — Derniere ordonnance**, presente UNIQUEMENT quand
 * `resume_ordonnance` est dans la charge utile. C'est un champ PROTEGE au
 * registre de projection (plan 04-05) : le serveur retire la cle a qui ne
 * detient pas `ordonnance.voir`, et cet ecran n'ajoute **aucune branche
 * cliente** — il rend ce qui est present, comme `colonnesVisiblesSurLignes` le
 * fait deja pour la liste. La cle ABSENTE et la valeur nulle se distinguent :
 * l'une dit « vous n'avez pas ce droit », l'autre « ce client n'a pas
 * d'ordonnance ».
 *
 * Elle est rendue par `BlocCorrection`, donc par `LigneDeCorrection` — LE
 * composant qui rend une correction, partout.
 *
 * **Region C — Achats : pas construite, et l'emplacement est vide EXPRES.**
 * CLIENT-02 (« voir l'historique d'achats complet d'un client ») et le critere
 * 1 de la feuille de route ont besoin des VENTES, qui sont la phase 6 : il n'y
 * a rien a montrer et il ne peut rien y avoir. La phase 4 livre donc la fiche
 * avec l'emplacement et sans l'onglet, et CLIENT-02 reste non cochee — meme
 * discipline que les plans 03-05 a 03-10, qui n'ont pas coche leurs exigences
 * avant l'existence de leur moitie interface.
 */
export function FicheClient() {
  const { id = "" } = useParams();
  const identifiant = Number.parseInt(id, 10);
  const { permissions } = useAuth();
  const modifiable = permissions.includes("client.modifier");

  const client = $api.useQuery("get", "/api/clients/{id}/", {
    params: { path: { id: identifiant } },
  });

  if (client.isError) {
    return (
      <CarteDechec
        quoi={QUOI_CHARGER_LA_FICHE}
        reessayer={() => void client.refetch()}
      />
    );
  }

  if (client.isPending) {
    return <p className="text-sm text-muted-foreground">{MESSAGE_CHARGEMENT}</p>;
  }

  const fiche = client.data as unknown as Record<string, unknown>;

  return (
    <div className="flex flex-col gap-8">
      <Coordonnees
        identifiant={identifiant}
        fiche={fiche}
        modifiable={modifiable}
        surEnregistrement={() => void client.refetch()}
      />
      <DerniereOrdonnance identifiant={identifiant} fiche={fiche} />
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * Region A — les coordonnees, en edition sur place
 * ------------------------------------------------------------------------- */

type ProprietesCoordonnees = {
  identifiant: number;
  fiche: Record<string, unknown>;
  modifiable: boolean;
  surEnregistrement: () => void;
};

/** Les champs modifiables sur place, dans l'ordre du papier. */
const CHAMPS_TEXTE = [
  { cle: "nom", label: LABEL_NOM, lignes: false },
  { cle: "telephone", label: LABEL_TELEPHONE, lignes: false },
  { cle: "adresse", label: LABEL_ADRESSE, lignes: false },
  { cle: "notes", label: LABEL_NOTES, lignes: true },
] as const;

function Coordonnees({
  identifiant,
  fiche,
  modifiable,
  surEnregistrement,
}: ProprietesCoordonnees) {
  const modification = $api.useMutation("patch", "/api/clients/{id}/");
  const [echecs, setEchecs] = useState<Record<string, boolean>>({});

  const enregistrer = (cle: string, valeur: unknown) => {
    setEchecs((precedents) => ({ ...precedents, [cle]: false }));
    modification.mutate(
      {
        params: { path: { id: identifiant } },
        body: { [cle]: valeur } as never,
      },
      {
        onSuccess: () => surEnregistrement(),
        // L'ECHEC EST RENDU SUR LE CHAMP, jamais en toast (`03` 7.8).
        onError: () => setEchecs((precedents) => ({ ...precedents, [cle]: true })),
      },
    );
  };

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-xl font-semibold">{TITRE_COORDONNEES}</h2>

      <div className="grid gap-4 sm:grid-cols-2">
        {CHAMPS_TEXTE.map((champ) => (
          <ChampEnPlace
            key={champ.cle}
            label={champ.label}
            valeur={typeof fiche[champ.cle] === "string" ? (fiche[champ.cle] as string) : ""}
            lignes={champ.lignes}
            modifiable={modifiable}
            echec={echecs[champ.cle] === true}
            surEnregistrement={(valeur) => enregistrer(champ.cle, valeur)}
          />
        ))}

        <DateDeNaissance
          valeur={typeof fiche.date_naissance === "string" ? fiche.date_naissance : ""}
          modifiable={modifiable}
          echec={echecs.date_naissance === true}
          surEnregistrement={(iso) => enregistrer("date_naissance", iso)}
        />

        {/* `Client depuis` est en LECTURE SEULE : c'est la date de creation de
            la fiche, pas une donnee saisie. */}
        <div>
          <p className="text-sm font-medium">{LABEL_CLIENT_DEPUIS}</p>
          <p className="mt-2 text-sm tabular-nums">
            {typeof fiche.created_at === "string"
              ? formaterDateCourte(fiche.created_at)
              : ""}
          </p>
        </div>
      </div>
    </section>
  );
}

type ProprietesChampEnPlace = {
  label: string;
  valeur: string;
  lignes: boolean;
  modifiable: boolean;
  echec: boolean;
  surEnregistrement: (valeur: string) => void;
};

/**
 * Un champ enregistre AU BLUR, et seulement s'il a change.
 *
 * Le telephone se rend par le formateur partage quand il n'est pas modifiable —
 * jamais par une interpolation locale — pour la meme raison que la colonne de
 * la liste : deux mises en forme d'un meme numero divergent.
 */
function ChampEnPlace({
  label,
  valeur,
  lignes,
  modifiable,
  echec,
  surEnregistrement,
}: ProprietesChampEnPlace) {
  const identifiant = useId();
  const [saisie, setSaisie] = useState(valeur);

  // La valeur servie fait foi des que le serveur a reparle.
  useEffect(() => setSaisie(valeur), [valeur]);

  if (!modifiable) {
    return (
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="mt-2 text-sm">
          <bdi>{label === LABEL_TELEPHONE ? formaterTelephone(valeur) : valeur}</bdi>
        </p>
      </div>
    );
  }

  const auBlur = () => {
    if (saisie !== valeur) {
      surEnregistrement(saisie);
    }
  };

  const identifiantFaute = `${identifiant}-faute`;

  return (
    <div>
      <Label htmlFor={identifiant}>{label}</Label>
      {lignes ? (
        <Textarea
          id={identifiant}
          className="mt-2"
          value={saisie}
          aria-invalid={echec}
          aria-describedby={echec ? identifiantFaute : undefined}
          onChange={(evenement) => setSaisie(evenement.target.value)}
          onBlur={auBlur}
        />
      ) : (
        <Input
          id={identifiant}
          className="mt-2"
          value={saisie}
          autoComplete="off"
          aria-invalid={echec}
          aria-describedby={echec ? identifiantFaute : undefined}
          onChange={(evenement) => setSaisie(evenement.target.value)}
          onBlur={auBlur}
        />
      )}
      {!echec ? null : (
        <p id={identifiantFaute} role="alert" className="mt-2 text-sm text-destructive">
          {ECHEC_ENREGISTREMENT_DU_CHAMP}
        </p>
      )}
    </div>
  );
}

function DateDeNaissance({
  valeur,
  modifiable,
  echec,
  surEnregistrement,
}: {
  valeur: string;
  modifiable: boolean;
  echec: boolean;
  surEnregistrement: (iso: string) => void;
}) {
  const [saisie, setSaisie] = useState(() => depuisISO(valeur));

  useEffect(() => setSaisie(depuisISO(valeur)), [valeur]);

  if (!modifiable) {
    return (
      <div>
        <p className="text-sm font-medium">{LABEL_DATE_NAISSANCE}</p>
        <p className="mt-2 text-sm tabular-nums">{depuisISO(valeur)}</p>
      </div>
    );
  }

  const auVerdict = (verdict: VerdictDate) => {
    if (!("valeur" in verdict)) {
      return;
    }
    const iso = verdict.valeur === "" ? "" : versISO(verdict.valeur);
    if (iso !== valeur) {
      surEnregistrement(iso);
    }
  };

  return (
    <div>
      <ChampDate
        label={LABEL_DATE_NAISSANCE}
        valeur={saisie}
        surChangement={setSaisie}
        surVerdict={auVerdict}
        faute={echec ? ECHEC_ENREGISTREMENT_DU_CHAMP : undefined}
      />
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * Region B — la derniere ordonnance, par la seule PRESENCE de la cle
 * ------------------------------------------------------------------------- */

function DerniereOrdonnance({
  identifiant,
  fiche,
}: {
  identifiant: number;
  fiche: Record<string, unknown>;
}) {
  const resume = fiche.resume_ordonnance;
  if (resume === undefined || resume === null || typeof resume !== "object") {
    // LA CLE EST ABSENTE, donc il n'y a rien a rendre. Aucune branche de droit
    // n'est ecrite ici, et c'est exactement ce que la conception de la phase 3
    // promettait : le serveur retire la cle, le client ne decide rien.
    return null;
  }

  const bloc = resume as Record<string, unknown>;
  const od = bloc.od as OeilServi;
  const og = bloc.og as OeilServi;
  const ecart: EcartServi = {
    ep_saisi: typeof bloc.ep_saisi === "string" ? bloc.ep_saisi : "",
    ep_binoculaire: lireDecimal(bloc.ep_binoculaire),
    ep_mono_od: lireDecimal(bloc.ep_mono_od),
    ep_mono_og: lireDecimal(bloc.ep_mono_og),
  };

  return (
    <section className="rounded-lg border border-border p-6">
      <h2 className="text-lg font-semibold">{TITRE_DERNIERE}</h2>
      <BlocCorrection className="mt-4 text-base" od={od} og={og} ecart={ecart} />
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <Button asChild type="button" variant="outline">
          <Link to={`/clients/${String(identifiant)}/ordonnances`}>
            {ACTION_VOIR_HISTORIQUE}
          </Link>
        </Button>
        {/* LE DERNIER MAILLON DE LA CHAINE HUMAINE vers l'ecran de saisie. Le
            plan 04-08 l'a nomme comme lui manquant : 18.2 interdit une colonne
            d'actions et un menu de ligne sur la liste, donc la carte de 19.3
            est le seul endroit legitime ou il pouvait etre pose. */}
        <BoutonDeSaisie identifiant={identifiant} />
      </div>
    </section>
  );
}

function lireDecimal(valeur: unknown): string | null {
  return typeof valeur === "string" ? valeur : null;
}

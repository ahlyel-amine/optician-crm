import { NavLink, Route, Routes, useParams } from "react-router-dom";

import { $api } from "@/api/requetes";
import { RequireDroit } from "@/auth/RequireDroit";
import { RequirePermission } from "@/auth/RequirePermission";
import { PageIntrouvable } from "@/etats/PageIntrouvable";
import { formaterDateCourte } from "@/format";
import { cn } from "@/lib/utils";

import { FicheClient } from "./FicheClient";
import {
  HistoriqueOrdonnances,
  VersionSeule,
} from "./ordonnances/HistoriqueOrdonnances";
import {
  NAV_DOSSIER,
  ONGLET_FICHE,
  ONGLET_ORDONNANCES,
  clientDepuis,
} from "./messages";

/**
 * LE DOSSIER D'UN CLIENT : son titre, ses onglets, et ses routes.
 *
 * ---
 *
 * **Ces onglets ne sont PAS dans le tableau `NAV`, et c'est ecrit pour qu'un
 * relecteur ne le « corrige » pas.** `03` 5.3 pose que le second niveau vit
 * dans le meme tableau que le premier, et la regle est juste — **pour des
 * sections**. Ceux-ci sont lies a un ENREGISTREMENT : leurs routes portent un
 * identifiant, et leur visibilite depend d'un droit que le predicat de `NAV`
 * connait deja, mais sur une RESSOURCE qu'il ne connait pas. Les y forcer
 * mettrait une route parametree dans un tableau de constantes.
 *
 * Ce qui EST herite, et c'est ce qui comptait, est le predicat : une entree
 * dont le code n'est pas detenu est **absente**, jamais grisee, et il n'y a
 * qu'un seul filtre — `RequirePermission`, le meme que la barre laterale.
 *
 * ---
 *
 * **Il n'y a pas d'onglet `Achats`, et ce n'est pas un oubli.** CLIENT-02 et le
 * critere 1 de la feuille de route ont besoin des ventes, qui sont la
 * **phase 6** : il n'y a rien a montrer et il ne peut rien y avoir. Un opticien
 * qui cliquerait et trouverait un vide permanent aurait appris que le produit
 * est casse — c'est l'argument `disponible: false` de `03` 5.3, un etage plus
 * bas. La phase 4 livre donc la fiche avec l'emplacement et sans l'onglet, et
 * CLIENT-02 **reste non cochee**.
 *
 * ---
 *
 * **La garde de route double l'onglet, et les deux disent des choses
 * differentes.** L'onglet retire est du confort ; `RequireDroit` sur la route
 * rend la 403 pleine page qui NOMME le droit manquant, a qui colle l'adresse
 * d'un collegue dans un message. Le controle reel reste la restriction de
 * queryset et la projection cote serveur.
 */
export function DossierClient() {
  const { id = "" } = useParams();
  const identifiant = Number.parseInt(id, 10);

  const client = $api.useQuery("get", "/api/clients/{id}/", {
    params: { path: { id: identifiant } },
  });

  const fiche = (client.data ?? {}) as Record<string, unknown>;
  const nom = typeof fiche.nom === "string" ? fiche.nom : "";
  const creeeLe = typeof fiche.created_at === "string" ? fiche.created_at : "";

  return (
    // 880px de largeur de contenu (19.1). Le dossier est une colonne de
    // lecture, pas un tableau de bord.
    <div className="mx-auto w-full max-w-[880px]">
      {/* Le nom du client est de la saisie utilisateur : `<bdi>` isole une
          graphie arabe du texte latin qui l'entoure. */}
      <h1 className="text-2xl font-semibold">
        <bdi>{nom}</bdi>
      </h1>
      {creeeLe === "" ? null : (
        <p className="mt-1 text-sm text-muted-foreground">
          {clientDepuis(formaterDateCourte(creeeLe))}
        </p>
      )}

      <nav aria-label={NAV_DOSSIER} className="mt-6 mb-6 flex gap-1 border-b border-border">
        <OngletDuDossier to={`/clients/${id}`} fin libelle={ONGLET_FICHE} />
        <RequirePermission code="ordonnance.voir">
          <OngletDuDossier
            to={`/clients/${id}/ordonnances`}
            libelle={ONGLET_ORDONNANCES}
          />
        </RequirePermission>
      </nav>

      <Routes>
        <Route index element={<FicheClient />} />
        <Route
          path="ordonnances"
          element={
            <RequireDroit code="ordonnance.voir">
              <HistoriqueOrdonnances />
            </RequireDroit>
          }
        />
        {/*
          21.4 — une version seule, pleine largeur, pour le LIEN et pour
          l'impression. La meme carte, les memes regles : `:version` est un
          numero de version et non une cle primaire, parce que c'est lui que
          l'opticien lit a l'ecran et colle dans un message.
        */}
        <Route
          path="ordonnances/:version"
          element={
            <RequireDroit code="ordonnance.voir">
              <VersionSeule />
            </RequireDroit>
          }
        />
        <Route path="*" element={<PageIntrouvable />} />
      </Routes>
    </div>
  );
}

function OngletDuDossier({
  to,
  libelle,
  fin = false,
}: {
  to: string;
  libelle: string;
  fin?: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={fin}
      className={({ isActive }) =>
        cn(
          "-mb-px border-b-2 px-3 py-2 text-sm transition-colors",
          "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
          isActive
            ? "border-primary font-semibold text-foreground"
            : "border-transparent text-muted-foreground hover:text-foreground",
        )
      }
    >
      {libelle}
    </NavLink>
  );
}

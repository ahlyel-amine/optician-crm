"""CLIENT-03/04/05/07 — la prescription, et les contraintes qui la tiennent en base.

Tout ce fichier est écrit contre **un** mode de défaillance, et ce n'est pas celui qu'on
attend : la valeur dangereuse n'est pas celle qui sort des bornes, c'est la valeur
**plausible et fausse**. Un axe de 90 saisi pour 9 passe tous les intervalles. Les
contraintes ci-dessous attrapent l'impossible ; le rattrapage du crédible est structurel —
CLIENT-06 garde lisible la version précédente (plan 04-05) et l'écran de relecture force
une seconde lecture (plan 04-08).

Aucun nombre clinique n'est écrit ici. Ils viennent tous de `bornes.BORNES`, et
`tests/test_optique.py::test_client07_les_bornes_vivent_a_un_seul_endroit` lit l'AST de ce
module pour le prouver.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import F, Q, Value
from django.db.models.functions import Mod
from django.db.models.lookups import Exact

from domaine.ordonnances.bornes import BORNES, BORNES_ENTIERES
from domaine.ordonnances.optique import canonicaliser_axe
from domaine.ordonnances.stockage import stockage_des_photos

#: Le zéro, nommé une fois. Ce n'est pas une borne — c'est la frontière entre « pas
#: d'astigmatisme » et « astigmatisme mesuré », et elle ne bougera jamais.
ZERO = Decimal("0")


class SourceOrdonnance(models.TextChoices):
    """CLIENT-05 — d'où viennent ces valeurs, et **sans valeur par défaut**.

    La distinction n'est pas administrative : une ordonnance médicale engage un
    prescripteur nommé et ouvre le remboursement AMO ; une réfraction d'opticien est une
    mesure faite au comptoir. Un défaut choisirait à la place de l'opticien, et la
    mauvaise moitié du temps il choisirait celle qui affirme qu'un médecin a prescrit.
    """

    MEDICALE = "ordonnance_medicale", "Ordonnance médicale"
    REFRACTION = "refraction_opticien", "Réfraction opticien"


class TypeRevision(models.TextChoices):
    """Pourquoi une nouvelle version existe. Vide sur la première version d'un client."""

    RENOUVELLEMENT = "renouvellement", "Renouvellement"
    CORRECTION = "correction", "Correction d'une erreur de saisie"


class EcartPupillaireSaisi(models.TextChoices):
    """Ce qui a été **écrit sur l'ordonnance**, pas ce qu'on en déduit."""

    BINOCULAIRE = "binoculaire", "Binoculaire"
    MONOCULAIRE = "monoculaire", "Monoculaire (par œil)"
    LES_DEUX = "les_deux", "Les deux"


#: Quelle borne gouverne quelles colonnes. Le seul endroit qui fait le lien entre le
#: vocabulaire clinique de `BORNES` et le nom des colonnes ; les contraintes se déduisent
#: de cette table par compréhension, donc ajouter une colonne d'œil ajoute sa contrainte.
CHAMPS_PAR_BORNE: dict[str, tuple[str, ...]] = {
    "sphere": ("sphere_od", "sphere_og"),
    "cylindre": ("cylindre_od", "cylindre_og"),
    "axe": ("axe_od", "axe_og"),
    "addition": ("addition_od", "addition_og"),
    "ep_binoculaire": ("ep_binoculaire",),
    "ep_monoculaire": ("ep_mono_od", "ep_mono_og"),
}

#: Les paires œil par œil dont l'axe dépend du cylindre.
PAIRES_CYLINDRE_AXE = (("cylindre_od", "axe_od"), ("cylindre_og", "axe_og"))


def _nombre(valeur):
    """Une valeur de `BORNES` en nombre exact : `Decimal` pour une chaîne, sinon l'entier.

    Les décimaux sont des chaînes dans `BORNES` pour traverser JSON sans passer par un
    binaire flottant (voir la docstring de `bornes.py`). La conversion se fait ici, une
    fois, du bon côté du fil.
    """
    return Decimal(valeur) if isinstance(valeur, str) else valeur


def _contraintes_cliniques() -> list[models.BaseConstraint]:
    """Les contraintes de bornes et de pas, **dérivées** de `BORNES` et jamais recopiées.

    Une contrainte par règle et par colonne, nommée, pour qu'une violation dise laquelle
    et pas seulement « une contrainte ». `NULL` traverse toutes ces expressions : en SQL
    un `CHECK` qui vaut `NULL` est satisfait, et la clause `isnull` explicite est là pour
    le lecteur plutôt que pour la base.
    """
    contraintes: list[models.BaseConstraint] = []

    for nom_borne, champs in CHAMPS_PAR_BORNE.items():
        borne = BORNES[nom_borne]
        minimum = _nombre(borne["min"])
        maximum = _nombre(borne["max"])
        pas = _nombre(borne["pas"])

        for champ in champs:
            contraintes.append(
                models.CheckConstraint(
                    condition=Q(**{f"{champ}__isnull": True})
                    | Q(**{f"{champ}__gte": minimum, f"{champ}__lte": maximum}),
                    name=f"ordonnance_{champ}_dans_les_bornes",
                    violation_error_message=(
                        f"{champ} doit rester entre {minimum} et {maximum}. "
                        "Au-delà, c'est une faute de frappe bien plus souvent qu'un "
                        "patient."
                    ),
                )
            )

            if nom_borne in BORNES_ENTIERES:
                # Le pas vaut une unité de la colonne : la contrainte serait toujours
                # vraie. Une garantie vide est pire qu'aucune, parce qu'elle se lit
                # comme une protection.
                continue

            contraintes.append(
                models.CheckConstraint(
                    condition=Q(**{f"{champ}__isnull": True})
                    | Q(Exact(Mod(F(champ), Value(pas)), Value(ZERO))),
                    name=f"ordonnance_{champ}_sur_la_grille",
                    violation_error_message=(
                        f"{champ} doit tomber sur un multiple de {pas}. Une valeur "
                        "intermédiaire est dans les bornes et n'existe sur aucune "
                        "ordonnance."
                    ),
                )
            )

    for cylindre, axe in PAIRES_CYLINDRE_AXE:
        contraintes.append(
            models.CheckConstraint(
                condition=Q(**{f"{cylindre}__isnull": True, f"{axe}__isnull": True})
                | Q(**{f"{cylindre}__isnull": False, f"{axe}__isnull": False}),
                name=f"ordonnance_{axe}_ssi_{cylindre}",
                violation_error_message=(
                    "Un axe sans cylindre ne veut rien dire, et un cylindre sans axe "
                    "n'est pas commandable. Les deux vont ensemble ou aucun des deux."
                ),
            )
        )
        contraintes.append(
            models.CheckConstraint(
                condition=~Q(**{cylindre: ZERO}),
                name=f"ordonnance_{cylindre}_non_nul_ou_absent",
                violation_error_message=(
                    "« Pas d'astigmatisme » et « astigmatisme de zéro dioptrie » sont "
                    "le même fait : il se range NULL, jamais zéro."
                ),
            )
        )

    contraintes.append(
        models.CheckConstraint(
            condition=(Q(source=SourceOrdonnance.MEDICALE) & ~Q(prescripteur=""))
            | (~Q(source=SourceOrdonnance.MEDICALE) & Q(prescripteur="")),
            name="ordonnance_prescripteur_ssi_source_medicale",
            violation_error_message=(
                "CLIENT-04/05 : une ordonnance médicale nomme son prescripteur, et une "
                "réfraction d'opticien n'en a pas — un prescripteur posé sur une "
                "réfraction affirme qu'un médecin a prescrit ce qui a été mesuré au "
                "comptoir."
            ),
        )
    )

    contraintes.append(
        models.UniqueConstraint(
            fields=["client", "version"],
            name="ordonnance_une_version_par_client",
            violation_error_message=(
                "Deux lignes portent le même numéro de version pour un client : "
                "l'historique de CLIENT-06 devient ambigu."
            ),
        )
    )

    return contraintes


class Ordonnance(models.Model):
    """Une prescription complète, à un instant, **immuable**.

    ## Immuable n'est pas « registre de deltas », et la nuance est celle de CLAUDE.md #4

    Le stock et la caisse tirent leur vérité d'une **agrégation** sur des deltas signés ;
    l'ordonnance tire la sienne d'une **sélection** sur des instantanés. Il n'existe pas
    d'« ordonnance compensatoire » : on n'additionne pas une ligne à −0,25 de sphère pour
    corriger une ligne à +2,00, parce que le résultat ne serait une prescription de
    personne. Ce que les deux partagent — et c'est ce dont la non-négociable parle
    réellement — c'est qu'**aucune colonne mutable ne porte la vérité, et qu'une
    correction est un ajout**. Ce qu'ils ne partagent pas, c'est l'arithmétique.

    Ce que l'immuabilité veut dire ici, concrètement : aucune route ne réécrit une ligne
    (plan 04-05), et une correction crée une version dont `supersede` désigne l'ancienne.
    La seule exception est la photo de l'ordonnance papier, qui peut passer de `null` à
    posée sur une version existante — décision Q5 du propriétaire : le scan arrive
    souvent au comptoir suivant, et forcer une version qui ne change aucune valeur
    polluerait l'historique que CLIENT-06 protège. On attache **une fois**.

    ## N'hérite PAS de `MagasinScopedModel`, et c'est une décision clinique (D-4a)

    Un gérant qui voit le client voit tout son historique d'ordonnances, quel que soit le
    comptoir qui l'a saisi. **La raison n'est pas ergonomique.** Filtrer l'ordonnance par
    magasin produit le danger que la recherche de phase a nommé : un gérant de Maârif qui
    ne voit pas l'ordonnance saisie à Anfa **en saisit une seconde**, et le client se
    retrouve avec deux historiques divergents pour un seul œil. Une duplication
    d'historique de prescription n'est pas une gêne d'interface — c'est un dossier
    clinique faux, sur une donnée de santé au sens de la loi 09-08.

    **Le garde ne dira rien de cette décision, ni dans un sens ni dans l'autre.**
    `plateforme/projection/checks.py::vues_sans_portee_magasin` saute tout modèle qui
    n'hérite pas du mixin : il est structurellement aveugle ici. Un relecteur de la
    phase 7 qui ajouterait le mixin allumerait le filtrage, le garde réclamerait alors le
    mixin de vue, il l'ajouterait, et tout serait vert avec le danger revenu. La seule
    protection qui survit à cela est une assertion **positive** :
    `tests/test_ordonnances.py::test_client07_une_ordonnance_n_est_pas_scopee_au_magasin`,
    qui porte cette raison dans son message d'échec (menace T-04-22).

    Le `magasin` ci-dessous est la **provenance** : qui a saisi, pour la traçabilité et
    pour les rappels de la phase 10. Porter la provenance n'est pas filtrer dessus.
    L'accès, lui, passe par le droit `ordonnance.voir`, qui gouverne l'objet entier.

    ## Trois décisions de forme

    1. **Colonnes plates `_od` / `_og`, jamais deux lignes par ordonnance.** Deux lignes
       rendraient représentable « axe OD présent, sphère OD absente », feraient de chaque
       lecture une agrégation et de chaque contrôle inter-yeux une auto-jointure. Onze
       colonnes n'est pas un échec de modélisation, c'est le domaine.
    2. **`supersede` pointe de la NOUVELLE ligne vers l'ancienne.** L'alternative — un
       drapeau `erronee` posé sur l'ancienne — serait une écriture sur une ligne
       immuable, ce que CLIENT-06 interdit. Avec le pointeur sur la nouvelle, « la
       version 2 était-elle une erreur ? » se **dérive** ; elle ne s'écrit jamais.
    3. **`ep_saisi` est stocké, jamais déduit des colonnes nulles.** `NULL` est ambigu
       entre « non mesuré » et « sans objet ». La règle, écrite une fois pour toutes :
       *on enregistre ce qui a été saisi ; la somme binoculaire s'affiche comme contrôle
       quand les deux monoculaires existent ; on ne calcule jamais un monoculaire.*
       Découper un binoculaire en deux suppose la symétrie à laquelle les progressifs
       sont précisément sensibles. `DecimalField(decimal_places=1)` et non un entier :
       le demi-millimètre porte les progressifs.
    """

    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.PROTECT,
        related_name="ordonnances",
    )
    #: **Provenance SEULE.** `PROTECT` parce qu'un magasin se désactive et ne se supprime
    #: pas : effacer le comptoir effacerait la traçabilité d'une donnée de santé.
    magasin = models.ForeignKey(
        "magasins.Magasin",
        on_delete=models.PROTECT,
        related_name="+",
    )

    #: Émis par le serveur sous verrou, dans la transaction d'insertion (plan 04-05).
    version = models.PositiveSmallIntegerField()
    #: La ligne que celle-ci remplace. Portée par la **nouvelle**, jamais par l'ancienne.
    supersede = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    type_revision = models.CharField(
        max_length=20, choices=TypeRevision.choices, blank=True
    )
    motif_revision = models.CharField(max_length=300, blank=True)

    source = models.CharField(max_length=24, choices=SourceOrdonnance.choices)
    prescripteur = models.CharField(max_length=120, blank=True)
    #: La date portée par l'ordonnance papier, distincte de `created_at` : elle est lue
    #: sur le document et saisie des jours plus tard. Les confondre daterait la
    #: prescription du jour de la frappe et fausserait sa validité.
    date_prescription = models.DateField()

    sphere_od = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    sphere_og = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    cylindre_od = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    cylindre_og = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    axe_od = models.PositiveSmallIntegerField(null=True, blank=True)
    axe_og = models.PositiveSmallIntegerField(null=True, blank=True)
    addition_od = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )
    addition_og = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )

    ep_binoculaire = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True
    )
    ep_mono_od = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    ep_mono_og = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    ep_saisi = models.CharField(max_length=16, choices=EcartPupillaireSaisi.choices)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    #: L'adresse du compte qui a saisi, **en chaîne et non en clé étrangère**. Les comptes
    #: vivent dans le plan de contrôle (CLAUDE.md #11) et `TenantRouter.allow_relation`
    #: refuse une relation entre les deux bases ; c'est le même choix que
    #: `AccesMagasin.magasin_code`, dans l'autre sens. La chaîne reste lisible dix ans
    #: plus tard, même si le compte a été désactivé.
    created_par = models.CharField(max_length=254, blank=True)

    # ----------------------------------------------------------------------------------
    # CLIENT-09 — la photo du papier. `null -> posee` est la SEULE mutation permise sur
    # une ligne par ailleurs immuable (decision §28-Q5, `04-UI-SPEC.md` §22.3).
    # ----------------------------------------------------------------------------------
    #
    # **Le chemin, jamais les octets.** Une colonne binaire de plusieurs Mo par
    # ordonnance rendrait la sauvegarde par client (TENANT-09) et la retention a dix ans
    # (art. 211 CGI) couteuses, sur une table qu'on lit a chaque ouverture de fiche.
    #
    # **`storage=` recoit un APPELABLE, et c'est deliberement le seul endroit du produit
    # ou cette forme est correcte.** `FileField.__init__` fait `self.storage =
    # self.storage()` une fois, a la construction du champ : cela fige *quel back-end*,
    # ce qui est un choix de deploiement, et cela ne peut pas figer *quel locataire*, qui
    # est un choix par requete. Le prefixe du locataire est donc rederive dans chaque
    # methode de `StockageOrdonnances`, et l'appelable est aussi ce qui garde la
    # migration independante du reglage — elle nomme la fonction, pas l'instance.
    #
    # **Ne JAMAIS faire entrer le locataire dans cet appelable.**
    # `storage=lambda: StockageDuLocataire(current_alias())` est la forme qui vient
    # naturellement a l'esprit et elle lierait le locataire lie a l'import, c'est-a-dire
    # aucun en pratique et un seul au pire. La garde n'est pas ce commentaire :
    # `test_client09_le_champ_ne_fige_aucun_locataire_a_la_construction` verifie que le
    # prefixe change avec le locataire lie et n'existe pas sans lui.
    #
    # `editable=False` : aucun formulaire et aucun serialiseur n'ecrit ni ne rend cette
    # colonne. Le nom stocke est un detail interne, et un `ModelSerializer` qui le
    # rendrait appellerait `storage.url()`, qui **leve** par decision.
    photo = models.FileField(
        storage=stockage_des_photos,
        upload_to="",
        max_length=120,
        blank=True,
        null=True,
        editable=False,
    )
    #: Le type **verifie** a l'attache — declare *et* confirme par les octets magiques —
    #: et non celui que l'appelant a annonce. C'est lui que la lecture renvoie en
    #: `Content-Type`.
    photo_type = models.CharField(max_length=40, blank=True)
    photo_octets = models.PositiveIntegerField(null=True, blank=True)
    photo_attachee_le = models.DateTimeField(null=True, blank=True)
    #: Qui a attache, en **adresse** et non en cle etrangere — meme choix que
    #: `created_par`, pour la meme raison (CLAUDE.md #11 : les comptes vivent dans le plan
    #: de controle). La provenance d'une piece justificative de sante est ce qui rend une
    #: mauvaise pieces jointe discutable au comptoir, dix ans plus tard.
    photo_par = models.CharField(max_length=254, blank=True)

    class Meta:
        ordering = ["-date_prescription", "-version"]
        verbose_name = "ordonnance"
        verbose_name_plural = "ordonnances"
        constraints = _contraintes_cliniques()
        indexes = [
            # Toute lecture part du client et veut la dernière version d'abord : c'est la
            # fiche client, l'écran de comparaison et le point de départ d'une vente.
            models.Index(fields=["client", "-version"], name="idx_ordonnance_client"),
        ]

    def __str__(self) -> str:
        return f"Ordonnance v{self.version} — {self.date_prescription}"

    def save(self, *args, **kwargs):
        """Canonicalise avant d'écrire : l'axe 0 devient 180, un cylindre nul devient NULL.

        **Le chemin normal, et non la garantie.** `bulk_create`, `queryset.update()`, un
        `RunPython` et le shell passent tous à côté d'ici — c'est pourquoi les mêmes
        règles existent aussi en contraintes de base. Les deux ne font pas double emploi :
        cette méthode **accepte et range** une saisie légitime que la contrainte
        refuserait (un axe de 0, un cylindre de 0), la contrainte **refuse** ce qu'aucun
        chemin ne doit écrire.
        """
        for cylindre, axe in PAIRES_CYLINDRE_AXE:
            if getattr(self, cylindre) == ZERO:
                setattr(self, cylindre, None)
                setattr(self, axe, None)
            else:
                setattr(self, axe, canonicaliser_axe(getattr(self, axe)))

        if update_fields := kwargs.get("update_fields"):
            # Une écriture ciblée qui ne nommerait pas les colonnes canonicalisées
            # laisserait un axe de 0 en base : la ligne serait refusée par la contrainte
            # au lieu d'être rangée, pour une raison qui ne nomme pas la cause.
            kwargs["update_fields"] = {*update_fields, *COLONNES_CANONICALISEES}

        # Aucun alias n'est nommé : `Model.save()` interroge `TenantRouter`, qui lit le
        # contextvar et **lève** quand rien n'est lié. Un `using=` en dur serait un
        # contournement déguisé du mécanisme que toute la phase 2 existe pour tenir.
        super().save(*args, **kwargs)


#: Les quatre colonnes que `save()` peut réécrire. Nommées pour que l'ajout à
#: `update_fields` ci-dessus n'ait pas à les recopier.
COLONNES_CANONICALISEES = tuple(
    colonne for paire in PAIRES_CYLINDRE_AXE for colonne in paire
)

"""L'ordonnance sur l'API : **deux** sérialiseurs, et la séparation est CLIENT-06.

======================================================================================
UN SÉRIALISEUR DE LECTURE SANS AUCUN VALIDATEUR DE BORNE — CE N'EST PAS UN CHOIX DE STYLE
======================================================================================

Séparer la lecture de l'écriture est ici la traduction mécanique de CLIENT-06. Un
sérialiseur unique porterait les validateurs de bornes des deux côtés, et le jour où le
propriétaire resserre un chiffre — il l'a **déjà fait une fois** — toutes les versions
enregistrées sous les anciennes bornes deviendraient illisibles, ou pire, s'afficheraient
annotées d'un avertissement. Faire paraître fausses les anciennes fiches parce que la
règle a bougé détruit exactement la garantie que CLIENT-06 achète :

> Une version enregistrée se rend **telle qu'elle a été saisie**. L'affichage ne la
> revalide jamais. (`04-UI-SPEC.md` §21.2)

`test_client06_une_version_stockee_ne_se_revalide_pas_a_la_lecture` tient la promesse en
trois temps — enregistrer, resserrer `BORNES`, vérifier que **la même saisie est
désormais refusée** et que **la lecture n'a pas bougé d'un octet**. Le temps du milieu est
ce qui empêche le test d'être vert au-dessus d'un monkeypatch sans effet.

## Les bornes sont lues à la validation, pas à la définition des champs

`bornes.BORNES[...]` est interrogé **dans** `validate()`, jamais figé dans un
`DecimalField(min_value=…)` au moment où la classe est construite. Deux raisons, et la
seconde est celle qui compte :

1. D-4b promet que « le prochain changement coûte une ligne » — une valeur capturée à
   l'import survit à un changement de `bornes.py` jusqu'au prochain redémarrage.
2. Un validateur posé à la construction serait **invisible au test** ci-dessus : le
   monkeypatch ne le toucherait pas, la même saisie resterait acceptée, et le test
   comparerait deux lectures identiques sans rien prouver.

Aucun nombre clinique n'est écrit dans ce fichier. La forme des colonnes — chiffres
significatifs, décimales — est lue sur le **modèle**, pas recopiée : une seconde écriture
de `max_digits` dériverait de la première.
`tests/test_optique.py::test_client07_les_bornes_vivent_a_un_seul_endroit` lit l'AST de ce
module et refuse le premier littéral.

## Le nom du composant OpenAPI est posé explicitement

Non pas pour résoudre une collision — contrairement à `FicheClient`, `Ordonnance` n'est
pris par rien, vérifié — mais parce que les classes ne s'appellent pas
`OrdonnanceSerializer` : `drf-spectacular` dériverait `OrdonnanceLecture` et
`OrdonnanceEcriture`, deux noms d'implémentation exposés dans le contrat public et donc
dans le client TypeScript.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from domaine.ordonnances import bornes
from domaine.ordonnances.models import (
    CHAMPS_PAR_BORNE,
    PAIRES_CYLINDRE_AXE,
    EcartPupillaireSaisi,
    Ordonnance,
    SourceOrdonnance,
    TypeRevision,
)
from domaine.ordonnances.optique import canonicaliser_axe
from plateforme.projection.serializers import SerializerProjete
from plateforme.projection.vues import MagasinAutoriseField

#: Les colonnes cliniques, et la borne qui gouverne chacune. **Dérivée** de la table du
#: modèle, prise à l'envers : ajouter une colonne d'œil à `CHAMPS_PAR_BORNE` la fait
#: valider ici sans qu'une ligne change, ce qui est le seul moyen que les deux endroits
#: d'application ne divergent pas.
BORNE_DE_LA_COLONNE: dict[str, str] = {
    colonne: nom_borne
    for nom_borne, colonnes in CHAMPS_PAR_BORNE.items()
    for colonne in colonnes
}

#: Les colonnes d'axe, qui sont des entiers de degrés et se canonicalisent avant d'être
#: comparées aux bornes. Dérivées, elles aussi, de la table du modèle.
COLONNES_D_AXE: tuple[str, ...] = tuple(axe for _cylindre, axe in PAIRES_CYLINDRE_AXE)


def _forme_du_modele(colonne: str) -> dict:
    """`max_digits` et `decimal_places` lus sur la colonne, jamais recopiés."""
    champ = Ordonnance._meta.get_field(colonne)
    return {"max_digits": champ.max_digits, "decimal_places": champ.decimal_places}


def _en_decimal(valeur):
    """La valeur en `Decimal` exact, ou `None` si elle n'en est pas un.

    `Decimal(str(...))` et jamais `Decimal(float)` : convertir depuis un binaire flottant
    reproduit l'erreur *dans* le type exact, ce qui la rend invisible au lieu de
    l'empêcher (même raison qu'`optique._exiger_decimal`).
    """
    if valeur is None:
        return None
    try:
        return Decimal(str(valeur))
    except (InvalidOperation, ValueError):  # pragma: no cover — DRF a déjà refusé
        return None


# ======================================================================================
# Lecture — la version telle qu'elle a été saisie
# ======================================================================================
@extend_schema_serializer(component_name="Ordonnance")
class OrdonnanceLectureSerializer(SerializerProjete):
    """Une version stockée, rendue **sans être revalidée**. CLIENT-06.

    Tous les champs sont en lecture seule, y compris ceux que l'écriture accepte : il n'y
    a aucune route de modification (plan 04-05, menace T-04-29), donc un champ
    inscriptible ici serait une porte qui ne mène nulle part aujourd'hui et une porte tout
    court le jour où quelqu'un monte un verbe de plus.

    `client` et `magasin` sortent en clés primaires. Le `magasin` est de la **provenance**
    — qui a saisi — et jamais un critère de filtrage : un gérant qui voit le client voit
    tout son historique, quel que soit le comptoir (D-4a).
    """

    class Meta:
        model = Ordonnance
        fields = [
            "id",
            "client",
            "magasin",
            "version",
            "supersede",
            "type_revision",
            "motif_revision",
            "source",
            "prescripteur",
            "date_prescription",
            "sphere_od",
            "sphere_og",
            "cylindre_od",
            "cylindre_og",
            "axe_od",
            "axe_og",
            "addition_od",
            "addition_og",
            "ep_binoculaire",
            "ep_mono_od",
            "ep_mono_og",
            "ep_saisi",
            "created_at",
            "created_par",
        ]
        read_only_fields = fields


# ======================================================================================
# Le résumé posé sur la fiche client — un champ PROTÉGÉ sur un objet visible
# ======================================================================================
class _OeilSerializer(serializers.Serializer):
    """Les quatre valeurs d'un œil. Une classe, pour que le contrat les nomme.

    Les décimaux voyagent en **chaîne**, comme les bornes de l'amorçage : JSON n'a pas de
    type décimal, et le contournement habituel — `float(...)` — est exactement la faute
    que CLAUDE.md #7 interdit.
    """

    sphere = serializers.CharField(allow_null=True)
    cylindre = serializers.CharField(allow_null=True)
    axe = serializers.IntegerField(allow_null=True)
    addition = serializers.CharField(allow_null=True)


class ResumeOrdonnanceSerializer(serializers.Serializer):
    """Ce que la fiche client montre de la version en cours. `04-UI-SPEC.md` §19.3.

    **Pourquoi la fiche porte ce bloc plutôt qu'un lien.** « Quelle est la correction
    actuelle de ce client » est la question la plus fréquente du comptoir ; en faire une
    seconde navigation est la friction que ce produit existe pour supprimer.

    Et pourquoi il est **protégé** : l'ordonnance en tant qu'objet est une *ligne*, gardée
    par `ordonnance.voir` au niveau du queryset. Ce résumé-ci est un **champ** posé sur un
    objet que l'appelant a par ailleurs le droit de voir, et son contenu est clinique.
    C'est exactement la forme que `CHAMPS_PROTEGES` existe pour traiter.
    """

    version = serializers.IntegerField()
    date_prescription = serializers.DateField()
    source = serializers.ChoiceField(choices=SourceOrdonnance.choices)
    prescripteur = serializers.CharField(allow_blank=True)
    type_revision = serializers.ChoiceField(
        choices=TypeRevision.choices, allow_blank=True
    )
    od = _OeilSerializer()
    og = _OeilSerializer()
    ep_saisi = serializers.ChoiceField(choices=EcartPupillaireSaisi.choices)
    ep_binoculaire = serializers.CharField(allow_null=True)
    ep_mono_od = serializers.CharField(allow_null=True)
    ep_mono_og = serializers.CharField(allow_null=True)


def _chaine(valeur) -> str | None:
    return None if valeur is None else str(valeur)


def resume_de(ordonnance) -> dict | None:
    """Le résumé d'une version, **construit sans revalidation**.

    Aucune borne n'est consultée ici, et c'est le point : cette fonction sert la version
    en cours d'une fiche, qui peut parfaitement porter une valeur que les bornes
    d'aujourd'hui refuseraient. Elle la rend telle quelle.
    """
    if ordonnance is None:
        return None
    return {
        "version": ordonnance.version,
        "date_prescription": ordonnance.date_prescription,
        "source": ordonnance.source,
        "prescripteur": ordonnance.prescripteur,
        "type_revision": ordonnance.type_revision,
        "od": {
            "sphere": _chaine(ordonnance.sphere_od),
            "cylindre": _chaine(ordonnance.cylindre_od),
            "axe": ordonnance.axe_od,
            "addition": _chaine(ordonnance.addition_od),
        },
        "og": {
            "sphere": _chaine(ordonnance.sphere_og),
            "cylindre": _chaine(ordonnance.cylindre_og),
            "axe": ordonnance.axe_og,
            "addition": _chaine(ordonnance.addition_og),
        },
        "ep_saisi": ordonnance.ep_saisi,
        "ep_binoculaire": _chaine(ordonnance.ep_binoculaire),
        "ep_mono_od": _chaine(ordonnance.ep_mono_od),
        "ep_mono_og": _chaine(ordonnance.ep_mono_og),
    }


# ======================================================================================
# Écriture — les bornes, lues au moment de valider
# ======================================================================================
@extend_schema_field(serializers.IntegerField)
class ChampMagasinDeSaisie(MagasinAutoriseField):
    """Le champ magasin restreint, **avec son type déclaré**. Mesuré, pas supposé.

    `drf-spectacular` dérive le type d'un champ lié depuis la clé primaire du modèle du
    sérialiseur ; un sérialiseur sans `Meta.model` — et celui d'écriture n'en a pas, il
    n'est pas un `ModelSerializer` — le laisse sans type. Observé en régénérant :

        Warning [VueOrdonnances > OrdonnanceEcritureSerializer]: Could not derive type
        for under-specified MagasinAutoriseField "magasin". […] Defaulting to string.

    Un avertissement n'est presque jamais cosmétique, et celui-ci ne l'est pas du tout :
    `--fail-on-warn` est une porte de CI commitée, donc il casse la génération — et s'il
    ne la cassait pas, le client TypeScript déclarerait `magasin: string` sur un champ
    qui est un entier, et chaque site d'appel porterait une conversion silencieuse.

    Le type est donc **déclaré** plutôt que déduit. Le décorateur ne touche ni la
    validation, ni le queryset restreint : la garantie de P5 / T-03-40 est intacte.
    """


@extend_schema_serializer(component_name="OrdonnanceASaisir")
class OrdonnanceEcritureSerializer(serializers.Serializer):
    """Ce qu'un comptoir envoie. **`version` n'y est pas, et c'est la garantie.**

    Un champ absent du sérialiseur n'atteint jamais `validated_data` : un corps qui nomme
    `{"version": 7}` est donc **ignoré**, pas obéi — et pas non plus refusé par un 400,
    parce que DRF ne lève sur aucune clé inconnue. C'est le même raisonnement que la
    projection des champs protégés (menace T-03-34), appliqué au numéro de série
    (T-04-31).

    Le `magasin` est un champ lié **restreint aux magasins accordés**. La vue restreint la
    lecture ; elle ne restreint pas la création, et un POST nommant un magasin étranger ne
    consulte aucun queryset de vue. DRF valide la clé primaire contre le queryset **du
    champ**, donc l'écriture inter-magasins est un 400 et non un 201 (P5, T-03-40).
    """

    magasin = ChampMagasinDeSaisie(
        help_text=(
            "Le comptoir qui saisit. C'est de la **provenance** : l'ordonnance "
            "appartient au client, pas au magasin, et tout l'historique se lit depuis "
            "n'importe quel comptoir (D-4a)."
        )
    )

    source = serializers.ChoiceField(choices=SourceOrdonnance.choices)
    prescripteur = serializers.CharField(
        max_length=Ordonnance._meta.get_field("prescripteur").max_length,
        allow_blank=True,
        required=False,
        default="",
    )
    date_prescription = serializers.DateField()

    supersede = serializers.PrimaryKeyRelatedField(
        queryset=Ordonnance.objects.all(),
        required=False,
        allow_null=True,
        default=None,
        help_text=(
            "La version que celle-ci remplace. Portée par la **nouvelle** ligne : un "
            "drapeau posé sur l'ancienne serait une écriture sur une ligne immuable."
        ),
    )
    type_revision = serializers.ChoiceField(
        choices=TypeRevision.choices, allow_blank=True, required=False, default=""
    )
    motif_revision = serializers.CharField(
        max_length=Ordonnance._meta.get_field("motif_revision").max_length,
        allow_blank=True,
        required=False,
        default="",
    )

    sphere_od = serializers.DecimalField(
        **_forme_du_modele("sphere_od"), required=False, allow_null=True, default=None
    )
    sphere_og = serializers.DecimalField(
        **_forme_du_modele("sphere_og"), required=False, allow_null=True, default=None
    )
    cylindre_od = serializers.DecimalField(
        **_forme_du_modele("cylindre_od"), required=False, allow_null=True, default=None
    )
    cylindre_og = serializers.DecimalField(
        **_forme_du_modele("cylindre_og"), required=False, allow_null=True, default=None
    )
    axe_od = serializers.IntegerField(required=False, allow_null=True, default=None)
    axe_og = serializers.IntegerField(required=False, allow_null=True, default=None)
    addition_od = serializers.DecimalField(
        **_forme_du_modele("addition_od"), required=False, allow_null=True, default=None
    )
    addition_og = serializers.DecimalField(
        **_forme_du_modele("addition_og"), required=False, allow_null=True, default=None
    )

    ep_binoculaire = serializers.DecimalField(
        **_forme_du_modele("ep_binoculaire"),
        required=False,
        allow_null=True,
        default=None,
    )
    ep_mono_od = serializers.DecimalField(
        **_forme_du_modele("ep_mono_od"), required=False, allow_null=True, default=None
    )
    ep_mono_og = serializers.DecimalField(
        **_forme_du_modele("ep_mono_og"), required=False, allow_null=True, default=None
    )
    ep_saisi = serializers.ChoiceField(choices=EcartPupillaireSaisi.choices)

    def validate(self, donnees):
        """Les bornes, le pas et la paire axe ↔ cylindre — **lus à cet instant**.

        Un message lisible au comptoir, là où la contrainte de base donne la garantie. Les
        deux lisent `BORNES` ; ce qui est dupliqué est le **lieu d'application**, jamais
        la valeur (`domaine/ordonnances/bornes.py`).
        """
        erreurs: dict[str, str] = {}

        for colonne in COLONNES_D_AXE:
            # CLIENT-07 dit littéralement « 0–180 » : on accepte 0 à la saisie et on le
            # range en 180, parce que les deux nomment le même méridien. La
            # canonicalisation vient **avant** la borne, sans quoi un 0 légitime serait
            # refusé par un plancher qu'il ne viole pas.
            donnees[colonne] = canonicaliser_axe(donnees.get(colonne))

        for colonne, nom_borne in BORNE_DE_LA_COLONNE.items():
            valeur = _en_decimal(donnees.get(colonne))
            if valeur is None:
                continue
            borne = bornes.BORNES[nom_borne]
            minimum = Decimal(str(borne["min"]))
            maximum = Decimal(str(borne["max"]))
            pas = Decimal(str(borne["pas"]))

            if not (minimum <= valeur <= maximum):
                erreurs[colonne] = (
                    f"Valeur hors bornes : attendu entre {minimum} et {maximum}. "
                    "Au-delà, c'est une faute de frappe bien plus souvent qu'un patient."
                )
                continue
            if valeur % pas:
                erreurs[colonne] = (
                    f"Valeur hors grille : attendu un multiple de {pas}. Une valeur "
                    "intermédiaire est dans les bornes et n'existe sur aucune ordonnance."
                )

        for cylindre, axe in PAIRES_CYLINDRE_AXE:
            # Un cylindre nul se range NULL, avec son axe : « pas d'astigmatisme » et
            # « astigmatisme de zéro dioptrie » sont un seul fait, et deux encodages d'un
            # même fait rendent deux fiches incomparables. `save()` le fait aussi ; le
            # faire ici évite de refuser une saisie légitime au nom de la paire.
            if _en_decimal(donnees.get(cylindre)) == Decimal(0):
                donnees[cylindre] = None
                donnees[axe] = None
            if (donnees.get(cylindre) is None) != (donnees.get(axe) is None):
                erreurs[axe] = (
                    "Un axe sans cylindre ne veut rien dire, et un cylindre sans axe "
                    "n'est pas commandable. Les deux vont ensemble ou aucun des deux."
                )

        medicale = donnees.get("source") == SourceOrdonnance.MEDICALE
        prescripteur = (donnees.get("prescripteur") or "").strip()
        if medicale and not prescripteur:
            erreurs["prescripteur"] = (
                "Une ordonnance médicale nomme son prescripteur."
            )
        if not medicale and prescripteur:
            erreurs["prescripteur"] = (
                "Une réfraction d'opticien n'a pas de prescripteur : en nommer un "
                "affirme qu'un médecin a prescrit ce qui a été mesuré au comptoir."
            )
        donnees["prescripteur"] = prescripteur

        if erreurs:
            raise serializers.ValidationError(erreurs)
        return donnees


@extend_schema_field(ResumeOrdonnanceSerializer(allow_null=True))
class ChampResumeOrdonnance(serializers.SerializerMethodField):
    """Un `SerializerMethodField` dont le contrat OpenAPI est nommé.

    Sans le décorateur, `drf-spectacular` rend `{}` — un champ décrit comme « n'importe
    quoi », donc un type TypeScript `unknown` que la SPA déballerait à la main. Le
    composant `ResumeOrdonnance` est le contrat, et il est généré depuis la même classe
    que celle qui décrit la charge.
    """

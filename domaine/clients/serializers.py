"""La fiche client telle que l'API la rend. CLIENT-01.

Un seul sérialiseur, et l'essentiel de ce fichier explique **son nom de composant**.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from domaine.clients.models import Client
from domaine.clients.recherche import RAISONS
from domaine.ordonnances.serializers import (
    ChampResumeOrdonnance,
    resume_de,
)
from domaine.ordonnances.services import derniere_ordonnance_de
from plateforme.projection.serializers import SerializerProjete

# ======================================================================================
# LE NOM `Client` EST DÉJÀ PRIS DANS LE SCHÉMA OPENAPI — NE PAS RETIRER LE DÉCORATEUR
# ======================================================================================
#
# `plateforme/comptes/serializers.py` déclare un `ClientSerializer` pour
# `control_plane.Client` — l'**affaire** de l'opticien, pas la personne qui achète — et
# il produit le composant OpenAPI `Client`, que `web/src/api/requetes.ts` aliase déjà
# `ClientDeLaffaire`.
#
# Sans `component_name` ci-dessous, ce sérialiseur-ci produirait un **second** composant
# `Client`. `drf-spectacular` émettrait un avertissement de collision, et
# `spectacular --fail-on-warn` — qui est une porte de CI commitée — sortirait non nul.
# Pire si le drapeau tombait un jour : l'un des deux composants écraserait l'autre, et le
# client TypeScript généré promettrait `raison_sociale` sur une fiche de personne.
#
# Le décorateur n'est donc pas du bruit, c'est la résolution d'une collision réelle. La
# garde G6 de `04-VALIDATION.md` la tient des deux côtés : `FicheClient` doit exister dans
# `web/src/api/schema.yml`, et `ClientDeLaffaire` doit toujours être dans `requetes.ts`.
#
# La clé du registre de projection, elle, n'est pas concernée : elle est
# `clients.Client.<champ>`, distincte de `control_plane.Client.<champ>`. Seul le **nom du
# composant** l'était.


@extend_schema_serializer(component_name="FicheClient")
class FicheClientSerializer(SerializerProjete):
    """La personne qui achète : ce qui se saisit, et ce qui s'affiche.

    **Les trois colonnes dérivées sont absentes de `fields`, et c'est une décision.**
    `nom_recherche`, `cle_phonetique` et `telephone_normalise` sont `editable=False` et
    recalculées par `Client.save()` : elles ne sont ni saisies ni servies. Un champ dérivé
    qu'un POST pourrait écrire serait une **seconde source de vérité**, et la divergence
    serait muette — fiche correcte à l'écran, introuvable à la recherche (T-04-05).

    `score` et `raison` ne sont pas des colonnes : ce sont les annotations que
    `chercher_clients` pose sur les résultats d'une recherche. Elles sont `null` hors
    recherche, et c'est honnête — « cette fiche n'est pas un résultat de recherche » est
    une information, pas une absence de droit. Le registre de projection ne les connaît
    donc pas, et `test_perm06_tout_champ_de_modele_expose_est_classe` les ignore : il ne
    classe que les champs qui sont des colonnes.
    """

    score = serializers.SerializerMethodField(
        help_text=(
            "Le rang du résultat dans la recherche courante, entre 0 et 2. "
            "Null hors recherche. **À ne jamais afficher tel quel** : « 0,333 » ne dit "
            "rien à un opticien — c'est `raison` qui se montre, en mots."
        )
    )
    raison = serializers.SerializerMethodField(
        help_text=(
            "Par quelle couche ce résultat a été trouvé : exact, telephone, "
            "orthographe, phonetique ou equivalence. Null hors recherche."
        )
    )

    # ==================================================================================
    # LES DEUX PREMIERS CHAMPS PROTÉGÉS DU PRODUIT — NE PAS LES RENDRE INCONDITIONNELS
    # ==================================================================================
    #
    # Ils sont déclarés ici comme n'importe quel champ, **sans aucune condition écrite à
    # la main** : `SerializerProjete.get_fields()` les retire par leur nom quand
    # `ordonnance.voir` manque, en lisant `CHAMPS_PROTEGES`. Le registre est clé par
    # champ de modèle, et les deux clés `clients.Client.derniere_ordonnance` /
    # `clients.Client.resume_ordonnance` s'y rangent sans que `Client` porte ces
    # colonnes — le retrait se fait par nom, donc un `SerializerMethodField` se retire
    # comme une colonne.
    #
    # **Un `if acces.peut(...)` ici serait la faute**, et elle est facile à commettre
    # parce qu'elle a l'air plus explicite : elle produirait une seconde source de
    # vérité que ni l'export, ni le document, ni le schéma OpenAPI ne liraient. Le
    # champ disparaîtrait de l'API et resterait dans le CSV.
    #
    # `04-UI-SPEC.md` §15.5 tranche la zone grise 5 : l'ordonnance en tant qu'objet est
    # une **ligne** (gardée par le queryset de `VueOrdonnances`), ces deux résumés sont
    # des **champs** posés sur un objet que l'appelant a par ailleurs le droit de voir.
    derniere_ordonnance = serializers.SerializerMethodField(
        help_text=(
            "La date de prescription de la version en cours, en ISO. `null` si le "
            "client n'a aucune ordonnance. **Absente de la charge utile** — et non "
            "`null` — pour qui ne détient pas `ordonnance.voir` : les deux se "
            "distinguent, et les confondre dirait « pas d'ordonnance » à qui n'a "
            "simplement pas le droit."
        )
    )
    resume_ordonnance = ChampResumeOrdonnance(
        help_text=(
            "Le bloc de correction de la version en cours, rendu tel qu'il a été saisi "
            "et **jamais revalidé** (CLIENT-06). Mêmes règles de présence que "
            "`derniere_ordonnance`."
        )
    )

    class Meta:
        model = Client
        fields = [
            "id",
            "nom",
            "telephone",
            "date_naissance",
            "adresse",
            "notes",
            "actif",
            "created_at",
            "score",
            "raison",
            "derniere_ordonnance",
            "resume_ordonnance",
        ]
        read_only_fields = ["id", "created_at"]

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_score(self, fiche):
        return getattr(fiche, "score", None)

    @extend_schema_field(
        serializers.ChoiceField(choices=list(RAISONS), allow_null=True)
    )
    def get_raison(self, fiche):
        return getattr(fiche, "raison", None)

    @extend_schema_field(serializers.DateField(allow_null=True))
    def get_derniere_ordonnance(self, fiche):
        """La date de prescription de la version en cours, **en ISO et en chaîne**.

        Une chaîne plutôt que l'objet `date`, et la raison est mesurable : les quatre
        rendus du registre n'en font pas la même chose. Le JSON de DRF produirait bien
        l'ISO, mais le gabarit de document passe la valeur à `{{ }}`, où Django applique
        le format de date de la locale — donc « 23 juillet 2019 » côté document et
        « 2019-07-23 » côté API, pour la même donnée. Le transport est ISO
        (`04-UI-SPEC.md` §15.4) et c'est la SPA qui formate en `jj/mm/aaaa`.
        """
        ordonnance = derniere_ordonnance_de(fiche)
        return None if ordonnance is None else ordonnance.date_prescription.isoformat()

    def get_resume_ordonnance(self, fiche):
        """Le bloc de correction de la version en cours, ou `null`.

        `null` ici veut dire « ce client n'a aucune ordonnance », et c'est une
        information. « Vous n'avez pas le droit de la voir » est l'autre cas, et il
        s'exprime par l'**absence de la clé** — jamais par `null`. Les deux se
        distinguent, et les confondre ferait afficher « aucune ordonnance » à un gérant
        qui en a simplement perdu la vue.
        """
        return resume_de(derniere_ordonnance_de(fiche))

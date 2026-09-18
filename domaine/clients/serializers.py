"""La fiche client telle que l'API la rend. CLIENT-01.

Un seul sérialiseur, et l'essentiel de ce fichier explique **son nom de composant**.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from domaine.clients.models import Client
from domaine.clients.recherche import RAISONS
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

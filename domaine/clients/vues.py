"""`/api/clients/` — lire, chercher, créer et corriger une fiche. CLIENT-01, CLIENT-10.

Trois choses sont à savoir avant de modifier ce fichier, et deux sont des absences.
"""

from __future__ import annotations

from django.db import router
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, permissions, viewsets

from domaine.clients.models import Client
from domaine.clients.recherche import LIMITE_PAR_DEFAUT, chercher_clients
from domaine.clients.serializers import FicheClientSerializer
from plateforme.comptes.permissions_catalogue import Permission
from plateforme.projection.filtres import ProjectedFieldFilter, ProjectedOrderingFilter
from plateforme.projection.vues import acces_de_la_requete

#: La phrase de contrat, écrite une fois et servie au client généré.
#:
#: Elle part dans le document OpenAPI, donc dans la documentation que lira le client
#: mobile de la phase 11 — c'est pourquoi elle est ici et pas seulement dans une
#: docstring Python, que seul un lecteur de ce dépôt verrait.
CONTRAT_DE_RECHERCHE = (
    "Liste de candidats classés. **Aucun appelant ne doit auto-sélectionner sur un "
    "nom.** Aucun seuil ne sépare « Mhamed ↔ Mohammed » (0,333) de "
    "« Fatima ↔ Fatiha » (0,571) : le classement est inversé, et un faux positif au "
    "comptoir ouvre la fiche du voisin — avec ses ordonnances, c'est une divulgation de "
    "donnée de santé, pas une gêne d'interface. `correspondance_exacte` ne se pose que "
    "sur un numéro de téléphone complet, jamais sur un nom."
)


class PeutVoirLesClients(permissions.BasePermission):
    """`client.voir` — exigé sur **toutes** les actions, lecture comme écriture."""

    def has_permission(self, request, view):
        return acces_de_la_requete(request).peut(Permission.CLIENT_VOIR)


class PeutModifierLesClients(permissions.BasePermission):
    """`client.modifier` — exigé dès que la méthode n'est pas sûre.

    **La condition porte sur la méthode HTTP, pas sur le nom de l'action**, et c'est la
    moitié que l'on oublie. Une classe qui n'aurait regardé que `view.action in
    {"create", "update"}` laisserait passer la première action `@action(methods=["post"])`
    qu'une phase ultérieure ajoute ici — la vue *aurait l'air* protégée, et elle le serait
    pour les deux écritures que quelqu'un a pensé à nommer.

    `SAFE_METHODS` est la liste de DRF : GET, HEAD, OPTIONS. Tout le reste passe par
    `client.modifier`, y compris un verbe qu'aucune route ne sert encore.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return acces_de_la_requete(request).peut(Permission.CLIENT_MODIFIER)


@extend_schema_view(
    list=extend_schema(
        summary="Chercher ou lister les clients",
        description=CONTRAT_DE_RECHERCHE,
        parameters=[
            OpenApiParameter(
                name="search",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                    "Le terme brut saisi au comptoir — nom ou téléphone, dans "
                    "n'importe quelle graphie et n'importe quelle écriture. Il est "
                    "normalisé **par le serveur** : ne rien retirer, ne rien plier et "
                    "ne rien filtrer côté client. Sous deux caractères, rien n'est "
                    "cherché. Au plus "
                    f"{LIMITE_PAR_DEFAUT} candidats sont rendus, chacun portant `score` "
                    "et `raison`."
                ),
            )
        ],
    ),
    retrieve=extend_schema(summary="La fiche d'un client"),
    create=extend_schema(summary="Créer une fiche client"),
    partial_update=extend_schema(summary="Corriger une fiche client"),
)
class VueClients(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """La ressource client. **Deux absences délibérées, écrites ici pour être trouvées.**

    ## 1. Le mixin de portée magasin est absent, et ce n'est pas un oubli

    Un client appartient à l'**affaire**, pas à un point de vente : il achète à Anfa
    aujourd'hui et à Maârif dans six mois, et c'est la même personne (décision D-4a). Le
    scoper produirait deux fiches pour un humain, donc deux historiques de prescription
    pour un seul œil. **Le raisonnement complet, avec sa conséquence clinique, vit dans
    la docstring de `clients.Client`** (`domaine/clients/models.py`), qui dit aussi
    pourquoi la garde de `plateforme/projection/checks.py` est structurellement aveugle
    ici — elle ne se déclenche que sur un modèle scopé, donc elle ne dira ni qu'il manque
    une portée, ni qu'il n'en faut pas. La garde **positive** vit au plan 04-04, à côté
    de `Ordonnance`.

    **Pourquoi ce paragraphe ne nomme pas le mixin.** Le plan 04-03 fait de son absence
    un critère grepable sur ce fichier ; l'y écrire rendrait le critère rouge sur le
    fichier même qui le respecte. C'est la même arbitrage qu'au plan 04-01 avec
    `unaccent`, et la même leçon : un critère qui attrape sa propre prose est un critère
    mal écrit — il devrait chercher une **ligne d'import** ou une **base de classe**, pas
    un mot. Noté pour `04-09`.

    Conséquence à ne pas manquer : la portée des lignes de cette ressource est
    l'**affaire entière**, et c'est `client.voir` qui en garde la porte. Il n'y a rien à
    filtrer dans `get_queryset()` à ce titre.

    ## 2. Pas de `DestroyModelMixin`, et `delete` absent de `http_method_names`

    Une fiche client se **désactive** (`actif = False`). L'article 211 du CGI impose dix
    ans de conservation, et la phase 6 posera un `PROTECT` depuis la facture. `put` est
    absent pour la raison de `VueComptes` : un remplacement complet n'a aucun usage ici
    et offrirait une seconde porte d'écriture à tenir en cohérence avec la première.

    ## 3. Aucun nouveau paramètre de requête, et c'est écrit pour que l'absence se lise

    `search` figure **déjà** dans `PARAMETRES_RESERVES`
    (`plateforme/projection/filtres.py`), donc `?search=` n'y ajoute rien et le fichier
    n'est pas touché par ce plan. Tout autre nom — `?q=`, `?telephone=` — devrait y
    entrer **dans le même commit**, sans quoi il produirait le refus unique.
    `test_client01_tout_parametre_hors_liste_blanche_est_refuse` vérifie les trois noms
    que l'on écrit sans y penser.
    """

    serializer_class = FicheClientSerializer
    queryset = Client.objects.all()
    permission_classes = [
        permissions.IsAuthenticated,
        PeutVoirLesClients,
        PeutModifierLesClients,
    ]
    filter_backends = [ProjectedOrderingFilter, ProjectedFieldFilter]
    #: Les colonnes sur lesquelles un appelant peut trier. Une allowlist, dont
    #: `ProjectedOrderingFilter` soustrait encore ce que la projection interdit à cet
    #: appelant. Tout autre nom est un 400, jamais un terme écarté en silence.
    ordering_fields = ["nom", "created_at", "date_naissance"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def _terme_de_recherche(self) -> str:
        """Le `?search=` de la requête, brut et seulement rogné de ses blancs.

        Aucune normalisation ici : elle appartient au service, qui l'applique avec la
        **même** fonction que celle qui a rempli les colonnes indexées. Une seconde
        normalisation posée à la vue divergerait de la première le jour où l'une des deux
        change, et la divergence serait muette.
        """
        parametres = getattr(self.request, "query_params", None) or {}
        return (parametres.get("search") or "").strip()

    def get_queryset(self):
        """Le queryset de la vue — **et le classement de la recherche, quand il y en a un.**

        La règle « le filtre est dans `get_queryset()`, jamais dans `list()` » (plan
        03-07, menace T-03-39) est tenue : ce qui décide des **lignes** est ici, donc
        `get_object()` en hérite et la route de détail n'est pas plus ouverte que la
        liste. Ici il n'y a d'ailleurs rien à restreindre — un client appartient à
        l'affaire — et `client.voir` garde la ressource entière.

        `chercher_clients` rend un **queryset**, pas une liste, précisément pour rester
        dans ce chemin : les backends de filtre s'appliquent ensuite comme sur n'importe
        quelle liste, donc `?search=x&zzz=1` est refusé comme `?zzz=1` le serait.
        Renvoyer une liste les court-circuiterait et rouvrirait l'oracle de paramètres
        (T-04-16).

        Le classement n'est appliqué qu'à `list` : `/api/clients/42/?search=…` doit rendre
        la fiche 42, pas le premier candidat d'une recherche.
        """
        queryset = super().get_queryset()
        if getattr(self, "action", None) != "list":
            return queryset
        terme = self._terme_de_recherche()
        if not terme:
            return queryset
        # L'alias vient du routeur, qui lit le contextvar et **lève** quand rien n'est
        # lié — jamais d'un défaut. Il est passé explicitement au service parce que
        # `seuil_de_mot` doit poser le seuil sur la transaction de cette connexion-là.
        return chercher_clients(terme, alias=router.db_for_read(Client))

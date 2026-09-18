"""`/api/clients/<id>/ordonnances/` — lire et saisir. **Jamais modifier.** CLIENT-06.

Trois absences gouvernent ce fichier, et chacune est une décision. Elles sont écrites ici
parce qu'une absence ne se lit pas dans un diff : on ne remarque pas une ligne qui n'a pas
été ajoutée.

======================================================================================
1. AUCUNE SURFACE DE MODIFICATION, ET DEUX VERROUS PLUTÔT QU'UN
======================================================================================

La vue ne compose que la liste, le détail et la création. Les deux mixins de DRF qui
serviraient un remplacement ou un retrait ne sont pas dans ses bases — leurs noms ne sont
pas écrits ici, parce qu'un critère d'acceptation du plan compte leurs occurrences dans ce
paquet, et les nommer rendrait ce critère rouge sur le fichier même qui les refuse. C'est
la même leçon que `unaccent` au plan 04-01 et que le mixin de portée au plan 04-03 : un
critère qui attrape sa propre prose est un critère mal écrit.

`http_method_names` redit la même chose autrement, et le doublon est délibéré : la
première protection se retire par un ajout de base distrait, la seconde se voit en diff.

**Ce que la surface promet, et qui n'est pas la même chose qu'un droit manquant.** Un
`PATCH` ou un `DELETE` sur une ordonnance rend **405**, pas 403. Un 403 dirait « la route
existe, un droit la garde » — donc qu'il suffit d'accorder ce droit, ou de se tromper dans
une classe de permission, pour que l'historique redevienne réécrivable. 405 dit qu'il n'y
a rien à garder. `test_client06_aucune_route_ne_modifie_une_ordonnance` joue les deux
requêtes **avec le compte du propriétaire**, qui détient tout : s'il obtient 405, personne
n'obtiendra autre chose.

Corriger une erreur de saisie se fait donc par une **nouvelle version** portant
`supersede` et un motif (`04-UI-SPEC.md` §21.3). L'ancienne n'est pas touchée.

======================================================================================
2. PAS DE PORTÉE MAGASIN, ET LA RAISON EST CLINIQUE (D-4a)
======================================================================================

Un gérant qui voit le client voit **tout** son historique d'ordonnances, quel que soit le
comptoir qui l'a saisie. Ce n'est pas une facilité d'ergonomie. Filtrer par comptoir
produit le danger que la recherche de phase a nommé : un gérant de Maârif qui ne voit pas
l'ordonnance saisie à Anfa **en saisit une seconde**, et le client se retrouve avec deux
historiques divergents pour un seul œil. Une duplication d'historique de prescription est
un dossier clinique faux, sur une donnée de santé au sens de la loi 09-08.

La colonne `magasin` est de la **provenance** : qui a saisi, pour la traçabilité et pour
les rappels de la phase 10. Porter la provenance n'est pas filtrer dessus.

Le garde d'énumération de `plateforme/projection/checks.py` ne dira **rien** de cette
décision, ni dans un sens ni dans l'autre : il saute tout modèle qui n'est pas scopé, donc
il est structurellement aveugle ici. La seule protection qui survit est l'assertion
positive `tests/test_ordonnances.py::test_client07_une_ordonnance_n_est_pas_scopee_au_magasin`
(menace T-04-22). Le nom du mixin de portée n'est pas écrit ici non plus, et pour la même
raison qu'au point 1.

**Mais la création, elle, est bornée** — par le champ `magasin` du sérialiseur d'écriture,
qui valide la clé primaire contre les magasins accordés. La vue restreint la lecture ;
elle ne restreint pas la création, et un POST nommant un magasin étranger ne consulte
aucun queryset de vue (P5, menace T-03-40).

======================================================================================
3. AUCUN NOUVEAU PARAMÈTRE DE REQUÊTE — LA LISTE EST UNE ROUTE IMBRIQUÉE
======================================================================================

« Les ordonnances de ce client » aurait pu s'écrire `?client=<id>` sur une ressource
plate. C'est refusé : un nouveau nom de paramètre devrait entrer dans
`PARAMETRES_RESERVES` (`plateforme/projection/filtres.py`) **dans le même commit**, sans
quoi il produirait le refus unique — et un paramètre de plus est une ligne de plus dans
une liste blanche et un oracle de plus à fermer. La route imbriquée n'introduit rien :
l'identifiant du client est un segment de chemin, pas une clé de requête.

Conséquence directe sur T-04-34 : le queryset est borné par le client **du chemin**, dans
`get_queryset()` et jamais dans `list()`. `get_object()` en hérite, donc
`/api/clients/1/ordonnances/42/` ne peut pas rendre l'ordonnance d'un autre dossier — elle
rend 404. C'est l'IDOR classique de cette forme de code, et il est fermé par construction
plutôt que par vigilance.
"""

from __future__ import annotations

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import exceptions, mixins, permissions, status, viewsets
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from domaine.clients.models import Client
from domaine.ordonnances.models import Ordonnance
from domaine.ordonnances.serializers import (
    OrdonnanceEcritureSerializer,
    OrdonnanceLectureSerializer,
    PhotoOrdonnanceSerializer,
    PhotoTeleverseeSerializer,
)
from domaine.ordonnances.services import (
    PhotoDejaAttachee,
    attacher_photo,
    enregistrer_ordonnance,
)
from domaine.ordonnances.stockage import EXTENSIONS
from plateforme.comptes.permissions_catalogue import Permission
from plateforme.erreurs import erreurs_de_service
from plateforme.projection.vues import acces_de_la_requete


class PeutVoirLesOrdonnances(permissions.BasePermission):
    """`ordonnance.voir` **et** `client.voir`, sur toutes les actions.

    Les deux, et la seconde n'est pas du zèle : la route nomme un client dans son chemin.
    Un appelant qui détiendrait `ordonnance.voir` sans `client.voir` pourrait énumérer les
    dossiers par identifiant — « celui-ci a trois ordonnances, celui-là aucune » — sans
    jamais atteindre une fiche. Le catalogue ne rend pas `client.voir` prérequis de
    `ordonnance.voir` (`plateforme/comptes/permissions_catalogue.py`), donc la conjonction
    doit être écrite ici plutôt que supposée acquise.
    """

    def has_permission(self, request, view):
        acces = acces_de_la_requete(request)
        return acces.peut(Permission.CLIENT_VOIR) and acces.peut(
            Permission.ORDONNANCE_VOIR
        )


class PeutSaisirUneOrdonnance(permissions.BasePermission):
    """`ordonnance.saisir` dès que la méthode n'est pas sûre.

    **La condition porte sur la méthode HTTP, pas sur le nom de l'action**, et c'est la
    moitié que l'on oublie. Une classe qui n'aurait regardé que `view.action == "create"`
    laisserait passer la première action `@action(methods=["post"])` qu'une phase
    ultérieure ajoute ici — la vue *aurait l'air* protégée. Même raisonnement, et mêmes
    mots, que `PeutModifierLesClients` au plan 04-03.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return acces_de_la_requete(request).peut(Permission.ORDONNANCE_SAISIR)


@extend_schema_view(
    list=extend_schema(
        summary="L'historique des ordonnances d'un client",
        description=(
            "Toutes les versions, la plus récente d'abord. Une version enregistrée se "
            "rend **telle qu'elle a été saisie** : l'affichage ne la revalide jamais, "
            "donc une valeur que les bornes d'aujourd'hui refuseraient s'affiche sans "
            "avertissement, sans badge d'erreur et sans annotation (CLIENT-06)."
        ),
        responses={200: OrdonnanceLectureSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Une version d'ordonnance",
        responses={200: OrdonnanceLectureSerializer},
    ),
    create=extend_schema(
        summary="Saisir une ordonnance",
        description=(
            "Crée une **nouvelle version**. Le numéro de version est émis par le "
            "serveur, sous verrou, dans la transaction d'insertion : un `version` "
            "envoyé dans le corps est ignoré. Les versions précédentes ne sont jamais "
            "réécrites — une correction porte `supersede` et un motif."
        ),
        request=OrdonnanceEcritureSerializer,
        responses={201: OrdonnanceLectureSerializer},
    ),
)
class VueOrdonnances(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """La ressource ordonnance, en lecture et en création seules. Voir l'en-tête du module."""

    serializer_class = OrdonnanceLectureSerializer
    queryset = Ordonnance.objects.all()
    permission_classes = [
        permissions.IsAuthenticated,
        PeutVoirLesOrdonnances,
        PeutSaisirUneOrdonnance,
    ]
    #: Le second verrou de l'immuabilité. Voir le point 1 de l'en-tête : il redit en une
    #: ligne visible en diff ce que l'absence des bases dit en silence.
    http_method_names = ["get", "post", "head", "options"]

    def _client_du_chemin(self) -> Client:
        """La fiche nommée par le chemin, ou **404**.

        Un identifiant inexistant doit rendre 404 et non une liste vide : une liste vide
        dit « ce client n'a pas d'ordonnance », ce qui est une affirmation sur un dossier
        qui n'existe pas. Sur un POST, elle produirait en plus une violation de clé
        étrangère, c'est-à-dire un 500 pour une saisie que l'appelant ne peut pas
        corriger.
        """
        return get_object_or_404(Client, pk=self.kwargs["client_id"])

    def get_queryset(self):
        """Les versions de **ce** client, la plus récente d'abord.

        Le filtre est ici et **jamais dans `list()`** : `get_object()` passe par
        `get_queryset()`, donc la route de détail hérite de la même borne. Filtrer dans
        `list()` laisserait `/api/clients/1/ordonnances/42/` rendre l'ordonnance du
        dossier 7 sur un petit entier deviné — l'IDOR classique de cette forme de code,
        que la revue ne voit pas parce que la liste, elle, est propre (menace T-04-34).

        Le tri est `-version` et non l'ordre par défaut du modèle : la « version en
        cours » est celle qui porte le plus grand numéro, pas la plus récemment
        prescrite. Les deux coïncident presque toujours et divergent exactement là où
        cela compte — une correction saisie aujourd'hui pour une ordonnance de l'an
        dernier.
        """
        return (
            super()
            .get_queryset()
            .filter(client_id=self.kwargs["client_id"])
            .order_by("-version")
        )

    def create(self, request, *args, **kwargs):
        """Valide, délègue au service, puis rend la **lecture** de ce qui a été écrit.

        La vue ne numérote rien : `enregistrer_ordonnance` émet la version sous verrou,
        dans sa transaction. Une numérotation posée ici serait hors de la transaction
        d'insertion, donc sans effet — et l'erreur serait invisible tant que deux
        comptoirs ne saisissent pas en même temps.

        La réponse passe par le sérialiseur de **lecture** : le client reçoit la ligne
        telle qu'elle est désormais stockée, canonicalisation comprise — un cylindre nul
        rangé `NULL`, un axe 0 rangé 180. Renvoyer la charge validée lui montrerait ce
        qu'il a envoyé, c'est-à-dire la seule version du document qu'il connaissait déjà.
        """
        client = self._client_du_chemin()

        ecriture = OrdonnanceEcritureSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        ecriture.is_valid(raise_exception=True)
        valeurs = dict(ecriture.validated_data)
        magasin = valeurs.pop("magasin")

        with erreurs_de_service():
            ordonnance = enregistrer_ordonnance(
                client=client,
                magasin=magasin,
                valeurs=valeurs,
                par=getattr(request.user, "email", "") or "",
            )

        lecture = OrdonnanceLectureSerializer(
            ordonnance, context=self.get_serializer_context()
        )
        return Response(lecture.data, status=status.HTTP_201_CREATED)


# ======================================================================================
# CLIENT-09 — la photo : deux verbes, une route, et aucune adresse directe
# ======================================================================================
class Conflit(exceptions.APIException):
    """409. L'état de la ressource interdit l'écriture, pas la forme de la requête.

    Un 400 dirait à l'appelant « corrigez votre corps de requête et recommencez », ce qui
    est faux : aucun corps ne fera accepter une seconde photo. Un 409 dit que la
    ressource est déjà dans l'état demandé et le restera.
    """

    status_code = status.HTTP_409_CONFLICT
    default_code = "conflit"


@extend_schema_view(
    get=extend_schema(
        summary="Les octets de la photo d'une ordonnance",
        description=(
            "Les octets sortent d'une vue qui a **déjà résolu** `ordonnance.voir` et "
            "`client.voir`. Il n'existe aucune adresse directe, aucun service de "
            "fichiers statiques et aucune adresse pré-signée : une adresse qui "
            "contournerait la permission ferait de la couche de projection un théâtre. "
            "`Storage.url()` lève, précisément pour que personne n'en fabrique une."
        ),
        responses={
            (200, "image/*"): OpenApiTypes.BINARY,
            404: OpenApiResponse(description="Aucune photo sur cette version."),
        },
    ),
    post=extend_schema(
        summary="Attacher la photo d'une ordonnance, **une fois**",
        description=(
            "`null → posée` est la seule mutation permise sur une version enregistrée "
            "(CLIENT-06, décision §28-Q5) : le papier arrive souvent le lendemain. Une "
            "photo ne se remplace ni ne s'efface — sur la mauvaise version, elle se "
            "corrige par une nouvelle version. Taille, type déclaré **et octets "
            "magiques** sont vérifiés."
        ),
        request={"multipart/form-data": PhotoTeleverseeSerializer},
        responses={
            201: PhotoOrdonnanceSerializer,
            409: OpenApiResponse(description="Cette version porte déjà une photo."),
        },
    ),
)
class VuePhotoOrdonnance(APIView):
    """`/api/ordonnances/<id>/photo/` — lire les octets, ou les poser une fois.

    **Une `APIView` rendant un `FileResponse`, et non un rendu au sens de
    `plateforme/projection/`.** La distinction est tranchée ici plutôt que laissée en
    suspens : cette vue ne sérialise aucun champ et ne consulte pas le registre, donc la
    liste `RENDUS` de `tests/test_projection.py` reste à **quatre**. Ce qui la garde,
    c'est son test de droit dédié — `test_client09_l_image_exige_le_droit_ordonnance_voir` —
    et non le test paramétré du registre. Une omission et une décision se ressemblent en
    diff ; celle-ci est écrite.

    **La route est plate, alors que l'historique est imbriqué sous la fiche.** Une
    ordonnance n'est pas scopée au magasin (D-4a) et son identifiant est déjà borné par
    la base du locataire, donc le segment `client` n'ajouterait aucune borne — il
    ajouterait un second identifiant à tenir cohérent, et un 404 de plus à distinguer.

    **`queryset` est déclaré sur une `APIView` exprès.** Il n'est pas utilisé par DRF
    ici ; il fait entrer cette vue dans `_modele_de_la_vue`, donc dans
    `test_client06_aucune_route_ne_modifie_une_ordonnance`, qui vérifie qu'aucune vue
    servant `Ordonnance` ne porte `put`, `patch` ni `delete`. Une garde qui existe déjà
    et qu'il suffit de rejoindre vaut mieux qu'une garde de plus.
    """

    queryset = Ordonnance.objects.all()
    permission_classes = [
        permissions.IsAuthenticated,
        PeutVoirLesOrdonnances,
        PeutSaisirUneOrdonnance,
    ]
    parser_classes = [MultiPartParser]
    #: `delete` est absent, donc `DELETE` rend **405** et non 403. Un 403 dirait que la
    #: route existe et qu'un droit la garde — donc qu'il suffirait d'accorder ce droit
    #: pour effacer une pièce justificative de santé.
    http_method_names = ["get", "post", "head", "options"]

    def _ordonnance(self, pk) -> Ordonnance:
        """La ligne, ou 404 — **après** que le droit a été résolu.

        L'ordre est la garantie : DRF appelle `check_permissions` dans `initial()`, donc
        avant ce corps. Un appelant sans `ordonnance.voir` reçoit exactement le même 403
        pour un identifiant qui existe et pour un identifiant qui n'existe pas, et il
        n'apprend donc rien sur ce que contient la base de cet opticien.
        """
        return get_object_or_404(Ordonnance, pk=pk)

    def get(self, request, pk):
        ordonnance = self._ordonnance(pk)
        if not ordonnance.photo:
            raise exceptions.NotFound("Cette version n'a pas de photo.")
        fichier = ordonnance.photo.storage.open(ordonnance.photo.name)
        return FileResponse(
            fichier,
            content_type=ordonnance.photo_type or "application/octet-stream",
            # Un nom **fabriqué** pour l'éventuel « enregistrer sous » : la version et
            # rien d'autre. Le nom du fichier envoyé n'existe plus depuis l'attache, et
            # le nom stocké est un détail interne qui n'a rien à faire dans un en-tête.
            filename=f"ordonnance-v{ordonnance.version}"
            f"{EXTENSIONS.get(ordonnance.photo_type, '')}",
        )

    def post(self, request, pk):
        ordonnance = self._ordonnance(pk)
        entree = PhotoTeleverseeSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        try:
            with erreurs_de_service():
                attacher_photo(
                    ordonnance,
                    entree.validated_data["fichier"],
                    par=getattr(request.user, "email", "") or "",
                )
        except PhotoDejaAttachee as erreur:
            # Traduit ici et non dans `erreurs_de_service` : ce n'est pas une erreur de
            # validation, et la faire passer par le traducteur commun la rendrait 400.
            raise Conflit(str(erreur)) from erreur

        return Response(
            PhotoOrdonnanceSerializer(
                {
                    "a_une_photo": True,
                    "photo_type": ordonnance.photo_type,
                    "photo_octets": ordonnance.photo_octets,
                    "photo_attachee_le": ordonnance.photo_attachee_le,
                    "photo_par": ordonnance.photo_par,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )

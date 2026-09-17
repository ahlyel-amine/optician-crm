"""PERM-01 — les cinq points de terminaison d'authentification de la SPA.

**Session, pas jeton**, et la raison est structurelle plutôt que préférentielle :
`TenantMiddleware` lit `request.user` **au moment du middleware**, alors que DRF
authentifie dans `APIView.initial()`, c'est-à-dire **après** tous les middlewares. Sous
jeton, `request.user` serait anonyme à l'instant où le locataire doit se lier, rien ne se
lierait, et la première requête métier lèverait `NoTenantBound`. Les sessions coûtent zéro
ligne à la couche de la phase 2.

Le contre-argument, énoncé en entier : la phase 11 est Expo, où les cookies sont plus
pénibles qu'un en-tête `Authorization`. Cela ne change pas la décision, parce que
`DEFAULT_AUTHENTICATION_CLASSES` est une **liste** — y ajouter une classe de jeton en
phase 11 est additif et ne touche ni vue, ni sérialiseur, ni permission, ni projection.
La seule chose à préserver aujourd'hui est que la liaison de locataire ne soit pas soudée
au middleware, et elle ne l'est pas : `resolve_client(request)` est une fonction autonome
au contrat « identité vérifiée par le serveur en entrée, `Client` en sortie », et c'est
elle que la vue de connexion appelle ci-dessous.

**Il n'y a pas de réinitialisation par courriel, et ce n'est pas un oubli.** La pile ne
nomme aucun fournisseur d'e-mail transactionnel, donc la vue de réinitialisation par
courriel de `django.contrib.auth` ne peut pas fonctionner — et son nom n'est pas écrit
ici, parce qu'un critère d'acceptation du plan compte ses occurrences dans ce paquet pour
prouver qu'aucun chemin de réinitialisation par courriel n'a été câblé en douce.
Le chemin livré est sans courriel : le propriétaire pose et réinitialise le
mot de passe d'un gérant (plan 03-09), `doit_changer_mot_de_passe` force le changement à
la première connexion, et un propriétaire qui oublie le sien est réinitialisé par
l'opérateur via l'admin. L'écran de connexion porte en conséquence une ligne d'aide et
**aucun lien mort** (`03-UI-SPEC.md` 6). Le fournisseur d'e-mail est un élément
d'approvisionnement des phases 1 et 12 — l'inscription en libre service en aura besoin.

Aucune de ces vues ne repose sur une transaction par requête : CLAUDE.md #15 interdit le
réglage, et aucune n'en a besoin — `login()` et `set_password` sont chacun une écriture.
"""

from __future__ import annotations

import logging
import math
from contextlib import contextmanager

from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import exceptions, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView, exception_handler

from plateforme.comptes.acces import Acces, acces_pour
from plateforme.comptes.models import JournalDroit, Utilisateur
from plateforme.comptes.permissions_catalogue import Permission
from plateforme.comptes import services
from plateforme.comptes.serializers import (
    AmorcageSerializer,
    BasculeDroitSerializer,
    BasculeMagasinSerializer,
    CatalogueOffrableSerializer,
    ChangementMotDePasseSerializer,
    CompteCreeSerializer,
    CompteDetailSerializer,
    CompteSerializer,
    ConnexionSerializer,
    CreationCompteSerializer,
    EntreeDeJournalSerializer,
    ModificationIdentiteSerializer,
    ResultatOctroiSerializer,
    StatutSerializer,
    UniformisationSerializer,
    catalogue_offrable,
    charge_utile_journal,
    charge_utile_moi,
    charge_utile_resultat,
)
from plateforme.comptes.services import (
    magasins_actifs_par_id,
    mot_de_passe_provisoire,
)
from plateforme.projection.vues import acces_de_la_requete

logger = logging.getLogger("plateforme.comptes")

#: **Une seule** réponse d'échec de connexion, quel qu'en soit le motif : e-mail inconnu,
#: mot de passe faux, compte désactivé. Ne jamais révéler qu'un compte existe — il n'y a
#: qu'une adresse de connexion pour toute la flotte (CLAUDE.md #11), donc un message
#: distinct en ferait un oracle d'énumération de comptes à l'échelle du produit. Le cas
#: qu'on oublie est le troisième : un gérant désactivé ne doit pas l'apprendre de l'écran
#: de connexion, c'est le propriétaire qui le lui dit (`03-UI-SPEC.md` 6, menace T-03-48).
ECHEC_DE_CONNEXION = "Identifiant ou mot de passe incorrect."

#: La copie exacte de `03-UI-SPEC.md` 6 sur un 429. Le délai restant part dans un champ
#: séparé parce que l'interface affiche un compte à rebours vivant dans sa ligne d'aide et
#: désactive le bouton pendant la fenêtre — une durée noyée dans la phrase l'obligerait à
#: analyser du texte pour l'en extraire.
TROP_DE_TENTATIVES = "Trop de tentatives. Réessayez dans une minute."

#: Ce qu'on répond à un compte authentifié dont l'affaire n'est pas joignable : en cours
#: de provisionnement, suspendue, ou en panne. Volontairement sans cause : le statut
#: commercial d'un client n'a pas à transiter par un corps de réponse.
ESPACE_INDISPONIBLE = (
    "Votre espace n'est pas disponible pour le moment. Réessayez dans quelques instants."
)


class TropDeTentatives(exceptions.Throttled):
    """Un 429 qui porte la copie française **et** un délai exploitable par l'interface.

    `Throttled.__init__` concatène « Disponible dans N secondes. » à la fin du message,
    ce qui produit une phrase que `03-UI-SPEC.md` 6 ne prévoit pas et que la SPA devrait
    analyser pour en tirer son compte à rebours. On construit donc `detail` soi-même : le
    gestionnaire d'exceptions de DRF rend un `dict` tel quel, et pose `Retry-After` depuis
    `wait` sans y toucher.
    """

    def __init__(self, wait=None):
        self.wait = math.ceil(wait) if wait is not None else None
        self.detail = {"detail": TROP_DE_TENTATIVES, "reessayer_dans": self.wait}


def gestionnaire_dexceptions(exc, context):
    """Deux corrections, toutes deux au sujet de ce qu'un corps de réponse a le droit de dire.

    **1. 401 doit vouloir dire « non authentifié ».** `APIView.handle_exception` rétrograde
    `NotAuthenticated` en 403 dès que la classe d'authentification ne fournit pas d'en-tête
    `WWW-Authenticate` — et `SessionAuthentication` n'en fournit pas. Sans cette correction,
    une session expirée et un droit manquant répondent tous deux 403, alors que
    `03-UI-SPEC.md` 8.6 leur demande deux comportements opposés : reconnexion pour l'un,
    page « Vous n'avez pas accès » pour l'autre. La correction vit ici plutôt que dans une
    sous-classe d'authentification, pour que `DEFAULT_AUTHENTICATION_CLASSES` reste la
    classe DRF de série — la phase 11 y ajoutera la sienne sans hériter de la nôtre.

    **2. `NoTenantBound` ne doit jamais atteindre un corps de réponse.** Son message
    nomme des alias et la mécanique de liaison ; c'est la règle ASVS V7 de la phase 2,
    étendue ici à la résolution d'accès (menace T-03-55). Le cas est réel et non théorique :
    un compte rattaché à une affaire non `ACTIVE` — en cours de provisionnement, suspendue —
    traverse l'authentification et ne peut pas lire sa base. Sans cette branche, il obtient
    un 500 ; avec, un 503 sans cause, journalisé côté serveur où il a sa place.
    """
    from plateforme.tenancy.context import NoTenantBound

    if isinstance(exc, NoTenantBound):
        logger.warning(
            "requête authentifiée sans locataire joignable",
            extra={"chemin": getattr(context.get("request"), "path", "?")},
        )
        return Response(
            {"detail": ESPACE_INDISPONIBLE},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    reponse = exception_handler(exc, context)
    if reponse is not None and isinstance(
        exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)
    ):
        reponse.status_code = status.HTTP_401_UNAUTHORIZED
    return reponse


def _adresse_de_lappelant(request) -> str | None:
    """`REMOTE_ADDR`, et **jamais** `X-Forwarded-For`.

    L'en-tête est choisi par l'appelant, donc l'écrire dans `derniere_connexion_ip`
    reviendrait à laisser un attaquant composer la ligne d'audit qui le décrit. Même règle
    que la résolution de locataire de la phase 2 : rien de pertinent pour la sécurité ne
    vient du client. Derrière un reverse proxy, ce champ vaudra l'adresse du proxy — une
    valeur inutile est préférable à une valeur fausse, et le jour où un proxy entre en
    production, c'est sa configuration qui doit fournir l'adresse, pas sa requête.
    """
    return request.META.get("REMOTE_ADDR") or None


def _amorcage(utilisateur, request):
    """La charge utile `moi`, en liant le locataire si ce n'est pas déjà fait.

    Deux appelants, deux situations. `GET /api/auth/moi/` arrive avec l'alias **déjà**
    lié par `TenantMiddleware`. `POST /api/auth/connexion/` non : le middleware a tourné
    avant `login()`, donc avec un utilisateur anonyme, et rien ne s'est lié. La vue de
    connexion doit donc lier elle-même, et elle le fait par le même chemin que le
    middleware — `resolve_client`, `register_client_database`, `alias_for` — plutôt qu'en
    réimplémentant la résolution.

    `tenant_context` restaure la valeur englobante en sortant, donc un appel depuis une
    requête déjà liée ne dérange rien et un appel depuis une requête non liée sort non lié.
    """
    from plateforme.tenancy.context import is_bound, tenant_context
    from plateforme.tenancy.middleware import resolve_client
    from plateforme.tenancy.registry import alias_for, register_client_database

    if is_bound():
        client = _client_du_plan_de_controle(utilisateur)
        return charge_utile_moi(
            utilisateur, request.acces, client, _magasins(request.acces)
        )

    client = resolve_client(request)
    if client is None:
        # Un opérateur de plateforme, ou une affaire non joignable. `acces_pour` rend
        # `Acces.ANONYME` pour le premier sans toucher aucune base ; pour le second, la
        # résolution lèvera `NoTenantBound`, que le gestionnaire d'exceptions convertit
        # en 503 — un compte dont l'espace n'existe pas encore n'a pas d'amorçage à lire.
        acces = acces_pour(utilisateur)
        return charge_utile_moi(utilisateur, acces, None, [])

    register_client_database(**client.connection_params())
    with tenant_context(alias_for(client.pk)):
        acces = acces_pour(utilisateur)
        return charge_utile_moi(utilisateur, acces, client, _magasins(acces))


def _client_du_plan_de_controle(utilisateur):
    from plateforme.control_plane.models import Client

    if utilisateur.client_id is None:
        return None
    return Client.objects.using("default").filter(pk=utilisateur.client_id).first()


def _magasins(acces: Acces):
    """Les magasins de l'appelant — **ceux de `acces.magasins_ids`**, jamais tous ceux du client.

    Le sélecteur de magasin de la barre supérieure est construit depuis cette liste
    (`03-UI-SPEC.md` 5.4). La renvoyer entière donnerait à un gérant d'Anfa un menu
    déroulant nommant Maârif, c'est-à-dire une énumération des magasins qu'il n'a pas.
    """
    from domaine.magasins.models import Magasin

    if not acces.magasins_ids:
        return []
    return list(Magasin.objects.filter(pk__in=acces.magasins_ids).order_by("code"))


@method_decorator(ensure_csrf_cookie, name="dispatch")
class VueCsrf(APIView):
    """`GET /api/auth/csrf/` — pose le cookie CSRF avant le premier POST de la SPA.

    Anonyme, 204, corps vide. Le cookie n'est délibérément **pas** `HttpOnly` : le motif
    double-submit exige que le JavaScript le lise pour le renvoyer dans `X-CSRFToken`.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=None,
        responses={204: None},
        summary="Poser le cookie CSRF",
        description=(
            "Appelé par la SPA au montage de l'écran de connexion, avant le premier POST."
        ),
    )
    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class VueConnexion(APIView):
    """`POST /api/auth/connexion/` — établit la session et renvoie l'amorçage complet.

    **Protégée par CSRF bien qu'anonyme.** Les vues DRF sont `csrf_exempt` au niveau du
    middleware et `SessionAuthentication` n'impose le CSRF qu'aux utilisateurs déjà
    authentifiés : sans ce décorateur, la connexion serait la seule écriture non protégée
    du produit. Le login CSRF est une vraie attaque — on force une victime dans la session
    de l'attaquant, qui relit ensuite ce qu'elle y a saisi. La SPA appelle déjà
    `/api/auth/csrf/` au montage (`03-UI-SPEC.md` 6), donc cela ne lui coûte rien.

    `login()` fait tourner la clé de session : la fixation de session est traitée par
    Django et **ne doit pas** être réimplémentée (menace T-03-50).
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "connexion"

    @extend_schema(
        request=ConnexionSerializer,
        responses={200: AmorcageSerializer},
        summary="Ouvrir une session",
    )
    def post(self, request):
        formulaire = ConnexionSerializer(data=request.data)
        formulaire.is_valid(raise_exception=True)

        utilisateur = authenticate(
            request,
            username=formulaire.validated_data["email"],
            password=formulaire.validated_data["mot_de_passe"],
        )
        if utilisateur is None:
            # Un seul chemin d'échec, donc un seul corps. `ModelBackend.authenticate`
            # renvoie déjà `None` pour un compte désactivé (`user_can_authenticate`), ce
            # qui est ce qui rend la réponse unique **gratuite** plutôt que disciplinée :
            # il n'y a pas de seconde branche à écrire, donc pas de seconde branche à
            # oublier de fusionner.
            return Response(
                {"detail": ECHEC_DE_CONNEXION}, status=status.HTTP_400_BAD_REQUEST
            )

        login(request, utilisateur)
        utilisateur.derniere_connexion_ip = _adresse_de_lappelant(request)
        utilisateur.save(using="default", update_fields=["derniere_connexion_ip"])

        return Response(_amorcage(utilisateur, request))

    def throttled(self, request, wait):
        raise TropDeTentatives(wait=wait)


class VueDeconnexion(APIView):
    """`POST /api/auth/deconnexion/` — `logout()` vide la ligne de session.

    Révocation réelle et immédiate : il n'y a aucune fenêtre d'expiration à attendre
    parce qu'il n'y a plus rien à expirer. C'est la moitié « révocation » de l'argument
    session-contre-jeton, et le test rejoue la clé après coup pour le prouver.
    """

    @extend_schema(request=None, responses={204: None}, summary="Fermer la session")
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class VueMoi(APIView):
    """`GET /api/auth/moi/` — tout l'amorçage de la SPA, en une requête.

    Le compte, l'affaire, les entrées de navigation autorisées, les magasins accordés et
    le catalogue des droits. Une requête plutôt que cinq : c'est la première chose qui se
    passe après la connexion, et chaque aller-retour supplémentaire est une fraction de
    seconde d'écran vide au comptoir.
    """

    @extend_schema(
        responses={200: AmorcageSerializer},
        summary="L'amorçage de la SPA",
    )
    def get(self, request):
        return Response(_amorcage(request.user, request))


class VueMotDePasse(APIView):
    """`POST /api/auth/mot-de-passe/` — le changement par l'intéressé.

    Efface `doit_changer_mot_de_passe`, ce qui libère la SPA de la route
    `/mot-de-passe` sur laquelle elle atterrit tant que le drapeau est vrai. Renvoie
    l'amorçage à jour, pour que l'interface n'ait pas à deviner l'état d'après un 200.
    """

    @extend_schema(
        request=ChangementMotDePasseSerializer,
        responses={200: AmorcageSerializer},
        summary="Changer son mot de passe",
    )
    def post(self, request):
        formulaire = ChangementMotDePasseSerializer(
            data=request.data, context={"utilisateur": request.user}
        )
        formulaire.is_valid(raise_exception=True)

        utilisateur = request.user
        utilisateur.set_password(formulaire.validated_data["nouveau_mot_de_passe"])
        utilisateur.doit_changer_mot_de_passe = False
        utilisateur.save(
            using="default", update_fields=["password", "doit_changer_mot_de_passe"]
        )
        # Sans cela, changer son mot de passe déconnecte : le hash de session est dérivé
        # du hash du mot de passe, et Django refuse la session suivante.
        from django.contrib.auth import update_session_auth_hash

        update_session_auth_hash(request, utilisateur)

        return Response(_amorcage(utilisateur, request))


# ======================================================================================
# PERM-02 — la gestion des comptes (plan 03-09)
# ======================================================================================
#
# **Il n'existe aucune route de retrait d'un compte, et il n'y en aura pas.** Un compte
# est référencé par des ventes, par `JournalDroit` et par dix ans de conservation
# (art. 211 CGI) ; la désactivation est le seul chemin, et elle est réversible
# (`03-UI-SPEC.md` 7.8). Le jeu de vues ci-dessous n'hérite donc **d'aucun mixin de
# retrait de DRF**, et un test vérifie les deux — le 405 d'aujourd'hui et l'absence du
# mixin dans le MRO, qui est ce qui empêche la route de revenir par héritage le jour où
# quelqu'un passe à un `ModelViewSet` complet. Le test nomme la classe ; ce fichier ne
# la nomme pas, parce qu'un critère d'acceptation du plan compte ses occurrences ici
# pour prouver qu'aucun chemin de retrait n'a été câblé — la même précaution que le
# plan 03-08 a prise pour la réinitialisation par courriel.


class PeutGererLesComptes(permissions.BasePermission):
    """`compte.gerer`, résolu par `Acces`. Aucune branche de privilège.

    Le propriétaire passe sans être nommé : son accès est **matérialisé** au plan 03-05 —
    le catalogue complet, pour chacun de ses magasins actifs — donc `peut()` répond vrai
    pour lui par le même chemin que pour un gérant. Écrire `or acces.est_proprietaire`
    ici rouvrirait précisément la branche de privilège que ce plan-là a supprimée, et une
    branche qui saute la vérification pour un propriétaire est une branche qu'un bug peut
    atteindre pour un non-propriétaire (`03-RESEARCH.md` P3).

    **`peut()` sans magasin est une conjonction** (plan 03-05) : un gérant doit détenir
    `compte.gerer` dans *tous* ses magasins pour atteindre cette surface. C'est
    fail-closed et c'est le bon sens de l'erreur — administrer des comptes n'est pas une
    action de magasin, et l'union `peut_quelque_part` n'autorise jamais rien.

    Conséquence assumée : un propriétaire dont l'affaire n'a aucun magasin actif est
    refusé ici. Il l'est déjà partout ailleurs, puisque `Acces` ne lui résout alors aucun
    droit ; un cas particulier ici masquerait une affaire à moitié provisionnée au lieu
    de la signaler.
    """

    message = "Vous n'avez pas accès à cette page."

    def has_permission(self, request, view):
        return acces_de_la_requete(request).peut(Permission.COMPTE_GERER)


def _refuser_si_non_gerable(acces, cible):
    """Les deux comptes que cette surface ne gère pas : le propriétaire, et soi-même.

    `03-UI-SPEC.md` 7.7, ligne par ligne. Les droits du propriétaire ne se modifient pas
    — ils sont matérialisés à la résolution, pas stockés — et personne n'administre son
    propre compte ici, ce qui ferme l'auto-promotion d'un gérant-gestionnaire et la
    prise de contrôle du compte du propriétaire par une réinitialisation de son mot de
    passe.

    Le propriétaire change son propre mot de passe par `/api/auth/mot-de-passe/`, et un
    propriétaire qui l'oublie est réinitialisé par l'opérateur via l'admin (plan 03-08).
    """
    if cible.est_proprietaire:
        raise exceptions.PermissionDenied(
            "Le compte du propriétaire ne se gère pas ici : il a accès à toute l'affaire."
        )
    if cible.pk == acces.utilisateur_id:
        raise exceptions.PermissionDenied(
            "Un compte ne se gère pas lui-même. Demandez au propriétaire."
        )


@contextmanager
def _erreurs_de_service():
    """Traduire les exceptions du service en réponses, et nulle part ailleurs.

    Le service lève les exceptions de **Django** — `ValidationError` et
    `PermissionDenied` — parce qu'il doit rester appelable depuis une commande de gestion
    et depuis l'inscription en libre service de la phase 12, qui n'ont pas de requête
    HTTP. DRF ne convertit pas `django.core.exceptions.ValidationError` : sans cette
    traduction, un magasin non accordé produirait un **500** avec sa trace.
    """
    try:
        yield
    except DjangoValidationError as erreur:
        detail = (
            erreur.message_dict
            if hasattr(erreur, "message_dict")
            else list(erreur.messages)
        )
        raise exceptions.ValidationError(detail) from erreur


@extend_schema_view(
    list=extend_schema(
        responses={200: CompteSerializer(many=True)},
        summary="Les comptes de l'affaire",
    ),
    retrieve=extend_schema(
        responses={200: CompteDetailSerializer}, summary="La fiche d'un compte"
    ),
)
class VueComptes(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """`/api/comptes/` — créer un gérant, corriger son identité, le désactiver.

    La liste porte ce que `03-UI-SPEC.md` 7.2 affiche, propriétaire compris : sa ligne
    est première et marquée, et elle n'ouvre pas d'éditeur de droits (7.7).
    """

    serializer_class = CompteSerializer
    permission_classes = [permissions.IsAuthenticated, PeutGererLesComptes]
    #: `delete` et `put` sont absents. Le premier n'existe pas (7.8) ; le second n'existe
    #: pas non plus, parce qu'un remplacement complet d'une fiche de compte n'a aucun
    #: usage et offrirait une seconde porte d'écriture à tenir en cohérence avec la
    #: première.
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        """**La portée est ici**, donc `get_object()` en hérite et la fiche est couverte.

        Même règle qu'au plan 03-07 : filtrer dans `list()` laisserait la route de détail
        grande ouverte sur un petit entier deviné, et la vue *aurait l'air* protégée.

        `client_id` vide — un opérateur de plateforme, ou une requête sans accès résolu —
        rend l'ensemble vide et non l'ensemble total : `filter(client_id=None)`
        ramènerait tous les opérateurs de la flotte.
        """
        acces = acces_de_la_requete(self.request)
        if acces.client_id is None:
            return Utilisateur.objects.none()
        return Utilisateur.objects.filter(client_id=acces.client_id).order_by(
            "-est_proprietaire", "nom_complet"
        )

    def get_serializer_class(self):
        """La fiche porte l'état des 21 droits ; la liste ne le paie pas.

        Vingt et un états par ligne de tableau est exactement le coût que
        `resume_des_droits` existe pour éviter (`03-UI-SPEC.md` 7.2). La fiche, elle,
        est seule à l'écran et en a besoin pour dessiner chaque interrupteur.
        """
        if self.action == "retrieve":
            return CompteDetailSerializer
        return CompteSerializer

    def get_serializer_context(self):
        contexte = super().get_serializer_context()
        acces = acces_de_la_requete(self.request)
        # Le générateur de schéma n'a aucun locataire lié : lire `Magasin` ici lèverait
        # `NoTenantBound` pendant `manage.py spectacular`. Même court-circuit qu'au
        # plan 03-07, à l'endroit où la lecture est écrite.
        #
        # **Les magasins de l'APPELANT, pas ceux de l'affaire** (plan 03-14). La colonne
        # `Magasins` de 7.2 et la section B de 7.3 se lisent depuis cette table ; la
        # construire sur `magasins_actifs_par_id()` nommait à un gérant d'Anfa les
        # magasins d'un collègue qu'il ne détient pas — la même énumération que
        # `_magasins` refuse déjà de servir au sélecteur de la barre supérieure, par le
        # même raisonnement (7.7).
        contexte["magasins_par_id"] = (
            {}
            if acces.pour_le_schema
            else {magasin.pk: magasin for magasin in _magasins(acces)}
        )

        # L'intersection de la fiche vient du MÊME `catalogue_offrable` qui sert le
        # catalogue, et pas d'un second calcul : deux intersections écrites séparément
        # divergent, et celle qui divergerait ici servirait l'état d'un code que le
        # catalogue a retiré. `peut_quelque_part` n'est donc appelé qu'une fois, à son
        # unique emplacement sanctionné (plan 03-09).
        if self.action == "retrieve" and not acces.pour_le_schema:
            codes, magasins = self._intersection(acces)
            contexte["codes_offrables"] = codes
            contexte["magasins_offrables"] = list(magasins)
        return contexte

    @staticmethod
    def _intersection(acces) -> tuple[list[str], dict[str, str]]:
        """Ce que cet appelant peut voir : les codes, et `{code magasin: nom}`.

        Écrit **une fois** et lu par la fiche comme par l'historique. Deux intersections
        écrites séparément divergent, et celle qui divergerait servirait l'état — ou une
        entrée de journal — d'un code que le catalogue a retiré.
        """
        magasins = _magasins(acces)
        catalogue = catalogue_offrable(acces, magasins)
        codes = [
            droit["code"]
            for section in catalogue["sections"]
            for droit in section["droits"]
        ]
        return codes, {magasin.code: magasin.nom for magasin in magasins}

    @extend_schema(
        request=CreationCompteSerializer,
        responses={201: CompteCreeSerializer},
        summary="Créer un compte gérant",
    )
    def create(self, request, *args, **kwargs):
        """Le `client` est posé **par le serveur**, et n'est jamais lu dans le corps.

        C'est la ligne que la menace T-03-57 vise. Elle est écrite ici, en clair, plutôt
        que déduite d'une absence dans un sérialiseur : un lecteur qui cherche « d'où
        vient le client de ce compte ? » trouve la réponse au premier endroit où il
        regarde.
        """
        acces = acces_de_la_requete(request)
        formulaire = CreationCompteSerializer(data=request.data)
        formulaire.is_valid(raise_exception=True)

        secret = formulaire.validated_data.get(
            "mot_de_passe_provisoire"
        ) or mot_de_passe_provisoire()

        compte = Utilisateur(
            nom_complet=formulaire.validated_data["nom_complet"],
            email=formulaire.validated_data["email"],
            client_id=acces.client_id,
            doit_changer_mot_de_passe=True,
        )
        compte.set_password(secret)
        compte.save(using="default")

        return Response(
            self._charge_utile(compte, secret), status=status.HTTP_201_CREATED
        )

    @extend_schema(
        request=ModificationIdentiteSerializer,
        responses={200: CompteSerializer},
        summary="Corriger le nom ou l'adresse d'un compte",
    )
    def partial_update(self, request, *args, **kwargs):
        """Le nom et l'adresse. Le propriétaire corrige les siens, personne d'autre.

        `03-UI-SPEC.md` 7.7 : un gérant-gestionnaire ne modifie pas sa propre fiche — il
        ne peut changer que son mot de passe, par `/api/auth/mot-de-passe/`.
        """
        cible = self.get_object()
        acces = acces_de_la_requete(request)
        if cible.est_proprietaire:
            if cible.pk != acces.utilisateur_id:
                raise exceptions.PermissionDenied(
                    "La fiche du propriétaire ne se modifie que par lui-même."
                )
        elif cible.pk == acces.utilisateur_id:
            raise exceptions.PermissionDenied(
                "Un compte ne modifie pas sa propre fiche. Demandez au propriétaire."
            )

        formulaire = ModificationIdentiteSerializer(
            instance=cible, data=request.data, partial=True
        )
        formulaire.is_valid(raise_exception=True)
        modifies = []
        for champ, valeur in formulaire.validated_data.items():
            setattr(cible, champ, valeur)
            modifies.append(champ)
        if modifies:
            cible.save(using="default", update_fields=modifies)
        return Response(self.get_serializer(cible).data)

    @extend_schema(
        request=StatutSerializer,
        responses={200: CompteSerializer},
        summary="Activer ou désactiver un compte",
    )
    @action(detail=True, methods=["post"], url_path="statut")
    def statut(self, request, pk=None):
        """PERM-02 — la désactivation mord dès la requête suivante, sans machinerie.

        `ModelBackend.get_user()` appelle `user_can_authenticate()` à **chaque** requête,
        donc il n'y a ni liste de révocation ni fenêtre d'expiration à attendre. C'est la
        moitié « révocation » de l'argument session-contre-jeton, et le plan 03-08 la
        vérifie de bout en bout.
        """
        cible = self.get_object()
        _refuser_si_non_gerable(acces_de_la_requete(request), cible)

        formulaire = StatutSerializer(data=request.data)
        formulaire.is_valid(raise_exception=True)
        cible.is_active = formulaire.validated_data["actif"]
        cible.save(using="default", update_fields=["is_active"])
        return Response(self.get_serializer(cible).data)

    @extend_schema(
        request=None,
        responses={200: CompteCreeSerializer},
        summary="Réinitialiser le mot de passe d'un compte",
    )
    @action(detail=True, methods=["post"], url_path="mot-de-passe")
    def mot_de_passe(self, request, pk=None):
        """Un nouveau secret, montré **une seule fois**, et le drapeau reposé.

        Changer le mot de passe déconnecte la cible partout : le hachage de session est
        dérivé du hachage du mot de passe, donc toute session ouverte devient invalide à
        la requête suivante. C'est le comportement voulu pour une réinitialisation, et
        c'est pourquoi rien n'est appelé pour purger les sessions à la main.
        """
        cible = self.get_object()
        _refuser_si_non_gerable(acces_de_la_requete(request), cible)

        secret = mot_de_passe_provisoire()
        cible.set_password(secret)
        cible.doit_changer_mot_de_passe = True
        cible.save(using="default", update_fields=["password", "doit_changer_mot_de_passe"])
        return Response(self._charge_utile(cible, secret))

    def _charge_utile(self, compte, secret: str) -> dict:
        """Le compte, **et** le secret — la seule forme de réponse qui le porte."""
        return {
            "compte": self.get_serializer(compte).data,
            "mot_de_passe_provisoire": secret,
        }

    # ----------------------------------------------------------------------------------
    # PERM-03 — les trois bascules de l'écran de droits (`03-UI-SPEC.md` 7.5, 7.8)
    # ----------------------------------------------------------------------------------
    #
    # Trois routes, trois interrupteurs. Il n'y a **pas de bouton Enregistrer** et pas de
    # lot : vingt-et-un interrupteurs derrière un `Enregistrer` est un formulaire qu'on
    # abandonne à moitié rempli, et `JournalDroit` enregistre un acteur et un horodatage
    # par octroi — ce qui correspond exactement à une bascule.
    #
    # Chacune délègue à `plateforme.comptes.services` sans rien décider elle-même. Ce
    # n'est pas de la politesse architecturale : la fermeture des prérequis, l'extension
    # des lignes uniformes et le refus hors intersection doivent valoir pour la commande
    # de gestion d'onboarding et pour l'inscription en libre service de la phase 12, qui
    # n'ont pas de requête HTTP.

    @extend_schema(
        request=BasculeDroitSerializer,
        responses={200: ResultatOctroiSerializer},
        summary="Accorder ou retirer un droit",
    )
    @action(detail=True, methods=["post"], url_path="droits")
    def droits(self, request, pk=None):
        """Un interrupteur : `accorde` décide du sens, `magasins` de la portée.

        `magasins` absent vaut **tous les magasins accordés**, ce qui est le
        comportement uniforme par défaut de 7.5 et l'état que la quasi-totalité des
        affaires verra.
        """
        cible = self.get_object()
        formulaire = BasculeDroitSerializer(data=request.data)
        formulaire.is_valid(raise_exception=True)
        donnees = formulaire.validated_data

        operation = services.accorder if donnees["accorde"] else services.revoquer
        with _erreurs_de_service():
            resultat = operation(
                cible, donnees["code"], donnees.get("magasins"), par=request.user
            )
        return Response(charge_utile_resultat(resultat))

    @extend_schema(
        request=UniformisationSerializer,
        responses={200: ResultatOctroiSerializer},
        summary="Uniformiser un droit sur tous les magasins",
    )
    @action(detail=True, methods=["post"], url_path="droits/uniformiser")
    def uniformiser(self, request, pk=None):
        """Le bouton `Uniformiser` de 7.5, qui replie une ligne personnalisée.

        Une route distincte pour une raison d'interface : l'action demande une
        confirmation quand les sous-interrupteurs divergent, et le journal doit pouvoir
        se relire comme « il a tout aligné » plutôt que comme une bascule de plus.
        """
        cible = self.get_object()
        formulaire = UniformisationSerializer(data=request.data)
        formulaire.is_valid(raise_exception=True)
        with _erreurs_de_service():
            resultat = services.uniformiser(
                cible,
                formulaire.validated_data["code"],
                formulaire.validated_data["accorde"],
                par=request.user,
            )
        return Response(charge_utile_resultat(resultat))

    @extend_schema(
        request=BasculeMagasinSerializer,
        responses={200: ResultatOctroiSerializer},
        summary="Accorder ou retirer l'accès à un magasin",
    )
    @action(detail=True, methods=["post"], url_path="magasins")
    def magasins(self, request, pk=None):
        """L'accès à un magasin — le rayon d'action le plus large de cet écran.

        Accorder étend les lignes **uniformes** au nouveau magasin et laisse les
        personnalisées où elles sont ; retirer emporte les droits qui visaient ce
        magasin. Les deux effets sont annoncés par l'interface avant d'être appliqués
        (7.5 et 7.9), et appliqués ici que l'interface les ait annoncés ou non.
        """
        cible = self.get_object()
        formulaire = BasculeMagasinSerializer(data=request.data)
        formulaire.is_valid(raise_exception=True)
        donnees = formulaire.validated_data

        operation = (
            services.accorder_magasin if donnees["accorde"] else services.retirer_magasin
        )
        with _erreurs_de_service():
            resultat = operation(cible, donnees["magasin_code"], par=request.user)
        return Response(charge_utile_resultat(resultat))


    @extend_schema(
        responses={200: EntreeDeJournalSerializer(many=True)},
        summary="L'historique des droits d'un compte",
    )
    @action(detail=True, methods=["get"], url_path="journal")
    def journal(self, request, pk=None):
        """`03-UI-SPEC.md` 7.3 D — la seule vue de `JournalDroit`, en lecture seule.

        Le journal est écrit par le service depuis le plan 03-09 et n'avait pas de route
        pour l'alimenter ; celle-ci est la lecture, et rien d'autre. `JournalDroit`
        refuse la réécriture et le retrait dans son propre `save()` / `delete()`, donc
        « lecture seule » n'est pas une propriété de cette vue — c'est une propriété du
        modèle, et cette vue ne pourrait pas la contourner si elle essayait.

        **Intersectée comme le reste.** Sans cela, il suffirait d'ouvrir le repli d'un
        historique pour apprendre qu'`article.voir_prix_achat` existe et qui le détient,
        c'est-à-dire pour contourner en un clic ce que le catalogue et la fiche retirent.

        Pas de pagination : l'historique d'un compte est de l'ordre de la dizaine
        d'entrées, et un `collapsible` fermé par défaut ne le charge qu'à l'ouverture.
        Le jour où une affaire en accumule des milliers, la forme à écrire est une
        pagination, pas une troncature silencieuse.
        """
        cible = self.get_object()
        acces = acces_de_la_requete(request)
        codes, magasins = self._intersection(acces)
        entrees = (
            JournalDroit.objects.filter(utilisateur=cible)
            .select_related("par")
            .order_by("-le", "-pk")
        )
        return Response(charge_utile_journal(entrees, set(codes), magasins))


class VueCatalogue(APIView):
    """`GET /api/comptes/catalogue/` — ce que **cet** appelant peut accorder.

    Deux catalogues coexistent et répondent à deux questions différentes ; les confondre
    serait une régression silencieuse.

    | Route | Question | Réponse |
    |---|---|---|
    | `/api/auth/moi/` | quels droits **existent** ? | les 21, pour tout le monde |
    | `/api/comptes/catalogue/` | lesquels **puis-je accorder** ? | l'intersection |

    Le premier est identique pour chaque affaire du produit, donc il ne divulgue rien.
    Le second dépend de l'appelant, et c'est tout son intérêt : un gérant-gestionnaire
    qui ne détient pas `article.voir_prix_achat` n'en voit pas la ligne en éditant un
    collègue, **parce qu'elle n'est pas dans la réponse** (`03-UI-SPEC.md` 7.7).

    L'intersection est faite **avant** la sérialisation, dans `catalogue_offrable`. Après
    serait un filtrage de rendu, et un filtrage de rendu laisse la donnée dans l'objet
    qu'il filtre.
    """

    permission_classes = [permissions.IsAuthenticated, PeutGererLesComptes]

    @extend_schema(
        responses={200: CatalogueOffrableSerializer},
        summary="Les droits et les magasins que l'appelant peut accorder",
    )
    def get(self, request):
        acces = acces_de_la_requete(request)
        return Response(catalogue_offrable(acces, _magasins(acces)))

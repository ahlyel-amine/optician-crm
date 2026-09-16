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

from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView, exception_handler

from plateforme.comptes.acces import Acces, acces_pour
from plateforme.comptes.serializers import (
    AmorcageSerializer,
    ChangementMotDePasseSerializer,
    ConnexionSerializer,
    charge_utile_moi,
)

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

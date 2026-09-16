"""La ressource qui prouve la machinerie de PERM-06, sans inventer un champ de phase 8.

**Pourquoi ce fichier est dans `tests/` et n'ira jamais dans `domaine/`.**

Le registre `CHAMPS_PROTEGES` est **vide** en phase 3, et il doit le rester :
`prix_achat` et `marge` naissent en phase 8 (ACHAT-04/07), le chiffre d'affaires global
en phase 10 (DASH-01). Les déclarer ici préempterait le schéma de la phase 8 — exactement
l'erreur contre laquelle la docstring de `domaine/stock/models.py` met déjà en garde, et
contre laquelle `03-RESEARCH.md` correction 3 met en garde nommément.

Mais un test paramétré sur zéro cas est vert et ne vaut rien. Il faut donc un **véhicule**
sous la machinerie tant que le registre est vide, et ce véhicule est ici : un modèle, son
sérialiseur, sa vue, sa route et sa tâche Celery, tous test-only. La phase 8 n'aura rien à
changer ici — elle ajoutera une ligne au vrai registre, et les trois assertions du test de
conformité apparaîtront toutes seules sur son champ à elle.

**Trois décisions de forme méritent une phrase, parce qu'elles paraissent arbitraires.**

1. `app_label = "tests"`. Il est imposé par la clé `tests.RessourceFixture.valeur_protegee`
   que le plan 03-02 a écrite dans `tests/test_projection.py`, et il est aussi le bon
   choix : `tests` n'est pas une application installée, donc `makemigrations` ne voit
   jamais ce modèle et `tenancy.E001` ne le contrôle jamais.
2. **L'alias est nommé explicitement**, par le gestionnaire et par `save()`. `tests` n'est
   ni dans `CONTROL_PLANE_APPS` ni dans `BUSINESS_APPS`, donc `TenantRouter._route` lève
   `ImproperlyClassifiedApp` — et c'est voulu. Classer `tests` dans le routeur mettrait une
   étiquette de test dans le fichier le plus sensible du dépôt, pour le confort d'un
   modèle fictif. Nommer l'alias ici coûte trois lignes et ne touche pas la production.
3. **La table est créée par une fixture de session**, pas par une migration. Il n'y a pas
   de migration possible pour une application non installée, et la créer par
   `schema_editor` au démarrage de la session la place hors de la transaction que
   pytest-django annule après chaque test — donc elle survit à toute la session et meurt
   avec la base de test.

Rien sous `plateforme/` ni sous `domaine/` ne nomme ce module ; le plan en fait un critère
d'acceptation grepable.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import connections, models
from django.urls import path
from rest_framework import viewsets
from rest_framework.response import Response

from config.celery import app as application_celery
from domaine.magasins.models import MagasinScopedModel, MagasinScopedQuerySet
from plateforme.comptes.permissions_catalogue import Permission
from plateforme.projection.filtres import ProjectedFieldFilter, ProjectedOrderingFilter
from plateforme.projection.registre import cle_de_champ
from plateforme.projection.serializers import SerializerProjete, acces_du_contexte
from plateforme.projection.vues import (
    MagasinAutoriseField,
    MagasinScopedViewSet,
    agreger_dans_la_portee,
)
from plateforme.tenancy.context import current_alias

#: L'alias sur lequel la ressource vit. Voir la décision 2 de la docstring du module.
ALIAS = "default"

#: La valeur du champ protégé, choisie pour être **cherchable** dans une chaîne HTML et
#: dans un CSV. « absent » se vérifie sur la valeur rendue, pas seulement sur le nom du
#: champ : un gabarit peut très bien ne pas nommer le champ et l'imprimer quand même.
VALEUR_PROTEGEE = Decimal("4242.42")

#: Le prix public, lui, doit apparaître partout. C'est le contrôle positif de chaque
#: assertion d'absence : sans lui, un rendu totalement vide passerait les trois.
PRIX_VENTE = Decimal("1800.00")

#: Le code du catalogue qui garde le champ. Un code **existant** (phase 3 les déclare
#: tous les 21), jamais un code inventé pour le test.
CODE_PROTEGE: str = Permission.ARTICLE_VOIR_PRIX_ACHAT

#: Le gabarit de document de la ressource. Il est **générique** et vit dans
#: `plateforme/projection/templates/` : le document itère une liste de colonnes déjà
#: projetée, donc il n'a rien de spécifique à une ressource (`03-RESEARCH.md` P10).
NOM_TEMPLATE = "projection/document.html"


class _GestionnaireSurLePlanDeControle(models.Manager):
    """Un gestionnaire qui nomme son alias, parce que le routeur refuse de deviner.

    `TenantRouter._route` lève sur une application non classée — délibérément, c'est la
    branche fail-closed de TENANT-04. Un modèle de test n'est pas une raison de classer
    `tests` dans le routeur de production.
    """

    def get_queryset(self):
        return super().get_queryset().using(ALIAS)


class RessourceFixture(models.Model):
    """Une ressource fictive portant **un** champ monétaire protégé.

    La forme imite celle qu'aura `achats.Article` en phase 8 — une référence, un libellé,
    un prix de vente public, un montant réservé au propriétaire — sans en fixer le nom ni
    le schéma.
    """

    reference = models.CharField(max_length=32, unique=True)
    libelle = models.CharField(max_length=120)
    prix_vente = models.DecimalField(max_digits=12, decimal_places=2)
    valeur_protegee = models.DecimalField(max_digits=12, decimal_places=2)

    objects = _GestionnaireSurLePlanDeControle()

    class Meta:
        app_label = "tests"
        db_table = "tests_ressource_fixture"

    def save(self, *args, **kwargs):
        kwargs.setdefault("using", ALIAS)
        return super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover — confort de débogage
        return f"{self.reference} — {self.libelle}"


#: La clé de registre du champ protégé, dérivée du modèle plutôt qu'écrite à la main : si
#: quelqu'un renomme le champ, la clé suit, et le test ne devient pas silencieusement
#: vacant.
CLE_PROTEGEE: str = cle_de_champ(RessourceFixture, "valeur_protegee")

#: Les champs délibérément visibles de tous. `03-RESEARCH.md` §3 exige que **chaque** champ
#: de modèle exposé soit dans l'une des deux structures ; ceux-ci sont la moitié publique
#: pour la ressource de test.
#:
#: `CHAMPS_PUBLICS_DE_LA_FIXTURE`, en bas de ce module, est l'union de cet ensemble et de
#: celui de la ressource magasin-scopée : `test_perm06_tout_champ_de_modele_expose_est_classe`
#: parcourt **toutes** les sous-classes de `ModelSerializer` chargées, donc les deux
#: ressources doivent être classées ensemble ou ce test d'un autre plan devient rouge.
CHAMPS_PUBLICS_DE_LA_RESSOURCE_PLAN_DE_CONTROLE: frozenset[str] = frozenset(
    cle_de_champ(RessourceFixture, nom)
    for nom in ("id", "reference", "libelle", "prix_vente")
)


class SerializerRessourceFixture(SerializerProjete):
    """Le sérialiseur de la ressource. **Projeté par le registre, pas par une classe.**

    Il héritait, en tâche 1, d'un `ModelSerializer` ordinaire portant un `get_fields()`
    de cinq lignes — celles-là mêmes que la tâche 2 a extraites dans `SerializerProjete`.
    Les assertions de la tâche 1 sont passées sans l'abstraction, et c'est le point : ce
    qui rend PERM-06 vrai est le **registre** et le test qui l'itère. La classe de base est
    du confort, pas la garantie.
    """

    class Meta:
        model = RessourceFixture
        fields = ["id", "reference", "libelle", "prix_vente", "valeur_protegee"]


class VueRessourceFixture(viewsets.ModelViewSet):
    """La vue de la ressource : lecture, détail et modification partielle.

    `authentication_classes = []` parce que les tests posent l'accès par
    `AccesMiddleware`, comme en production, et n'ont donc aucune session à présenter. La
    projection ne dépend pas de l'authentification : elle dépend de `request.acces`, et le
    défaut de `request.acces` est `Acces.ANONYME` (`03-RESEARCH.md` P2).
    """

    queryset = RessourceFixture.objects.all().order_by("pk")
    serializer_class = SerializerRessourceFixture
    authentication_classes: list = []
    permission_classes: list = []


#: La route. Elle existe pour que le générateur OpenAPI ait un point de terminaison à
#: décrire (tâche 3) : `override_settings(ROOT_URLCONF="tests.ressources_fixture")` suffit
#: alors à produire un schéma complet, sans monter quoi que ce soit dans `config/urls.py`.
urlpatterns = [
    path(
        "api/ressources-fixture/",
        VueRessourceFixture.as_view({"get": "list"}),
        name="ressource-fixture-liste",
    ),
    path(
        "api/ressources-fixture/<int:pk>/",
        VueRessourceFixture.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="ressource-fixture-detail",
    ),
]


class VueRessourceFiltrable(VueRessourceFixture):
    """La même ressource, avec le tri et le filtre branchés. Le sujet de l'oracle A-03-07.

    **Une vue à part, et volontairement hors de `urlpatterns`.** Le test de schéma du plan
    03-06 prend ce module pour `ROOT_URLCONF` ; y ajouter une vue changerait le document
    que ce plan-là a rendu déterministe, pour une raison qui n'a rien à voir avec lui.

    Les deux listes déclarent le champ protégé **exprès**. C'est tout l'intérêt : une
    allowlist qui l'omettrait déjà à la main rendrait le test vert sans que
    `champs_interdits` ait servi à quoi que ce soit, et la première phase qui ajoute une
    colonne en oubliant de la retirer des listes rouvrirait l'oracle en silence. Ce qui
    doit fermer la porte est la **dérivation** depuis la projection, pas la vigilance.
    """

    filter_backends = [ProjectedOrderingFilter, ProjectedFieldFilter]
    ordering_fields = ["id", "reference", "libelle", "prix_vente", "valeur_protegee"]
    champs_filtrables = {
        "id": ["exact"],
        "reference": ["exact"],
        "prix_vente": ["exact", "gt", "lt"],
        "valeur_protegee": ["exact", "gt", "lt"],
    }


def appeler_vue_filtrable(utilisateur, chaine_de_requete=""):
    """La route de **liste** de `VueRessourceFiltrable`, avec sa chaîne de requête.

    Même idiome que `_appeler` dans `tests/test_projection.py`, `force_authenticate`
    compris et pour la même raison : sans lui l'appelant devient anonyme, et un test de
    tri qui attend 400 l'obtiendrait pour la mauvaise raison.
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    from plateforme.comptes.middleware import AccesMiddleware

    vue = VueRessourceFiltrable.as_view({"get": "list"})
    requete = APIRequestFactory().get(f"/api/ressources-fixture/{chaine_de_requete}")
    requete.user = utilisateur
    force_authenticate(requete, user=utilisateur)
    reponse = AccesMiddleware(vue)(requete)
    reponse.render()
    return reponse


@application_celery.task(name="tests.exporter_ressources_fixture")
def exporter_ressources_fixture(*, client_id, acting_utilisateur_id, **kwargs):
    """La tâche de rendu de référence — le **contrôle positif** de A-03-03.

    Sa seule raison d'être est que le garde
    `test_perm06_toute_tache_de_rendu_exige_acting_utilisateur_id` ne soit pas vide : sans
    une seule tâche de rendu enregistrée, il passerait en n'examinant rien et resterait
    vert jusqu'à la phase 9, où il aurait dû mordre.

    Elle porte la signature que la règle impose — `(*, client_id, acting_utilisateur_id,
    ...)` — et recalcule l'accès dans le contexte lié, jamais un `Acces` reçu en argument.
    """
    from plateforme.comptes.acces import acces_pour
    from plateforme.projection.export import exporter_csv

    from tests.ressources_fixture import RessourceFixture, SerializerRessourceFixture

    utilisateur = _charger_utilisateur(acting_utilisateur_id)
    return exporter_csv(
        SerializerRessourceFixture,
        RessourceFixture.objects.all(),
        acces=acces_pour(utilisateur),
    )


def _charger_utilisateur(utilisateur_id):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.using("default").get(pk=utilisateur_id)


# ======================================================================================
# Les fixtures pytest de la ressource
# ======================================================================================
#
# Elles vivent ici plutôt que dans `conftest.py` pour la même raison que le module entier :
# rien de ce qui suit ne concerne la production, et `tests/test_projection.py` les rend
# disponibles en les important.


@pytest.fixture(scope="session")
def table_ressource_fixture(django_db_setup, django_db_blocker):
    """Crée `tests_ressource_fixture` une fois par session, hors transaction de test.

    Portée session, et c'est le point : pytest-django enveloppe chaque test dans une
    transaction qu'il annule, donc une table créée dans un test disparaîtrait avec lui. La
    créer après `django_db_setup` la place dans la base de test, où elle vit jusqu'à ce que
    la base soit détruite.

    Idempotente, pour `--reuse-db`.
    """
    with django_db_blocker.unblock():
        connexion = connections[ALIAS]
        if RessourceFixture._meta.db_table not in connexion.introspection.table_names():
            with connexion.schema_editor() as editeur:
                editeur.create_model(RessourceFixture)
    yield


@pytest.fixture
def registre_de_la_fixture(monkeypatch):
    """Inscrit la ressource de test au registre, le temps d'un test.

    **Le vrai registre reste vide**, et c'est une exigence du plan, pas une pudeur : une
    entrée `tests.*` dans `plateforme/projection/registre.py` serait du code de test en
    production, et elle ferait porter la paramétrisation du test de conformité sur un champ
    fictif au lieu du repli explicite.

    L'injection est exactement la ligne que la phase 8 écrira à demeure — une clé, un code
    — donc ce que le test vérifie est bien le mécanisme que la phase 8 utilisera.
    """
    from plateforme.projection import registre

    monkeypatch.setitem(registre.CHAMPS_PROTEGES, CLE_PROTEGEE, CODE_PROTEGE)
    monkeypatch.setattr(
        registre,
        "CHAMPS_PUBLICS",
        registre.CHAMPS_PUBLICS | CHAMPS_PUBLICS_DE_LA_FIXTURE,
    )
    return CLE_PROTEGEE, CODE_PROTEGE


@pytest.fixture
def ressource(table_ressource_fixture, registre_de_la_fixture, db_all):
    """Une ligne de ressource, avec sa valeur protégée et son prix public."""
    return RessourceFixture.objects.create(
        reference="MON-4412",
        libelle="Monture Anfa",
        prix_vente=PRIX_VENTE,
        valeur_protegee=VALEUR_PROTEGEE,
    )


def acces_sans_le_droit(magasins):
    """L'accès d'un gérant à qui `article.voir_prix_achat` n'a **pas** été accordé.

    Il détient un autre droit, dans les deux magasins : un gérant sans aucun droit ne
    prouverait pas que c'est *ce* code qui manque, seulement que la résolution rend du
    vide.
    """
    from plateforme.comptes.acces import acces_pour
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    gerant = GerantFactory()
    for magasin in magasins:
        AccesMagasinFactory(utilisateur=gerant, magasin_code=magasin.code)
        DroitAccordeFactory(
            utilisateur=gerant,
            magasin_code=magasin.code,
            code=Permission.STOCK_VOIR,
        )
    return gerant, acces_pour(gerant)


def acces_avec_le_droit(magasins):
    """L'accès du propriétaire : le catalogue complet, matérialisé (03-05).

    C'est le contrôle positif de chaque assertion d'absence. Un rendu qui n'imprimerait
    jamais rien passerait « absent » pour tout le monde.
    """
    from plateforme.comptes.acces import acces_pour
    from tests.factories import ProprietaireFactory

    proprietaire = ProprietaireFactory()
    return proprietaire, acces_pour(proprietaire)


# ======================================================================================
# La ressource magasin-scopée — le véhicule de PERM-04 et PERM-05 (plan 03-07)
# ======================================================================================
#
# **Pourquoi une seconde ressource plutôt qu'un champ de plus sur la première.**
# `RessourceFixture` vit sur le plan de contrôle, parce que la projection de champs ne
# dépend d'aucune base client. La portée des *lignes*, elle, ne peut pas vivre là : elle
# porte une clé étrangère vers `magasins.Magasin`, qui est une table de la base de
# l'opticien, et `TenantRouter.allow_relation` refuse toute relation entre les deux. La
# ressource ci-dessous vit donc dans la base du locataire **lié**, comme le feront la
# caisse (phase 7) et les ventes (phase 6).
#
# Elle dérive de `MagasinScopedModel` pour une raison précise : le garde d'énumération du
# plan 03-07 parcourt les vues dont le modèle en dérive et exige le mixin de portée. Sans
# un sujet réel, ce garde passerait en n'examinant rien — la même faiblesse que le test
# paramétré sur zéro cas, un étage plus haut.

#: Les montants semés par `semer_ressources_magasin`, en `Decimal` parce que CLAUDE.md #7
#: ne connaît pas d'exception et parce qu'une assertion sur un `float` passe pendant que
#: l'argent est faux (`.planning/TESTING.md` §4).
MONTANTS_ANFA = (Decimal("1200.00"), Decimal("600.00"))
MONTANTS_MAARIF = (Decimal("2500.00"),)

#: La somme sur le seul magasin accordé, et la somme de toute l'affaire. **Elles doivent
#: différer**, sans quoi le test d'agrégat ne distingue pas un calcul restreint d'un
#: calcul global — exactement le piège « un seul magasin » de `03-RESEARCH.md` P16.
TOTAL_ANFA = sum(MONTANTS_ANFA, Decimal("0.00"))
TOTAL_ENTREPRISE = TOTAL_ANFA + sum(MONTANTS_MAARIF, Decimal("0.00"))


class _QuerySetDuLocataireLie(MagasinScopedQuerySet):
    """Un queryset qui résout son alias **au moment de s'exécuter**, pas d'être construit.

    Même raison que `_GestionnaireSurLePlanDeControle` plus haut, autre côté de la
    frontière : `tests` n'est pas une application classée, donc `TenantRouter._route`
    lève plutôt que de deviner, et classer `tests` dans le routeur de production pour le
    confort d'un modèle fictif serait mettre une étiquette de test dans le fichier le plus
    sensible du dépôt.

    Pourquoi la propriété `db` plutôt qu'un `.using(current_alias())` dans le
    gestionnaire : un `VueRessourceMagasin.queryset` écrit au niveau de la classe est
    construit à l'**import** du module, où aucun locataire n'est lié — `current_alias()`
    y lèverait `NoTenantBound` et la suite entière refuserait de se collecter. Django
    interroge `db` à l'exécution de la requête, ce qui est exactement le bon moment.

    Et `current_alias()` plutôt qu'une constante `"tenant_a"` : la portée magasin ne doit
    **jamais** servir d'isolation inter-clients, ni l'inverse. Lire l'alias lié laisse un
    test poser la ressource chez le client B aussi bien que chez le client A, donc laisse
    écrire l'assertion qui sépare les deux couches.
    """

    @property
    def db(self):
        return self._db or current_alias()


class _GestionnaireDuLocataireLie(
    models.Manager.from_queryset(_QuerySetDuLocataireLie)
):
    """Le gestionnaire correspondant. Il n'ajoute rien : toute la paresse est au-dessus."""


class RessourceMagasin(MagasinScopedModel):
    """Une ligne qui appartient à **un** magasin et porte un montant.

    La forme qu'auront `caisse.Ecriture` (phase 7) et `ventes.Vente` (phase 6) : une clé
    étrangère `magasin`, un montant, et rien d'autre. Aucun champ protégé ici — la
    visibilité des champs est l'affaire du plan 03-06 et de `RessourceFixture`. Ce
    modèle-ci sert la visibilité des **lignes** et des **agrégats**, qui est une autre
    garantie et se teste séparément.
    """

    libelle = models.CharField(max_length=120)
    montant = models.DecimalField(max_digits=12, decimal_places=2)

    objects = _GestionnaireDuLocataireLie()

    class Meta:
        app_label = "tests"
        db_table = "tests_ressource_magasin"

    def __init__(self, *args, **kwargs):
        """Nommer l'alias **avant** que la clé étrangère ne soit affectée.

        `ForwardManyToOneDescriptor.__set__` appelle `router.db_for_write(Ressource...)`
        quand `instance._state.db` est encore `None` — et le routeur lève sur
        l'application `tests`, non classée, délibérément. Le magasin est donc retiré des
        arguments, l'alias posé, puis la relation affectée : `allow_relation` compare alors
        deux instances du même alias et accepte.

        Trois lignes de plomberie de test qui achètent de ne pas classer `tests` dans
        `plateforme/tenancy/router.py`, ce qui mettrait une étiquette de test dans le
        fichier le plus sensible du dépôt.
        """
        magasin = kwargs.pop("magasin", None)
        super().__init__(*args, **kwargs)
        if magasin is not None:
            if self._state.db is None:
                self._state.db = current_alias()
            self.magasin = magasin

    def save(self, *args, **kwargs):
        kwargs.setdefault("using", current_alias())
        return super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover — confort de débogage
        return f"{self.libelle} ({self.montant})"


#: Les champs de la ressource magasin-scopée, tous publics. Aucun champ protégé ici :
#: cette ressource sert la portée des **lignes**, pas la visibilité des champs.
CHAMPS_PUBLICS_DE_LA_RESSOURCE_MAGASIN: frozenset[str] = frozenset(
    cle_de_champ(RessourceMagasin, nom)
    for nom in ("id", "magasin", "libelle", "montant")
)

#: L'union des deux ressources — ce que `registre_de_la_fixture` injecte dans
#: `CHAMPS_PUBLICS`. Une seule constante exportée, parce que
#: `test_perm06_tout_champ_de_modele_expose_est_classe` examine les deux sérialiseurs dès
#: que ce module est importé : en classer un et pas l'autre rendrait rouge un test d'un
#: autre plan, pour une raison qui n'aurait rien à voir avec lui.
CHAMPS_PUBLICS_DE_LA_FIXTURE: frozenset[str] = (
    CHAMPS_PUBLICS_DE_LA_RESSOURCE_PLAN_DE_CONTROLE
    | CHAMPS_PUBLICS_DE_LA_RESSOURCE_MAGASIN
)


class SerializerRessourceMagasin(SerializerProjete):
    """Le sérialiseur de la ressource magasin-scopée.

    `magasin` est un `MagasinAutoriseField`, **jamais** le `PrimaryKeyRelatedField` que
    `ModelSerializer` produirait tout seul — celui-là valide la clé contre
    `Magasin.objects.all()` et accepte donc une écriture vers un magasin non accordé avec
    un 201 (`03-RESEARCH.md` P5, menace T-03-40). C'est le champ que tout le monde oublie,
    parce que la vue *a l'air* protégée : sa lecture l'est.
    """

    magasin = MagasinAutoriseField()

    class Meta:
        model = RessourceMagasin
        fields = ["id", "magasin", "libelle", "montant"]


class VueRessourceMagasin(MagasinScopedViewSet, viewsets.ModelViewSet):
    """La vue magasin-scopée : liste, détail, création et agrégat.

    L'ordre des bases n'est pas cosmétique. `MagasinScopedViewSet` doit précéder
    `ModelViewSet` dans le MRO, sinon `GenericAPIView.get_queryset` gagne et la portée
    disparaît **sans erreur** — c'est précisément ce que le garde d'énumération du plan
    03-07 vérifie, et la raison pour laquelle il regarde l'ordre plutôt que l'héritage.
    """

    queryset = RessourceMagasin.objects.all().order_by("pk")
    serializer_class = SerializerRessourceMagasin
    authentication_classes: list = []
    permission_classes: list = []

    def total(self, requete, *args, **kwargs):
        """L'agrégat, pris sur le queryset **déjà restreint**. PERM-05.

        Écrit avec l'aide dédiée plutôt qu'avec `RessourceMagasin.objects.aggregate(...)`,
        et la différence est tout le plan : le manager par défaut repart de zéro et ignore
        le queryset que la vue vient de construire. Un `SUM` global renvoyé à un gérant
        d'un seul magasin est le chiffre d'affaires de toute l'affaire, sans qu'aucun champ
        protégé ni aucune ligne interdite n'ait été servi.
        """
        from django.db.models import Sum

        portee = agreger_dans_la_portee(
            RessourceMagasin.objects.all(),
            acces_du_contexte({"request": requete}),
            total=Sum("montant"),
        )
        return Response({"total": str(portee["total"] or Decimal("0.00"))})


#: Les routes de la ressource magasin-scopée.
#:
#: **Volontairement séparées de `urlpatterns`.** Ce module sert de `ROOT_URLCONF` au test
#: de schéma du plan 03-06 (`override_settings(ROOT_URLCONF="tests.ressources_fixture")`) ;
#: y verser des routes dont le queryset exige un locataire lié ferait dépendre la
#: génération du schéma d'un contexte que le générateur n'a pas. Les tests de portée
#: appellent la vue directement, exactement comme ceux du plan 03-06.
urlpatterns_magasin = [
    path(
        "api/ressources-magasin/",
        VueRessourceMagasin.as_view({"get": "list", "post": "create"}),
        name="ressource-magasin-liste",
    ),
    path(
        "api/ressources-magasin/<int:pk>/",
        VueRessourceMagasin.as_view({"get": "retrieve"}),
        name="ressource-magasin-detail",
    ),
    path(
        "api/ressources-magasin/total/",
        VueRessourceMagasin.as_view({"get": "total"}),
        name="ressource-magasin-total",
    ),
]


@pytest.fixture(scope="session")
def table_ressource_magasin(django_db_setup, django_db_blocker):
    """Crée `tests_ressource_magasin` dans **chaque** base locataire de test.

    Les deux, et pas seulement `tenant_a` : le registre de menaces du plan 03-07 exige que
    la portée magasin ne serve jamais d'isolation inter-clients, et une table absente chez
    le client B rendrait cette assertion impossible à écrire — elle échouerait pour la
    mauvaise raison.

    Portée session pour la même raison que `table_ressource_fixture` : une table créée
    dans un test disparaîtrait avec la transaction que pytest-django annule.
    """
    from conftest import TENANT_DBS

    with django_db_blocker.unblock():
        for alias in TENANT_DBS:
            if alias == "default":
                continue
            connexion = connections[alias]
            if (
                RessourceMagasin._meta.db_table
                not in connexion.introspection.table_names()
            ):
                with connexion.schema_editor() as editeur:
                    editeur.create_model(RessourceMagasin)
    yield


def semer_ressources_magasin(anfa, maarif):
    """Sème les lignes des deux magasins et renvoie `(lignes_anfa, lignes_maarif)`.

    Les montants diffèrent d'un magasin à l'autre, et c'est l'essentiel : avec les mêmes
    montants de part et d'autre, une somme globale et une somme restreinte seraient
    indiscernables et le test de PERM-05 serait vert contre un `aggregate` non filtré.
    """
    lignes_anfa = [
        RessourceMagasin.objects.create(
            magasin=anfa, libelle=f"Anfa {indice}", montant=montant
        )
        for indice, montant in enumerate(MONTANTS_ANFA)
    ]
    lignes_maarif = [
        RessourceMagasin.objects.create(
            magasin=maarif, libelle=f"Maârif {indice}", montant=montant
        )
        for indice, montant in enumerate(MONTANTS_MAARIF)
    ]
    return lignes_anfa, lignes_maarif


def acces_sur_un_seul_magasin(magasin):
    """Un gérant à qui **un seul** des deux magasins a été accordé.

    Il détient un droit dans ce magasin : un gérant sans aucun droit ne prouverait pas que
    la portée vient de l'octroi de magasin, seulement que la résolution rend du vide.
    """
    from plateforme.comptes.acces import acces_pour
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    gerant = GerantFactory()
    AccesMagasinFactory(utilisateur=gerant, magasin_code=magasin.code)
    DroitAccordeFactory(
        utilisateur=gerant, magasin_code=magasin.code, code=Permission.CAISSE_SAISIR
    )
    return gerant, acces_pour(gerant)


def appeler_vue_magasin(utilisateur, methode, action, *, chemin="/api/ressources-magasin/", corps=None, **kwargs):
    """Une vraie requête sur la vue magasin-scopée : principal -> middleware -> vue.

    Même idiome que `_appeler` dans `tests/test_projection.py`, et pour les mêmes deux
    raisons : passer par `AccesMiddleware` rend le test de bout en bout, et
    `force_authenticate` est obligatoire parce que le setter `Request.user` de DRF réécrit
    `_request.user` — sans lui, l'appelant devient anonyme et l'assertion « il ne voit que
    Anfa » passerait parce qu'il ne voit rien du tout.
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    from plateforme.comptes.middleware import AccesMiddleware

    vue = VueRessourceMagasin.as_view({methode: action})
    fabrique = APIRequestFactory()
    if methode == "post":
        requete = fabrique.post(chemin, corps or {}, format="json")
    else:
        requete = fabrique.get(chemin)
    requete.user = utilisateur
    force_authenticate(requete, user=utilisateur)
    reponse = AccesMiddleware(lambda recue: vue(recue, **kwargs))(requete)
    reponse.render()
    return reponse

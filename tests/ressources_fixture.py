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
from rest_framework import serializers, viewsets

from config.celery import app as application_celery
from plateforme.comptes.permissions_catalogue import Permission
from plateforme.projection.registre import champs_interdits, cle_de_champ

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
CHAMPS_PUBLICS_DE_LA_FIXTURE: frozenset[str] = frozenset(
    cle_de_champ(RessourceFixture, nom)
    for nom in ("id", "reference", "libelle", "prix_vente")
)


class SerializerRessourceFixture(serializers.ModelSerializer):
    """Le sérialiseur de la ressource. **Projeté par le registre, pas par une classe.**

    En tâche 1 la projection est écrite ici, en cinq lignes, exactement celles que la
    tâche 2 extraira dans `plateforme.projection.serializers.SerializerProjete`. Ce n'est
    pas un détour : c'est la thèse du plan rendue visible. Ce qui rend PERM-06 vrai est le
    **registre** et le test qui l'itère, pas l'abstraction — la preuve étant qu'un
    sérialiseur qui lit le registre sans hériter de quoi que ce soit passe déjà le test.
    """

    class Meta:
        model = RessourceFixture
        fields = ["id", "reference", "libelle", "prix_vente", "valeur_protegee"]

    def get_fields(self):
        from plateforme.comptes.acces import Acces

        champs = super().get_fields()
        acces = getattr(self.context.get("request"), "acces", None) or Acces.ANONYME
        for nom in champs_interdits(self.Meta.model, acces):
            champs.pop(nom, None)
        return champs


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

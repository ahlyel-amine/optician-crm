"""factory_boy factories for the tenancy suite.

Note the asymmetry, which mirrors the architecture:

* `ClientFactory` builds control-plane rows and therefore always writes to `default`.
* `MagasinFactory` builds business rows and writes to whichever tenant alias is bound —
  it names no alias at all, because the router resolves it from the context. A factory
  that hardcoded an alias would be a `.using()` in disguise and would silently bypass
  exactly the mechanism these tests exist to check.
"""

from __future__ import annotations

import factory
from django.conf import settings

from domaine.magasins.models import Magasin
from plateforme.control_plane.models import Client


class ClientFactory(factory.django.DjangoModelFactory):
    """A control-plane `Client` row, PENDING by default.

    PENDING rather than ACTIVE on purpose: only ACTIVE clients are routable, so a test
    that needs a routable client has to say so. That makes "half-provisioned clients are
    invisible to the router" (TENANT-05) visible in the tests rather than assumed.
    """

    class Meta:
        model = Client
        database = "default"
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"opt-{n:04d}")
    raison_sociale = factory.Sequence(lambda n: f"Optique {n:04d} SARL")
    status = Client.PENDING
    db_host = factory.LazyFunction(lambda: settings.DATABASES["default"]["HOST"])
    db_port = factory.LazyFunction(lambda: int(settings.DATABASES["default"]["PORT"]))


class MagasinFactory(factory.django.DjangoModelFactory):
    """A `Magasin` in whichever client database is currently bound."""

    class Meta:
        model = Magasin
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"MAG{n:03d}")
    nom = factory.Sequence(lambda n: f"Magasin {n:03d}")
    adresse = ""
    telephone = ""
    actif = True


# ======================================================================================
# Comptes — plan de contrôle (CLAUDE.md #11)
# ======================================================================================
#
# L'identité, l'appartenance à une affaire et les droits vivent dans la base du plan de
# contrôle, et nulle part ailleurs. Ces factories nomment donc `database = "default"`
# explicitement, exactement comme `ClientFactory` et pour la même raison : ce ne sont pas
# des lignes métier, le routeur n'a pas de contexte de locataire à consulter pour elles,
# et une factory qui laisserait le routeur décider produirait un compte dans la base d'un
# opticien le jour où quelqu'un l'appelle depuis un `tenant_context`.


#: Le mot de passe de tous les comptes de test, sauf mention contraire. Nommé plutôt
#: qu'inliné pour que les tests de connexion (PERM-01, plan 03-08) s'y réfèrent au lieu de
#: le recopier, et pour qu'il soit visiblement un littéral de test.
MOT_DE_PASSE_DE_TEST = "mot-de-passe-de-test"


class UtilisateurFactory(factory.django.DjangoModelFactory):
    """Un `Utilisateur` sur le plan de contrôle, **sans client** par défaut.

    `client = None` par défaut signifie « opérateur de plateforme ». C'est le choix le
    plus neutre : un test qui a besoin d'un compte rattaché à une affaire doit le dire, en
    passant par `ProprietaireFactory` ou `GerantFactory`. Un défaut qui rattacherait
    silencieusement à un client fabriqué au passage cacherait précisément l'erreur que
    PERM-02 surveille — un compte créé dans la mauvaise affaire.

    **Le mot de passe passe par `set_password`, jamais par une assignation.**
    `Utilisateur.password` stocke un hash Argon2 ; y écrire une chaîne en clair produit un
    compte qui ne peut pas s'authentifier, et le test de connexion échouerait alors pour
    une raison qui n'a rien à voir avec ce qu'il vérifie. `skip_postgeneration_save` est
    posé à `True` et la sauvegarde est faite ici : factory_boy 3.3 déprécie la sauvegarde
    implicite d'après-génération, et une `DeprecationWarning` dans une suite qui en compte
    zéro est du bruit qui finit par masquer un vrai avertissement.
    """

    class Meta:
        model = "comptes.Utilisateur"
        database = "default"
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"utilisateur{n:04d}@optique.test")
    nom_complet = factory.Sequence(lambda n: f"Utilisateur {n:04d}")
    client = None
    est_proprietaire = False
    is_active = True

    @factory.post_generation
    def mot_de_passe(self, create, extracted, **kwargs):
        """Pose un vrai hash Argon2, sur `default` et nulle part ailleurs."""
        self.set_password(extracted or MOT_DE_PASSE_DE_TEST)
        if create:
            self.save(using="default", update_fields=["password"])


class ProprietaireFactory(UtilisateurFactory):
    """L'opticien qui détient l'affaire. **Un seul par client** — la base le garantit.

    `un_seul_proprietaire_par_client` est une `UniqueConstraint` partielle, donc en
    demander un deuxième pour le même client lève `IntegrityError` plutôt que de créer
    discrètement un second propriétaire. C'est voulu : le test qui découvre la contrainte
    est celui qui l'a franchie.

    `client` est une `SubFactory` et non `None` : `un_proprietaire_appartient_a_un_client`
    refuse un propriétaire sans affaire.
    """

    class Meta:
        model = "comptes.Utilisateur"
        database = "default"
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    client = factory.SubFactory(ClientFactory)
    est_proprietaire = True


class GerantFactory(UtilisateurFactory):
    """Un gérant : un compte rattaché à une affaire, et **aucun droit par défaut**.

    C'est le sujet de presque toute la phase. Il se connecte (CLAUDE.md #6), il n'est pas
    propriétaire, et ce qu'il peut voir est entièrement décrit par des lignes de droits
    accordées une par une — donc, tant que personne n'en a accordé, il ne peut rien.
    Partir de zéro plutôt que d'un jeu de droits « raisonnable » est ce qui rend visible
    la règle « l'accès absent vaut aucun droit » (`03-RESEARCH.md` P2) : un défaut
    permissif la rendrait intestable.
    """

    class Meta:
        model = "comptes.Utilisateur"
        database = "default"
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    client = factory.SubFactory(ClientFactory)
    est_proprietaire = False


# `AccesMagasinFactory` et `DroitAccordeFactory` arrivent au **plan 03-04**, dans le même
# changement que les modèles `AccesMagasin`, `DroitAccorde` et `JournalDroit` qu'elles
# construisent. Elles ne sont pas ici parce qu'une factory ne peut pas différer la
# résolution de son modèle : `Meta.model` est lu à la création de la classe, donc une
# factory écrite avant son modèle casse la **collecte** de toute la suite — exactement le
# mode de défaillance que les stubs `pending` de ce plan évitent par ailleurs. Leur place
# est ici, sous ce commentaire, et elles écriront elles aussi sur `default`.

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

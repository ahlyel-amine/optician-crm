"""PERM-02 — le socle du compte utilisateur, et ce que la base garantit à sa place.

Ces tests ne testent pas Django (`.planning/TESTING.md` §1). Ils testent quatre règles qui
nous appartiennent, et chacune est une décision de CLAUDE.md qu'on doit pouvoir voir
devenir rouge si quelqu'un la rétablit à l'envers :

1. **Un compte rattaché à un client n'est jamais opérateur.** L'admin Django est la
   gestion de flotte — il expose `db_name`, `db_host` et les identifiants de connexion de
   *chaque* opticien (menaces T-03-01, T-03-02). La garantie est une `CheckConstraint`, et
   c'est pour cela que le test passe par `queryset.update()` : un `clean()` est contourné
   par `update()`, par `bulk_update()` et par une session shell. Si le test passait par
   `save()`, il resterait vert au-dessus d'une garantie en papier.
2. **Un propriétaire appartient à un client**, sinon `est_proprietaire` est un titre sans
   périmètre.
3. **Un seul propriétaire par client** (CLAUDE.md #6 : l'opticien, puis des gérants).
4. **`Utilisateur` n'expose aucun système de droits Django.** Pas de `PermissionsMixin`,
   donc pas de `groups` ni de `user_permissions`. `Group` *est* un palier de rôle, interdit
   par CLAUDE.md #6, et deux systèmes de permissions dans un même code sont la dérive que
   la phase 9 paierait (menace T-03-04). L'absence est la garantie ; ce test la constate.

Tout se passe sur `default` : l'identité vit dans le plan de contrôle (CLAUDE.md #11).
Aucune base client n'est impliquée.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from tests.factories import ClientFactory

pytestmark = pytest.mark.django_db


def _utilisateur(**kwargs):
    """Un compte minimal. `client=None` par défaut, donc opérateur-compatible."""
    from plateforme.comptes.models import Utilisateur

    params = {
        "email": "karim@optique-anfa.ma",
        "nom_complet": "Karim Bennani",
        "password": "un-mot-de-passe-de-test",
    }
    params.update(kwargs)
    return Utilisateur.objects.create_user(**params)


def test_perm02_un_utilisateur_client_ne_peut_jamais_etre_operateur():
    """La garantie est une contrainte de base, prouvée en la contournant par `update()`.

    `queryset.update()` n'appelle ni `save()`, ni `full_clean()`, ni un signal. S'il passe,
    la seule chose qui reste entre un compte d'opticien et la gestion de flotte est une
    convention. Les deux drapeaux sont éprouvés séparément : `is_staff` ouvre l'admin,
    `is_superuser` y donne tous les droits, et un modèle qui n'en contraindrait qu'un
    laisserait l'autre comme chemin.
    """
    from plateforme.comptes.models import Utilisateur

    client = ClientFactory()
    utilisateur = _utilisateur(client=client)

    for champ in ("is_staff", "is_superuser"):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Utilisateur.objects.filter(pk=utilisateur.pk).update(**{champ: True})


def test_perm02_un_proprietaire_appartient_a_un_client():
    """`est_proprietaire=True` sans client est un titre sans périmètre — refusé en base."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _utilisateur(client=None, est_proprietaire=True)


def test_perm02_un_seul_proprietaire_par_client():
    """Deux propriétaires pour une même affaire : refusé par une `UniqueConstraint`.

    Partielle, sur `est_proprietaire=True` : les gérants du même client ne se gênent pas
    entre eux, seul le rôle unique est unique.
    """
    client = ClientFactory()
    _utilisateur(client=client, est_proprietaire=True)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _utilisateur(
                email="fatima@optique-anfa.ma",
                nom_complet="Fatima Zahra Alami",
                client=client,
                est_proprietaire=True,
            )


def test_perm02_utilisateur_n_expose_aucun_systeme_de_droits_django():
    """Pas de `PermissionsMixin` : `Group` et `user_permissions` sont hors d'atteinte.

    CLAUDE.md #6 — les droits sont accordés par gérant, comme des données, jamais comme
    des paliers de rôle. `Group` est exactement un palier. Hériter du mixin mettrait
    `user.has_perm("achats.view_article")` à une frappe de `acces.peut(...)`, et les deux
    systèmes cohabiteraient jusqu'à ce que l'un mente. Ce test est la seule chose qui
    remarque si quelqu'un ajoute le mixin « pour faire marcher l'admin ».
    """
    utilisateur = _utilisateur()

    assert not hasattr(utilisateur, "groups"), (
        "Utilisateur expose `groups`, donc PermissionsMixin est revenu. Group est un "
        "palier de rôle (CLAUDE.md #6) et un second système de droits à côté du nôtre."
    )
    assert not hasattr(utilisateur, "user_permissions"), (
        "Utilisateur expose `user_permissions`, donc PermissionsMixin est revenu."
    )

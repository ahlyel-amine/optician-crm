"""PERM-02 / PERM-06 — le socle du compte utilisateur, et ce que la base garantit à sa place.

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

Puis trois règles de plus, autour de l'admin opérateur :

5. **Aucun modèle métier n'est enregistré dans l'admin** (PERM-06). Un `ModelAdmin` métier
   tournerait sans passer par la couche de projection, donc sans les droits par gérant.
6. **Seul un opérateur sans client atteint l'admin.** La contrainte de base est la défense
   de fond ; `has_permission` est la seconde, et les deux sont testées.
7. **Un rôle PostgreSQL client ne peut pas ouvrir la base du plan de contrôle**
   (CLAUDE.md #12, menace T-03-03). C'est la seule garantie de cette phase qui possède une
   couche **sous** Python, et le test se connecte comme le mauvais principal pour le
   prouver plutôt que de lire une ACL.

Tout se passe sur `default` : l'identité vit dans le plan de contrôle (CLAUDE.md #11).
Aucune base client n'est impliquée.
"""

from __future__ import annotations

import os
import secrets

import psycopg
import pytest
from django.conf import settings
from django.contrib import admin
from django.db import IntegrityError, transaction
from django.test import RequestFactory
from psycopg import sql

from plateforme.tenancy.router import BUSINESS_APPS
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


# --------------------------------------------------------------------------------------
# L'admin opérateur (PERM-06, PERM-02)
# --------------------------------------------------------------------------------------
def test_perm06_aucun_modele_metier_n_est_enregistre_dans_ladmin():
    """L'admin est la gestion de flotte. Aucun modèle métier n'y figure, jamais.

    Deux raisons, et la seconde est celle qui compte. D'abord un `ModelAdmin` métier
    lèverait `NoTenantBound` dès l'ouverture de la page, parce que l'admin ne tourne pas
    dans une requête liée à un locataire. Ensuite, et surtout : il rendrait les données
    **sans passer par la couche de projection** (PERM-06), donc sans les droits par
    gérant, sans le filtrage par magasin, et sans aucune des trois assertions que le test
    de conformité paramétré produira.

    Le contrôle positif n'est pas de la décoration : sans lui, un registre vide — parce
    que `autodiscover` n'a pas tourné, par exemple — ferait passer l'assertion négative
    sans rien prouver.
    """
    enregistres = {
        modele._meta.label: modele._meta.app_label for modele in admin.site._registry
    }

    metier = {
        label: app for label, app in enregistres.items() if app in BUSINESS_APPS
    }
    assert not metier, (
        f"Modèles métier enregistrés dans l'admin : {sorted(metier)}. Un ModelAdmin "
        "métier rend les données sans la couche de projection, donc sans les droits par "
        "gérant (PERM-06)."
    )

    assert "comptes.Utilisateur" in enregistres, (
        "Utilisateur n'est pas enregistré dans l'admin — le contrôle positif de ce test. "
        "Un registre vide rendrait l'assertion ci-dessus vraie sans rien prouver."
    )
    assert "control_plane.Client" in enregistres, (
        "Client n'est pas enregistré : l'admin a perdu la gestion de flotte, ou "
        "l'AdminSite installé n'est pas celui que control_plane/admin.py alimente."
    )


def test_perm02_seul_un_operateur_sans_client_atteint_ladmin():
    """`has_permission` exige `is_active`, `is_superuser` **et** `client_id is None`.

    Le porteur d'un `client_id` avec `is_superuser=True` est inatteignable en base grâce à
    `un_utilisateur_client_n_est_jamais_operateur` — il est donc construit en mémoire ici.
    C'est volontaire : les deux défenses sont indépendantes, et tester la seconde à travers
    la première ne testerait que la première. Si la contrainte était un jour assouplie,
    cette assertion resterait la dernière à tenir.
    """
    from plateforme.comptes.models import Utilisateur

    requete = RequestFactory().get("/admin/")

    requete.user = Utilisateur(
        email="gerant@optique-anfa.ma",
        nom_complet="Gérant promu à tort",
        client_id=1,
        is_active=True,
        is_staff=True,
        is_superuser=True,
    )
    assert admin.site.has_permission(requete) is False, (
        "Un compte porteur d'un client_id a atteint l'admin de flotte, qui expose "
        "db_name, db_host et les identifiants de connexion de chaque opticien "
        "(menaces T-03-01, T-03-02)."
    )

    requete.user = Utilisateur(
        email="operateur@optique.local",
        nom_complet="Opérateur plateforme",
        client=None,
        is_active=True,
        is_staff=True,
        is_superuser=True,
    )
    assert admin.site.has_permission(requete) is True, (
        "L'opérateur sans client n'atteint plus l'admin : la garde est trop serrée et il "
        "n'existe plus aucun moyen d'administrer la flotte."
    )

    requete.user = Utilisateur(
        email="ancien@optique.local",
        nom_complet="Opérateur désactivé",
        client=None,
        is_active=False,
        is_staff=True,
        is_superuser=True,
    )
    assert admin.site.has_permission(requete) is False, (
        "Un opérateur désactivé atteint encore l'admin. is_active doit être lu à chaque "
        "requête (PERM-02)."
    )


@pytest.mark.slow
def test_perm02_un_role_client_ne_peut_pas_ouvrir_la_base_du_plan_de_controle():
    """CLAUDE.md #12 — la quatrième occurrence du même défaut par défaut de PostgreSQL.

    `CONNECT` est accordé à `PUBLIC` sur **toute** base neuve, donc l'absence du `REVOKE`
    est silencieuse : rien dans le code Python ne change d'apparence, et la garantie qui
    casse est écrite une couche au-dessus. Trois trous de ce type existaient déjà dans ce
    projet — les bases clients, la base de maintenance `postgres`, et une fonction
    `SECURITY DEFINER` renvoyant des vérificateurs SCRAM. Voici le quatrième : depuis
    cette phase, `optique_control` porte les empreintes de mots de passe et tous les
    droits de **toute la flotte**.

    Le test se connecte comme le mauvais principal et exige d'être refusé. Lire l'ACL ne
    suffirait pas : c'est la connexion réelle qui est la garantie.

    Il vise la base de **développement**, pas la base de test : le `REVOKE` vit dans
    `docker/postgres/init/00-databases.sql`, et `test_optique_control` est créée par le
    lanceur de tests à partir d'un modèle qui ne l'a jamais vu.
    """
    from plateforme.tenancy.maintenance import maintenance_connection

    # Pas `settings.DATABASES["default"]["NAME"]` : pytest-django y écrit le nom de la
    # base de test (`test_optique_control`) avant le premier test. Le nom est donc relu à
    # la source que `config/settings/base.py` lit lui-même, jamais écrit en dur ici.
    base = os.environ.get("CONTROL_PLANE_DB_NAME", "optique_control")
    assert not base.startswith("test_"), (
        f"Base du plan de contrôle inattendue : {base!r}. Ce test vise la grappe de "
        "développement, pas une base de test."
    )

    # Le préfixe est celui que le faucheur de conftest.py ramasse si ce test est tué.
    role = f"test_client_u{secrets.randbelow(1_000_000):06d}"
    mot_de_passe = secrets.token_urlsafe(24)

    with maintenance_connection() as cur:
        cur.execute(
            sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(mot_de_passe)
            )
        )
        try:
            cur.execute(
                "SELECT has_database_privilege(%s, %s, 'CONNECT')", (role, base)
            )
            assert cur.fetchone()[0] is False, (
                f"{role} détient CONNECT sur {base}. PostgreSQL l'accorde à PUBLIC sur "
                "toute base neuve ; le REVOKE de 00-databases.sql est la seule chose qui "
                "le retire. Docker ne rejoue /docker-entrypoint-initdb.d que sur un "
                "volume vide, donc une grappe de développement existante a besoin qu'on "
                "l'applique à la main."
            )

            cur.execute("SELECT has_database_privilege('public', %s, 'CONNECT')", (base,))
            assert cur.fetchone()[0] is False, (
                f"PUBLIC détient encore CONNECT sur {base}."
            )

            with pytest.raises(psycopg.OperationalError) as refus:
                psycopg.connect(
                    host=settings.PG_ADMIN_HOST,
                    port=settings.PG_ADMIN_PORT,
                    user=role,
                    password=mot_de_passe,
                    dbname=base,
                    connect_timeout=5,
                ).close()

            assert "permission denied for database" in str(refus.value), (
                "La connexion a échoué, mais pas pour la bonne raison : "
                f"{refus.value!r}. Un refus d'authentification ferait passer ce test "
                "au-dessus d'un CONNECT toujours accordé."
            )
        finally:
            cur.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))

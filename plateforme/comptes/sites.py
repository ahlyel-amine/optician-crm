"""L'`AdminSite` opérateur — la seconde défense, la contrainte de base étant la première.

Ce que l'admin expose est la raison d'être de cette garde : `ClientAdmin` affiche
`db_name`, `db_host` et `db_port` de **chaque** opticien, et `MigrationRunAdmin` et
`BackupRunAdmin` racontent l'état de toute la flotte (menaces T-03-01, T-03-02). Un compte
d'opticien qui atteindrait cette page n'y verrait pas ses propres données : il y verrait
celles de tous les autres.

Deux défenses indépendantes, et c'est voulu :

1. `un_utilisateur_client_n_est_jamais_operateur` — PostgreSQL refuse la ligne. Défense de
   fond : même `queryset.update()` ne la contourne pas.
2. `has_permission` ci-dessous — exige `client_id is None` en plus de `is_superuser`. Si la
   contrainte était un jour assouplie, ceci tiendrait encore.

**Pourquoi ce module est séparé de `admin.py`.** `django.contrib.admin.site` est un
`LazyObject` dont `_setup()` importe la classe nommée par `default_site`. Si cette classe
vivait dans un module qui, à l'import, appelle `admin.register(...)`, l'accès à
`admin.site` depuis ce décorateur relancerait `_setup()` alors que `_wrapped` est encore
vide : une seconde instance recevrait l'enregistrement, puis le `_setup()` extérieur
l'écraserait par une troisième. Le modèle enregistré disparaîtrait **sans erreur**. Le
module que `default_site` désigne ne doit donc rien enregistrer ; `admin.py`, découvert
normalement par `autodiscover()`, s'en charge.
"""

from __future__ import annotations

from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig


class AdminOperateurConfig(AdminConfig):
    """Remplace `django.contrib.admin` dans `INSTALLED_APPS` pour installer le site ci-dessous.

    C'est la voie supportée par Django pour que `django.contrib.admin.site` soit notre
    `AdminSite` plutôt que le sien — et donc pour que les `@admin.register(...)` déjà
    écrits (ceux de `control_plane/admin.py`) atterrissent sur le site gardé, au lieu d'un
    second site monté en parallèle à côté d'un premier resté ouvert.

    `name` reste `"django.contrib.admin"` par héritage, donc le label reste `admin`, déjà
    classé dans `CONTROL_PLANE_APPS`, et `tenancy.E001` l'exempte comme tout `django.*`.

    Cette classe n'est **pas** dans `apps.py` : Django y cherche les configurations de
    `plateforme.comptes` avec `inspect.getmembers`, qui ne distingue pas une classe
    définie d'une classe importée, et y trouver une configuration d'étiquette `admin` fait
    échouer le démarrage sur « Application labels aren't unique ».
    """

    default = False
    default_site = "plateforme.comptes.sites.AdminOperateurSite"


class AdminOperateurSite(AdminSite):
    """L'admin de flotte. Réservé aux opérateurs de la plateforme, qui n'ont aucun client."""

    site_title = "Optique — plateforme"
    site_header = "Administration de la flotte"
    index_title = "Plan de contrôle"

    def has_permission(self, request) -> bool:
        """Actif, super-opérateur, **et** rattaché à aucun client.

        La troisième condition est celle qui n'existe pas dans l'admin de Django. Elle est
        écrite en positif (`client_id is None`) plutôt qu'en négatif, pour qu'un
        `AnonymousUser` — dont `client_id` n'existe pas — échoue sur `is_active` avant
        d'arriver ici plutôt que de passer par un `getattr` complaisant.
        """
        utilisateur = getattr(request, "user", None)
        if utilisateur is None:
            return False
        if not getattr(utilisateur, "is_active", False):
            return False
        if not getattr(utilisateur, "is_superuser", False):
            return False
        # `getattr` avec un défaut *refusant* : un principal sans la notion de client —
        # AnonymousUser, ou un modèle d'utilisateur qu'une phase ultérieure échangerait —
        # est refusé, jamais admis par défaut (le pendant du fail-closed du routeur).
        return getattr(utilisateur, "client_id", "absent") is None

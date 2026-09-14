"""`Utilisateur` — l'identité de toute la flotte, sur le plan de contrôle.

Trois décisions sont prises ici, et chacune est une garantie plutôt qu'une préférence.

**Le champ s'appelle `client`.** `TenantMiddleware.resolve_client` lit déjà
`user.client_id` (`plateforme/tenancy/middleware.py`), donc nommer ainsi la clé étrangère
fait que la phase 3 ne change **aucune ligne** de la couche tenancy. `NULL` signifie
opérateur de plateforme : quelqu'un qui n'appartient à aucun opticien.

**Le mixin de droits de `django.contrib.auth` est délibérément absent.** Il créerait
`auth_user_groups` et `auth_user_user_permissions`, et mettrait
`user.has_perm("achats.view_article")` à une frappe de
`acces.peut("article.voir_prix_achat")`. Deux systèmes de droits dans un même code, c'est
la dérive de la phase 9 ; et `Group` **est** un palier de rôle, que CLAUDE.md #6 interdit.
Ne pas en hériter rend le palier inatteignable au lieu de simplement déconseillé — et
`test_perm02_utilisateur_n_expose_aucun_systeme_de_droits_django` constate cette absence,
donc la réintroduire tourne la suite au rouge. Le coût, énoncé honnêtement : l'admin
opérateur devient tout-ou-rien (`is_superuser` ou rien), ce qui est correct pour un
opérateur seul.

**Les garanties sont des `CheckConstraint`, pas des `clean()`.** Même raisonnement que
`control_plane.Client.active_client_has_db_name` : `queryset.update()`, `bulk_update()` et
une session shell contournent tous `clean()`. Ce que la base refuse, personne ne le fait.

Cette table vit sur `default` et nulle part ailleurs (CLAUDE.md #11) : `comptes` est dans
`CONTROL_PLANE_APPS`, donc `allow_migrate` l'épingle là et `_route` renvoie `"default"`
avant même de regarder le contexte de locataire — c'est pourquoi une requête de connexion,
qui n'a encore aucun client, ne lève jamais `NoTenantBound`.
"""

from __future__ import annotations

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models

from plateforme.comptes.managers import UtilisateurManager


class Utilisateur(AbstractBaseUser):
    """Un opticien propriétaire, un gérant, ou un opérateur de la plateforme."""

    email = models.EmailField(
        unique=True,
        verbose_name="adresse e-mail",
        help_text=(
            "L'identifiant de connexion. Unique sur toute la flotte, donc une adresse "
            "e-mail plutôt qu'un nom d'utilisateur : une collision sur « karim » "
            "révélerait l'existence du compte d'une autre affaire."
        ),
    )
    nom_complet = models.CharField(max_length=150, verbose_name="nom complet")

    #: **Le lien de locataire.** `resolve_client` lit `client_id` sur le principal
    #: authentifié, jamais sur quoi que ce soit que l'appelant puisse fournir
    #: (menace T-02-13). `PROTECT` : supprimer un client dont des comptes dépendent doit
    #: échouer bruyamment, art. 211 CGI imposant dix ans de conservation.
    client = models.ForeignKey(
        "control_plane.Client",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="utilisateurs",
        verbose_name="client",
        help_text="Vide pour un opérateur de la plateforme, qui n'appartient à aucune affaire.",
    )
    est_proprietaire = models.BooleanField(
        default=False,
        verbose_name="est propriétaire",
        help_text="L'opticien qui détient l'affaire. Un seul par client.",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="actif",
        help_text=(
            "Décoché, le compte est refusé dès la requête suivante : "
            "ModelBackend.get_user appelle user_can_authenticate à chaque requête, "
            "donc la désactivation (PERM-02) ne demande aucune machinerie de révocation."
        ),
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name="opérateur",
        help_text="Accès à l'admin de flotte. Impossible pour un compte rattaché à un client.",
    )
    is_superuser = models.BooleanField(default=False, verbose_name="super-opérateur")

    doit_changer_mot_de_passe = models.BooleanField(
        default=False, verbose_name="doit changer son mot de passe"
    )
    derniere_connexion_ip = models.GenericIPAddressField(
        null=True, blank=True, verbose_name="IP de dernière connexion"
    )
    cree_le = models.DateTimeField(auto_now_add=True, verbose_name="créé le")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nom_complet"]

    objects = UtilisateurManager()

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["email"]
        constraints = [
            # `condition=`, pas `check=` : le mot-clé `check` a été déprécié en Django 5.1
            # et supprimé en 6.1. Même idiome que control_plane.Client.
            models.CheckConstraint(
                condition=models.Q(client__isnull=True)
                | (models.Q(is_staff=False) & models.Q(is_superuser=False)),
                name="un_utilisateur_client_n_est_jamais_operateur",
                violation_error_message=(
                    "Un compte rattaché à un client ne peut pas être opérateur. "
                    "L'admin Django est la gestion de flotte — il expose le nom, l'hôte "
                    "et les identifiants de la base de chaque opticien — pas les données "
                    "d'un opticien."
                ),
            ),
            models.CheckConstraint(
                condition=models.Q(client__isnull=False)
                | models.Q(est_proprietaire=False),
                name="un_proprietaire_appartient_a_un_client",
                violation_error_message=(
                    "Un propriétaire sans client est un titre sans périmètre : il n'y a "
                    "aucune affaire dont il serait le propriétaire."
                ),
            ),
            models.UniqueConstraint(
                fields=["client"],
                condition=models.Q(est_proprietaire=True),
                name="un_seul_proprietaire_par_client",
                violation_error_message=(
                    "Cette affaire a déjà un propriétaire. Les comptes supplémentaires "
                    "sont des gérants, avec des droits accordés un par un."
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.nom_complet} <{self.email}>"

    # -- ce que l'admin exige d'un AbstractBaseUser sans le mixin de droits de Django ---
    #
    # `ModelAdmin` et `AdminSite` appellent ces deux méthodes sur chaque vue. Sans elles,
    # l'admin lève `AttributeError`. Elles renvoient `is_superuser` et rien d'autre : le
    # tout-ou-rien assumé ci-dessus. Elles ne sont **pas** le système de droits du
    # produit — celui-là est posé au plan 03-04, se lit `acces.peut(code, magasin)`, et ne
    # passe jamais par `has_perm`.

    def has_perm(self, perm, obj=None) -> bool:
        return bool(self.is_active and self.is_superuser)

    def has_module_perms(self, app_label) -> bool:
        return bool(self.is_active and self.is_superuser)

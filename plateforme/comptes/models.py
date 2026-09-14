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

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import models

from plateforme.comptes.managers import UtilisateurManager
from plateforme.comptes.permissions_catalogue import Permission


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


# ======================================================================================
# Les octrois — trois tables, sur le plan de contrôle
# ======================================================================================
#
# Le catalogue (`permissions_catalogue.py`) est du **code** ; ce qui suit est la **donnée**
# : une ligne par droit effectivement accordé. La séparation est ce qui permet à la phase 8
# d'ajouter un code sans migration, et à un propriétaire de retirer un droit sans
# déploiement.
#
# Les trois tables vivent sur `default` et nulle part ailleurs : `comptes` est dans
# `CONTROL_PLANE_APPS` depuis le plan 03-01, donc `allow_migrate` les y épingle et `_route`
# renvoie `"default"` sans regarder le contexte de locataire (CLAUDE.md #11).


class AccesMagasin(models.Model):
    """PERM-04 — quels magasins ce compte peut atteindre. Un magasin, une ligne.

    **`magasin_code` est une valeur, jamais une clé étrangère.** `Magasin` vit dans la base
    de l'opticien et cette table dans le plan de contrôle ; `TenantRouter.allow_relation`
    refuse explicitement toute relation dont les deux extrémités ne sont pas sur le même
    alias. Une `ForeignKey` ici ne serait donc pas seulement indésirable, elle serait
    inconstructible — et c'est la même frontière qui rend `django-guardian` structurellement
    impossible sur ce projet, pas seulement inutile.

    **Le code métier plutôt que la clé primaire**, pour que l'octroi survive à une
    restauration et à une bascule (TENANT-09) : les `id` sont réattribués par un
    `pg_restore` dans une base neuve, le code `ANFA` non. Le prix est qu'un code peut
    devenir obsolète ou désigner un magasin désactivé ; il est donc intersecté avec les
    magasins actifs au moment de la résolution (plan 03-05, menace T-03-20), et cette
    ligne-ci n'affirme jamais à elle seule qu'un magasin existe.
    """

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="acces_magasins",
        verbose_name="utilisateur",
    )
    magasin_code = models.CharField(
        max_length=20,
        verbose_name="code du magasin",
        help_text=(
            "Le code métier du magasin, tel qu'il existe dans la base de l'opticien. "
            "Une valeur, pas une relation : la base du client et le plan de contrôle "
            "sont deux connexions distinctes."
        ),
    )
    accorde_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="accordé par",
    )
    accorde_le = models.DateTimeField(auto_now_add=True, verbose_name="accordé le")

    class Meta:
        verbose_name = "accès à un magasin"
        verbose_name_plural = "accès aux magasins"
        ordering = ["utilisateur", "magasin_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["utilisateur", "magasin_code"],
                name="uniq_acces_magasin_par_utilisateur",
                violation_error_message=(
                    "Ce compte a déjà accès à ce magasin. L'accès est une ligne, pas un "
                    "compteur."
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.utilisateur_id} → {self.magasin_code}"


class DroitAccorde(models.Model):
    """PERM-03 — **un droit est une ligne `(gérant, magasin, permission)`**. CLAUDE.md #13.

    Mot pour mot : *« Permission grants are stored per (gérant, magasin, permission). The
    owner may override permissions per magasin, so the storage shape must support that from
    day one […] Do not "simplify" this to one permission set per gérant; reversing it is a
    data migration. »*

    `03-RESEARCH.md` §4 propose `DroitAccorde(utilisateur, code)`, sans dimension magasin ;
    son propre bandeau de correction et `03-UI-SPEC.md` 0.1 disent que cette forme est
    abandonnée. **Retirer `magasin_code` serait une migration de données sur des droits en
    production, plus un changement de signature de `peut()`, donc de chacun de ses sites
    d'appel.** Si cette colonne paraît superflue en lisant l'interface, c'est normal :
    l'écran montre une case à cocher par droit et n'expose le « par magasin » que sur
    demande (`03-UI-SPEC.md` 7.5). C'est le stockage qui doit pouvoir, pas l'écran qui doit
    montrer.

    Le `code` est contraint au catalogue par `choices`, et le catalogue est du code : il n'y
    a pas de table de permissions à peupler, donc pas d'état où une base aurait un code que
    l'application ignore.
    """

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="droits",
        verbose_name="utilisateur",
    )
    magasin_code = models.CharField(
        max_length=20,
        verbose_name="code du magasin",
        help_text=(
            "Le magasin dans lequel ce droit s'applique. Un droit accordé à Anfa ne vaut "
            "rien à Maârif — c'est toute la raison d'être de cette colonne."
        ),
    )
    code = models.CharField(
        max_length=64,
        choices=Permission.choices,
        verbose_name="permission",
        help_text="Un code du catalogue, jamais une permission Django.",
    )
    accorde_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="accordé par",
    )
    accorde_le = models.DateTimeField(auto_now_add=True, verbose_name="accordé le")

    class Meta:
        verbose_name = "droit accordé"
        verbose_name_plural = "droits accordés"
        ordering = ["utilisateur", "magasin_code", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["utilisateur", "magasin_code", "code"],
                name="uniq_droit_par_utilisateur_magasin_code",
                violation_error_message=(
                    "Ce droit est déjà accordé à ce compte pour ce magasin. Les trois "
                    "colonnes sont dans la contrainte : la même permission peut être "
                    "accordée dans un magasin et refusée dans un autre (CLAUDE.md #13)."
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.utilisateur_id} → {self.code} @ {self.magasin_code}"

    def valider_acces_magasin(self, using: str | None = None) -> None:
        """Refuse un droit visant un magasin auquel le compte n'a pas accès.

        Menace T-03-18 : une telle ligne n'accorde rien aujourd'hui et devient active le
        jour où le magasin est accordé — un droit que personne n'a décidé d'accorder,
        apparu à l'occasion d'une action sans rapport.

        **Admis franchement : la base ne peut pas nous sauver ici.** Une `CheckConstraint`
        porte sur une ligne, pas sur l'existence d'une ligne dans une autre table, et une
        clé étrangère composite vers `AccesMagasin` ferait de la paire
        `(utilisateur, magasin)` la clé de cette table, ce qui interdirait de révoquer un
        accès sans détruire l'historique des droits. Contrairement à la garantie opérateur
        du plan 03-01, celle-ci est donc une règle Python : posée ici, appliquée une
        seconde fois par le service d'octroi (plan 03-09), et tenue par
        `test_perm03_un_droit_ne_peut_viser_un_magasin_non_accorde`. `queryset.update()`
        la contourne toujours.
        """
        acces = AccesMagasin.objects.all()
        if using is not None:
            acces = acces.using(using)
        if not acces.filter(
            utilisateur_id=self.utilisateur_id, magasin_code=self.magasin_code
        ).exists():
            raise ValidationError(
                {
                    "magasin_code": (
                        f"Ce compte n'a pas accès au magasin « {self.magasin_code} ». "
                        f"Un droit sans accès au magasin n'accorde rien : accordez "
                        f"l'accès au magasin d'abord."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.valider_acces_magasin(using=kwargs.get("using"))
        return super().save(*args, **kwargs)


class JournalDroit(models.Model):
    """PERM-03 — l'histoire, en append-only. « Qui a donné les marges à Karim ? »

    La révocation **supprime** la ligne d'octroi : c'est ce qui rend la résolution
    trivialement juste — il n'y a pas de ligne « inactive » à oublier de filtrer. Le prix
    est qu'après une révocation il ne reste rien à interroger, sauf ce journal, que
    `03-UI-SPEC.md` 7.3 D affiche sur la fiche du compte (menace T-03-19).

    Trois choix le rendent utilisable après coup :

    * **`PROTECT` sur les deux clés.** Supprimer un compte dont le journal parle doit
      échouer bruyamment, pas effacer l'historique en cascade.
    * **Aucune relation vers `DroitAccorde`.** Une clé étrangère vers la ligne d'octroi
      serait supprimée avec elle, et le journal ne répondrait à la question que tant que
      la question ne se pose pas. `cible` est donc une **valeur** — un code de permission
      ou un code de magasin.
    * **`save()` refuse la réécriture.** Un journal modifiable répond toujours à la
      question, mais pas forcément la vérité.
    """

    class Action(models.TextChoices):
        ACCORDE = "accorde", "Accordé"
        REVOQUE = "revoque", "Révoqué"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="journal",
        verbose_name="utilisateur concerné",
    )
    action = models.CharField(
        max_length=8, choices=Action.choices, verbose_name="action"
    )
    cible = models.CharField(
        max_length=64,
        verbose_name="cible",
        help_text="Un code de permission ou un code de magasin. Une valeur, pas une clé.",
    )
    par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="par",
    )
    le = models.DateTimeField(auto_now_add=True, verbose_name="le")

    class Meta:
        verbose_name = "entrée de journal des droits"
        verbose_name_plural = "journal des droits"
        ordering = ["-le"]
        indexes = [
            models.Index(fields=["utilisateur", "-le"], name="idx_journal_utilisateur"),
        ]

    def __str__(self) -> str:
        return f"{self.le:%Y-%m-%d %H:%M} — {self.action} {self.cible}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(
                "Le journal des droits est en ajout seul : une entrée écrite ne se "
                "réécrit pas. Pour corriger, ajoutez une entrée qui décrit la correction."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Le journal des droits est en ajout seul : il survit délibérément à la ligne "
            "d'octroi qu'il décrit, sans quoi il ne répondrait plus après une révocation."
        )

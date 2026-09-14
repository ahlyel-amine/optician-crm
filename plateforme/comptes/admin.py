"""Ce que l'opérateur voit des comptes. **Aucun modèle métier, jamais** (PERM-06).

La règle négative est la plus importante de ce fichier : rien de `domaine.` n'y est
importé, et `test_perm06_aucun_modele_metier_n_est_enregistre_dans_ladmin` le vérifie.
Un `ModelAdmin` métier rendrait les données **sans passer par la couche de projection**,
donc sans les droits par gérant, sans le filtrage par magasin, et sans aucune des
assertions du test de conformité paramétré. Il lèverait de toute façon `NoTenantBound`,
l'admin ne tournant pas dans une requête liée à un locataire — mais c'est le second motif,
pas le premier.

La classe de l'`AdminSite` vit dans `sites.py` et non ici : voir la docstring de ce
module-là pour le piège de ré-entrance qui l'impose.

Le compte lui-même est presque entièrement en lecture seule. L'appartenance à un client et
le titre de propriétaire sont des faits d'onboarding, tenus par les contraintes de base ;
les modifier depuis cette page ferait passer un opticien d'une affaire à une autre en un
clic, et c'est le plan 03-02 (le propriétaire crée ses gérants) qui possède le vrai
parcours de gestion des comptes.
"""

from __future__ import annotations

from django.contrib import admin

from plateforme.comptes.models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(admin.ModelAdmin):
    """Qui existe sur la flotte, et à quelle affaire chacun appartient."""

    list_display = (
        "email",
        "nom_complet",
        "client",
        "est_proprietaire",
        "is_active",
        "is_staff",
        "cree_le",
    )
    list_filter = ("is_active", "is_staff", "est_proprietaire")
    search_fields = ("email", "nom_complet")
    ordering = ("email",)
    date_hierarchy = "cree_le"

    # `client` et `est_proprietaire` ne sont pas modifiables ici. Les rendre modifiables
    # donnerait à l'admin de flotte le pouvoir de déplacer un compte d'une affaire à une
    # autre, ce qui est une opération d'onboarding, pas une correction de fiche.
    readonly_fields = (
        "client",
        "est_proprietaire",
        "last_login",
        "cree_le",
        "derniere_connexion_ip",
    )
    # L'empreinte du mot de passe ne doit apparaître dans aucun formulaire ni aucune vue
    # en lecture seule : une page d'admin qui l'affiche la dépose dans un cache de
    # navigateur, une capture d'écran et un ticket de support. Même raisonnement que le
    # jeton Fernet exclu de `ClientAdmin`.
    exclude = ("password",)

    def has_delete_permission(self, request, obj=None):
        """Jamais. Un compte se désactive (`is_active`), il ne se supprime pas.

        La désactivation prend effet dès la requête suivante — `ModelBackend.get_user`
        appelle `user_can_authenticate` à chaque requête — donc elle ne coûte rien en
        latence de révocation. La suppression, elle, effacerait la piste d'audit d'un
        compte qui a pu signer des factures, que l'art. 211 CGI demande de conserver dix
        ans.
        """
        return False

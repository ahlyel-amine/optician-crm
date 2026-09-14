"""Le gestionnaire d'`Utilisateur`, et les deux seules façons de créer un compte.

La normalisation de l'adresse est la partie qui mérite d'être lue. L'unicité est à
l'échelle de la **flotte entière** — un seul plan de contrôle, une seule table
(CLAUDE.md #11) — donc `Karim@optique-anfa.ma` et `karim@optique-anfa.ma` doivent être le
même compte. `BaseUserManager.normalize_email` ne met en minuscules que le *domaine* ;
sans la mise en minuscules complète ci-dessous, deux comptes distincts coexistent, la
connexion devient sensible à la casse et un propriétaire peut, par accident, créer un
doublon de son propre gérant.
"""

from __future__ import annotations

from django.contrib.auth.base_user import BaseUserManager


class UtilisateurManager(BaseUserManager):
    """Crée les comptes d'opticiens et les comptes opérateurs, jamais autrement."""

    use_in_migrations = True

    def normalize_email(self, email):
        """Minuscules sur la partie locale **et** le domaine.

        Django ne normalise que le domaine, parce que la RFC 5321 laisse la partie locale
        sensible à la casse. Aucun fournisseur de messagerie réel ne s'en sert, et le coût
        du doute est un identifiant de connexion sur lequel deux comptes peuvent exister.
        """
        return super().normalize_email(email or "").lower()

    def create_user(self, email, nom_complet, password=None, **extra):
        if not email:
            raise ValueError("Un compte doit avoir une adresse e-mail.")
        if not nom_complet:
            raise ValueError("Un compte doit avoir un nom complet.")

        utilisateur = self.model(
            email=self.normalize_email(email), nom_complet=nom_complet, **extra
        )
        # set_password, jamais une affectation directe : le hachage passe par
        # PASSWORD_HASHERS, dont Argon2 est la tête. `None` produit un mot de passe
        # inutilisable, ce qui est le bon défaut pour un compte créé par le propriétaire
        # et activé par son destinataire.
        utilisateur.set_password(password)
        utilisateur.save(using=self._db)
        return utilisateur

    def create_superuser(self, email, nom_complet, password=None, **extra):
        """Un opérateur de plateforme. **N'appartient à aucun client**, par construction.

        `client=None` est forcé plutôt que laissé à l'appelant : la contrainte
        `un_utilisateur_client_n_est_jamais_operateur` refuserait la ligne de toute façon,
        et `createsuperuser` échouerait alors avec une erreur PostgreSQL au lieu d'une
        phrase compréhensible.
        """
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("est_proprietaire", False)

        if extra.get("is_staff") is not True:
            raise ValueError("Un opérateur doit avoir is_staff=True.")
        if extra.get("is_superuser") is not True:
            raise ValueError("Un opérateur doit avoir is_superuser=True.")
        if extra.get("client") is not None:
            raise ValueError(
                "Un opérateur n'appartient à aucun client. L'admin Django est la gestion "
                "de flotte, pas les données d'un opticien."
            )
        extra["client"] = None

        return self.create_user(email, nom_complet, password=password, **extra)

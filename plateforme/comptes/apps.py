"""Configuration de l'application `comptes`.

`label = "comptes"` est explicite plutôt que dérivé : c'est ce label — pas le chemin
pointé — que `CONTROL_PLANE_APPS` et `allow_migrate` comparent, et c'est lui qui apparaît
dans `AUTH_USER_MODEL = "comptes.Utilisateur"`.
"""

from __future__ import annotations

from django.apps import AppConfig


class ComptesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plateforme.comptes"
    label = "comptes"
    verbose_name = "Comptes"

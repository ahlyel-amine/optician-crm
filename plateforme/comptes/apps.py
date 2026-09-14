"""Configuration de l'application `comptes`.

`label = "comptes"` est explicite plutôt que dérivé : c'est ce label — pas le chemin
pointé — que `CONTROL_PLANE_APPS` et `allow_migrate` comparent, et c'est lui qui apparaît
dans `AUTH_USER_MODEL = "comptes.Utilisateur"`.
"""

from __future__ import annotations

from django.apps import AppConfig

# N'importez **rien** d'autre ici qui soit une sous-classe d'`AppConfig`. Django peuple
# l'application en passant `inspect.getmembers(module, inspect.isclass)` sur ce module et
# retient toute sous-classe d'`AppConfig` qu'il y trouve, sans regarder si elle y a été
# définie ou seulement importée. `AdminConfig` importé ici a produit
# « Application labels aren't unique, duplicates: admin » — d'où `AdminOperateurConfig`
# posé dans `sites.py`, à côté du site qu'il installe.


class ComptesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plateforme.comptes"
    label = "comptes"
    verbose_name = "Comptes"

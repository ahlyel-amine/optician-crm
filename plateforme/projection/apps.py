"""Configuration de l'application `projection`.

Aucun modèle, donc aucune migration. Le classement dans `CONTROL_PLANE_APPS` n'est pas de
la paperasse : `plateforme/tenancy/checks.py` n'exempte que les noms commençant par
`django.`, et une application non classée fait échouer `manage.py check` avec
`tenancy.E001`.
"""

from __future__ import annotations

from django.apps import AppConfig


class ProjectionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plateforme.projection"
    label = "projection"
    verbose_name = "Projection"

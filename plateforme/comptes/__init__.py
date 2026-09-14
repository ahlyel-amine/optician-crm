"""Identité de la flotte : le modèle `Utilisateur` et l'admin opérateur.

Application de **plan de contrôle** (CLAUDE.md #11) : ses tables vivent sur `default` et
nulle part ailleurs. Elle porte `AUTH_USER_MODEL`, donc elle doit être classée dans
`CONTROL_PLANE_APPS` — voir `plateforme/tenancy/router.py`.
"""

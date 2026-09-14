"""La couche de projection unique (PERM-06) : un registre, plusieurs consommateurs.

Coquille posée ici, remplie par les plans 03-05 et suivants. Elle **ne possède aucun
modèle** — sa raison d'être est un registre `(modèle, champ) -> code de droit` lu par les
sérialiseurs DRF, l'export CSV, le contexte des documents imprimés et le post-traitement
du schéma OpenAPI. Ce qui empêche ces rendus de diverger n'est pas l'abstraction mais le
test de conformité paramétré sur le registre × les rendus (`03-RESEARCH.md` §3).

Une application sans modèle a quand même besoin de son étiquette dans
`CONTROL_PLANE_APPS` : `plateforme/tenancy/checks.py` n'exempte que les noms commençant
par `django.`, donc sans classement `tenancy.E001` refuse le démarrage.
"""

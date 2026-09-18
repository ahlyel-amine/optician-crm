"""CLIENT-10 — les deux extensions PostgreSQL, sur chaque base client et nulle part ailleurs.

Deux tests, et ils tirent dans des directions opposées **exprès**.

Le premier est la moitié positive : `pg_trgm` et `fuzzystrmatch` doivent exister dans
CHAQUE base client. Il est paramétré sur les deux locataires, jamais sur un seul — une
extension créée sur un seul alias par un accident de fixture passerait un test
mono-locataire, et c'est précisément la forme de bug que `.planning/TESTING.md` §3 dit
qu'un locataire unique ne peut pas attraper.

Le second est la moitié `allow_migrate`, et c'est un **contrôle négatif assumé** : il est
vert avant comme après la migration. Il est écrit malgré cela parce qu'il deviendrait
rouge le jour où quelqu'un « réparerait » la migration d'extensions en la déplaçant dans
une application du plan de contrôle — ce qui poserait une extension métier sur `default`,
donc la preuve qu'une migration métier a touché le plan de contrôle (menace T-04-04).
"""

from __future__ import annotations

import pytest

#: Les deux seules extensions que la phase 4 installe. `unaccent` n'y est **pas**, et son
#: absence est une décision mesurée, pas un oubli : elle est `STABLE`, donc inindexable
#: (`42P17`), colonne générée comprise. La normalisation NFKD de
#: `domaine/clients/recherche.py` fait le même travail, est immuable par construction, et
#: supprime le besoin de prouver une troisième extension sur trois cents bases.
EXTENSIONS_ATTENDUES = frozenset({"pg_trgm", "fuzzystrmatch"})


def _extensions(alias: str) -> set[str]:
    """Les extensions réellement installées dans la base derrière `alias`."""
    from django.db import connections

    with connections[alias].cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension")
        return {ligne[0] for ligne in cur.fetchall()}


@pytest.mark.parametrize("nom_de_fixture", ["tenant_a", "tenant_b"])
def test_client10_les_extensions_sont_presentes_sur_chaque_base_client(
    db_all, request, nom_de_fixture
):
    """Les deux extensions existent dans la base des DEUX clients.

    Rouge dans un sens : la migration `0001_extensions` n'existe pas, ou n'a pas été
    appliquée, et l'ensemble rendu ne contient que `plpgsql`.

    Rouge dans l'autre : la migration existe mais a été classée dans une application du
    plan de contrôle, donc `allow_migrate` l'a refusée sur les alias client.

    L'alias est résolu par `request.getfixturevalue` plutôt que par un `if` sur le
    paramètre : un `if` ferait exécuter au test un chemin différent par locataire, ce qui
    est exactement ce qu'un test d'isolation ne doit pas faire.
    """
    alias = request.getfixturevalue(nom_de_fixture)

    presentes = _extensions(alias)
    manquantes = EXTENSIONS_ATTENDUES - presentes

    assert not manquantes, (
        f"{sorted(manquantes)} manquent dans la base de {alias} ; présentes : "
        f"{sorted(presentes)}. Les extensions arrivent par la migration "
        "domaine/clients/migrations/0001_extensions.py, PAS par le provisionnement — "
        "`provision_client()` rend la main tôt sur `status == ACTIVE`, donc une création "
        "au provisionnement sauterait en silence tous les clients existants."
    )


def test_client10_aucune_extension_metier_n_atterrit_sur_default(db_all):
    """`pg_trgm` est absent de la base du plan de contrôle. **Contrôle négatif assumé.**

    Ce test est vert avant comme après la migration, et ce n'est pas un échec : sa valeur
    est dans le futur. `CreateExtension.database_forwards` consulte
    `router.allow_migrate(alias, app_label)` sans `model_name` ; `TenantRouter` rend
    `is_tenant_alias(db)` pour une application métier, donc `False` sur `default`.

    Il devient rouge si quelqu'un déplace la migration dans une application du plan de
    contrôle, ou ajoute `"clients"` à `CONTROL_PLANE_APPS` au lieu de `BUSINESS_APPS` —
    deux « corrections » plausibles qui poseraient une table métier sur la base partagée
    de toute la flotte.
    """
    presentes = _extensions("default")

    debordantes = EXTENSIONS_ATTENDUES & presentes
    assert not debordantes, (
        f"{sorted(debordantes)} sont installées sur `default`, la base du plan de "
        "contrôle. Une extension métier sur `default` est la preuve qu'une migration "
        "métier y a été appliquée — `allow_migrate` aurait dû la refuser. Vérifier que "
        "`clients` est dans BUSINESS_APPS et non dans CONTROL_PLANE_APPS."
    )

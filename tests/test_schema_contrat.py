"""Le contrat OpenAPI — PERM-06 appliqué aux types, et non plus aux valeurs.

**Ce test n'est pas encore implémenté.** Marqueur `pending`, corps volontairement rouge ;
le plan **03-10** l'implémente, génère le schéma, le commite et retire le marqueur.

Pourquoi ce fichier est séparé de `tests/test_projection.py` : les tests de projection
interrogent un schéma **généré à la volée** pendant le test. Celui-ci compare le schéma
généré au schéma **commité dans le dépôt**. Ce sont deux questions différentes — « la
projection est-elle correcte ? » et « le fichier dont dépend le client TypeScript est-il à
jour ? » — et la seconde est la seule qui puisse devenir fausse sans qu'aucune ligne de
`plateforme/projection/` ne change.

**Aucun import du code en construction au niveau du module.**
"""

from __future__ import annotations

import pytest


@pytest.mark.pending
def test_perm06_le_schema_committe_correspond_au_schema_genere():
    """Le client TypeScript est généré depuis `web/src/api/schema.yml`, pas depuis l'API.

    Ce que ce test garde : un schéma qui change en silence est exactement le mode de
    défaillance de PERM-06, appliqué aux types au lieu des valeurs. Un champ protégé retiré
    d'un sérialiseur mais toujours présent dans le YAML commité donne au client une
    `interface` qui le déclare ; la phase 8 écrira une colonne de tableau sur la foi de ce
    type, elle rendra `undefined`, et personne ne saura si c'est un bug de rendu, de droits
    ou de contrat. L'inverse est pire : un champ ajouté au sérialiseur et absent du YAML est
    servi sur le fil sans que le contrat le mentionne — donc sans qu'aucune revue le voie.

    Le fichier est commité plutôt que généré au build pour une raison précise : commité, un
    changement de contrat apparaît **en diff**, dans la revue, à côté du code qui l'a causé.
    Généré, il n'apparaît nulle part.

    Rouge, ce test dit qu'il faut régénérer le schéma et le commiter dans le même
    changement. C'est une porte à bruit voulu : le coût est une commande, l'alternative est
    une dérive silencieuse entre le serveur et le client, sur dix phases.
    """
    pytest.fail("non implémenté : plan 03-10")

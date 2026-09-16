"""Le contrat OpenAPI — PERM-06 appliqué aux types, et non plus aux valeurs.

Pourquoi ce fichier est séparé de `tests/test_projection.py` : les tests de projection
interrogent un schéma **généré à la volée** pendant le test. Celui-ci compare le schéma
généré au schéma **commité dans le dépôt**. Ce sont deux questions différentes — « la
projection est-elle correcte ? » et « le fichier dont dépend le client TypeScript est-il à
jour ? » — et la seconde est la seule qui puisse devenir fausse sans qu'aucune ligne de
`plateforme/projection/` ne change.

**Aucun import du code en construction au niveau du module.**
"""

from __future__ import annotations

from pathlib import Path

#: Le document commité, celui dont `npm run api:types` génère le client TypeScript.
RACINE = Path(__file__).resolve().parent.parent
SCHEMA_COMMITE = RACINE / "web" / "src" / "api" / "schema.yml"

#: La commande exacte, écrite une fois : elle apparaît dans les messages d'échec, dans
#: `docs/ci-schema.md` et dans la porte de CI, et les trois doivent dire la même chose.
COMMANDE = (
    "uv run python manage.py spectacular --file web/src/api/schema.yml --fail-on-warn"
)

SCHEMA = "/api/schema/"


def _generer(chemin: Path, *, fail_on_warn: bool = True) -> str:
    """Génère le document par la **commande**, pas par le générateur.

    Appeler `SchemaGenerator` directement testerait un chemin de code voisin de celui que
    la CI exécute : le rendu YAML, l'ordre des clés et l'encodage viennent de la commande.
    Un test qui passe pendant que `manage.py spectacular` produit un octet différent
    n'aurait aucune valeur, puisque c'est ce fichier-là qui est commité.
    """
    from django.core.management import call_command

    call_command("spectacular", file=str(chemin), fail_on_warn=fail_on_warn)
    return chemin.read_text(encoding="utf-8")


def test_perm06_le_schema_committe_correspond_au_schema_genere(tmp_path):
    """Le client TypeScript est généré depuis `web/src/api/schema.yml`, pas depuis l'API.

    Ce que ce test garde : un schéma qui change en silence est exactement le mode de
    défaillance de PERM-06, appliqué aux types au lieu des valeurs. Un champ protégé
    retiré d'un sérialiseur mais toujours présent dans le YAML commité donne au client une
    `interface` qui le déclare ; la phase 8 écrira une colonne de tableau sur la foi de ce
    type, elle rendra `undefined`, et personne ne saura si c'est un bug de rendu, de
    droits ou de contrat. L'inverse est pire : un champ ajouté au sérialiseur et absent du
    YAML est servi sur le fil sans que le contrat le mentionne — donc sans qu'aucune revue
    le voie.

    Le fichier est commité plutôt que généré au build pour une raison précise : commité,
    un changement de contrat apparaît **en diff**, dans la revue, à côté du code qui l'a
    causé. Généré, il n'apparaît nulle part.

    Rouge, ce test dit qu'il faut régénérer le schéma et le commiter dans le même
    changement. C'est une porte à bruit voulu : le coût est une commande, l'alternative
    est une dérive silencieuse entre le serveur et le client, sur dix phases.
    """
    assert SCHEMA_COMMITE.is_file(), f"{SCHEMA_COMMITE} est absent. Générez-le : {COMMANDE}"

    genere = _generer(tmp_path / "schema.yml")
    committe = SCHEMA_COMMITE.read_text(encoding="utf-8")

    assert committe == genere, (
        "Le contrat d'API a changé et le fichier commité ne l'a pas suivi. Régénérez-le "
        f"dans le même changement :\n    {COMMANDE}\n"
        "Puis relisez le diff : c'est exactement ce que ce test existe pour rendre "
        "visible."
    )


def test_perm06_la_generation_du_schema_n_emet_aucun_avertissement(tmp_path):
    """`--fail-on-warn` doit passer, sinon la porte de CI ne peut pas exister.

    Un avertissement de `drf-spectacular` n'est presque jamais cosmétique : il dit qu'une
    vue n'a pas pu être introspectée, donc que son type côté client sera `unknown` ou
    absent. Tolérer le premier revient à ne plus jamais lire les suivants, et la porte de
    CI devient impossible à poser parce que l'arbre est déjà bruyant.

    C'est aussi ce qui rend exécutable la règle du plan 03-08 : toute `APIView` porte son
    `extend_schema` **dans le plan qui la crée**. Sans cette assertion, l'oubli est
    silencieux jusqu'au jour où quelqu'un cherche la route dans le client généré.
    """
    _generer(tmp_path / "schema.yml", fail_on_warn=True)


def test_perm06_le_contrat_porte_les_routes_montees_et_aucune_route_de_test(tmp_path):
    """Deux inventaires, dans les deux sens.

    Les routes des plans 03-08 et 03-09 doivent y être : c'est la moitié qui attrape une
    `APIView` nue, qu'`AutoSchema` ignore en silence — la route existe, elle est servie,
    et le client TypeScript n'en sait rien.

    La ressource de test du plan 03-06 ne doit **pas** y être, et c'est la moitié plus
    intéressante. Elle est montée par `override_settings(ROOT_URLCONF=...)` dans les tests
    de projection, jamais dans `config/urls.py` ; le jour où quelqu'un la monte « pour
    déboguer », le document commité décrirait un point de terminaison de test au client, et
    `npm run api:types` en générerait le type. Un inventaire n'a de valeur que s'il refuse
    aussi ce qui ne doit pas y figurer.
    """
    import yaml

    document = yaml.safe_load(_generer(tmp_path / "schema.yml"))
    chemins = set(document["paths"])

    attendus = {
        "/api/auth/connexion/",
        "/api/auth/deconnexion/",
        "/api/auth/moi/",
        "/api/auth/csrf/",
        "/api/auth/mot-de-passe/",
        "/api/comptes/",
        "/api/comptes/catalogue/",
    }
    manquants = attendus - chemins
    assert not manquants, (
        f"Le contrat ne décrit pas {sorted(manquants)}. Une APIView sans `extend_schema` "
        "est ignorée par le générateur : la route est servie et le client généré l'ignore."
    )

    testeurs = [chemin for chemin in chemins if "ressource" in chemin or "fixture" in chemin]
    assert not testeurs, (
        f"Des routes de test sont dans le contrat commité : {testeurs}. Elles se montent "
        "par `override_settings(ROOT_URLCONF=...)`, jamais dans `config/urls.py`."
    )

    assert SCHEMA not in chemins, (
        "Le point de terminaison de schéma se décrit lui-même. `SERVE_INCLUDE_SCHEMA` "
        "doit rester à False : c'est de l'infrastructure, pas de la surface d'API."
    )


def test_perm06_le_schema_servi_est_identique_pour_chaque_appelant(affaire_reelle):
    """T-03-70 — le document servi ne varie pas selon qui le demande, et égale le commité.

    C'est la vérification de bout en bout du crochet posé au plan 03-06.
    `SchemaGenerator.parse` remplace la requête par `GET_MOCK_REQUEST(...)`
    (`generators.py:231`) et le `build_mock_request` d'origine y recopie `request.user`
    (`plumbing.py:1283-1299`), lequel arrive jusqu'au contexte des sérialiseurs — donc la
    projection s'appliquerait au **document**. Un gérant téléchargerait un schéma d'où les
    champs protégés sont absents, et le comparer à celui du propriétaire **énumérerait**
    la liste des champs protégés : la projection deviendrait son propre oracle.

    Le plan 03-06 a fermé cela par une ligne de réglage. Ce test est ce qui empêche que la
    ligne soit retirée : il est le seul à faire la comparaison sur deux appelants réels et
    sur le fil, plutôt que sur un générateur appelé en mémoire.
    """
    from rest_framework.test import APIClient

    from tests.factories import MOT_DE_PASSE_DE_TEST, GerantFactory, ProprietaireFactory

    documents = {}
    for nom, fabrique in (("propriétaire", ProprietaireFactory), ("gérant", GerantFactory)):
        compte = fabrique(client=affaire_reelle.client)
        api = APIClient()
        connexion = api.post(
            "/api/auth/connexion/",
            {"email": compte.email, "mot_de_passe": MOT_DE_PASSE_DE_TEST},
            format="json",
        )
        assert connexion.status_code == 200, connexion.data
        reponse = api.get(SCHEMA)
        assert reponse.status_code == 200, reponse.content[:400]
        documents[nom] = reponse.content.decode("utf-8")

    assert documents["propriétaire"] == documents["gérant"], (
        "Le document servi varie selon l'appelant : la projection s'applique au schéma. "
        "Vérifiez que `SPECTACULAR_SETTINGS['GET_MOCK_REQUEST']` pointe toujours "
        "`plateforme.projection.schema.requete_mock_schema`."
    )
    assert documents["propriétaire"] == SCHEMA_COMMITE.read_text(encoding="utf-8"), (
        "Le document servi et le document commité diffèrent. « Un seul client généré » "
        f"cesse alors d'être vrai. Régénérez : {COMMANDE}"
    )


def test_perm06_le_schema_n_est_pas_servi_a_un_appelant_anonyme():
    """Le contrat est un inventaire complet du produit, et il est fermé par défaut.

    `SERVE_PERMISSIONS` vaut `AllowAny` chez `drf-spectacular` (vérifié sur la 0.30.0
    installée), ce qui en ferait le seul point de terminaison anonyme du produit — et
    celui qui énumère toutes les routes, tous les champs, toutes les énumérations et les
    messages d'erreur de chaque vue. C'est de la reconnaissance offerte, et l'absence de
    ce réglage ne se voit pas en lisant `config/urls.py` : elle se voit ici.
    """
    from rest_framework.test import APIClient

    reponse = APIClient().get(SCHEMA)

    assert reponse.status_code == 401, (
        f"Le schéma répond {reponse.status_code} à un appelant anonyme. `SERVE_PERMISSIONS` "
        "doit être posé explicitement : son défaut est `AllowAny`."
    )

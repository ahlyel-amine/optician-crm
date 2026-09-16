"""Consommateur 4 du registre : le schéma OpenAPI, et donc le client TypeScript.

C'est le consommateur qu'on oublie, et c'est celui qui décide si le contrat de types de
tout le produit est vrai. Deux comportements de `drf-spectacular`, tous deux vérifiés dans
le source de la version épinglée, obligent à écrire ce module.

**1. Le schéma servi varierait par utilisateur.** `SchemaGenerator.parse` pose
`view.request = GET_MOCK_REQUEST(method, path, view, input_request)`
(`generators.py:231`), et `build_mock_request` recopie `request.user` de l'appelant
(`plumbing.py:1283-1299`). Ce faux `request` arrive dans le contexte des sérialiseurs par
`build_serializer_context` (`plumbing.py:1502-1506`), donc la projection s'y applique. Le
gérant téléchargerait un document d'où les champs protégés sont absents, le comparer à
celui du propriétaire **énumérerait** la liste des champs protégés, et « un seul client
généré » cesserait d'être vrai : le `schema.yml` commité et le document servi divergeraient
en silence.

`requete_mock_schema` épingle donc `Acces.SCHEMA` **quel que soit l'appelant**. Une ligne.

**2. Un champ protégé atterrirait dans `required`.** L'appartenance est calculée comme
`field.required or (readOnly and not <réglage global>)` (`openapi.py:1094-1099`), donc un
champ monétaire calculé et en lecture seule y entre automatiquement. Le TypeScript généré
déclare alors `prix_achat: string` — **un type qui ment** : à l'exécution, la charge utile
d'un gérant n'a pas la clé, `data.prix_achat.toString()` explose en production, et le
compilateur avait dit que tout allait bien.

`marquer_champs_proteges_optionnels` retire chaque champ du registre du tableau `required`
de son composant. Le réglage global qui rendrait *tous* les champs en lecture seule
optionnels reste à son défaut, et son nom n'apparaît nulle part dans `config/settings/` :
le basculer rendrait `id` optionnel sur chaque ressource du produit, ce qui est un mensonge
bien plus large que celui qu'on répare. Le crochet est chirurgical ; l'interrupteur ne
l'est pas.

**L'alternative écartée, et pourquoi elle perd.** « `null` plutôt qu'absent » — toujours
émettre la clé, à `null` quand le droit manque — donnerait un type plus simple et ne
toucherait pas à `required`. Elle est refusée pour trois raisons :

* PERM-05 et le critère 4 de la feuille de route disent **absent**, pas vide ;
* une colonne toujours présente dans un CSV est une **colonne vide**, qui livre
  l'existence et la position du champ à celui à qui on le refuse ;
* une valeur monétaire `null` invite un `?? 0` au site d'appel, donc une marge de **zéro**
  au lieu d'une marge visiblement manquante. Un nombre faux sans erreur — exactement ce que
  la docstring de `MagasinScopedModel` refuse déjà, et le pire mode de défaillance d'un
  produit fiscal.
"""

from __future__ import annotations

import warnings

from drf_spectacular.plumbing import ResolvedComponent, build_mock_request

from plateforme.comptes.acces import Acces
from plateforme.projection.registre import CHAMPS_PROTEGES, codes_proteges_de


def requete_mock_schema(method, path, view, original_request, **kwargs):
    """`SPECTACULAR_SETTINGS["GET_MOCK_REQUEST"]` — le schéma voit tout, pour tout le monde.

    `Acces.SCHEMA` porte le catalogue complet sous un magasin fictif et `pour_le_schema` à
    vrai (plan 03-05), donc `champs_interdits` n'interdit rien. Il est posé **après**
    `build_mock_request` et sans regarder `original_request` : c'est précisément la recopie
    de l'appelant qu'il s'agit de neutraliser.
    """
    requete = build_mock_request(method, path, view, original_request, **kwargs)
    requete.acces = Acces.SCHEMA
    return requete


def _noms_proteges() -> frozenset[str]:
    """Les derniers segments des clés du registre — la vue « par nom de champ »."""
    return frozenset(cle.rsplit(".", 1)[-1] for cle in CHAMPS_PROTEGES)


def _composants_par_modele(generator):
    """`{nom_de_composant: modèle}` pour les composants adossés à un `ModelSerializer`.

    Lit `generator.registry._components`, qui est privé. C'est assumé et borné : la version
    de `drf-spectacular` est épinglée à l'exact, le registre public n'expose pas le lien
    composant -> sérialiseur, et la seule alternative — redériver le nom du composant
    depuis la classe du sérialiseur — dupliquerait une règle de nommage de la bibliothèque,
    ce qui casserait plus discrètement. Si l'attribut disparaît, l'appelant bascule sur un
    filtrage par nom de champ, plus large mais jamais plus permissif.
    """
    interne = getattr(generator.registry, "_components", None)
    if interne is None:
        return None
    par_modele = {}
    for composant in interne.values():
        if composant.type != ResolvedComponent.SCHEMA:
            continue
        objet = composant.object
        modele = getattr(getattr(objet, "Meta", None), "model", None)
        if modele is not None:
            par_modele[composant.name] = modele
    return par_modele


def marquer_champs_proteges_optionnels(generator, request, public, result):
    """`SPECTACULAR_SETTINGS["POSTPROCESSING_HOOKS"]` — aucun champ protégé n'est `required`.

    Deux chemins, et le second est volontairement **plus large** que le premier :

    * chemin nominal — le composant est relié à son modèle, donc seuls les champs protégés
      *de ce modèle* sortent de `required` ;
    * chemin de repli — si le registre interne de `drf-spectacular` change de forme, tout
      champ portant le nom d'un champ protégé sort de `required`, dans tous les composants.
      Plus de champs optionnels que nécessaire est un type moins précis ; moins de champs
      optionnels serait un type qui ment. La direction de l'erreur est choisie.
    """
    if not CHAMPS_PROTEGES:
        return result

    composants = (result.get("components") or {}).get("schemas") or {}
    if not composants:
        return result

    par_modele = _composants_par_modele(generator)
    if par_modele is None:  # pragma: no cover — drf-spectacular a changé de forme
        warnings.warn(
            "drf-spectacular n'expose plus `registry._components` : le post-traitement "
            "de PERM-06 retombe sur un filtrage par nom de champ, plus large. "
            "Corriger plateforme/projection/schema.py.",
            stacklevel=2,
        )
        globalement_proteges = _noms_proteges()

    for nom_composant, schema in composants.items():
        requis = schema.get("required")
        if not requis:
            continue
        if par_modele is None:  # pragma: no cover
            interdits = globalement_proteges
        else:
            modele = par_modele.get(nom_composant)
            if modele is None:
                continue
            interdits = frozenset(codes_proteges_de(modele))

        restant = [nom for nom in requis if nom not in interdits]
        if len(restant) == len(requis):
            continue
        if restant:
            schema["required"] = restant
        else:
            # Un tableau `required` vide est invalide en OpenAPI 3.0 (`minItems: 1`), donc
            # la clé disparaît plutôt que de rester vide.
            schema.pop("required")

    return result

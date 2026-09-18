"""D-4b — l'UNIQUE endroit où vivent les chiffres cliniques de la saisie.

Le propriétaire a déjà changé d'avis une fois sur ces nombres, et sa demande était
explicite : « **les bornes vivent à UN endroit nommé** […] le prochain changement doit
coûter une ligne. » Ce module est cet endroit. Trois consommateurs le lisent et **aucun
ne recopie une valeur** :

| Consommateur | Ce qu'il en fait |
|---|---|
| `domaine/ordonnances/models.py` | des `CheckConstraint` dérivées — la garantie |
| le sérialiseur d'ordonnance (plan 04-05) | un 400 lisible au comptoir |
| `plateforme/comptes/serializers.py` | la charge d'amorçage, donc la saisie du SPA |

**Pourquoi les bornes sont écrites deux fois côté serveur, et pourquoi ce n'est pas une
duplication.** Le sérialiseur donne un message lisible ; la contrainte donne la garantie.
Un `clean()` est contourné par `bulk_create`, par `queryset.update()`, par un `RunPython`
de migration et par le shell — c'est l'argument littéral que
`plateforme/control_plane/models.py` a déjà écrit pour `active_client_has_db_name`. Les
deux chemins lisent `BORNES`, donc ce qui est dupliqué est le **lieu d'application**,
jamais la **valeur**.

**Et la garde qui tient cette promesse est dans `tests/test_optique.py`** :
`test_client07_les_bornes_vivent_a_un_seul_endroit` lit l'AST des modules de cette
application et refuse tout littéral numérique qui recopie une valeur ci-dessous. Elle lit
des nœuds, pas du texte — donc la table de provenance de cette docstring, qui cite tous
les nombres, n'est pas attrapée.

---

## D'où vient chaque chiffre

| Champ | Borne | Source |
|---|---|---|
| Sphère | −20,00 .. +20,00 | `.planning/research/PITFALLS.md:449`, recherche antérieure du projet. **Ce module écrase explicitement le ±30 de `04-CONTEXT.md` zone grise 1**, qui n'avait aucune source. Au-delà de ±20 c'est du domaine spécialisé ; au comptoir, un −24 est bien plus souvent une faute de frappe qu'un patient. Ni l'un ni l'autre chiffre n'est normatif : les deux sont des jugements, et `04-RESEARCH.md` §6.3 le dit franchement |
| Cylindre | −10,00 .. 0 | inchangé depuis la zone grise 1, non contesté. La borne haute **est** la règle de signe : un cylindre positif est hors bornes, donc refusé par la même contrainte |
| Axe | **1 .. 180** | `04-RESEARCH.md` §6.2, schéma TABO. L'axe s'écrit 1–180 ; 180 s'emploie là où 0 serait. **CLIENT-07 dit littéralement « 0–180 »** : on **accepte** 0 à la saisie et `canonicaliser_axe` le ramène à 180, donc l'exigence est servie à la lettre et le stockage n'admet qu'un seul encodage par axe |
| Addition | +0,75 .. +4,00 | `.planning/research/PITFALLS.md:449`. Le plancher à +0,50 de la zone grise 1 admettait une valeur qui ne se prescrit pratiquement pas |
| EP binoculaire | 45,0 .. 85,0 | **`04-UI-SPEC.md` §16.2, JUGEMENT SANS SOURCE**, marqué comme tel par l'UI-SPEC elle-même et resté question ouverte §28-Q4 |
| EP monoculaire | 18,0 .. 44,5 | **idem — jugement sans source.** La question part à un opticien marocain avec les quatre questions de facturation : *à partir de quel écart un nombre saisi comme binoculaire est-il certainement monoculaire ?* |

**Les deux dernières lignes sont d'une nature différente des quatre premières**, et le
mélange serait dangereux s'il n'était pas écrit : quatre bornes reposent sur une source
citée, deux sur un jugement. C'est aussi pourquoi le discriminant monoculaire/binoculaire
de 45 mm est un **avertissement** et non un refus (décision Q4 du propriétaire,
2026-09-18) : un refus fondé sur un nombre deviné bloque une saisie légitime au comptoir,
et le coût d'un faux refus est un opticien qui ne peut pas enregistrer une ordonnance
réelle, là où le coût d'un faux avertissement est une phrase à lire.

---

## La forme des valeurs, et pourquoi elles sont des chaînes

Les décimaux sont des **chaînes**, pas des flottants ni des `Decimal`. Trois raisons, dans
l'ordre de gravité :

1. Un flottant dans ce dictionnaire produirait `20.0` dans le contrat OpenAPI, donc une
   comparaison flottante côté client, donc un refus de `−0,25` un jour où la somme
   binaire tombe à côté de la grille.
2. JSON n'a pas de type décimal : la valeur doit de toute façon traverser le fil en
   chaîne, et convertir ici puis re-sérialiser là-bas ajoute un aller-retour où la
   précision peut se perdre.
3. `Decimal("0.25")` ne se sérialise pas tout seul en JSON, et le contournement habituel
   — `float(...)` — est exactement la faute n° 1.

L'axe est un **entier** parce qu'un degré est un entier : son pas vaut un degré, et la
contrainte de pas n'existe donc pas pour lui (voir `BORNES_ENTIERES` ci-dessous).
"""

from __future__ import annotations

#: Les bornes de saisie d'une ordonnance. **Ne pas recopier une de ces valeurs ailleurs.**
#:
#: `signe_obligatoire` et `convention` ne sont pas des bornes : ce sont les deux phrases
#: que l'interface doit afficher à côté du champ (`04-UI-SPEC.md` §16.2). Elles voyagent
#: avec les nombres parce qu'une convention affichée ailleurs que la valeur qu'elle
#: gouverne finit par la contredire.
BORNES: dict[str, dict[str, object]] = {
    "sphere": {
        "min": "-20.00",
        "max": "20.00",
        "pas": "0.25",
        "signe_obligatoire": True,
    },
    "cylindre": {
        "min": "-10.00",
        "max": "0.00",
        "pas": "0.25",
        "convention": "negatif",
    },
    "axe": {"min": 1, "max": 180, "pas": 1},
    "addition": {"min": "0.75", "max": "4.00", "pas": "0.25"},
    "ep_binoculaire": {"min": "45.0", "max": "85.0", "pas": "0.5"},
    "ep_monoculaire": {"min": "18.0", "max": "44.5", "pas": "0.5"},
}

#: Les bornes portées par une colonne **entière**. Leur pas vaut une unité de la colonne,
#: donc une contrainte de pas y serait toujours vraie — l'écrire donnerait une garantie
#: apparente et vide, ce qui est pire qu'aucune.
#:
#: Nommé plutôt que testé par `pas == 1` : ce littéral-là serait précisément la recopie
#: que la garde de `tests/test_optique.py` refuse.
BORNES_ENTIERES: frozenset[str] = frozenset({"axe"})

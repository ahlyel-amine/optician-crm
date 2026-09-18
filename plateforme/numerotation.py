"""Le numéro suivant d'une série émise par le serveur. CLAUDE.md #3.

**Deux lignes de code, et deux raisons d'exister — la seconde n'est pas celle qu'on
devine.**

## 1. La phase 6 réutilisera ce module, et l'écrire deux fois serait la dette

Le numéro de version d'une ordonnance et le numéro de facture sont le **même mécanisme**
sur deux enjeux très différents. Un trou dans les versions d'une ordonnance est une gêne ;
un trou dans la série des factures est traitable comme une fraude (art. 145 CGI), et c'est
l'exposition fiscale du client causée par notre logiciel. Ce qu'ils partagent :

* le numéro est **émis par le serveur**, jamais proposé par un client ;
* il vient du **maximum existant plus un pas**, lu sous un verrou `FOR UPDATE` posé sur
  une ligne, **dans la transaction d'insertion** ;
* il ne vient **jamais** d'une `SEQUENCE` PostgreSQL, qui ne revient pas en arrière à
  l'annulation et produit donc des trous.

Le **verrou** reste chez l'appelant, et délibérément : la ligne à verrouiller n'est pas la
même d'un domaine à l'autre — la fiche client pour une ordonnance, un compteur par série
et par exercice pour une facture — et une abstraction qui prétendrait la choisir à sa place
cacherait précisément la décision qui compte. Ce qui est partagé ici est l'arithmétique,
qui elle ne varie pas.

## 2. Le pas d'une série n'est pas un nombre clinique, et il ne doit pas vivre là-bas

`tests/test_optique.py::test_client07_les_bornes_vivent_a_un_seul_endroit` lit l'AST de
`domaine/ordonnances/{models,serializers,vues,services}.py` et refuse **tout** littéral
numérique dont la magnitude figure dans `BORNES` — ce qui inclut `1`, le minimum de l'axe.
Mesuré, pas supposé : un `maximum + 1` écrit dans `services.py` produit
`['ligne 6 : 1', 'ligne 6 : 1']`.

La garde a raison, et ce n'est pas un faux positif à contourner : elle ne peut pas
distinguer l'incrément d'une série du plancher d'un axe, et l'assouplir pour `1` la
désarmerait sur la borne la plus facile à recopier. La bonne réponse n'est donc pas de
l'affaiblir, c'est de **sortir la constante du paquet clinique** — où elle n'a de toute
façon rien à faire, puisqu'elle ne change pas quand le propriétaire change d'avis sur ce
qu'un opticien peut taper. Même arbitrage qu'`optique.py`, que la garde exclut parce qu'il
porte de la géométrie et non des bornes révisables.
"""

from __future__ import annotations

from typing import Final

#: Le premier numéro d'une série. Les séries de ce produit se lisent par un humain — « la
#: version 2 », « la facture 2026-000 1 » — donc elles commencent à un, pas à zéro.
PREMIER_NUMERO: Final[int] = 1

#: Le pas. Nommé plutôt qu'écrit en clair pour que « la série est dense » soit une
#: propriété qu'on lit, et non une propriété qu'on déduit d'un `+ 1` perdu dans une ligne.
PAS: Final[int] = 1


def numero_suivant(maximum: int | None) -> int:
    """`PREMIER_NUMERO` s'il n'y a rien, sinon `maximum + PAS`.

    L'appelant est responsable des deux choses que cette fonction ne peut pas savoir :
    avoir **verrouillé** la ligne qui sérialise la série, et être **dans la transaction**
    qui insère. Sans elles, deux appels concurrents lisent le même maximum et rendent le
    même numéro — ce que le test `slow` à deux fils de
    `tests/test_ordonnances.py` existe pour attraper, et que `TestCase` seul ne peut pas
    voir.
    """
    return PREMIER_NUMERO if maximum is None else maximum + PAS

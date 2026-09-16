"""Le tri et le filtre comme oracle, fermés par des listes dérivées de la projection.

**Pourquoi ce module existe, en une phrase.** `?ordering=prix_achat` divulgue l'ordre
total d'un champ caché, et `?prix_achat__gt=1500` en récupère une valeur exacte par
dichotomie en une vingtaine de requêtes. **Le champ n'apparaît dans aucune réponse et il
est pourtant entièrement divulgué** (`03-RESEARCH.md` A-03-07).

C'est la classe d'attaque que la projection de champs ne voit pas passer : elle vérifie ce
qui sort, et l'oracle ne demande rien qui sorte. Il demande un **ordre** et un **compte**.

---

## Les trois règles, et chacune est une décision

**1. Les listes autorisées sont dérivées de la projection, jamais écrites à la main.** Une
liste maintenue à part se désynchronise du registre à la première phase qui ajoute une
colonne — et sa désynchronisation est silencieuse dans le mauvais sens : l'allowlist reste
trop large, personne ne s'en aperçoit, et le champ tout juste protégé est triable le jour
même. `champs_interdits(modele, acces)` est donc soustrait de la liste déclarée à chaque
requête, parce que le résultat dépend de l'appelant.

**2. Une valeur non autorisée renvoie 400. Elle n'est jamais ignorée en silence.** C'est le
comportement par défaut de `OrderingFilter`, et il est remplacé ici exprès. **Ignorer en
silence est aussi un oracle** : l'ordre du résultat change selon que le terme a été accepté
ou écarté, donc la réponse répond quand même « ce champ existe ». Un refus discret n'est
pas un refus, c'est un refus lent.

**3. Le message d'erreur ne nomme pas le champ, et il est le même pour tous les refus.** Un
400 dont les *clés* révèlent qu'un champ protégé existe est la même fuite avec une étape de
plus (A-03-13). Mais ne pas nommer le champ ne suffit pas : si un champ protégé produisait
un 400 là où un nom inexistant produit un 200, le **code de statut** serait l'oracle. D'où
la règle plus forte, celle que le test vérifie : **la chaîne de requête est une allowlist,
et tout ce qui n'y figure pas — champ protégé, champ public non déclaré, nom qui n'existe
nulle part — produit exactement la même réponse.** L'indiscernabilité est la garantie ; ne
pas nommer le champ n'en est qu'une conséquence.

Comme le champ est retiré dans `get_fields()` (plan 03-06), il ne peut déjà pas apparaître
dans une erreur de validation de ce sérialiseur. Ce qui reste à faire est de ne pas l'y
réintroduire à la main, ici.

---

## Ce que ces backends ne remplacent pas

Ils filtrent des **colonnes nommées par l'appelant**. La portée des lignes est ailleurs —
`plateforme/projection/vues.py` — et les deux se composent sans se substituer : une
allowlist n'a jamais empêché de lire la ligne d'un autre magasin, et une portée magasin n'a
jamais empêché de trier sur un champ caché.

`django-filter` n'est pas une dépendance du projet et n'est pas ajoutée ici : une
dépendance qui entre dans la pile est une décision de `PROJECT.md`, pas un détail
d'implémentation d'un plan de phase. `ProjectedFieldFilter` couvre ce dont la phase 3 a
besoin — un `dict` de champs et de lookups autorisés — et le jour où un `FilterSet` complet
devient nécessaire, la soustraction de `champs_interdits` se reporte sur
`FilterSet.get_filters` sans que la règle change.
"""

from __future__ import annotations

from rest_framework.exceptions import ValidationError
from rest_framework.filters import BaseFilterBackend, OrderingFilter

from plateforme.projection.registre import champs_interdits
from plateforme.projection.serializers import acces_du_contexte

#: Le message unique de tout refus. **Un seul**, délibérément : c'est ce qui rend le refus
#: d'un champ protégé indiscernable du refus d'un nom inexistant. Un message plus utile
#: serait un message plus bavard, et ici « plus bavard » veut dire « qui répond à
#: l'attaquant ».
MESSAGE_DE_REFUS = (
    "Paramètre de requête non autorisé sur cette ressource. Consultez le schéma OpenAPI "
    "pour les paramètres acceptés."
)

#: Les paramètres qui ne sont pas des filtres et que `ProjectedFieldFilter` laisse passer.
#:
#: Ils sont énumérés plutôt que devinés : un paramètre inconnu doit être **refusé**, pas
#: ignoré, sans quoi l'ensemble des paramètres refusés dessine l'ensemble des champs qui
#: existent. Une phase qui ajoute la pagination ou la recherche ajoute son nom ici, dans le
#: même commit.
PARAMETRES_RESERVES: frozenset[str] = frozenset(
    {"ordering", "format", "page", "page_size", "cursor", "search"}
)


def _refuser():
    """Lever le refus unique. Aucune clé de champ, aucun nom, aucune variante.

    `ValidationError` avec une chaîne nue produit un corps sans **clé** de champ — ce qui
    est le point : un corps `{"valeur_protegee": [...]}` nommerait le champ dans sa
    structure même, là où le lecteur pressé ne regarde que le message.
    """
    raise ValidationError(MESSAGE_DE_REFUS)


def champs_de_tri_autorises(noms, modele, acces) -> list[str]:
    """La liste déclarée, moins ce que cet accès n'a pas le droit de voir.

    Écrite comme une fonction libre et non comme une méthode, pour que le garde de revue
    et un éventuel `FilterSet` de phase ultérieure appellent littéralement le même code.
    Deux soustractions réimplémentées séparément finissent par diverger, et le mode de
    divergence est silencieux du mauvais côté.
    """
    interdits = champs_interdits(modele, acces)
    return [nom for nom in noms if nom not in interdits]


class ProjectedOrderingFilter(OrderingFilter):
    """`OrderingFilter`, moins les champs interdits, et **sans ignorance silencieuse**.

    Les deux crochets remplacés font deux choses distinctes :

    - `get_valid_fields` soustrait `champs_interdits(modele, acces)`. Il couvre les trois
      formes que DRF accepte — une liste explicite, `"__all__"`, et le repli sur les champs
      du sérialiseur. La troisième est déjà projetée par `SerializerProjete`, mais les deux
      premières ne le sont pas du tout, et ce sont celles qu'une vue écrit quand elle veut
      contrôler son tri.
    - `remove_invalid_fields` **lève** au lieu d'écarter. Le nom hérité de DRF est
      désormais un mensonge poli : il ne retire rien, il refuse. Il est conservé parce que
      c'est le crochet que `get_ordering` appelle, et le renommer obligerait à recopier
      `get_ordering` pour rien.
    """

    def get_valid_fields(self, queryset, view, context=None):
        valides = super().get_valid_fields(queryset, view, context or {})
        acces = acces_du_contexte(context or {})
        autorises = set(
            champs_de_tri_autorises(
                [item[0] for item in valides], queryset.model, acces
            )
        )
        return [item for item in valides if item[0] in autorises]

    def remove_invalid_fields(self, queryset, fields, view, request):
        """Tout terme hors liste est un **400**, jamais un terme écarté en silence.

        `pk` est accepté sans figurer dans une allowlist : il n'est le nom d'aucune colonne
        cachée, et DRF le traite déjà comme toujours valide.
        """
        autorises = {
            item[0]
            for item in self.get_valid_fields(queryset, view, {"request": request})
        }
        autorises.add("pk")
        for terme in fields:
            nom = terme[1:] if terme.startswith("-") else terme
            if nom not in autorises:
                _refuser()
        return list(fields)


class ProjectedFieldFilter(BaseFilterBackend):
    """Le filtre par champ : une allowlist par vue, moins ce que la projection interdit.

    La vue déclare `champs_filtrables = {"prix_vente": ["exact", "gt", "lt"], ...}`. Tout
    paramètre de requête qui n'est ni réservé ni dans cette table, **après soustraction de
    `champs_interdits`**, est refusé avec le message unique.

    Refuser plutôt qu'ignorer les paramètres inconnus est la partie qui surprend, et c'est
    la partie qui ferme l'oracle : si `?zzz=1` était ignoré pendant que
    `?prix_achat__gt=1` renvoyait 400, le code de statut dirait à lui seul quels noms de
    colonnes existent. L'ensemble des paramètres acceptés est donc exactement l'ensemble
    déclaré, et rien d'autre ne passe.
    """

    def filter_queryset(self, request, queryset, view):
        table = dict(getattr(view, "champs_filtrables", {}) or {})
        acces = acces_du_contexte({"request": request})
        for nom in champs_interdits(queryset.model, acces):
            table.pop(nom, None)

        conditions = {}
        for parametre, valeur in request.query_params.items():
            if parametre in PARAMETRES_RESERVES:
                continue
            nom, _, lookup = parametre.partition("__")
            lookup = lookup or "exact"
            if nom not in table or lookup not in table[nom]:
                _refuser()
            conditions[f"{nom}__{lookup}"] = valeur

        if not conditions:
            return queryset
        try:
            return queryset.filter(**conditions)
        except (ValueError, TypeError):
            # Une valeur mal typée — `?prix_vente__gt=abc`. Le même refus que tout le
            # reste : « la valeur n'est pas un nombre » est une réponse utile à un
            # développeur et une réponse utile à un attaquant, et ici la seconde coûte
            # plus cher que la première ne rapporte.
            _refuser()

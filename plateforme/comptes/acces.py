"""L'accès résolu : la couture que tout le reste du code lit.

**C'est la seule fonction du dépôt qui lise encore `utilisateur.client` ou
`utilisateur.droits`.** Partout ailleurs on lit `request.acces`, ou l'`Acces` qu'une tâche
Celery ou une commande de gestion a résolu elle-même. Ce n'est pas une préférence de style :
c'est ce qui rend réversible le choix « clé étrangère contre table d'appartenance » du plan
03-01, et ce qui permet à un rendu PDF hors requête HTTP de piloter exactement la même
projection que l'API.

Deux propriétés portent tout le reste de la phase, et les deux sont testées.

1. **Fail-closed.** Un accès absent vaut l'ensemble vide, jamais « autoriser ». C'est
   CLAUDE.md #8 appliqué à la couche de permissions : le contexte de locataire échoue fermé,
   l'accès aussi. Le défaut à mettre partout est `Acces.ANONYME` — une **valeur** — et jamais
   `None`, parce que `getattr(request, "acces", None)` suivi de « si None, tout montrer » est
   le fail-open que `03-RESEARCH.md` P2 décrit (menace T-03-22).

2. **Un seul chemin de code.** L'accès du propriétaire est **matérialisé** : le catalogue
   complet, pour chacun de ses magasins actifs, écrit dans la table comme celui d'un gérant.
   Délibérément, pour que `peut()` n'ait aucune branche `if est_proprietaire`. Une branche
   qui saute la vérification pour les propriétaires est une branche qu'un bug peut atteindre
   pour un non-propriétaire (`03-RESEARCH.md` P3, menace T-03-23). La branche existe ici,
   une fois, à la résolution — pas à chacun des centaines de sites d'appel des phases 5 à 10.

**La divergence assumée avec `03-RESEARCH.md` §4.** La recherche propose un unique
`permissions: frozenset[str]`. C'est la forme sans dimension magasin que CLAUDE.md #13
interdit, et son propre bandeau de correction l'abandonne. L'unité de stockage étant
`(gérant, magasin, permission)`, l'unité de résolution l'est aussi :
`droits_par_magasin: Mapping[int, frozenset[str]]`.

**La règle que les phases 5 à 10 doivent connaître avant d'appeler `peut`.** Sans argument
magasin, `peut(code)` est une **conjonction** : vrai seulement si le code est détenu dans
*tous* les magasins accordés. Pas « détenu quelque part ». La raison est que la projection de
champs s'applique à un **serializer**, pas à une ligne : au moment où elle décide de garder
ou d'ôter `prix_achat`, elle ne sait pas encore de quel magasin sera la ligne rendue.
N'autoriser que ce qui est vrai partout évite de livrer le prix d'achat du magasin A à un
gérant qui ne le détient que dans B (menace T-03-25). L'union existe — `peut_quelque_part` —
et elle n'est jamais une autorisation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from plateforme.comptes.permissions_catalogue import Permission

#: L'ensemble vide, partagé. Éviter d'en construire un par appel de `peut` sur un magasin
#: inconnu est accessoire ; ce qui compte est qu'il n'existe **aucune** valeur de repli
#: autre que « rien ».
_AUCUN_DROIT: frozenset[str] = frozenset()

#: La table vide, partagée et immuable.
_AUCUNE_TABLE: Mapping[int, frozenset[str]] = MappingProxyType({})

#: Le magasin fictif sous lequel `Acces.SCHEMA` porte le catalogue complet.
#:
#: Le générateur OpenAPI (plan 03-06) doit voir **tous** les champs projetables, sans
#: appartenir à aucune affaire ni à aucun magasin. Deux façons de l'exprimer : un
#: court-circuit `if pour_le_schema` dans `peut`, ou une clé qui n'existe pas. La première
#: rouvre le second chemin de code que ce module existe pour fermer — le test du
#: propriétaire refuse d'ailleurs `pour_le_schema` dans le corps de `peut` au même titre que
#: `est_proprietaire`. C'est donc une clé, et négative : les identifiants de `Magasin`
#: viennent d'une séquence Postgres, qui n'en produit jamais. `magasins_ids` reste vide, donc
#: la portée des lignes (plan 03-07) ne rend rien — c'est `pour_le_schema` qui court-circuite
#: la portée, à l'endroit où elle est écrite, et pas ici.
MAGASIN_DU_SCHEMA: int = -1


@dataclass(frozen=True, slots=True)
class Acces:
    """Ce qu'un principal peut faire, magasin par magasin. Immuable, résolu, sans surprise.

    `droits_par_magasin` porte une entrée **par magasin accordé et actif**, y compris quand
    l'ensemble de codes associé est vide : c'est ce qui donne un sens à la conjonction de
    `peut`. Un gérant qui a accès à Anfa et Maârif mais n'y détient aucun droit a donc deux
    clés et deux ensembles vides, et non une table vide.
    """

    utilisateur_id: int | None
    client_id: int | None
    est_proprietaire: bool
    droits_par_magasin: Mapping[int, frozenset[str]] = field(default=_AUCUNE_TABLE)
    magasins_ids: frozenset[int] = field(default=_AUCUN_DROIT)  # type: ignore[assignment]
    pour_le_schema: bool = False

    # -- les trois accesseurs, et leur séparation est le cœur de la conception -----------

    def peut(self, code: str, magasin_id: int | None = None) -> bool:
        """L'autorisation. La seule des trois qui en soit une.

        Avec un magasin : le code doit être dans l'ensemble de **ce** magasin.

        Sans magasin : le code doit être dans l'ensemble de **tous** les magasins accordés —
        une conjonction, pas une union. Voir la docstring du module pour la raison ; la forme
        courte est que la projection de champs s'applique à un serializer et non à une ligne,
        donc « autorisé quelque part » y devient « montré partout ».

        Sur une table vide — accès anonyme, opérateur sans affaire, gérant sans aucun magasin
        actif — la réponse est `False`. Un `all()` sur une collection vide vaut `True`, ce qui
        est exactement le fail-open à ne pas écrire ; d'où le `bool(portee)` explicite.
        """
        if magasin_id is not None:
            return code in self.droits_par_magasin.get(magasin_id, _AUCUN_DROIT)

        portee = self.droits_par_magasin
        return bool(portee) and all(code in codes for codes in portee.values())

    def peut_quelque_part(self, code: str) -> bool:
        """L'union : vrai si le code est détenu dans **au moins un** magasin.

        **Ce n'est jamais une autorisation.** Elle répond « quelque part », et « quelque
        part » ne dit pas *ici*. Deux usages, exactement deux, tous deux au sujet de ce qu'on
        *propose* à l'écran et non de ce qu'on *sert* :

        1. conditionner une entrée de navigation (`/api/auth/moi/`, plan 03-08) ;
        2. construire le catalogue pré-intersecté servi à un gérant-gestionnaire (plan 03-09).

        Une docstring ne garde rien. `tests/test_magasin_acces.py` énumère les appelants de
        cette méthode dans `plateforme/` et exige que chacun porte l'une des deux étiquettes
        sanctionnées — un troisième appelant rougit la suite plutôt que d'autoriser trop,
        discrètement, sans que personne ouvre de ticket.
        """
        return any(code in codes for codes in self.droits_par_magasin.values())

    def magasins_pour(self, code: str) -> frozenset[int]:
        """Les identifiants de magasins où le code est détenu.

        Ce que le plan 03-09 interroge pour répondre « uniforme » ou « personnalisé » à
        l'interface (`03-UI-SPEC.md` 7.5) : une ligne est uniforme quand ce résultat vaut
        `magasins_ids`, et c'est l'état que la quasi-totalité des entreprises verra.
        """
        return frozenset(
            magasin_id
            for magasin_id, codes in self.droits_par_magasin.items()
            if code in codes
        )


#: L'accès de personne : aucun droit, aucun magasin, aucune affaire.
#:
#: C'est la valeur de repli à écrire partout où un `Acces` pourrait manquer. `ANONYME`
#: plutôt que `None` est tout l'argument de la menace T-03-22 : `None` invite au `if acces
#: is None: tout montrer`, une constante vide ne laisse rien à décider.
Acces.ANONYME = Acces(
    utilisateur_id=None,
    client_id=None,
    est_proprietaire=False,
    droits_par_magasin=_AUCUNE_TABLE,
    magasins_ids=frozenset(),
)

#: L'accès du générateur OpenAPI (plan 03-06) : le catalogue complet, aucun magasin réel.
#:
#: Un schéma dont les champs varieraient selon le lecteur ne serait pas un contrat. Le
#: générateur voit donc tout, sous `MAGASIN_DU_SCHEMA`, et `pour_le_schema` dit à la portée
#: des lignes (plan 03-07) de ne pas s'appliquer. À ne consommer nulle part ailleurs : c'est
#: un accès total, et il ne doit jamais atteindre une requête.
Acces.SCHEMA = Acces(
    utilisateur_id=None,
    client_id=None,
    est_proprietaire=False,
    droits_par_magasin=MappingProxyType(
        {MAGASIN_DU_SCHEMA: frozenset(Permission.values)}
    ),
    magasins_ids=frozenset(),
    pour_le_schema=True,
)


def acces_pour(utilisateur) -> Acces:
    """Résoudre l'accès d'un principal. Une fois par requête, et sans aucun cache.

    Aucun cache, délibérément : `03-UI-SPEC.md` 7.8 affiche en toutes lettres qu'une
    révocation prend effet sans reconnexion, et cette phrase n'est vraie que si les lignes
    sont relues. Un `lru_cache` ici, ou un `Acces` posé en session, rendrait la promesse
    fausse sans rien casser de visible (`test_perm03_la_revocation_prend_effet_sans_reconnexion`).

    Deux bases sont lues : les octrois vivent dans le plan de contrôle (`default`), les
    magasins dans la base de l'opticien. **L'alias du client doit donc être lié** — c'est
    pourquoi `AccesMiddleware` passe strictement après `TenantMiddleware`.
    """
    # Trois conditions, une seule sortie. Un utilisateur absent, un utilisateur non
    # authentifié, et un opérateur de plateforme — qui n'appartient à aucune affaire et n'a
    # donc aucun accès métier, par conception (menace T-03-28).
    if utilisateur is None or not getattr(utilisateur, "is_authenticated", False):
        return Acces.ANONYME
    if getattr(utilisateur, "client_id", None) is None:
        return Acces.ANONYME

    # Importé ici, pas au niveau du module : `plateforme/` ne dépend pas de `domaine/` à
    # l'import, et une résolution est de toute façon le seul moment où le magasin compte.
    from domaine.magasins.models import Magasin

    est_proprietaire = bool(utilisateur.est_proprietaire)

    # `magasin_code` est une **valeur**, jamais une clé étrangère : `TenantRouter`
    # interdit une relation entre le plan de contrôle et la base client. L'accès effectif
    # est donc une intersection avec les magasins **vivants et actifs**, recalculée à
    # chaque résolution. Un octroi nommant un magasin désactivé ne résout vers rien — et
    # comme les magasins se désactivent sans jamais se supprimer, ce cas est normal, pas
    # exceptionnel (menace T-03-24).
    if est_proprietaire:
        magasins = Magasin.objects.filter(actif=True)
    else:
        codes_accordes = list(
            utilisateur.acces_magasins.values_list("magasin_code", flat=True)
        )
        magasins = Magasin.objects.filter(actif=True, code__in=codes_accordes)
    identifiant_par_code = {
        code: identifiant for identifiant, code in magasins.values_list("pk", "code")
    }

    if est_proprietaire:
        # **Matérialisé**, pas court-circuité. La branche est ici, une fois ; `peut` n'en a
        # aucune. C'est la seule différence entre un propriétaire et un gérant à qui tout
        # aurait été accordé à la main, et c'est voulu : il n'y a qu'un chemin de code à
        # tester, et la phase 8 ne peut pas y brancher un agrégat non filtré par mégarde.
        catalogue = frozenset(Permission.values)
        table = {identifiant: catalogue for identifiant in identifiant_par_code.values()}
    else:
        # Une entrée par magasin accordé et actif, **même vide** : c'est ce qui rend la
        # conjonction de `peut` bien définie. Sans cela, un gérant à qui l'on accorde un
        # second magasin sans y poser aucun droit verrait ses droits du premier devenir
        # subitement universels.
        accumulateur: dict[int, set[str]] = {
            identifiant: set() for identifiant in identifiant_par_code.values()
        }
        droits = utilisateur.droits.filter(
            magasin_code__in=list(identifiant_par_code)
        ).values_list("magasin_code", "code")
        for magasin_code, code in droits:
            accumulateur[identifiant_par_code[magasin_code]].add(code)
        table = {
            identifiant: frozenset(codes) for identifiant, codes in accumulateur.items()
        }

    return Acces(
        utilisateur_id=utilisateur.pk,
        client_id=utilisateur.client_id,
        est_proprietaire=est_proprietaire,
        droits_par_magasin=MappingProxyType(table),
        magasins_ids=frozenset(identifiant_par_code.values()),
    )


class _PorteurAcces:
    """Un faux « request » de cinq lignes, pour piloter la projection sans requête HTTP.

    Une tâche Celery qui rend un PDF, ou une commande de gestion qui exporte un CSV, doit
    projeter exactement ce que l'API projetterait — sinon la garantie PERM-06 tient sur trois
    rendus et se perd sur le quatrième. Les consommateurs de la projection (plan 03-06)
    n'ont besoin que de `.acces` et de `.user` ; leur en donner davantage inviterait à lire
    autre chose.

    Le nom est privé par intention : on ne fabrique pas ceci dans une vue.
    """

    __slots__ = ("acces", "user")

    def __init__(self, utilisateur=None, acces: Acces | None = None):
        self.user = utilisateur
        self.acces = acces if acces is not None else acces_pour(utilisateur)

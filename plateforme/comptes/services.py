"""Les services de la gestion des comptes et des droits. PERM-02 et PERM-03.

**La logique vit ici et non dans la vue**, et ce n'est pas une préférence d'architecture :
une commande de gestion d'onboarding (TENANT-06) et l'inscription en libre service de la
phase 12 devront créer un compte et poser des droits **sans requête HTTP**. Une règle
écrite dans une vue est une règle qui n'existe que pour les appelants qui passent par
cette vue, et la fermeture des prérequis est exactement le genre de règle qu'un second
appelant réimplémente de travers.

Trois invariants portent ce module, et chacun a son test nommé.

1. **Un octroi écrit une ligne par magasin accordé** — CLAUDE.md #13. C'est ce qui rend
   l'interface uniforme par défaut tout en gardant le stockage à la granularité
   `(gérant, magasin, permission)`. Une révocation les supprime toutes.
2. **La fermeture des prérequis est appliquée ici, pas dans l'interface.**
   `03-UI-SPEC.md` 7.6 l'écrit en toutes lettres : « la note de l'interface est une
   explication, pas la règle ». Un appel direct à l'API obtient donc exactement le
   résultat d'une bascule d'interrupteur (menace T-03-61).
3. **On ne donne que ce qu'on détient.** L'appelant ne peut accorder ni un code ni un
   magasin qui sortent de son propre `Acces` (menaces T-03-58, T-03-59).

**Ce que ce module lit, et pourquoi ce n'est pas une entorse à `acces.py`.** La docstring
de `plateforme/comptes/acces.py` réserve à `acces_pour` la lecture de `utilisateur.droits`
et de `utilisateur.client`. Elle parle de la **résolution** : rien d'autre ne doit
répondre à « que peut ce compte ». Ce module-ci est le **rédacteur** des mêmes tables, et
un rédacteur doit lire l'état avant d'écrire le delta. La frontière tenue est donc
précise : l'autorité de l'appelant vient toujours d'un `Acces`, jamais d'une relecture des
lignes ; l'état de la cible vient des gestionnaires de modèle `AccesMagasin.objects` et
`DroitAccorde.objects`, jamais des accesseurs inverses.

**Les magasins sont désignés par leur code**, comme dans les tables d'octroi, et
convertis en identifiants uniquement pour interroger l'`Acces` de l'appelant — qui, lui,
est indexé par identifiant (plan 03-05). La conversion passe par la table `Magasin` de la
base de l'opticien, donc ce module exige un locataire lié.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from plateforme.comptes.acces import acces_pour

#: L'alphabet du mot de passe provisoire. `I`, `l`, `1`, `O` et `0` en sont absents : il
#: est dicté de vive voix ou recopié depuis un écran (il n'y a pas de chemin par courriel,
#: plan 03-08), donc une ambiguïté typographique se paie en appel au support.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"

#: Quatorze caractères de `_ALPHABET`, soit ~80 bits. Au-dessus du minimum de dix de
#: `AUTH_PASSWORD_VALIDATORS`, et hors d'atteinte de `CommonPasswordValidator` par
#: construction — un tirage uniforme ne produit pas un mot de passe de liste.
_LONGUEUR_PROVISOIRE = 14


def mot_de_passe_provisoire() -> str:
    """Un mot de passe provisoire, tiré par `secrets` et montré **une seule fois**.

    `secrets` et non `random` : ce dernier est un Mersenne Twister dont l'état se
    reconstruit à partir de quelques sorties, ce qui est sans conséquence pour un jeu de
    dés et fatal pour un secret d'authentification.
    """
    return "".join(secrets.choice(_ALPHABET) for _ in range(_LONGUEUR_PROVISOIRE))


# ======================================================================================
# Lire l'état — ce que la liste de comptes affiche, et ce que l'octroi renvoie
# ======================================================================================


def magasins_actifs_par_id() -> dict[int, object]:
    """`{pk: Magasin}` pour les magasins **actifs** de l'affaire liée.

    Importé dans le corps de la fonction : `plateforme/` ne dépend pas de `domaine/` à
    l'import, et un magasin n'a de sens qu'une fois le locataire lié.
    """
    from domaine.magasins.models import Magasin

    return {magasin.pk: magasin for magasin in Magasin.objects.filter(actif=True)}


def magasins_actifs_par_code() -> dict[str, int]:
    """`{code: pk}` pour les magasins actifs. L'unité de conversion des deux mondes.

    Les octrois nomment un **code** — une valeur qui survit à un `pg_restore` (TENANT-09,
    plan 03-04) — et l'`Acces` est indexé par **identifiant**. Un octroi visant un code
    qui ne figure pas ici désigne un magasin supprimé ou désactivé : il ne résout vers
    rien, exactement comme dans `acces_pour` (menace T-03-24).
    """
    from domaine.magasins.models import Magasin

    return dict(Magasin.objects.filter(actif=True).values_list("code", "pk"))


@dataclass(frozen=True, slots=True)
class ResumeDesDroits:
    """Ce que la ligne de la liste des comptes affiche (`03-UI-SPEC.md` 7.2).

    `personnalise` est calculé **côté serveur** parce que l'interface ne doit pas avoir à
    recomposer l'uniformité depuis N requêtes : à trois magasins et vingt-et-un codes, le
    badge « Personnalisé par magasin » coûterait soixante-trois lectures par ligne de
    tableau.
    """

    magasins_ids: tuple[int, ...] = ()
    nombre_de_droits: int = 0
    personnalise: bool = False


def resume_des_droits(utilisateur) -> ResumeDesDroits:
    """Le résumé d'un compte, calculé **depuis `acces_pour`** et non depuis les lignes.

    Passer par la résolution plutôt que par un comptage direct de `DroitAccorde` a un
    effet précis : la liste ne peut pas afficher autre chose que ce que le compte obtient
    réellement. Un octroi visant un magasin désactivé, ou l'accès complet matérialisé du
    propriétaire, sont traités par le même chemin que la requête de ce compte — donc il
    n'y a pas de seconde vérité à maintenir, et pas de branche `if est_proprietaire` ici.

    Le prix est une résolution par ligne de tableau. Assumé : une affaire compte une
    poignée de comptes, et l'alternative — une agrégation SQL — réintroduirait la branche
    du propriétaire que le plan 03-05 a supprimée.
    """
    acces = acces_pour(utilisateur)
    table = acces.droits_par_magasin
    if not table:
        return ResumeDesDroits()

    codes = set().union(*table.values())
    total = len(table)
    personnalise = any(0 < len(acces.magasins_pour(code)) < total for code in codes)
    return ResumeDesDroits(
        magasins_ids=tuple(sorted(table)),
        nombre_de_droits=len(codes),
        personnalise=personnalise,
    )



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
from dataclasses import dataclass, field

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from plateforme.comptes.acces import Acces, acces_pour
from plateforme.comptes.models import AccesMagasin, DroitAccorde, JournalDroit
from plateforme.comptes.permissions_catalogue import (
    Permission,
    dependants,
    fermeture_prerequis,
)

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


# ======================================================================================
# Écrire l'état — octroi, révocation, uniformisation
# ======================================================================================
#
# La forme de la réponse est un contrat, et le plan 03-14 construit l'interface contre
# elle. Elle porte **de quoi reconstruire la ligne** — uniforme, mixte ou éteinte — pour
# chaque code touché, cascade comprise, sans quoi l'interface devrait recharger toute la
# page après chaque bascule (`03-UI-SPEC.md` 7.8 : sauvegarde par interrupteur, immédiate).


#: Les trois états d'une ligne de l'écran de droits (`03-UI-SPEC.md` 7.5). `mixte` est ce
#: que l'interface rend en tri-état, avec `aria-checked="mixed"`.
ETAT_ACTIF = "actif"
ETAT_INACTIF = "inactif"
ETAT_MIXTE = "mixte"


@dataclass(frozen=True, slots=True)
class LigneDeDroit:
    """L'état d'un code pour une cible : sa valeur, et où elle vaut."""

    code: str
    etat: str
    magasins: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Resultat:
    """Ce qu'une bascule renvoie. Le contrat de l'écran de droits.

    `lignes` porte le code demandé **en tête**, suivi des codes emportés par la cascade,
    chacun avec son état reconstruit. `cascade` ne répète que les codes emportés, parce
    que l'interface en fait deux choses distinctes : elle affiche une note en ligne
    (« Consulter le stock a été activé automatiquement ») et elle couvre l'ensemble d'un
    **seul** toast d'annulation (`03-UI-SPEC.md` 7.6).
    """

    code: str
    action: str
    lignes: tuple[LigneDeDroit, ...] = ()
    cascade: tuple[str, ...] = ()
    magasins_accordes: tuple[str, ...] = ()
    magasins_etendus: tuple[str, ...] = field(default=())


def magasins_accordes(cible) -> list[str]:
    """Les codes de magasins accordés à `cible` **et actifs**, triés.

    L'intersection avec les magasins actifs est la même que celle d'`acces_pour` et pour
    la même raison : un `AccesMagasin` nommant un magasin désactivé n'accorde rien, donc
    étendre un droit uniforme jusqu'à lui écrirait une ligne morte.
    """
    vivants = magasins_actifs_par_code()
    codes = AccesMagasin.objects.filter(utilisateur=cible).values_list(
        "magasin_code", flat=True
    )
    return sorted(code for code in codes if code in vivants)


def _detenus(cible, code: str) -> set[str]:
    """Les codes de magasins où `cible` détient `code`, restreints aux magasins vivants."""
    vivants = set(magasins_actifs_par_code())
    return {
        magasin
        for magasin in DroitAccorde.objects.filter(
            utilisateur=cible, code=code
        ).values_list("magasin_code", flat=True)
        if magasin in vivants
    }


def ligne_de(cible, code: str, accordes: list[str] | None = None) -> LigneDeDroit:
    """L'état d'un code pour une cible : `actif`, `inactif` ou `mixte`.

    « Uniforme » au sens de `03-UI-SPEC.md` 7.5 veut dire que **tous les magasins
    accordés sont d'accord** — donc `actif` et `inactif` sont tous deux uniformes, et
    `mixte` est l'unique état personnalisé.
    """
    accordes = magasins_accordes(cible) if accordes is None else accordes
    detenus = _detenus(cible, code)
    if not detenus:
        etat = ETAT_INACTIF
    elif detenus >= set(accordes) and accordes:
        etat = ETAT_ACTIF
    else:
        etat = ETAT_MIXTE
    return LigneDeDroit(code=str(code), etat=etat, magasins=tuple(sorted(detenus)))


# --------------------------------------------------------------------------------------
# Les refus — l'appelant ne donne que ce qu'il détient
# --------------------------------------------------------------------------------------


def _verifier_la_cible(cible, acces_appelant: Acces) -> None:
    """La cible appartient à l'affaire de l'appelant, et n'est ni lui ni le propriétaire.

    Les octrois vivent dans le plan de contrôle, donc **tous les gérants de la flotte
    partagent une table** et rien dans le schéma n'empêche une ligne visant le compte
    d'une autre affaire : c'est une clé étrangère parfaitement valide (menace T-03-59).
    La garantie est applicative, elle est ici, et elle est testée.

    Les deux autres refus viennent de `03-UI-SPEC.md` 7.7 : les droits du propriétaire ne
    se modifient pas — ils sont matérialisés à la résolution, pas stockés — et personne
    ne modifie ses propres droits, ce qui ferme l'auto-promotion d'un
    gérant-gestionnaire par la porte de service.
    """
    if acces_appelant.client_id is None or cible.client_id != acces_appelant.client_id:
        raise PermissionDenied(
            "Ce compte n'appartient pas à votre affaire."
        )
    if cible.est_proprietaire:
        raise PermissionDenied(
            "Les droits du propriétaire ne se modifient pas : il a accès à toute "
            "l'affaire."
        )
    if cible.pk == acces_appelant.utilisateur_id:
        raise PermissionDenied(
            "Un compte ne modifie pas ses propres droits. Demandez au propriétaire."
        )


def _verifier_le_pouvoir(
    acces_appelant: Acces, code: str, magasins: list[str], par_code: dict[str, int]
) -> None:
    """L'appelant détient-il `code` dans **chacun** des magasins visés ?

    Un gérant-gestionnaire qui ne détient pas `article.voir_prix_achat` ne peut pas
    l'accorder ; un gérant-gestionnaire d'Anfa ne peut rien accorder à Maârif. Le refus
    porte sur `peut(code, magasin_id)` — la question précise — et jamais sur
    `peut_quelque_part`, qui répond « quelque part » et n'autorise rien.
    """
    for magasin in magasins:
        identifiant = par_code.get(magasin)
        if identifiant is None or identifiant not in acces_appelant.magasins_ids:
            raise PermissionDenied(
                f"Vous n'avez pas accès au magasin « {magasin} », donc vous ne pouvez "
                f"pas y accorder de droit."
            )
        if not acces_appelant.peut(code, magasin_id=identifiant):
            raise PermissionDenied(
                "Vous ne pouvez accorder qu'un droit que vous détenez vous-même."
            )


def _magasins_vises(cible, magasins, accordes: list[str]) -> list[str]:
    """Les magasins d'une bascule : ceux demandés, ou **tous les accordés** par défaut.

    Le défaut est ce qui produit le comportement uniforme de `03-UI-SPEC.md` 7.5 —
    allumer un interrupteur écrit une ligne par magasin accordé — et c'est l'état que la
    quasi-totalité des affaires verra.
    """
    if magasins is None:
        return list(accordes)
    vises = [str(magasin) for magasin in magasins]
    inconnus = sorted(set(vises) - set(accordes))
    if inconnus:
        raise ValidationError(
            {
                "magasins": (
                    f"Ce compte n'a pas accès à : {', '.join(inconnus)}. Un droit sans "
                    f"accès au magasin n'accorde rien ; accordez l'accès au magasin "
                    f"d'abord."
                )
            }
        )
    return vises


def _journaliser(cible, action: str, cible_du_journal: str, par) -> None:
    JournalDroit.objects.create(
        utilisateur=cible, action=action, cible=str(cible_du_journal), par=par
    )


# --------------------------------------------------------------------------------------
# Les cinq opérations
# --------------------------------------------------------------------------------------


@transaction.atomic(using="default")
def accorder(cible, code, magasins=None, *, par) -> Resultat:
    """Accorder `code` à `cible`, une ligne par magasin visé, prérequis compris.

    `transaction.atomic` explicite, jamais `ATOMIC_REQUESTS` : CLAUDE.md #15 interdit le
    réglage, qui ouvrirait une transaction par alias enregistré et par requête.

    La cascade est appliquée **ici**. `fermeture_prerequis` remonte transitivement, donc
    accorder `vente.voir_marge` accorde aussi `article.voir_prix_achat` ; et l'appelant
    doit détenir **chaque** code de la fermeture, sans quoi la cascade deviendrait le
    moyen d'accorder indirectement ce qu'un refus direct interdit.
    """
    acces_appelant = acces_pour(par)
    _verifier_la_cible(cible, acces_appelant)

    code = str(code)
    accordes = magasins_accordes(cible)
    vises = _magasins_vises(cible, magasins, accordes)
    par_code = magasins_actifs_par_code()

    # La fermeture d'abord, les refus ensuite : un appelant qui ne détient pas un
    # prérequis doit être refusé, pas servi à moitié.
    ferme = fermeture_prerequis([code])
    for candidat in sorted(ferme):
        _verifier_le_pouvoir(acces_appelant, candidat, vises, par_code)

    cascade: list[str] = []
    for candidat in [code] + sorted(ferme - {code}):
        ajoutes = _poser(cible, candidat, vises, par=par)
        if ajoutes and candidat != code:
            cascade.append(candidat)

    return Resultat(
        code=code,
        action=JournalDroit.Action.ACCORDE,
        lignes=tuple(
            ligne_de(cible, candidat, accordes)
            for candidat in [code] + sorted(ferme - {code})
        ),
        cascade=tuple(cascade),
        magasins_accordes=tuple(accordes),
    )


def _poser(cible, code: str, magasins: list[str], *, par) -> list[str]:
    """Créer les lignes manquantes pour `code`, et journaliser chaque création."""
    existants = set(
        DroitAccorde.objects.filter(
            utilisateur=cible, code=code, magasin_code__in=magasins
        ).values_list("magasin_code", flat=True)
    )
    ajoutes = [magasin for magasin in magasins if magasin not in existants]
    for magasin in ajoutes:
        # `DroitAccorde.save` revérifie l'accès au magasin (plan 03-04) : la règle est
        # posée deux fois, au modèle et ici, parce qu'aucune contrainte de base ne peut
        # porter sur l'existence d'une ligne dans une autre table.
        DroitAccorde.objects.create(
            utilisateur=cible, magasin_code=magasin, code=code, accorde_par=par
        )
    if ajoutes:
        _journaliser(cible, JournalDroit.Action.ACCORDE, code, par)
    return ajoutes


@transaction.atomic(using="default")
def revoquer(cible, code, magasins=None, *, par) -> Resultat:
    """Retirer `code` à `cible`, et avec lui tous ses dépendants.

    Le sens « révoquer » de la cascade : retirer `caisse.voir` retire `caisse.saisir` et
    `caisse.comptage`, sans quoi le stockage garderait des droits que la règle déclare
    absurdes — un gérant qui doit encaisser dans une caisse qu'il ne voit pas.

    **Une seule opération de service couvre toute la cascade**, pour que l'interface
    présente un seul toast d'annulation la couvrant entièrement (`03-UI-SPEC.md` 7.6).
    """
    acces_appelant = acces_pour(par)
    _verifier_la_cible(cible, acces_appelant)

    code = str(code)
    accordes = magasins_accordes(cible)
    vises = _magasins_vises(cible, magasins, accordes)
    par_code = magasins_actifs_par_code()

    emportes = dependants(code)
    for candidat in sorted({code} | emportes):
        _verifier_le_pouvoir(acces_appelant, candidat, vises, par_code)

    cascade: list[str] = []
    for candidat in [code] + sorted(emportes):
        retires = _retirer(cible, candidat, vises, par=par)
        if retires and candidat != code:
            cascade.append(candidat)

    return Resultat(
        code=code,
        action=JournalDroit.Action.REVOQUE,
        lignes=tuple(
            ligne_de(cible, candidat, accordes)
            for candidat in [code] + sorted(emportes)
        ),
        cascade=tuple(cascade),
        magasins_accordes=tuple(accordes),
    )


def _retirer(cible, code: str, magasins: list[str], *, par) -> list[str]:
    """Supprimer les lignes de `code` sur `magasins`, et journaliser la révocation.

    La révocation **supprime** la ligne plutôt que de la marquer inactive : c'est ce qui
    rend `acces.peut()` trivialement juste — il n'y a pas de ligne « désactivée » à
    oublier de filtrer. Le prix est qu'il ne reste rien à interroger après coup, sauf le
    journal, qui est écrit ici et survit délibérément à la ligne (menace T-03-19).
    """
    lignes = DroitAccorde.objects.filter(
        utilisateur=cible, code=code, magasin_code__in=magasins
    )
    retires = sorted(lignes.values_list("magasin_code", flat=True))
    if retires:
        lignes.delete()
        _journaliser(cible, JournalDroit.Action.REVOQUE, code, par)
    return retires


@transaction.atomic(using="default")
def uniformiser(cible, code, accorde: bool, *, par) -> Resultat:
    """Aligner tous les magasins accordés de `cible` sur une seule valeur pour `code`.

    Le bouton `Uniformiser` de `03-UI-SPEC.md` 7.5, qui replie une ligne personnalisée.
    Rien de plus qu'un octroi ou une révocation **sans argument `magasins`** — écrit comme
    une fonction nommée parce que l'interface, elle, le présente comme une action
    distincte et que le journal doit pouvoir la relire comme telle.
    """
    if accorde:
        return accorder(cible, code, None, par=par)
    return revoquer(cible, code, None, par=par)


@transaction.atomic(using="default")
def accorder_magasin(cible, magasin_code: str, *, par) -> Resultat:
    """Donner accès à un magasin, et y **étendre les lignes uniformes uniquement**.

    C'est la règle de `03-UI-SPEC.md` 7.5 la plus facile à écrire de travers, et son mode
    de défaillance est une élévation silencieuse : étendre une ligne **personnalisée**
    distribuerait dans le nouveau magasin une permission que le propriétaire n'a jamais
    accordée, à l'occasion d'une action sans rapport (menace T-03-62). Le nouveau magasin
    démarre donc à l'arrêt pour tout code mixte, et l'interface affiche sa note
    « Californie a été ajouté. Vérifiez les 2 droits personnalisés par magasin. »
    """
    acces_appelant = acces_pour(par)
    _verifier_la_cible(cible, acces_appelant)

    magasin_code = str(magasin_code)
    par_code = magasins_actifs_par_code()
    identifiant = par_code.get(magasin_code)
    if identifiant is None:
        raise ValidationError(
            {"magasin_code": f"Le magasin « {magasin_code} » n'existe pas ou est désactivé."}
        )
    if identifiant not in acces_appelant.magasins_ids:
        raise PermissionDenied(
            f"Vous n'avez pas accès au magasin « {magasin_code} », donc vous ne pouvez "
            f"pas l'accorder."
        )

    avant = magasins_accordes(cible)
    if magasin_code in avant:
        return Resultat(
            code=magasin_code,
            action=JournalDroit.Action.ACCORDE,
            magasins_accordes=tuple(avant),
        )

    AccesMagasin.objects.create(
        utilisateur=cible, magasin_code=magasin_code, accorde_par=par
    )
    _journaliser(cible, JournalDroit.Action.ACCORDE, magasin_code, par)

    # Les lignes uniformes s'étendent ; les personnalisées non. Le calcul est fait sur
    # l'état **d'avant**, sans quoi le magasin qu'on vient d'ajouter rendrait toute ligne
    # mixte et rien ne s'étendrait jamais.
    etendus: list[str] = []
    if avant:
        for code in sorted(set(Permission.values)):
            if ligne_de(cible, code, avant).etat != ETAT_ACTIF:
                continue
            if not acces_appelant.peut(code, magasin_id=identifiant):
                # L'appelant ne détient pas ce code ici : l'extension serait un octroi
                # qu'un appel direct lui aurait refusé.
                continue
            DroitAccorde.objects.create(
                utilisateur=cible, magasin_code=magasin_code, code=code, accorde_par=par
            )
            _journaliser(cible, JournalDroit.Action.ACCORDE, code, par)
            etendus.append(code)

    apres = magasins_accordes(cible)
    return Resultat(
        code=magasin_code,
        action=JournalDroit.Action.ACCORDE,
        lignes=tuple(ligne_de(cible, code, apres) for code in etendus),
        magasins_accordes=tuple(apres),
        magasins_etendus=tuple(etendus),
    )


@transaction.atomic(using="default")
def retirer_magasin(cible, magasin_code: str, *, par) -> Resultat:
    """Retirer l'accès à un magasin, **et les droits qui le visaient**.

    Le dialogue de confirmation l'annonce en toutes lettres (`03-UI-SPEC.md` 7.9 : « Les
    réglages par magasin de 2 droits pour ce magasin seront supprimés »), et la raison de
    le faire vraiment est la menace T-03-18 : une ligne de droit visant un magasin non
    accordé est inerte aujourd'hui et redevient active le jour où le magasin est
    réaccordé — un droit que personne n'a décidé d'accorder, réapparu à l'occasion d'une
    action sans rapport.

    **Le dernier magasin n'est pas refusé ici**, et c'est une décision. `03-UI-SPEC.md`
    7.3 B refuse la case en ligne, mais un compte fraîchement créé n'a légitimement aucun
    magasin (7.2), donc « au moins un » n'est pas un invariant du modèle : c'est un
    garde-fou d'interface. Le contourner produit un compte qui voit `Acces.ANONYME`,
    c'est-à-dire rien — fail-closed, donc sans conséquence à fermer côté serveur.
    """
    acces_appelant = acces_pour(par)
    _verifier_la_cible(cible, acces_appelant)

    magasin_code = str(magasin_code)
    par_code = magasins_actifs_par_code()
    identifiant = par_code.get(magasin_code)
    if identifiant is not None and identifiant not in acces_appelant.magasins_ids:
        raise PermissionDenied(
            f"Vous n'avez pas accès au magasin « {magasin_code} », donc vous ne pouvez "
            f"pas en retirer l'accès."
        )

    droits = DroitAccorde.objects.filter(utilisateur=cible, magasin_code=magasin_code)
    perdus = sorted(set(droits.values_list("code", flat=True)))
    droits.delete()
    for code in perdus:
        _journaliser(cible, JournalDroit.Action.REVOQUE, code, par)

    acces = AccesMagasin.objects.filter(utilisateur=cible, magasin_code=magasin_code)
    if acces.exists():
        acces.delete()
        _journaliser(cible, JournalDroit.Action.REVOQUE, magasin_code, par)

    apres = magasins_accordes(cible)
    return Resultat(
        code=magasin_code,
        action=JournalDroit.Action.REVOQUE,
        lignes=tuple(ligne_de(cible, code, apres) for code in perdus),
        cascade=tuple(perdus),
        magasins_accordes=tuple(apres),
    )

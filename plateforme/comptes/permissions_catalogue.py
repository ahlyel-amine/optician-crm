"""Le catalogue des droits : 21 codes, sept sections, et la carte des prérequis.

**Le catalogue est du code, pas des données.** Il doit être énumérable à l'import, parce
que quatre consommateurs l'itèrent : le test de conformité de la projection (PERM-06), le
post-processeur de schéma OpenAPI, le point de terminaison qui sert la liste à la SPA, et
le service d'octroi. Ce sont les **octrois** qui sont des données — une ligne
`DroitAccorde(utilisateur, magasin_code, code)` par droit accordé, dans le plan de
contrôle (CLAUDE.md #11, #13).

**Les libellés vivent ici, jamais dans la SPA.** L'écran de droits (`03-UI-SPEC.md` 7.4)
reçoit du serveur le code, son libellé et son explication. Un code ajouté en phase 8
apparaît donc à l'écran sans aucun changement côté client, et un libellé ne peut jamais
dériver de son code.

**Aucun paquet de droits, et c'est une règle, pas un goût.** Pas de « gérant type », pas
de « tout cocher », pas de « copier les droits de… ». CLAUDE.md #6 dit que les droits sont
accordés individuellement, **comme données et non comme paliers de rôle** ; les trois
raccourcis ci-dessus sont exactement un palier de rôle portant un nom sympathique, et
`03-UI-SPEC.md` 7.4 en fait un point de revue explicite plutôt qu'une affaire de style.
La raison commerciale est aussi forte que la raison technique : `research/FEATURES.md`
donne les droits par gérant comme le **seul** différenciateur trouvé sur ce marché, et un
niveau « Gérant standard » le supprime en une migration. Le prochain lecteur qui voudra en
ajouter un est invité à contester ce paragraphe, pas à l'ignorer.
`test_perm03_un_droit_est_une_ligne_pas_un_palier` refuse les deux formes : un attribut
dont le nom l'annonce, et un attribut dont la valeur est une collection de codes.

**Et un seul système de droits.** `auth.Permission` et `Group` sont hors d'atteinte depuis
le plan 03-01 : `Utilisateur` n'hérite pas du mixin de droits de Django, donc
`user.has_perm("achats.view_article")` ne peut pas cohabiter avec `acces.peut(code,
magasin)` (menace T-03-21). Les codes ci-dessous ne sont pas des permissions Django et ne
sont jamais enregistrés comme telles.

Vocabulaire (`03-UI-SPEC.md` 9.3) : **droits** en interface, `permission` dans le code et
dans l'API. Ce module est du code ; il dit donc `Permission`.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple

from django.db import models


class Permission(models.TextChoices):
    """Les 21 codes qui existent. Rien d'autre ne peut être accordé.

    Vingt viennent de `03-RESEARCH.md` §4. Le vingt-et-unième, `vente.voir`, est ajouté
    par `03-UI-SPEC.md` 0.2 : sans lui, un gérant qui peut consulter une facture passée
    sans enregistrer de vente est inexprimable, et l'entrée de navigation « Ventes » n'a
    aucun code auquel se raccrocher.

    Trois codes sont déclarés avant les colonnes qu'ils protègent : `article.voir_prix_achat`
    et `vente.voir_marge` (phase 8), `dashboard.voir_ca_global` (phase 10). C'est
    délibéré — la phase 3 livre le mécanisme, et la phase 8 n'aura qu'une ligne de
    registre à écrire au lieu d'un modèle de droits à inventer sous pression. Les accorder
    aujourd'hui n'a simplement aucun effet visible.
    """

    CLIENT_VOIR = "client.voir", "Consulter les clients"
    CLIENT_MODIFIER = "client.modifier", "Créer et modifier des clients"
    ORDONNANCE_VOIR = "ordonnance.voir", "Consulter les ordonnances"
    ORDONNANCE_SAISIR = "ordonnance.saisir", "Saisir une ordonnance"
    STOCK_VOIR = "stock.voir", "Consulter le stock"
    STOCK_AJUSTER = "stock.ajuster", "Ajuster le stock / inventaire"
    ARTICLE_VOIR_PRIX_ACHAT = "article.voir_prix_achat", "Voir le prix d'achat"
    VENTE_VOIR = "vente.voir", "Consulter les ventes et les factures"
    VENTE_CREER = "vente.creer", "Enregistrer une vente"
    VENTE_REMISE = "vente.remise", "Accorder une remise"
    VENTE_VOIR_MARGE = "vente.voir_marge", "Voir la marge"
    FACTURE_AVOIR = "facture.avoir", "Émettre un avoir"
    CAISSE_VOIR = "caisse.voir", "Consulter la caisse"
    CAISSE_SAISIR = "caisse.saisir", "Saisir en caisse"
    CAISSE_COMPTAGE = "caisse.comptage", "Faire le comptage"
    FOURNISSEUR_VOIR = "fournisseur.voir", "Consulter les fournisseurs"
    ACHAT_COMMANDER = "achat.commander", "Passer un bon de commande"
    ACHAT_VOIR_SOLDES = "achat.voir_soldes", "Voir les soldes fournisseurs"
    RAPPEL_VOIR = "rappel.voir", "Consulter les rappels"
    DASHBOARD_VOIR_CA_GLOBAL = "dashboard.voir_ca_global", "Voir le CA de toute l'entreprise"
    COMPTE_GERER = "compte.gerer", "Gérer les comptes et les droits"


class Section(NamedTuple):
    """Un bloc de l'écran de droits. `codes` est dans l'ordre d'affichage."""

    titre: str
    codes: tuple[str, ...]


#: Les sept sections de l'écran de droits, dans l'ordre, et leur contenu.
#:
#: Elles **correspondent exactement à la navigation** (`03-UI-SPEC.md` 5.3 et 7.4) : un
#: propriétaire qui accorde « Consulter la caisse » doit pouvoir prévoir qu'une entrée
#: `Caisse` apparaît dans la barre latérale de Karim. Ce n'est pas un regroupement
#: esthétique, c'est ce qui rend l'écran prévisible.
#:
#: Ce n'est pas non plus un paquet de droits : une section ne s'accorde pas, elle
#: s'affiche. L'écran itère les sections, donc un code absent de toutes serait invisible
#: et impossible à accorder — d'où le test qui exige la couverture exacte.
SECTIONS: tuple[Section, ...] = (
    Section(
        "Clients et ordonnances",
        (
            Permission.CLIENT_VOIR,
            Permission.CLIENT_MODIFIER,
            Permission.ORDONNANCE_VOIR,
            Permission.ORDONNANCE_SAISIR,
        ),
    ),
    Section(
        "Stock",
        (
            Permission.STOCK_VOIR,
            Permission.STOCK_AJUSTER,
            Permission.ARTICLE_VOIR_PRIX_ACHAT,
        ),
    ),
    Section(
        "Ventes et factures",
        (
            Permission.VENTE_VOIR,
            Permission.VENTE_CREER,
            Permission.VENTE_REMISE,
            Permission.VENTE_VOIR_MARGE,
            Permission.FACTURE_AVOIR,
        ),
    ),
    Section(
        "Caisse",
        (
            Permission.CAISSE_VOIR,
            Permission.CAISSE_SAISIR,
            Permission.CAISSE_COMPTAGE,
        ),
    ),
    Section(
        "Fournisseurs et achats",
        (
            Permission.FOURNISSEUR_VOIR,
            Permission.ACHAT_COMMANDER,
            Permission.ACHAT_VOIR_SOLDES,
        ),
    ),
    Section(
        "Rappels et tableau de bord",
        (
            Permission.RAPPEL_VOIR,
            Permission.DASHBOARD_VOIR_CA_GLOBAL,
        ),
    ),
    Section("Comptes", (Permission.COMPTE_GERER,)),
)


#: Une phrase de français simple par code, nommant la **conséquence** plutôt que le code.
#:
#: Affichée sous chaque ligne de l'écran, pas dans une infobulle : une infobulle est
#: invisible à quelqu'un qui parcourt la page, et cette ligne est le levier de coût de
#: support de `03-UI-SPEC.md` 7.4. À 2 400 MAD par an et par boutique, la différence entre
#: un propriétaire qui comprend ce qu'il coche et un appel téléphonique décide si la
#: charge de support est soutenable. Ce n'est donc pas de la décoration.
EXPLICATIONS: dict[str, str] = {
    Permission.CLIENT_VOIR: (
        "La liste des clients, leurs coordonnées et leur historique d'achats."
    ),
    Permission.CLIENT_MODIFIER: (
        "Créer un client et corriger sa fiche. Sans ce droit, la fiche se consulte mais "
        "ne se change pas."
    ),
    Permission.ORDONNANCE_VOIR: (
        "Les ordonnances d'un client, donc une donnée de santé. À n'accorder qu'aux "
        "personnes qui en ont besoin."
    ),
    Permission.ORDONNANCE_SAISIR: (
        "Enregistrer une nouvelle ordonnance et la rattacher à un client."
    ),
    Permission.STOCK_VOIR: (
        "Les articles disponibles et leurs quantités, magasin par magasin."
    ),
    Permission.STOCK_AJUSTER: (
        "Corriger une quantité après un inventaire ou une casse. Chaque correction reste "
        "tracée."
    ),
    Permission.ARTICLE_VOIR_PRIX_ACHAT: (
        "Le prix payé au fournisseur. Sans ce droit, la marge est également masquée, "
        "partout."
    ),
    Permission.VENTE_VOIR: (
        "Les ventes déjà enregistrées et les factures émises. Sans ce droit, l'entrée "
        "« Ventes » n'apparaît pas."
    ),
    Permission.VENTE_CREER: (
        "Enregistrer une vente au comptoir et émettre la facture correspondante."
    ),
    Permission.VENTE_REMISE: (
        "Baisser le prix d'une vente. Sans ce droit, les prix s'appliquent tels "
        "qu'affichés."
    ),
    Permission.VENTE_VOIR_MARGE: (
        "Ce que l'affaire gagne sur chaque vente. Demande aussi le droit de voir le prix "
        "payé au fournisseur."
    ),
    Permission.FACTURE_AVOIR: (
        "Annuler une facture par un avoir. Une facture n'est jamais supprimée, elle est "
        "compensée."
    ),
    Permission.CAISSE_VOIR: (
        "Le contenu de la caisse d'un magasin et les mouvements de la journée."
    ),
    Permission.CAISSE_SAISIR: (
        "Enregistrer une entrée ou une sortie d'espèces dans la caisse."
    ),
    Permission.CAISSE_COMPTAGE: (
        "Compter la caisse en fin de journée et déclarer l'écart constaté."
    ),
    Permission.FOURNISSEUR_VOIR: ("La liste des fournisseurs et leurs coordonnées."),
    Permission.ACHAT_COMMANDER: (
        "Passer un bon de commande à un fournisseur, au nom de l'affaire."
    ),
    Permission.ACHAT_VOIR_SOLDES: ("Ce qui reste dû à chaque fournisseur."),
    Permission.RAPPEL_VOIR: (
        "Les rappels de renouvellement et les relances à passer aux clients."
    ),
    Permission.DASHBOARD_VOIR_CA_GLOBAL: (
        "Le chiffre d'affaires de toute l'affaire, tous magasins confondus."
    ),
    Permission.COMPTE_GERER: (
        "Créer des comptes et accorder des droits, dans la limite de ses propres droits."
    ),
}


#: Les droits qui n'ont aucun sens seuls, et ce dont ils dépendent.
#:
#: La liste est celle de `03-UI-SPEC.md` 7.6. Déclarée **côté serveur**, à côté du
#: catalogue, et livrée avec lui : l'interface s'en sert pour expliquer la cascade
#: (« Consulter le stock a été activé automatiquement »), mais l'explication n'est pas la
#: règle — la fermeture est appliquée par le service d'octroi (plan 03-09).
#:
#: Ce n'est pas un paquet de droits déguisé : un prérequis ne regroupe pas des codes sous
#: un nom, il dit qu'un code isolé serait inopérant. Accorder `stock.ajuster` sans
#: `stock.voir` produit un gérant qui doit corriger un stock qu'il ne voit pas — la classe
#: d'appels que cette carte existe pour supprimer.
PREREQUIS: dict[str, tuple[str, ...]] = {
    Permission.CLIENT_MODIFIER: (Permission.CLIENT_VOIR,),
    Permission.ORDONNANCE_SAISIR: (Permission.ORDONNANCE_VOIR,),
    Permission.STOCK_AJUSTER: (Permission.STOCK_VOIR,),
    Permission.VENTE_CREER: (Permission.VENTE_VOIR,),
    Permission.VENTE_REMISE: (Permission.VENTE_VOIR,),
    Permission.VENTE_VOIR_MARGE: (Permission.ARTICLE_VOIR_PRIX_ACHAT,),
    Permission.CAISSE_SAISIR: (Permission.CAISSE_VOIR,),
    Permission.CAISSE_COMPTAGE: (Permission.CAISSE_VOIR,),
    Permission.ACHAT_COMMANDER: (Permission.FOURNISSEUR_VOIR,),
}


def _valider(codes: Iterable[str]) -> list[str]:
    """Refuse tout code hors catalogue, plutôt que de l'ignorer.

    Une faute de frappe dans un octroi doit être bruyante. Ignorée, elle produit un droit
    qui n'accorde rien et que personne ne remarque avant que le gérant n'appelle.
    """
    connus = set(Permission.values)
    demandes = [str(code) for code in codes]
    inconnus = sorted({code for code in demandes if code not in connus})
    if inconnus:
        raise ValueError(
            f"Codes de permission inconnus du catalogue : {', '.join(inconnus)}."
        )
    return demandes


def fermeture_prerequis(codes: Iterable[str]) -> frozenset[str]:
    """Les codes demandés, plus tout ce dont ils dépendent, transitivement.

    Le sens « accorder » de la cascade : cocher `vente.voir_marge` doit aussi accorder
    `article.voir_prix_achat`, sans quoi la marge serait affichée à quelqu'un dont le
    droit de voir le prix d'achat a été refusé — et le prix d'achat se recalcule à la
    main depuis la marge.
    """
    restants = _valider(codes)
    resultat: set[str] = set()
    while restants:
        code = restants.pop()
        if code in resultat:
            continue
        resultat.add(code)
        restants.extend(PREREQUIS.get(code, ()))
    return frozenset(resultat)


def dependants(code: str) -> frozenset[str]:
    """Les codes qui deviennent inopérants si `code` est retiré, transitivement.

    Le sens « révoquer » de la cascade, et l'autre moitié dont le plan 03-09 a besoin :
    retirer `caisse.voir` doit retirer `caisse.saisir` et `caisse.comptage`, faute de quoi
    le stockage garderait des droits que la règle déclare absurdes.
    """
    (depart,) = _valider([code])
    resultat: set[str] = set()
    a_visiter = [depart]
    while a_visiter:
        courant = a_visiter.pop()
        for candidat, requis in PREREQUIS.items():
            if courant in requis and candidat not in resultat:
                resultat.add(candidat)
                a_visiter.append(candidat)
    return frozenset(resultat)

"""PERM-02 et PERM-03 — créer un compte gérant, le désactiver, accorder et révoquer.

**Ces tests ne sont pas encore implémentés.** Ils portent le marqueur `pending` et
échouent volontairement. Trois plans se partagent leur mise au vert :

* **03-04** pose `DroitAccorde(utilisateur, magasin_code, code)`, `AccesMagasin` et
  `JournalDroit` — la forme de stockage ;
* **03-05** pose `Acces` et `acces_pour()` — la résolution ;
* **03-09** pose la surface d'écriture de l'API — création de compte, octroi, révocation.

La règle que ce fichier existe pour pinner est CLAUDE.md **#6** : *« Permissions are
granted per gérant individually, as data, not as role tiers »*, et CLAUDE.md **#13** :
les droits sont stockés par **(gérant, magasin, permission)**. `03-RESEARCH.md` §4 propose
`DroitAccorde(utilisateur, code)`, sans dimension magasin ; son propre bandeau de
correction et `03-UI-SPEC.md` 0.1 disent que cette forme est abandonnée. Les deux derniers
tests de ce fichier sont ceux que CLAUDE.md #13 impose et que la table de `03-VALIDATION.md`
avait omis — sans eux, un modèle conforme à la recherche passerait toute la suite.

Tout se joue sur `default` : identité, appartenance et droits vivent dans le plan de
contrôle (CLAUDE.md #11). Les magasins, eux, sont des lignes dans la base d'un opticien,
ce qui est précisément pourquoi le droit stocke un `magasin_code` et non une clé
étrangère — une FK inter-alias n'existe pas.

**Aucun import du code en construction au niveau du module** : ils descendent dans le
corps des fonctions, sans quoi la collecte de la suite entière casserait tant que les
modèles n'existent pas.
"""

from __future__ import annotations

import re

import pytest


# --------------------------------------------------------------------------------------
# PERM-02 — le compte
# --------------------------------------------------------------------------------------
@pytest.mark.pending
def test_perm02_un_proprietaire_ne_cree_un_compte_que_dans_son_propre_client(db_all):
    """PERM-02 — le `client` du nouveau compte est imposé par le serveur, jamais reçu.

    Rouge, ce test dirait que `client` est un champ acceptable en entrée : le propriétaire
    de l'affaire A poste `client: <id de B>` et obtient un compte dans l'affaire d'un
    concurrent, avec une adresse de connexion qu'il contrôle. C'est l'élévation de
    privilèges la plus directe de la phase, et elle ne demande aucun outil — juste un
    champ de plus dans le corps JSON (`03-RESEARCH.md` A-03-05).

    Le test crée deux clients, précisément parce qu'un test à un seul client ne peut pas
    distinguer « le serveur impose le bon » de « le serveur accepte ce qu'on lui donne,
    qui se trouve être le bon ».
    """
    pytest.fail("non implémenté : plan 03-09")


@pytest.mark.pending
def test_perm02_un_compte_desactive_est_refuse_des_la_requete_suivante(db_all):
    """PERM-02 — désactiver doit mordre tout de suite, sans machinerie de révocation.

    `ModelBackend.get_user()` appelle `user_can_authenticate()` à **chaque** requête, donc
    `is_active = False` est effectif dès la suivante, gratuitement — à condition que rien
    n'ait mis le principal en cache. Rouge, ce test dirait qu'une couche de cache ou un
    jeton porteur s'est glissée entre la base et `request.user`, et qu'un gérant congédié
    ce matin travaille encore cet après-midi.

    Le test agit sur une session **déjà ouverte** : désactiver avant la connexion ne
    prouverait que le refus au login, qui n'est pas ce que PERM-02 demande.
    """
    pytest.fail("non implémenté : plan 03-09")


# --------------------------------------------------------------------------------------
# PERM-03 — le droit
# --------------------------------------------------------------------------------------
def test_perm03_un_droit_est_une_ligne_pas_un_palier(db_all):
    """PERM-03 / CLAUDE.md #6 — aucun palier de rôle, nulle part.

    Rouge, ce test dirait qu'un `role`, un `profil`, un `niveau` ou un `Group` est réapparu
    quelque part — c'est-à-dire que les droits ne sont plus des données mais des bundles.
    Le mode de défaillance est commercial autant que technique : `research/FEATURES.md`
    donne le modèle de permissions par gérant comme le **seul** différenciateur trouvé sur
    ce marché, et un palier « Gérant » le supprime en une migration.

    Le test affirme sur `DroitAccorde._meta` et sur le catalogue, pas sur une docstring :
    une docstring qui dit « pas de rôles » ne devient pas rouge quand quelqu'un en ajoute.
    """
    from django.apps import apps

    from plateforme.comptes import permissions_catalogue
    from plateforme.comptes.permissions_catalogue import Permission

    # -- moitié catalogue : aucun champ de palier, nulle part dans `comptes` ------------
    #
    # `_meta.get_fields()` voit les colonnes réelles, y compris celles qu'une classe de
    # base aurait apportées sans qu'on les relise — c'est pour cela que l'assertion porte
    # là plutôt que sur le texte de la classe.
    interdits = {"role", "roles", "tier", "palier", "niveau", "profil", "groupe", "groupes"}
    for modele in apps.get_app_config("comptes").get_models():
        noms = {champ.name.lower() for champ in modele._meta.get_fields()}
        fautifs = noms & interdits
        assert not fautifs, (
            f"{modele.__name__} porte {sorted(fautifs)} : un palier de rôle est revenu "
            f"dans le plan de contrôle (CLAUDE.md #6)."
        )

    # -- moitié catalogue : aucun ensemble préconstitué de codes ------------------------
    #
    # Un preset est un palier avec un nom sympathique. Les deux formes sont refusées : un
    # attribut dont le *nom* l'annonce, et un attribut dont la *valeur* est une collection
    # de codes prête à accorder. `SECTIONS` n'en est pas une — elle partitionne le
    # catalogue pour l'affichage et ses éléments ne sont pas des chaînes ; `EXPLICATIONS`
    # et `PREREQUIS` sont des applications code par code, pas des paquets.
    codes = set(Permission.values)
    for nom, valeur in vars(permissions_catalogue).items():
        if nom.startswith("_"):
            continue
        assert not re.search(
            r"preset|bundle|palier|role|tier|niveau|standard", nom, re.IGNORECASE
        ), f"`{nom}` annonce un paquet de droits ; CLAUDE.md #6 n'en veut aucun."
        if (
            isinstance(valeur, (list, tuple, set, frozenset))
            and valeur
            and all(isinstance(element, str) for element in valeur)
        ):
            assert not set(valeur) <= codes, (
                f"`{nom}` est un ensemble de codes du catalogue, donc un palier de rôle "
                f"servi sous un autre nom."
            )


def test_perm03_les_sept_sections_couvrent_exactement_le_catalogue():
    """PERM-03 — un code hors section est invisible à l'écran, donc inaccordable.

    L'écran de droits (`03-UI-SPEC.md` 7.4) n'affiche pas `Permission.values` : il itère
    les **sections**. Un code ajouté en phase 8 et oublié d'une section existerait donc
    dans la base, dans le schéma et dans les tests, et nulle part où un propriétaire
    puisse le cocher. Rouge, ce test dit soit cela, soit l'inverse — un code listé deux
    fois, qui apparaîtrait sous deux interrupteurs pour une seule ligne de droit.

    Les sept titres sont affirmés mot pour mot, parce que leur alignement sur la
    navigation (`03-UI-SPEC.md` 5.3) est le contrat : un propriétaire qui accorde
    « Consulter la caisse » doit pouvoir prévoir qu'une entrée `Caisse` apparaît chez
    Karim.
    """
    from plateforme.comptes.permissions_catalogue import (
        EXPLICATIONS,
        SECTIONS,
        Permission,
    )

    assert len(Permission.values) == 21
    assert [section.titre for section in SECTIONS] == [
        "Clients et ordonnances",
        "Stock",
        "Ventes et factures",
        "Caisse",
        "Fournisseurs et achats",
        "Rappels et tableau de bord",
        "Comptes",
    ]

    vus = [code for section in SECTIONS for code in section.codes]
    doublons = sorted({code for code in vus if vus.count(code) > 1})
    assert not doublons, f"codes listés dans plusieurs sections : {doublons}"
    assert set(vus) == set(Permission.values), (
        f"orphelins (aucune section) : {sorted(set(Permission.values) - set(vus))} ; "
        f"inconnus (hors catalogue) : {sorted(set(vus) - set(Permission.values))}"
    )

    # Chaque code porte sa phrase d'explication : c'est le levier de coût de support de
    # `03-UI-SPEC.md` 7.4, et un code sans explication est une case à cocher muette.
    assert set(EXPLICATIONS) == set(Permission.values)
    for code, phrase in EXPLICATIONS.items():
        assert phrase.strip() and phrase.strip().endswith("."), code
        assert code not in phrase, (
            f"l'explication de {code} récite le code ; elle doit nommer la conséquence."
        )


def test_perm03_la_carte_des_prerequis_est_acyclique_et_close_sur_le_catalogue():
    """PERM-03 — la cascade des prérequis est déclarée côté serveur, dans les deux sens.

    `03-UI-SPEC.md` 7.6 : accorder `stock.ajuster` accorde `stock.voir`, et retirer
    `stock.voir` retire `stock.ajuster`. Les deux sens sont appliqués côté serveur (plan
    03-09) ; l'interface ne fait que l'expliquer. Rouge, ce test dirait qu'un prérequis
    pointe un code qui n'existe pas — donc une cascade qui n'accorde rien sous une note
    d'interface qui affirme le contraire — ou qu'un cycle est apparu, auquel cas la
    fermeture d'un octroi ne termine pas, ou accorde tout le cycle d'un coup.
    """
    from plateforme.comptes.permissions_catalogue import (
        PREREQUIS,
        Permission,
        dependants,
        fermeture_prerequis,
    )

    # La liste est celle de `03-UI-SPEC.md` 7.6, affirmée en entier : une assertion
    # « chaque clé est un code » laisserait passer une entrée discrètement supprimée.
    assert PREREQUIS == {
        "client.modifier": ("client.voir",),
        "ordonnance.saisir": ("ordonnance.voir",),
        "stock.ajuster": ("stock.voir",),
        "vente.creer": ("vente.voir",),
        "vente.remise": ("vente.voir",),
        "vente.voir_marge": ("article.voir_prix_achat",),
        "caisse.saisir": ("caisse.voir",),
        "caisse.comptage": ("caisse.voir",),
        "achat.commander": ("fournisseur.voir",),
    }

    codes = set(Permission.values)
    for dependant, requis in PREREQUIS.items():
        assert dependant in codes, dependant
        assert isinstance(requis, tuple), dependant
        for prerequis in requis:
            assert prerequis in codes, prerequis
            assert prerequis != dependant, dependant

    # Acyclicité, par parcours en profondeur : un cycle rendrait `fermeture_prerequis`
    # soit non terminante, soit silencieusement totale.
    def descendre(depart):
        chemin = [depart]

        def marcher(code):
            for suivant in PREREQUIS.get(code, ()):
                assert suivant not in chemin, f"cycle : {' -> '.join(chemin + [suivant])}"
                chemin.append(suivant)
                marcher(suivant)
                chemin.pop()

        marcher(depart)

    for code in codes:
        descendre(code)

    # Les deux sens de la cascade, dont le plan 03-09 a besoin.
    assert fermeture_prerequis(["vente.voir_marge"]) == {
        "vente.voir_marge",
        "article.voir_prix_achat",
    }
    assert fermeture_prerequis(["caisse.saisir", "caisse.comptage"]) == {
        "caisse.saisir",
        "caisse.comptage",
        "caisse.voir",
    }
    assert fermeture_prerequis([]) == frozenset()
    assert dependants("vente.voir") == {"vente.creer", "vente.remise"}
    assert dependants("compte.gerer") == frozenset()

    # Un code inconnu est refusé plutôt qu'ignoré : une faute de frappe dans un octroi
    # doit être bruyante, pas silencieusement sans effet.
    with pytest.raises(ValueError):
        fermeture_prerequis(["stock.inexistant"])
    with pytest.raises(ValueError):
        dependants("stock.inexistant")


@pytest.mark.pending
def test_perm03_un_droit_est_stocke_par_gerant_magasin_et_permission(db_all, deux_magasins):
    """PERM-03 / CLAUDE.md #13 — la dimension magasin existe dans le stockage, dès le jour un.

    Ce test **n'est pas dans la table de `03-VALIDATION.md`** ; il est ajouté ici parce que
    CLAUDE.md #13 l'impose et que `03-UI-SPEC.md` 0.1 montre que la forme proposée par la
    recherche — `UniqueConstraint(utilisateur, code)` — la reverse. Sans ce test, un modèle
    à une seule dimension passerait la phase entière et la correction serait une migration
    de données, sur des droits, en production.

    Rouge, il dit exactement une chose : la contrainte d'unicité porte sur
    `(utilisateur, magasin_code, code)` et non sur `(utilisateur, code)`. L'interface, elle,
    reste une case à cocher unique par droit — le « par magasin » ne se montre que sur
    demande (`03-UI-SPEC.md` §6.4). C'est le stockage qui doit pouvoir, pas l'écran qui doit
    montrer.
    """
    pytest.fail("non implémenté : plan 03-04")


@pytest.mark.pending
def test_perm03_un_droit_accorde_dans_un_magasin_ne_fuit_pas_vers_un_autre(
    db_all, deux_magasins
):
    """PERM-03 / CLAUDE.md #13 — la moitié *comportementale* de la dimension magasin.

    Le test précédent regarde la contrainte ; celui-ci regarde la réponse. Une contrainte
    à trois colonnes au-dessus d'un `acces.peut(code)` qui ignore le magasin stocke
    correctement une distinction que le code ne fait pas : le gérant qui peut faire une
    remise à Anfa peut en faire une à Maârif, et la base a l'air juste.

    Il faut **deux** magasins pour que ce test veuille dire quelque chose, d'où
    `deux_magasins` : avec un seul, « le droit du bon magasin » et « n'importe quel droit »
    sont le même objet et l'assertion passe au-dessus du bug (`03-RESEARCH.md` P16).
    """
    pytest.fail("non implémenté : plan 03-05")


@pytest.mark.pending
def test_perm03_la_revocation_prend_effet_sans_reconnexion(db_all):
    """PERM-03 — retirer un droit mord à la requête suivante, sans déconnecter personne.

    C'est la promesse que `03-UI-SPEC.md` §7.8 affiche à l'écran, en toutes lettres, sous
    la liste des droits. Rouge, ce test dirait que cette phrase est fausse : l'`Acces` est
    résolu une fois et posé en session, ou mis en cache par utilisateur, donc le droit
    retiré à 14 h continue de s'appliquer jusqu'à la déconnexion. Une promesse affichée et
    non tenue est pire qu'une promesse absente — le propriétaire croit avoir agi.
    """
    pytest.fail("non implémenté : plan 03-05")


@pytest.mark.pending
def test_perm03_un_proprietaire_ne_peut_pas_accorder_a_un_utilisateur_dun_autre_client(
    db_all,
):
    """PERM-03 — l'octroi traverse la frontière des affaires si personne ne l'en empêche.

    Les droits vivent dans le plan de contrôle, donc **tous les gérants de la flotte sont
    dans la même table**. Rien dans le schéma n'empêche une ligne `DroitAccorde` dont
    l'`utilisateur` appartient à une autre affaire : c'est une clé étrangère parfaitement
    valide. La garantie est applicative, donc elle a besoin d'un test, et le test a besoin
    d'un second client — d'où `db_all`.

    Rouge, il dirait qu'un propriétaire peut accorder des droits sur ses propres magasins à
    un compte qu'il ne contrôle pas, ou pire, à un compte d'une autre affaire qu'il
    rendrait ainsi actif chez lui.
    """
    pytest.fail("non implémenté : plan 03-09")


@pytest.mark.pending
def test_perm03_le_journal_enregistre_qui_a_accorde_quoi_et_quand(db_all):
    """PERM-03 — « qui a donné les marges à Karim ? » doit avoir une réponse après coup.

    La révocation **supprime** la ligne d'octroi : c'est ce qui rend `acces.peut()`
    trivialement juste. Le prix est qu'après une révocation il ne reste rien à interroger,
    sauf journal. `JournalDroit` est append-only et survit à la ligne qu'il décrit
    (menace T-03-19).

    Rouge, ce test dirait soit que le journal n'est pas écrit, soit — le cas sournois —
    qu'il est écrit mais supprimé en cascade avec le droit, donc qu'il ne répond à la
    question que tant que la question ne se pose pas.
    """
    pytest.fail("non implémenté : plan 03-04")

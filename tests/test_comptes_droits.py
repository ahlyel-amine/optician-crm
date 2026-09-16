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


#: Les chemins de la surface d'écriture, écrits une fois. Un test qui recopie une URL
#: passe le jour où la route change de place, parce qu'il teste alors une 404 bien formée.
COMPTES = "/api/comptes/"
CATALOGUE = "/api/comptes/catalogue/"


def _detail(compte) -> str:
    return f"{COMPTES}{compte.pk}/"


def _droits(compte) -> str:
    return f"{COMPTES}{compte.pk}/droits/"


def _uniformiser(compte) -> str:
    return f"{COMPTES}{compte.pk}/droits/uniformiser/"


def _magasins(compte) -> str:
    return f"{COMPTES}{compte.pk}/magasins/"


def _client_api(csrf=False):
    from rest_framework.test import APIClient

    return APIClient(enforce_csrf_checks=csrf)


def _connecter(api, utilisateur):
    """Ouvre une vraie session par le point de terminaison de connexion du plan 03-08.

    Par l'API et non par `force_login`, délibérément : ce que ces tests vérifient est le
    comportement d'un appelant réel, lié à son locataire par le même chemin qu'en
    production. `force_login` sauterait `_amorcage`, donc la liaison.
    """
    from tests.factories import MOT_DE_PASSE_DE_TEST

    reponse = api.post(
        "/api/auth/connexion/",
        {"email": utilisateur.email, "mot_de_passe": MOT_DE_PASSE_DE_TEST},
        format="json",
    )
    assert reponse.status_code == 200, reponse.data
    return api


def _gerant_gestionnaire(affaire, magasins_codes, codes_supplementaires=()):
    """Un gérant détenant `compte.gerer` dans chacun de ses magasins, et rien de plus.

    `peut()` sans magasin est une **conjonction** (plan 03-05), donc un gérant qui ne
    détiendrait `compte.gerer` que dans l'un de ses deux magasins n'atteint pas cette
    surface. C'est voulu et c'est fail-closed : administrer des comptes n'est pas une
    action de magasin, et l'union — `peut_quelque_part` — n'autorise jamais rien.
    """
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    gerant = GerantFactory(client=affaire.client)
    for code_magasin in magasins_codes:
        AccesMagasinFactory(utilisateur=gerant, magasin_code=code_magasin)
        for code in (Permission.COMPTE_GERER, *codes_supplementaires):
            DroitAccordeFactory(
                utilisateur=gerant, magasin_code=code_magasin, code=code
            )
    return gerant


# --------------------------------------------------------------------------------------
# PERM-02 — le compte
# --------------------------------------------------------------------------------------
def test_perm02_un_proprietaire_ne_cree_un_compte_que_dans_son_propre_client(
    affaire_reelle,
):
    """PERM-02 — le `client` du nouveau compte est imposé par le serveur, jamais reçu.

    Rouge, ce test dirait que `client` est un champ acceptable en entrée : le propriétaire
    de l'affaire A poste `client: <id de B>` et obtient un compte dans l'affaire d'un
    concurrent, avec une adresse de connexion qu'il contrôle. C'est l'élévation de
    privilèges la plus directe de la phase, et elle ne demande aucun outil — juste un
    champ de plus dans le corps JSON (`03-RESEARCH.md` A-03-05).

    Le test crée deux clients, précisément parce qu'un test à un seul client ne peut pas
    distinguer « le serveur impose le bon » de « le serveur accepte ce qu'on lui donne,
    qui se trouve être le bon ».

    Les cinq champs d'élévation sont soumis **ensemble**, dans une seule requête : c'est
    la forme que prend l'attaque, et vérifier chaque champ dans son propre test laisserait
    passer une implémentation qui en refuse quatre. Le filet de la base (plan 03-01)
    n'aurait de toute façon attrapé que `is_staff` et `is_superuser` ; `client` et
    `est_proprietaire` n'ont que le sérialiseur devant eux.
    """
    from plateforme.comptes.models import Utilisateur
    from tests.factories import ClientFactory, ProprietaireFactory

    proprietaire = ProprietaireFactory(client=affaire_reelle.client)
    concurrent = ClientFactory()  # une autre affaire, une clé étrangère parfaitement valide
    assert concurrent.pk != affaire_reelle.client.pk

    api = _connecter(_client_api(), proprietaire)
    reponse = api.post(
        COMPTES,
        {
            "nom_complet": "Karim Benali",
            "email": "karim.benali@optiqueanfa.ma",
            "client": concurrent.pk,
            "est_proprietaire": True,
            "is_staff": True,
            "is_superuser": True,
            "derniere_connexion_ip": "10.0.0.1",
        },
        format="json",
    )
    assert reponse.status_code == 201, reponse.data

    cree = Utilisateur.objects.using("default").get(email="karim.benali@optiqueanfa.ma")
    assert cree.client_id == affaire_reelle.client.pk, (
        "Le compte a été créé dans l'affaire soumise par l'appelant. `client` est une "
        "entrée de sérialiseur, donc un propriétaire peut poser une adresse de connexion "
        "qu'il contrôle chez un concurrent."
    )
    assert cree.est_proprietaire is False
    assert cree.is_staff is False
    assert cree.is_superuser is False
    assert cree.derniere_connexion_ip is None

    # Et le contrôle positif : l'affaire du concurrent n'a rien gagné. Sans lui, une
    # implémentation qui créerait *deux* comptes passerait les assertions ci-dessus.
    assert not Utilisateur.objects.using("default").filter(client=concurrent).exists()


def test_perm02_la_suppression_dun_compte_nexiste_nulle_part(affaire_reelle):
    """PERM-02 / `03-UI-SPEC.md` 7.8 — il n'y a pas de route de suppression, et il n'y en aura pas.

    Un compte est référencé par des ventes, par `JournalDroit` et par dix ans de
    conservation (art. 211 CGI). Une suppression réussie n'est donc pas une perte de
    confort : c'est une violation fiscale et un journal des droits amputé de son sujet.
    La désactivation est le seul chemin, et elle est réversible.

    Trois assertions, parce qu'une seule ne tient pas. Le 405 constate la route absente
    aujourd'hui ; l'absence de `destroy` et de `DestroyModelMixin` dans le MRO constate
    qu'elle ne peut pas revenir par héritage — passer le jeu de vues à un `ModelViewSet`
    complet la rendrait d'un coup, sans qu'une ligne de route change.
    """
    from rest_framework import mixins

    from plateforme.comptes import views
    from tests.factories import GerantFactory, ProprietaireFactory

    proprietaire = ProprietaireFactory(client=affaire_reelle.client)
    karim = GerantFactory(client=affaire_reelle.client)
    api = _connecter(_client_api(), proprietaire)

    # Le contrôle positif d'abord : la fiche existe et se lit. Sans lui, un 405 sur une
    # route inexistante prouverait la même chose qu'un 405 sur une route protégée.
    assert api.get(_detail(karim)).status_code == 200

    assert api.delete(_detail(karim)).status_code == 405, (
        "Une route de suppression de compte répond. `03-UI-SPEC.md` 7.8 : la suppression "
        "n'existe nulle part, et le mot n'apparaît jamais."
    )

    assert not hasattr(views.VueComptes, "destroy")
    assert mixins.DestroyModelMixin not in views.VueComptes.__mro__


def test_perm02_seul_un_appelant_habilite_atteint_la_gestion_des_comptes(affaire_reelle):
    """PERM-02 — `compte.gerer`, ou propriétaire. Sinon 403, sur chaque route.

    Rouge, ce test dirait que la surface d'écriture de la phase est ouverte à tout compte
    authentifié — c'est-à-dire qu'un gérant sans aucun droit peut créer un collègue et
    s'accorder ce qu'il veut par son intermédiaire.

    Le refus est un **403** et non un 401 : la session est valide, c'est le droit qui
    manque, et `03-UI-SPEC.md` 8.6 branche des écrans opposés sur les deux codes (plan
    03-08). Le contrôle positif est le gérant-gestionnaire : sans lui, une permission qui
    refuserait tout le monde passerait.
    """
    from tests.factories import GerantFactory

    simple = GerantFactory(client=affaire_reelle.client)
    api = _connecter(_client_api(), simple)

    for chemin in (COMPTES, CATALOGUE, _detail(simple)):
        assert api.get(chemin).status_code == 403, (
            f"{chemin} a répondu à un gérant sans `compte.gerer`."
        )
    assert api.post(COMPTES, {"nom_complet": "X", "email": "x@y.ma"}, format="json").status_code == 403

    gestionnaire = _gerant_gestionnaire(affaire_reelle, ["AUTHANFA"])
    autre = _connecter(_client_api(), gestionnaire)
    assert autre.get(COMPTES).status_code == 200, (
        "Un gérant détenant `compte.gerer` est refusé : la permission refuse tout le "
        "monde, et les trois 403 ci-dessus ne prouvent rien."
    )


def test_perm02_le_mot_de_passe_provisoire_nest_montre_quune_seule_fois(affaire_reelle):
    """PERM-02 — il n'y a pas de chemin par courriel, donc le secret transite une fois.

    Le plan 03-08 a fermé la réinitialisation par courriel faute de fournisseur d'e-mail
    dans la pile. Le chemin livré est donc : le propriétaire pose le mot de passe, le lit
    **une fois**, le transmet de vive voix, et `doit_changer_mot_de_passe` force le
    changement à la première connexion.

    Rouge, ce test dirait que le secret est relisible — dans la fiche, dans la liste, ou
    dans un champ oublié d'un sérialiseur. Un mot de passe provisoire relisible par tout
    détenteur de `compte.gerer` est une prise de contrôle silencieuse du compte d'un
    collègue (menace T-03-65).
    """
    from plateforme.comptes.models import Utilisateur
    from tests.factories import ProprietaireFactory

    proprietaire = ProprietaireFactory(client=affaire_reelle.client)
    api = _connecter(_client_api(), proprietaire)

    creation = api.post(
        COMPTES,
        {"nom_complet": "Karim Benali", "email": "karim@optiqueanfa.ma"},
        format="json",
    )
    assert creation.status_code == 201, creation.data
    provisoire = creation.data["mot_de_passe_provisoire"]
    assert provisoire, "Aucun mot de passe provisoire n'est renvoyé à la création."

    karim = Utilisateur.objects.using("default").get(email="karim@optiqueanfa.ma")
    # Le contrôle positif : le secret rendu est bien celui du compte. Sans lui, un point
    # de terminaison qui renverrait une chaîne aléatoire sans la poser passerait.
    assert karim.check_password(provisoire)
    assert karim.doit_changer_mot_de_passe is True

    interdits = re.compile(r"password|mot_de_passe_provisoire")
    for chemin in (COMPTES, _detail(karim)):
        reponse = api.get(chemin)
        corps = reponse.content.decode()
        assert provisoire not in corps, f"{chemin} relit le mot de passe provisoire."
        lignes = reponse.data if isinstance(reponse.data, list) else [reponse.data]
        for ligne in lignes:
            fautifs = sorted(cle for cle in ligne if interdits.search(cle))
            assert not fautifs, (
                f"{chemin} expose {fautifs}. Le hash lui-même n'a rien à faire dans une "
                "charge utile : il se soumet à une attaque hors ligne. "
                "(`doit_changer_mot_de_passe` est un drapeau, pas un secret.)"
            )

    reinitialisation = api.post(f"{_detail(karim)}mot-de-passe/", {}, format="json")
    assert reinitialisation.status_code == 200, reinitialisation.data
    nouveau = reinitialisation.data["mot_de_passe_provisoire"]
    assert nouveau and nouveau != provisoire

    karim.refresh_from_db()
    assert karim.check_password(nouveau)
    assert not karim.check_password(provisoire), (
        "L'ancien mot de passe fonctionne encore après une réinitialisation."
    )
    assert karim.doit_changer_mot_de_passe is True
    assert nouveau not in api.get(_detail(karim)).content.decode()


def test_perm02_un_compte_desactive_est_refuse_des_la_requete_suivante(affaire_reelle):
    """PERM-02 — désactiver doit mordre tout de suite, sans machinerie de révocation.

    `ModelBackend.get_user()` appelle `user_can_authenticate()` à **chaque** requête, donc
    `is_active = False` est effectif dès la suivante, gratuitement — à condition que rien
    n'ait mis le principal en cache. Rouge, ce test dirait qu'une couche de cache ou un
    jeton porteur s'est glissée entre la base et `request.user`, et qu'un gérant congédié
    ce matin travaille encore cet après-midi.

    Le test agit sur une session **déjà ouverte** : désactiver avant la connexion ne
    prouverait que le refus au login, qui n'est pas ce que PERM-02 demande. C'est aussi
    précisément le test qui échouerait sous un jeton porteur de quinze minutes (menace
    T-03-51), et c'est pour cela qu'il interroge l'API plutôt que `ModelBackend` : on ne
    teste pas Django, on teste que **notre** chemin d'authentification n'a rien mis en
    cache devant lui.

    Le refus est un **401** et non un 403 : `03-UI-SPEC.md` 8.6 branche sur 401 la
    reconnexion globale, et un gérant désactivé doit atterrir sur l'écran de connexion,
    pas sur « Vous n'avez pas accès à cette page ».

    Implémenté au plan 03-08 plutôt qu'au 03-09 comme l'annonçait le stub : il lui faut
    une session ouverte par le vrai point de terminaison de connexion, qui naît là.
    """
    from rest_framework.test import APIClient

    from tests.factories import MOT_DE_PASSE_DE_TEST, GerantFactory

    gerant = GerantFactory(client=affaire_reelle.client)
    api = APIClient()
    connexion = api.post(
        "/api/auth/connexion/",
        {"email": gerant.email, "mot_de_passe": MOT_DE_PASSE_DE_TEST},
        format="json",
    )
    assert connexion.status_code == 200, connexion.data
    assert api.get("/api/auth/moi/").status_code == 200, (
        "La session ne fonctionne pas avant la désactivation : le refus qui suit ne "
        "prouverait rien."
    )

    gerant.is_active = False
    gerant.save(using="default", update_fields=["is_active"])

    assert api.get("/api/auth/moi/").status_code == 401, (
        "Le compte désactivé est encore servi. Quelque chose met le principal en cache "
        "entre la base et `request.user` — c'est la fenêtre de révocation que la phase 3 "
        "existe pour ne pas avoir."
    )


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

    # -- moitié stockage : accorder un code n'en rend aucun autre vrai ------------------
    #
    # C'est la forme que prend un palier réintroduit par la porte de service : un octroi
    # qui en entraîne d'autres. Un droit est une ligne, donc accorder `stock.voir` crée
    # exactement une ligne et laisse les vingt autres codes faux.
    from plateforme.comptes.models import DroitAccorde
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    gerant = GerantFactory()
    AccesMagasinFactory(utilisateur=gerant, magasin_code="ANFA")
    DroitAccordeFactory(
        utilisateur=gerant, magasin_code="ANFA", code=Permission.STOCK_VOIR
    )

    accordes = set(
        DroitAccorde.objects.filter(utilisateur=gerant).values_list("code", flat=True)
    )
    assert accordes == {Permission.STOCK_VOIR.value}, (
        f"accorder un code en a rendu d'autres vrais : {sorted(accordes)}"
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
    from django.db import IntegrityError, models, transaction

    from plateforme.comptes.models import DroitAccorde
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    # -- la forme, affirmée sur `_meta` ------------------------------------------------
    champs = {champ.name for champ in DroitAccorde._meta.get_fields()}
    assert {"utilisateur", "magasin_code", "code"} <= champs

    uniques = [
        contrainte
        for contrainte in DroitAccorde._meta.constraints
        if isinstance(contrainte, models.UniqueConstraint)
    ]
    par_nom = {contrainte.name: contrainte for contrainte in uniques}
    assert "uniq_droit_par_utilisateur_magasin_code" in par_nom
    assert list(par_nom["uniq_droit_par_utilisateur_magasin_code"].fields) == [
        "utilisateur",
        "magasin_code",
        "code",
    ]
    # Et aucune unicité plus étroite ne coexiste : `UniqueConstraint(utilisateur, code)`
    # — la forme de `03-RESEARCH.md` §4 — rendrait impossible d'accorder le même droit
    # dans deux magasins, donc reverserait CLAUDE.md #13 en restant verte sur la ligne
    # au-dessus.
    for contrainte in uniques:
        assert "magasin_code" in contrainte.fields, contrainte.name

    # `magasin_code` est une **valeur**. Une clé étrangère vers `magasins.Magasin` ne peut
    # pas exister : le magasin vit dans la base du client et `TenantRouter.allow_relation`
    # refuse toute relation inter-alias.
    champ_magasin = DroitAccorde._meta.get_field("magasin_code")
    assert not champ_magasin.is_relation
    assert isinstance(champ_magasin, models.CharField)

    # -- et le comportement que cette forme rend possible -------------------------------
    anfa, maarif = deux_magasins
    assert {anfa.code, maarif.code} == {"ANFA", "MAARIF"}

    gerant = GerantFactory()
    for code_magasin in (anfa.code, maarif.code):
        AccesMagasinFactory(utilisateur=gerant, magasin_code=code_magasin)

    for code_magasin in (anfa.code, maarif.code):
        DroitAccordeFactory(
            utilisateur=gerant,
            magasin_code=code_magasin,
            code=Permission.CAISSE_SAISIR,
        )

    # Le même code, deux magasins : deux lignes. Sous la forme de la recherche, la seconde
    # aurait levé `IntegrityError`.
    assert (
        DroitAccorde.objects.filter(
            utilisateur=gerant, code=Permission.CAISSE_SAISIR
        ).count()
        == 2
    )

    # Le doublon exact, lui, est refusé par la base et non par une convention.
    with transaction.atomic(using="default"), pytest.raises(IntegrityError):
        DroitAccordeFactory(
            utilisateur=gerant,
            magasin_code=anfa.code,
            code=Permission.CAISSE_SAISIR,
        )


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

    **Portée de cette version.** Le plan 03-04 pose le stockage, donc ce qui est affirmé
    ici est la lecture du stockage. Le plan 03-05, qui pose `Acces` et `acces_pour()`,
    étend ce même test à la résolution : `acces.peut(caisse.saisir, MAARIF)` doit être faux
    là où `acces.peut(caisse.saisir, ANFA)` est vrai. Les deux moitiés vivent dans le même
    test parce qu'elles sont la même promesse à deux couches, et qu'une contrainte à trois
    colonnes au-dessus d'un `peut()` aveugle au magasin est précisément le cas que la
    première moitié seule ne voit pas.
    """
    from plateforme.comptes.acces import acces_pour
    from plateforme.comptes.models import AccesMagasin, DroitAccorde
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    anfa, maarif = deux_magasins
    gerant = GerantFactory()

    # Les **deux** magasins sont accordés au compte : ce que ce test mesure est le droit,
    # pas l'accès. Sans cela il passerait pour la mauvaise raison — un droit qui ne fuit
    # pas parce que le magasin n'est pas accessible ne prouve rien sur CLAUDE.md #13.
    for code_magasin in (anfa.code, maarif.code):
        AccesMagasinFactory(utilisateur=gerant, magasin_code=code_magasin)
    assert set(
        AccesMagasin.objects.filter(utilisateur=gerant).values_list(
            "magasin_code", flat=True
        )
    ) == {"ANFA", "MAARIF"}

    DroitAccordeFactory(
        utilisateur=gerant, magasin_code=anfa.code, code=Permission.CAISSE_SAISIR
    )

    # Le contrôle positif, d'abord : sans lui, un stockage qui n'accorde jamais rien
    # passerait l'assertion négative qui suit.
    assert DroitAccorde.objects.filter(
        utilisateur=gerant, magasin_code="ANFA", code=Permission.CAISSE_SAISIR
    ).exists()

    assert not DroitAccorde.objects.filter(
        utilisateur=gerant, magasin_code="MAARIF", code=Permission.CAISSE_SAISIR
    ).exists()

    # Et la lecture sans dimension magasin — celle qu'un `peut(code)` ferait — ne doit
    # ramener qu'Anfa. C'est l'assertion qui serait impossible à écrire sous la forme de
    # `03-RESEARCH.md` §4, où la ligne n'a pas de colonne `magasin_code` à ramener.
    assert set(
        DroitAccorde.objects.filter(
            utilisateur=gerant, code=Permission.CAISSE_SAISIR
        ).values_list("magasin_code", flat=True)
    ) == {"ANFA"}

    # ----------------------------------------------------------------------------------
    # La moitié **résolution**, annoncée par la docstring et livrée par le plan 03-05.
    # ----------------------------------------------------------------------------------
    # C'est ici que la dimension magasin cesse d'être une colonne et devient une réponse.
    # Une contrainte à trois colonnes au-dessus d'un `peut()` aveugle au magasin stocke
    # correctement une distinction que le code ne fait pas : les quatre assertions
    # ci-dessus resteraient vertes, et le gérant ferait quand même sa remise à Maârif.
    acces = acces_pour(gerant)

    assert acces.peut(Permission.CAISSE_SAISIR, magasin_id=anfa.pk) is True
    assert acces.peut(Permission.CAISSE_SAISIR, magasin_id=maarif.pk) is False, (
        "Le droit accordé à Anfa a répondu oui pour Maârif. CLAUDE.md #13 est renversé "
        "non par le stockage — il porte bien la colonne — mais par la résolution qui "
        "l'ignore."
    )

    # Et le contrôle positif de la résolution elle-même : les deux magasins sont bien dans
    # la portée. Sans cette ligne, un `acces_pour` qui n'aurait rien résolu du tout
    # passerait l'assertion négative qui précède.
    assert acces.magasins_ids == frozenset({anfa.pk, maarif.pk})


def test_perm03_la_revocation_prend_effet_sans_reconnexion(db_all, deux_magasins):
    """PERM-03 — retirer un droit mord à la requête suivante, sans déconnecter personne.

    C'est la promesse que `03-UI-SPEC.md` §7.8 affiche à l'écran, en toutes lettres, sous
    la liste des droits. Rouge, ce test dirait que cette phrase est fausse : l'`Acces` est
    résolu une fois et posé en session, ou mis en cache par utilisateur, donc le droit
    retiré à 14 h continue de s'appliquer jusqu'à la déconnexion. Une promesse affichée et
    non tenue est pire qu'une promesse absente — le propriétaire croit avoir agi.

    **Ce que ce test peut affirmer au plan 03-05, et pourquoi c'est déjà la promesse
    entière.** Il n'y a pas encore de vue à appeler ; ce qui est vérifié est donc la
    propriété qui rend la promesse vraie : `acces_pour` lit les lignes de droits **à chaque
    appel**, et le middleware l'appelle une fois par requête. Un cache par utilisateur, un
    `lru_cache`, ou un `Acces` posé en session se verrait ici et nulle part ailleurs — les
    tests de vue des plans suivants, qui construisent une requête neuve, ne sauraient pas
    distinguer un cache d'une résolution.
    """
    from plateforme.comptes.acces import acces_pour
    from plateforme.comptes.models import DroitAccorde
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    anfa, _maarif = deux_magasins
    gerant = GerantFactory()
    AccesMagasinFactory(utilisateur=gerant, magasin_code=anfa.code)
    droit = DroitAccordeFactory(
        utilisateur=gerant, magasin_code=anfa.code, code=Permission.CAISSE_SAISIR
    )

    avant = acces_pour(gerant)
    assert avant.peut(Permission.CAISSE_SAISIR, magasin_id=anfa.pk) is True

    # 14 h : le propriétaire retire le droit. Personne n'est déconnecté, aucune session
    # n'est invalidée, aucun cache n'est purgé — parce qu'il n'y en a pas.
    droit.delete()
    assert not DroitAccorde.objects.filter(pk=droit.pk).exists()

    apres = acces_pour(gerant)
    assert apres.peut(Permission.CAISSE_SAISIR, magasin_id=anfa.pk) is False, (
        "Le droit retiré s'applique encore. Un Acces mis en cache, ou résolu une seule "
        "fois et gardé, rend fausse la phrase que 03-UI-SPEC 7.8 affiche en toutes "
        "lettres sous la liste des droits."
    )
    # Et le compte lui-même n'a rien perdu d'autre : le magasin reste accordé. Retirer un
    # droit n'est pas retirer un accès, et une révocation qui emporterait les deux serait
    # verte sur l'assertion ci-dessus pour la mauvaise raison.
    assert apres.magasins_ids == frozenset({anfa.pk})


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


def test_perm03_un_droit_ne_peut_viser_un_magasin_non_accorde(db_all):
    """PERM-03 — un droit sans accès au magasin n'accorde rien : c'est un mensonge stocké.

    Menace T-03-18 : la ligne est inerte tant que l'accès manque, puis devient active le
    jour où le propriétaire accorde le magasin — donc un droit que personne n'a jamais
    décidé d'accorder apparaît, plus tard, à l'occasion d'une action sans rapport.

    **La base ne peut pas nous sauver ici**, et cela vaut d'être dit franchement plutôt
    que d'être découvert : une contrainte `CHECK` porte sur une ligne, pas sur l'existence
    d'une ligne dans une autre table. Contrairement à la garantie opérateur du plan 03-01,
    celle-ci est une règle Python — posée dans `save()`, appliquée une seconde fois par le
    service d'octroi (plan 03-09), et testée ici parce que rien d'autre ne la tient.
    `queryset.update()` la contourne toujours ; c'est le prix admis de cette forme.
    """
    from django.core.exceptions import ValidationError

    from plateforme.comptes.models import DroitAccorde
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    gerant = GerantFactory()
    AccesMagasinFactory(utilisateur=gerant, magasin_code="ANFA")

    with pytest.raises(ValidationError):
        DroitAccordeFactory(
            utilisateur=gerant, magasin_code="MAARIF", code=Permission.CAISSE_SAISIR
        )
    assert not DroitAccorde.objects.filter(
        utilisateur=gerant, magasin_code="MAARIF"
    ).exists()

    # Le contrôle positif : la même écriture, sur un magasin accordé, passe. Sans lui, un
    # `save()` qui refuserait *tout* rendrait l'assertion ci-dessus verte et le modèle
    # inutilisable.
    droit = DroitAccordeFactory(
        utilisateur=gerant, magasin_code="ANFA", code=Permission.CAISSE_SAISIR
    )
    assert droit.pk is not None


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
    from django.core.exceptions import ValidationError

    from plateforme.comptes.models import DroitAccorde, JournalDroit
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import (
        AccesMagasinFactory,
        DroitAccordeFactory,
        GerantFactory,
        ProprietaireFactory,
    )

    proprietaire = ProprietaireFactory()
    karim = GerantFactory(client=proprietaire.client)
    AccesMagasinFactory(
        utilisateur=karim, magasin_code="ANFA", accorde_par=proprietaire
    )
    droit = DroitAccordeFactory(
        utilisateur=karim,
        magasin_code="ANFA",
        code=Permission.VENTE_VOIR_MARGE,
        accorde_par=proprietaire,
    )
    entree = JournalDroit.objects.create(
        utilisateur=karim,
        action=JournalDroit.Action.ACCORDE,
        cible=Permission.VENTE_VOIR_MARGE,
        par=proprietaire,
    )
    horodatage = entree.le

    # La révocation **supprime** la ligne d'octroi : c'est ce qui rend `peut()`
    # trivialement juste, et c'est exactement ce qui effacerait la réponse si le journal
    # y était rattaché.
    droit.delete()
    assert not DroitAccorde.objects.filter(pk=droit.pk).exists()

    # « Qui a donné les marges à Karim ? » — la question se pose après coup, donc la
    # réponse est relue depuis la base, pas depuis l'objet encore en mémoire.
    survivante = JournalDroit.objects.get(pk=entree.pk)
    assert survivante.utilisateur == karim
    assert survivante.par == proprietaire
    assert survivante.cible == Permission.VENTE_VOIR_MARGE.value
    assert survivante.action == "accorde"
    assert survivante.le == horodatage

    # Append-only : une entrée ne se réécrit pas. Un journal modifiable répond à la
    # question, mais pas forcément la vérité.
    survivante.par = karim
    with pytest.raises(ValidationError):
        survivante.save()
    assert JournalDroit.objects.get(pk=entree.pk).par == proprietaire
